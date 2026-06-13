"""Turn raw fetched items into a daily digest of notable industry updates.

With an ANTHROPIC_API_KEY set, Claude separates signal from noise and writes
a curated digest. Without one, render_raw() produces a plain grouped listing
so the tracker still works (and stays free), just without AI curation."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

from .items import Item

log = logging.getLogger(__name__)

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = """\
You are an analyst tracking the frontier of LLMs, artificial intelligence,
machine learning, and recommender systems. Each day you receive raw posts
(X.com) and video uploads (YouTube) from a curated list of top researchers,
lab leaders, and educators in these fields.

Your job is to identify what is NOTABLE for the industry and discard the rest.
Notable means things like: new model releases or benchmarks, significant
research results or papers, major product or API launches, funding or
strategic moves by labs, important safety/policy developments, substantive
technical insights or tutorials, and meaningful shifts in expert opinion.
Not notable: personal chatter, congratulations, memes, vague hype,
event-attendance posts, and reposts without commentary.

Write a markdown digest with exactly this structure:

## Top stories
The 3-7 most significant updates, most important first. For each:
a bold one-line headline, then 1-3 sentences explaining what happened and
why it matters to the industry, then a "Source:" line linking the post/video
with the author's name.

## Also worth noting
A bullet list of smaller but still notable items, one line each with an
inline source link. Omit this section if there is nothing.

## Themes
2-4 sentences on any cross-cutting patterns across today's items.
Omit this section if the items are too sparse to support one.

Rules:
- Only use the provided items. Never invent updates, links, or numbers.
- If multiple items cover the same story, merge them and cite all sources.
- If nothing is genuinely notable, say so plainly in one short paragraph
  instead of inflating minor items.
"""


def build_user_prompt(items: list[Item]) -> str:
    lines = [
        f"Items collected on {datetime.now(timezone.utc).strftime('%Y-%m-%d')} (UTC).",
        f"Total: {len(items)}.",
        "",
    ]
    for item in sorted(items, key=lambda i: i.published_at, reverse=True):
        lines.append(f"--- [{item.source}] {item.author} ({item.focus})")
        lines.append(f"published: {item.published_at.isoformat()}")
        if item.metrics:
            lines.append(f"engagement: {item.metrics}")
        lines.append(f"url: {item.url}")
        lines.append(item.text.strip())
        lines.append("")
    return "\n".join(lines)


def generate_digest(items: list[Item]) -> str:
    import anthropic  # imported lazily so the no-key path needs no dependency

    client = anthropic.Anthropic()
    with client.messages.stream(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(items)}],
    ) as stream:
        response = stream.get_final_message()
    if response.stop_reason == "refusal":
        log.error("Claude declined the digest request: %s", response.stop_details)
        return "_Digest generation was declined by the model today._"
    return next(b.text for b in response.content if b.type == "text")


def render_raw(items: list[Item]) -> str:
    """Plain grouped listing used when no ANTHROPIC_API_KEY is set.

    No AI curation — just every new item, grouped by source and author,
    newest first, so you can skim the raw feed yourself."""
    lines = [
        "> No `ANTHROPIC_API_KEY` set — showing the raw scrape without AI "
        "curation. Add the secret to get notable-updates summaries.\n",
    ]
    source_labels = {"x": "X / Twitter", "youtube": "YouTube"}
    by_source: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        by_source[item.source].append(item)

    for source in ("x", "youtube"):
        bucket = by_source.get(source)
        if not bucket:
            continue
        lines.append(f"## {source_labels[source]}\n")
        by_author: dict[str, list[Item]] = defaultdict(list)
        for item in bucket:
            by_author[item.author].append(item)
        for author in sorted(by_author):
            entries = sorted(by_author[author], key=lambda i: i.published_at, reverse=True)
            focus = entries[0].focus
            lines.append(f"### {author} — {focus}\n")
            for item in entries:
                headline = item.text.strip().splitlines()[0] if item.text.strip() else "(no text)"
                stamp = item.published_at.strftime("%Y-%m-%d %H:%M UTC")
                meta = f" · {item.metrics}" if item.metrics else ""
                lines.append(f"- [{headline}]({item.url}) — {stamp}{meta}")
            lines.append("")
    return "\n".join(lines)
