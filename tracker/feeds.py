"""Minimal Atom/RSS parsing with the stdlib, replacing feedparser
(whose sgmllib3k dependency no longer builds on modern setuptools)."""

from __future__ import annotations

import dataclasses
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

log = logging.getLogger(__name__)

_ATOM = "{http://www.w3.org/2005/Atom}"
_YT = "{http://www.youtube.com/xml/schemas/2015}"
_MEDIA = "{http://search.yahoo.com/mrss/}"


@dataclasses.dataclass
class FeedEntry:
    id: str
    title: str
    link: str
    published: datetime
    summary: str = ""


def parse_youtube_atom(content: bytes) -> list[FeedEntry]:
    entries = []
    root = ET.fromstring(content)
    for entry in root.findall(f"{_ATOM}entry"):
        published = datetime.fromisoformat(entry.findtext(f"{_ATOM}published"))
        link_el = entry.find(f"{_ATOM}link[@rel='alternate']")
        media = entry.find(f"{_MEDIA}group")
        description = media.findtext(f"{_MEDIA}description", "") if media is not None else ""
        entries.append(
            FeedEntry(
                id=entry.findtext(f"{_YT}videoId", ""),
                title=entry.findtext(f"{_ATOM}title", ""),
                link=link_el.get("href") if link_el is not None else "",
                published=published.astimezone(timezone.utc),
                summary=description,
            )
        )
    return entries


def parse_rss(content: bytes) -> list[FeedEntry]:
    entries = []
    root = ET.fromstring(content)
    for item in root.iter("item"):
        pub_date = item.findtext("pubDate")
        if not pub_date:
            continue
        try:
            published = parsedate_to_datetime(pub_date).astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
        link = (item.findtext("link") or "").strip()
        entries.append(
            FeedEntry(
                id=(item.findtext("guid") or link).strip(),
                title=(item.findtext("title") or "").strip(),
                link=link,
                published=published,
                summary=(item.findtext("description") or "").strip(),
            )
        )
    return entries
