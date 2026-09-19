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
- Run the checks: `.venv/bin/python -B test_playlist_logic.py` (classification rules, 29
  checks) and `.venv/bin/python -B test_app_sidebar.py` (sidebar wiring via
  `st.testing.v1.AppTest`, headless, 20 checks). Both are plain scripts that print
  PASS/FAIL and exit non-zero on failure. Added 2026-09-19.
- No lint or build tooling, no pytest, no config files, no CI. The `-B` flag keeps test
  runs from rewriting the git-tracked `__pycache__/*.pyc` files.

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

- `classify_song`: **fixed 2026-09-19 — this is no longer a quirk.** It now decides in two
  tiers. Tier 1: the profile's energy bands alone (`energy >= hype_min_energy` -> Hype,
  `energy <= chill_max_energy` -> Chill), because they are the only mood signal the user
  controls. Tier 2, reached only by songs in the ambiguous middle band: `HYPE_KEYWORDS`
  (`rock`, `punk`, `party`) and `CHILL_KEYWORDS` (`lofi`, `ambient`, `sleep`) break the tie,
  matched by `mood_keyword_words()` as **whole words** against the lowercased genre + title +
  tags together. A song hitting both lists, or neither, stays Mixed. Consequences worth
  knowing: the profile's `favorite_genre` is deliberately **not** read (it used to return
  "Hype" on a genre match, so a favorite of "ambient" threw energy-1 sleep tracks into Hype);
  a mid-energy rock song still lands in Hype at the default profile, which is intended
  (Danny, 2026-09-19); and whole-word matching means "afterparty" is not "party" and
  "Rocket Man" is not a rock song. Do not change the keyword lists to make a check pass.
- `compute_playlist_stats`: `hype_ratio` divides by `len(hype)` instead of total song count, so
  it's always 1.0 whenever any hype song exists. `avg_energy` sums energy over the `hype` list
  only but divides by the total song count across all playlists.
- `merge_playlists(a, b)`: `merged[key] = a.get(key, [])` reuses `a`'s list object rather than
  copying it, so `.extend(b[key])` mutates `a` in place. Harmless today since `app.py` always
  passes `b={}`, but would cause aliasing bugs if that call site changes.
- `lucky_pick`: `mode="any"` only draws from `Hype + Chill` — Mixed songs are never eligible.
  (README's stretch goals explicitly mention improving Mixed-song handling.)
- `app.py`'s `profile_sidebar()`: **the "Favorite genre" selectbox no longer affects any
  playlist** (2026-09-19), since `classify_song` stopped reading `favorite_genre`. It still
  renders and still records the choice into the profile, so it currently looks live but is
  inert — repurposing it (lucky-pick weighting, sort order) is an open follow-up.
  Correction (2026-09-19): an earlier note here claimed the hardcoded `index=0` made it
  "visually reset to rock on every rerender". That is **wrong**. `index=0` is only the
  initial default; Streamlit persists widget state across reruns, so a selection survives.
  Verified with AppTest: after selecting "ambient", it still reads "ambient" following two
  unrelated reruns.
- `app.py`'s `profile_sidebar()` energy controls: **fixed 2026-09-19.** The two independent
  sliders (which allowed Chill max above Hype min, an overlapping band that silently
  resolved to Hype) are now one two-handle range slider, "Mood energy bands", whose handles
  cannot cross. This also removed a `st.sidebar.columns(2)` block that never rendered
  anything, because the `st.sidebar.slider(...)` calls inside it bypassed the `with col1:`
  context.

### Repo hygiene notes

- No `.gitignore` exists. `__pycache__/*.pyc` files are currently committed to git and will
  keep showing as modified/dirty as Python regenerates them — flag this if asked about
  unexpected working-tree changes, but don't add a `.gitignore` or untrack files unless asked.
- `.agents/skills/developing-with-streamlit` and `.claude/skills/developing-with-streamlit` are
  git-tracked symlinks pointing into `.venv/lib/python3.13/site-packages/streamlit/...`. They
  only resolve when that exact `.venv` exists at that exact relative path — they'll be dangling
  on a fresh clone until the venv is recreated.
