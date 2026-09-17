# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A small two-file Streamlit app ("Playlist Chaos") from a course assignment. Per README.md,
the app was AI-generated and deliberately contains unpredictable/buggy behavior; the intended
workflow is to explore the running app, use an AI assistant to explain the relevant code, and
fix the issues found. Treat debugging requests here as the primary expected task, not an
edge case.

## Commands

- Install deps: `pip install -r requirements.txt` (only dependency: `streamlit>=1.36.0`) —
  a `.venv` already exists in the repo with this installed.
- Run the app: `streamlit run app.py`
- No lint, test, or build tooling exists in this repo (no pytest, no config files, no CI).

## Architecture

Two files carry all logic:

- `app.py` — Streamlit UI only. Owns `st.session_state` (`songs`, `profile`, `history`) and
  renders sidebar controls, playlist tabs, search, "feeling lucky", stats, and history. Holds
  the hardcoded seed data (`default_songs()`, 22 songs) — there is no persistence layer or data
  file; all state is in-memory and resets on process restart.
- `playlist_logic.py` — pure logic, no Streamlit imports. Pipeline: `normalize_song` →
  `classify_song` (assigns "Hype" / "Chill" / "Mixed") → `build_playlists` (buckets into a
  `{"Hype": [...], "Chill": [...], "Mixed": [...]}` map) → consumed by `search_songs`,
  `compute_playlist_stats`, `lucky_pick`, `history_summary`. `app.py` calls
  `merge_playlists(playlists, {})` after `build_playlists` — this is a no-op pass-through
  today (merging against an empty dict) but is the extension point the README's "merging
  playlist data" description refers to.

### Known quirks worth knowing before debugging

These live in `playlist_logic.py` and match the "unpredictable behavior" the README describes:

- `classify_song`: checks Hype conditions before Chill, so a song matching both always lands
  in Hype. Hype genre keywords (`rock`, `punk`, `party`) are matched against the lowercased
  genre; Chill keywords (`lofi`, `ambient`, `sleep`) are matched against the *raw, unlowercased*
  title (`normalize_title` only strips whitespace, unlike `normalize_artist`/`normalize_genre`).
- `compute_playlist_stats`: `hype_ratio` divides by `len(hype)` instead of total song count, so
  it's always 1.0 whenever any hype song exists. `avg_energy` sums energy over the `hype` list
  only but divides by the total song count across all playlists.
- `merge_playlists(a, b)`: `merged[key] = a.get(key, [])` reuses `a`'s list object rather than
  copying it, so `.extend(b[key])` mutates `a` in place. Harmless today since `app.py` always
  passes `b={}`, but would cause aliasing bugs if that call site changes.
- `lucky_pick`: `mode="any"` only draws from `Hype + Chill` — Mixed songs are never eligible.
  (README's stretch goals explicitly mention improving Mixed-song handling.)
- `app.py`'s `profile_sidebar()`: the `favorite_genre` selectbox is created with a hardcoded
  `index=0`, so it visually resets to "rock" on every rerender instead of reflecting the
  profile's stored value.

### Repo hygiene notes

- No `.gitignore` exists. `__pycache__/*.pyc` files are currently committed to git and will
  keep showing as modified/dirty as Python regenerates them — flag this if asked about
  unexpected working-tree changes, but don't add a `.gitignore` or untrack files unless asked.
- `.agents/skills/developing-with-streamlit` and `.claude/skills/developing-with-streamlit` are
  git-tracked symlinks pointing into `.venv/lib/python3.13/site-packages/streamlit/...`. They
  only resolve when that exact `.venv` exists at that exact relative path — they'll be dangling
  on a fresh clone until the venv is recreated.
