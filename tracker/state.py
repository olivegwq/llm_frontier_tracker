"""Persistent state between runs: seen item IDs and resolved channel/user IDs.

State is committed to the repo by the daily workflow so deduplication
survives across CI runs.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import STATE_PATH

_MAX_SEEN_IDS = 5000


def load_state(path: Path = STATE_PATH) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {"seen_ids": [], "youtube_channel_ids": {}, "x_user_ids": {}}


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    # Keep only the most recent IDs so the file doesn't grow forever.
    state["seen_ids"] = state["seen_ids"][-_MAX_SEEN_IDS:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def is_new(state: dict, item_id: str) -> bool:
    return item_id not in set(state["seen_ids"])


def mark_seen(state: dict, item_id: str) -> None:
    if item_id not in set(state["seen_ids"]):
        state["seen_ids"].append(item_id)
