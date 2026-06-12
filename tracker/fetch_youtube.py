"""Fetch recent YouTube uploads via channel RSS feeds (no API key required).

YouTube handles are resolved to channel IDs by scraping the channel page once;
resolved IDs are cached in state so subsequent runs skip the lookup.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests

from .config import LOOKBACK_HOURS, Influencer
from .feeds import parse_youtube_atom
from .items import Item

log = logging.getLogger(__name__)

_FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
_HANDLE_URL = "https://www.youtube.com/@{handle}"
_CHANNEL_ID_RE = re.compile(r'"channelId":"(UC[\w-]{22})"')
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; llm-frontier-tracker/1.0)"}


def resolve_channel_id(handle: str, cache: dict[str, str]) -> str | None:
    if handle in cache:
        return cache[handle]
    try:
        resp = requests.get(_HANDLE_URL.format(handle=handle), headers=_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("Could not resolve YouTube handle @%s: %s", handle, exc)
        return None
    match = _CHANNEL_ID_RE.search(resp.text)
    if not match:
        log.warning("No channelId found on page for @%s", handle)
        return None
    cache[handle] = match.group(1)
    return cache[handle]


def fetch_youtube_items(influencers: list[Influencer], state: dict) -> list[Item]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    cache: dict[str, str] = state.setdefault("youtube_channel_ids", {})
    items: list[Item] = []

    for inf in influencers:
        if not inf.youtube:
            continue
        channel_id = resolve_channel_id(inf.youtube, cache)
        if not channel_id:
            continue
        try:
            resp = requests.get(_FEED_URL.format(channel_id=channel_id),
                                headers=_HEADERS, timeout=30)
            resp.raise_for_status()
            entries = parse_youtube_atom(resp.content)
        except (requests.RequestException, ET.ParseError) as exc:
            log.warning("Failed to fetch feed for %s (@%s): %s", inf.name, inf.youtube, exc)
            continue
        for entry in entries:
            if entry.published < cutoff:
                continue
            items.append(
                Item(
                    id=f"yt:{entry.id}",
                    source="youtube",
                    author=inf.name,
                    focus=inf.focus,
                    text=f"{entry.title}\n{entry.summary[:300]}".strip(),
                    url=entry.link,
                    published_at=entry.published,
                )
            )
    log.info("YouTube: %d recent items", len(items))
    return items
