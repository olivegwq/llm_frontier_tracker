"""Fetch recent X.com posts.

Two backends, tried in order:

1. Official X API v2 — used when the X_BEARER_TOKEN env var is set.
   Reading tweets requires a paid (Basic or higher) X API plan.
2. Nitter RSS — a best-effort fallback through public Nitter instances.
   Public instances are frequently rate-limited or down, so treat this
   as opportunistic rather than guaranteed.

If neither backend yields data the run still succeeds; the digest will
note that X coverage was unavailable.
"""

from __future__ import annotations

import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests

from .config import LOOKBACK_HOURS, Influencer
from .feeds import parse_rss
from .items import Item

log = logging.getLogger(__name__)

_X_API = "https://api.x.com/2"
_NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.privacyredirect.com",
]
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; llm-frontier-tracker/1.0)"}


def fetch_x_items(influencers: list[Influencer], state: dict) -> tuple[list[Item], str]:
    """Return (items, status_note). status_note is shown in the digest header."""
    handles = [inf for inf in influencers if inf.x]
    token = os.environ.get("X_BEARER_TOKEN")
    if token:
        try:
            return _fetch_via_api(handles, state, token), "X API v2"
        except Exception:
            log.exception("X API fetch failed, falling back to Nitter")
    items = _fetch_via_nitter(handles)
    if items:
        return items, "Nitter RSS (best-effort)"
    return [], (
        "unavailable — set the X_BEARER_TOKEN secret (paid X API plan) "
        "for reliable X coverage; Nitter fallback returned nothing"
    )


# ── Backend 1: official X API v2 ─────────────────────────────────────────

def _api_get(url: str, token: str, params: dict) -> dict:
    for attempt in range(3):
        resp = requests.get(url, params=params, timeout=30,
                            headers={"Authorization": f"Bearer {token}", **_HEADERS})
        if resp.status_code == 429:
            wait = int(resp.headers.get("retry-after", 2 ** (attempt + 2)))
            log.warning("X API rate limited, sleeping %ss", wait)
            time.sleep(min(wait, 120))
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    return {}


def _resolve_user_ids(handles: list[Influencer], state: dict, token: str) -> dict[str, str]:
    cache: dict[str, str] = state.setdefault("x_user_ids", {})
    missing = [inf.x for inf in handles if inf.x not in cache]
    # /users/by accepts up to 100 usernames per call
    for i in range(0, len(missing), 100):
        batch = missing[i:i + 100]
        data = _api_get(f"{_X_API}/users/by", token, {"usernames": ",".join(batch)})
        for user in data.get("data", []):
            cache[user["username"]] = user["id"]
    return cache


def _fetch_via_api(handles: list[Influencer], state: dict, token: str) -> list[Item]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    user_ids = _resolve_user_ids(handles, state, token)
    items: list[Item] = []
    for inf in handles:
        user_id = user_ids.get(inf.x)
        if not user_id:
            log.warning("No X user ID for @%s", inf.x)
            continue
        data = _api_get(
            f"{_X_API}/users/{user_id}/tweets", token,
            {
                "max_results": 10,
                "exclude": "retweets,replies",
                "tweet.fields": "created_at,public_metrics",
                "start_time": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        for tweet in data.get("data", []):
            m = tweet.get("public_metrics", {})
            items.append(
                Item(
                    id=f"x:{tweet['id']}",
                    source="x",
                    author=inf.name,
                    focus=inf.focus,
                    text=tweet["text"],
                    url=f"https://x.com/{inf.x}/status/{tweet['id']}",
                    published_at=datetime.fromisoformat(
                        tweet["created_at"].replace("Z", "+00:00")
                    ),
                    metrics=f"{m.get('like_count', 0)} likes, "
                            f"{m.get('retweet_count', 0)} reposts",
                )
            )
        time.sleep(1)  # stay well under per-endpoint rate limits
    log.info("X API: %d recent items", len(items))
    return items


# ── Backend 2: Nitter RSS fallback ───────────────────────────────────────

def _fetch_via_nitter(handles: list[Influencer]) -> list[Item]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    items: list[Item] = []
    instance = _pick_nitter_instance()
    if not instance:
        log.warning("No reachable Nitter instance")
        return items
    for inf in handles:
        try:
            resp = requests.get(f"{instance}/{inf.x}/rss", headers=_HEADERS, timeout=20)
            if resp.status_code != 200:
                continue
            entries = parse_rss(resp.content)
        except (requests.RequestException, ET.ParseError):
            continue
        for entry in entries:
            if entry.published < cutoff:
                continue
            status_id = entry.link.rstrip("/").split("/")[-1].split("#")[0]
            items.append(
                Item(
                    id=f"x:{status_id}",
                    source="x",
                    author=inf.name,
                    focus=inf.focus,
                    text=entry.title,
                    url=f"https://x.com/{inf.x}/status/{status_id}",
                    published_at=entry.published,
                )
            )
        time.sleep(1)
    log.info("Nitter: %d recent items", len(items))
    return items


def _pick_nitter_instance() -> str | None:
    for instance in _NITTER_INSTANCES:
        try:
            if requests.get(instance, headers=_HEADERS, timeout=10).status_code == 200:
                return instance
        except requests.RequestException:
            continue
    return None
