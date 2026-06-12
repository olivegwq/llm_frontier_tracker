"""Load the influencer roster and shared paths."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "influencers.yaml"
STATE_PATH = REPO_ROOT / "data" / "state.json"
DIGEST_DIR = REPO_ROOT / "digests"

# Items older than this are ignored even if never seen before, so a stalled
# job doesn't dump weeks of backlog into one digest.
LOOKBACK_HOURS = 36


@dataclasses.dataclass
class Influencer:
    name: str
    focus: str = ""
    x: str | None = None
    youtube: str | None = None


def load_influencers(path: Path = CONFIG_PATH) -> list[Influencer]:
    raw = yaml.safe_load(path.read_text())
    return [Influencer(**entry) for entry in raw["influencers"]]
