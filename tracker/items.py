"""Common shape for fetched content items."""

from __future__ import annotations

import dataclasses
from datetime import datetime


@dataclasses.dataclass
class Item:
    id: str            # globally unique, e.g. "x:1234567890" or "yt:dQw4w9WgXcQ"
    source: str        # "x" or "youtube"
    author: str        # influencer display name
    focus: str         # focus tag from the roster
    text: str          # tweet text or video title (+ description snippet)
    url: str
    published_at: datetime
    metrics: str = ""  # e.g. "1.2k likes, 300 reposts" — optional context
