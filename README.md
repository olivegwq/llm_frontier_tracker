# LLM Frontier Tracker

Daily tracker of ~30 top influencers in **LLMs, AI, machine learning, and
recommender systems** — lab leaders (Altman, Hassabis, Suleyman, Sutskever),
researchers and educators (Karpathy, LeCun, Hinton, Ng, Chollet, Raschka,
Chip Huyen, …), leading AI YouTube channels (Lex Fridman, Two Minute Papers,
Yannic Kilcher, AI Explained, MLST, …), and RecSys experts (Amatriain,
Eugene Yan, the NVIDIA Merlin team).

Every day a GitHub Actions job:

1. **Scrapes X.com posts** from each influencer (official X API v2 when a
   bearer token is configured; best-effort Nitter RSS fallback otherwise).
2. **Pulls YouTube channel updates** via channel RSS feeds (no API key needed).
3. **Asks Claude (`claude-opus-4-8`) to identify the notable updates** for the
   industry — model releases, significant papers, product launches, policy
   moves — and discard the noise. _Skipped when no API key is set (see below)._
4. **Commits a markdown digest** to [`digests/`](digests/) —
   `digests/YYYY-MM-DD.md` plus a rolling `digests/latest.md`.

## The API key is optional

- **With `ANTHROPIC_API_KEY` set** — Claude curates the scrape into a
  notable-updates digest (top stories, smaller items, themes).
- **Without it** — the tracker still scrapes daily and writes a *raw* digest:
  every new post/video grouped by source and author, newest first, with no AI
  filtering. Completely free; the digest header shows `Mode: raw (no API key)`.

Note: an **Anthropic API key is billed separately from a Claude Pro/Max
subscription** — it uses pay-as-you-go credits set up in the
[Anthropic Console](https://console.anthropic.com), not your chat plan. A daily
run is only cents/month, but the raw mode above lets you run entirely free.

## Setup

1. Add repository secrets (**Settings → Secrets and variables → Actions**):
   - `ANTHROPIC_API_KEY` — optional. Enables AI curation; omit it for raw mode.
   - `X_BEARER_TOKEN` — optional but strongly recommended. Reading posts
     requires a **paid X API plan** (Basic or higher). Without it the tracker
     falls back to public Nitter instances, which are unreliable; the digest
     header reports which X backend was used each day.
2. The workflow ([`.github/workflows/daily-digest.yml`](.github/workflows/daily-digest.yml))
   runs daily at **13:30 UTC** once it is on the default branch. You can also
   trigger it manually from the Actions tab (`workflow_dispatch`).

## Run locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # optional — omit for free raw mode
export X_BEARER_TOKEN=...             # optional
python -m tracker.main
```

## Customizing the roster

Edit [`config/influencers.yaml`](config/influencers.yaml). Each entry takes a
`name`, a `focus` tag (used for grouping in the digest), and optional `x`
(handle, no `@`) and `youtube` (handle, no `@`) fields. YouTube handles are
resolved to channel IDs automatically and cached in `data/state.json`.

## How deduplication works

`data/state.json` stores the IDs of items already digested (plus resolved
YouTube channel / X user IDs). The workflow commits it after each run, so an
item is only ever analyzed once. Items older than 36 hours are skipped even
if unseen, so a stalled job can't dump weeks of backlog into one digest.
