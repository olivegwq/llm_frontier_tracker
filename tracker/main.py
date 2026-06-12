"""Daily run: fetch new posts/videos, have Claude flag notable updates,
write digests/YYYY-MM-DD.md (and digests/latest.md), update state.

Usage: python -m tracker.main
Env:   ANTHROPIC_API_KEY (required), X_BEARER_TOKEN (optional but recommended)
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from .config import DIGEST_DIR, load_influencers
from .digest import generate_digest
from .fetch_x import fetch_x_items
from .fetch_youtube import fetch_youtube_items
from .state import is_new, load_state, mark_seen, save_state

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def main() -> int:
    influencers = load_influencers()
    state = load_state()

    x_items, x_status = fetch_x_items(influencers, state)
    yt_items = fetch_youtube_items(influencers, state)

    new_items = [i for i in x_items + yt_items if is_new(state, i.id)]
    log.info("%d new items (of %d fetched)", len(new_items), len(x_items) + len(yt_items))

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    header = (
        f"# LLM Frontier Digest — {today}\n\n"
        f"_Sources: {len(new_items)} new items from "
        f"{sum(1 for i in influencers if i.x)} X accounts ({x_status}) and "
        f"{sum(1 for i in influencers if i.youtube)} YouTube channels._\n\n"
    )

    if new_items:
        body = generate_digest(new_items)
    else:
        body = "_No new posts or videos in the lookback window._\n"

    for item in new_items:
        mark_seen(state, item.id)
    save_state(state)

    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    content = header + body + "\n"
    (DIGEST_DIR / f"{today}.md").write_text(content)
    (DIGEST_DIR / "latest.md").write_text(content)
    log.info("Wrote digests/%s.md", today)
    return 0


if __name__ == "__main__":
    sys.exit(main())
