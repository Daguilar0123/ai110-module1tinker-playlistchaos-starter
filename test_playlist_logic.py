"""Checks for the pure logic in playlist_logic.py.

No test framework is installed in this repo and none is required. Run with:

    .venv/bin/python -B test_playlist_logic.py

(-B just avoids writing bytecode nobody reads. Until 2026-09-19 it also kept test
runs from dirtying git-tracked .pyc files, but __pycache__/ is gitignored now.)

Written 2026-09-19 BEFORE the classify_song fix, test-first, so it is expected to
fail until the fix lands. Revised 2026-09-19 after review (see
agent_messages/2026-09-19-01-tester1-to-claude-cp.md): the original check 1 demanded
Hotel California be Mixed at the default profile, which contradicted the regression
guard and the planned design. Danny decided the same day that a mid-energy rock song
stays Hype at the default profile.

Extended 2026-09-19 to cover compute_playlist_stats and lucky_pick, per
agent_messages/2026-09-19-03-tester1-to-claude-cp.md.

Each check is tagged in its label:
    [red]   fails on the unfixed code; the fix must turn it green
    [guard] already passes on the unfixed code; the fix must not break it
"""

import app
from playlist_logic import (
    DEFAULT_PROFILE,
    build_playlists,
    classify_song,
    compute_playlist_stats,
    lucky_pick,
    normalize_song,
)

FAILURES = []


def check(label, actual, expected):
    """Record a comparison instead of raising, so one run reports every failure."""
    if actual == expected:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}\n          expected {expected!r}, got {actual!r}")
        FAILURES.append(label)


def attempt(fn):
    """Run fn; return its result, or a string naming the exception it raised."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - a crash is a reportable result here
        return f"raised {type(exc).__name__}"


def profile(**overrides):
    p = dict(DEFAULT_PROFILE)
    p.update(overrides)
    return p


def seed(title):
    """Return one normalized song from app.default_songs() by title."""
    for raw in app.default_songs():
        if raw["title"] == title:
            return normalize_song(raw)
    raise AssertionError(f"no seed song titled {title!r}")


def song(**fields):
    """Return a normalized made-up song; mid energy and a neutral genre by default."""
    raw = {"title": "Untitled", "artist": "a", "genre": "other", "energy": 5, "tags": []}
    raw.update(fields)
    return normalize_song(raw)


ROCK_SEEDS = (
    "Thunderstruck",
    "Bohemian Rhapsody",
    "Smells Like Teen Spirit",
    "Sweet Child O' Mine",
    "Hotel California",
)
neutral = profile(favorite_genre="none")

# --- Defect 1: a hype genre keyword must not outrank the energy bands ----------
print("\nDefect 1 - hype keyword overriding energy")
check(
    "[red] Hotel California (rock, energy 6) is Chill when chill_max_energy is 6",
    classify_song(seed("Hotel California"), profile(chill_max_energy=6)),
    "Chill",
)
mellow = profile(hype_min_energy=10, chill_max_energy=9)
for title in ROCK_SEEDS:
    check(
        f"[red] {title} is Chill when hype_min_energy is 10 and chill_max_energy is 9",
        classify_song(seed(title), mellow),
        "Chill",
    )
check(
    "[guard] Sandstorm (energy 10) is still Hype at hype_min_energy 10",
    classify_song(seed("Sandstorm"), mellow),
    "Hype",
)
check(
    "[guard] Hotel California stays Hype at the default profile (Danny, 2026-09-19: "
    "in the middle band a rock keyword still breaks the tie toward Hype)",
    classify_song(seed("Hotel California"), profile()),
    "Hype",
)
check(
    "[guard] energy outranks chill keywords too: an ambient song at energy 9 is Hype",
    classify_song(song(genre="ambient", energy=9), neutral),
    "Hype",
)
check(
    "[guard] touching bands (hype_min 5, chill_max 5): energy 5 goes Hype",
    classify_song(song(energy=5), profile(hype_min_energy=5, chill_max_energy=5, favorite_genre="none")),
    "Hype",
)

# --- Defect 2: favorite_genre is an affinity, not a mood signal ----------------
print("\nDefect 2 - favorite_genre treated as a mood signal")
likes_ambient = profile(favorite_genre="ambient")
for title in ("Weightless", "Soft Piano", "Clair de Lune", "Gymnopedie No.1"):
    check(
        f"[red] {title} (energy 1-2) stays Chill when favorite_genre is ambient",
        classify_song(seed(title), likes_ambient),
        "Chill",
    )
check(
    "[red] Take Five (jazz, energy 4, no keywords) stays Mixed when favorite_genre is jazz",
    classify_song(seed("Take Five"), profile(favorite_genre="jazz")),
    "Mixed",
)
check(
    "[red] Bad Guy (pop, energy 6, no keywords) stays Mixed when favorite_genre is pop",
    classify_song(seed("Bad Guy"), profile(favorite_genre="pop")),
    "Mixed",
)

# --- Defect 3: both keyword lists must read the same fields, tags included -----
print("\nDefect 3 - keyword lists reading different fields, tags ignored")
check(
    "[red] a mid-energy song tagged 'sleep' reads as Chill",
    classify_song(song(tags=["sleep"]), neutral),
    "Chill",
)
check(
    "[red] a mid-energy song tagged 'party' reads as Hype",
    classify_song(song(tags=["party"]), neutral),
    "Hype",
)
check(
    "[guard] a song hitting both keyword lists stays Mixed instead of defaulting to Hype",
    classify_song(song(title="Punk Lullaby", genre="ambient"), neutral),
    "Mixed",
)
check(
    "[guard] tags=None on a raw dict does not crash classification",
    attempt(lambda: classify_song(
        {"title": "Untitled", "artist": "a", "genre": "other", "energy": 5, "tags": None},
        neutral,
    )),
    "Mixed",
)
# Added by claude-cp 2026-09-19, after the 16-red/12-guard gate was recorded and
# again after 28/28 passed, so tester1's two numbers stand unchanged. tester1
# caught tags=None in classify_song; normalize_song has the same defect one
# layer up, where it is worse: it stored None and app.py:288 then crashed on
# ", ".join(None) at render time. Danny authorized fixing both. See
# agent_messages/2026-09-19-02-claude-cp-to-tester1.md.
check(
    "[red] normalize_song turns tags=None into a list, so rendering cannot crash",
    normalize_song({"title": "X", "artist": "a", "genre": "other", "energy": 5, "tags": None})["tags"],
    [],
)

# --- Defect 4: keyword matching must ignore case --------------------------------
print("\nDefect 4 - case-sensitive keyword matching")
check(
    "[red] 'Sleep Tight' (capitalized, energy 5) reads as Chill",
    classify_song(song(title="Sleep Tight"), neutral),
    "Chill",
)
check(
    "[guard] 'sleep tight' (lowercase, energy 5) reads as Chill",
    classify_song(song(title="sleep tight"), neutral),
    "Chill",
)
check(
    "[red] a capitalized tag 'Party' reads as Hype",
    classify_song(song(tags=["Party"]), neutral),
    "Hype",
)
check(
    "[guard] normalize_song keeps the title's capitalization for display",
    normalize_song({"title": "Sleep Tight", "artist": "a", "genre": "other", "energy": 5})["title"],
    "Sleep Tight",
)

# --- Whole-word matching (Danny, 2026-09-19) ------------------------------------
print("\nWhole-word keyword matching")
check(
    "[guard] 'Rocket Man' is not a rock song: stays Mixed",
    classify_song(song(title="Rocket Man", genre="pop"), neutral),
    "Mixed",
)
check(
    "[guard] 'Sleepless Nights' is not a sleep song: stays Mixed",
    classify_song(song(title="Sleepless Nights"), neutral),
    "Mixed",
)
check(
    "[guard] a multi-word genre still matches: 'indie rock' at energy 5 is Hype",
    classify_song(song(genre="indie rock"), neutral),
    "Hype",
)

# --- Regression guard: default-profile membership must not drift ---------------
print("\nRegression guard - default profile, song by song")
EXPECTED_DEFAULT = {
    "Hype": [
        "Thunderstruck", "Bohemian Rhapsody", "Blinding Lights", "Strobe",
        "Smells Like Teen Spirit", "Levitating", "Midnight City",
        "Sweet Child O' Mine", "Sandstorm", "Hotel California", "Uptown Funk",
    ],
    "Chill": [
        "Lo-fi Rain", "Soft Piano", "Weightless", "So What",
        "Gymnopedie No.1", "Clair de Lune",
    ],
    "Mixed": [
        "Night Drive", "Take Five", "Bad Guy", "Fly Me to the Moon", "Feeling Good",
    ],
}
actual_default = {
    mood: [s["title"] for s in songs]
    for mood, songs in build_playlists(app.default_songs(), profile()).items()
}
check(
    "[guard] default profile puts every one of the 22 seed songs where it is today",
    actual_default,
    EXPECTED_DEFAULT,
)


def library(hype=(), chill=(), mixed=()):
    """Return a playlist map built from bare energy numbers, e.g. library(hype=[9])."""
    def make(mood, energy):
        return {"title": f"{mood} {energy}", "artist": "a", "genre": "other",
                "energy": energy, "tags": [], "mood": mood}
    return {
        "Hype": [make("Hype", e) for e in hype],
        "Chill": [make("Chill", e) for e in chill],
        "Mixed": [make("Mixed", e) for e in mixed],
    }


def picked_title(playlists, mode):
    """Return the title lucky_pick chose, None if it chose nothing, or the crash."""
    pick = attempt(lambda: lucky_pick(playlists, mode=mode))
    return pick["title"] if isinstance(pick, dict) else pick


# --- Stats: ratios and averages are over the whole library ----------------------
print("\nStats - hype_ratio and avg_energy must use every song")
small = library(hype=[9], chill=[1, 2], mixed=[4])
check(
    "[red] hype_ratio is Hype songs over ALL songs: 1 of 4 is 0.25",
    compute_playlist_stats(small)["hype_ratio"],
    0.25,
)
check(
    "[red] avg_energy averages ALL songs: (9 + 1 + 2 + 4) / 4 is 4.0",
    compute_playlist_stats(small)["avg_energy"],
    4.0,
)
check(
    "[guard] the four counts are unchanged: total 4, hype 1, chill 2, mixed 1",
    tuple(compute_playlist_stats(small)[k]
          for k in ("total_songs", "hype_count", "chill_count", "mixed_count")),
    (4, 1, 2, 1),
)
no_hype = library(chill=[1, 3])
check(
    "[red] avg_energy still works with no Hype songs: (1 + 3) / 2 is 2.0",
    compute_playlist_stats(no_hype)["avg_energy"],
    2.0,
)
check(
    "[guard] hype_ratio is 0.0 when there are no Hype songs",
    compute_playlist_stats(no_hype)["hype_ratio"],
    0.0,
)
check(
    "[guard] an empty library gives zeros, not a ZeroDivisionError",
    attempt(lambda: tuple(compute_playlist_stats(library())[k]
                          for k in ("total_songs", "hype_ratio", "avg_energy"))),
    (0, 0.0, 0.0),
)
seed_playlists = build_playlists(app.default_songs(), profile())
check(
    "[red] seed library at the default profile: hype_ratio is 11 of 22, 0.5",
    compute_playlist_stats(seed_playlists)["hype_ratio"],
    0.5,
)
check(
    "[red] seed library at the default profile: avg_energy is 126 / 22, shown as 5.73",
    round(compute_playlist_stats(seed_playlists)["avg_energy"], 2),
    5.73,
)

# --- Lucky pick: "any" means any song (Danny, 2026-09-19) -----------------------
print("\nLucky pick - 'any' must include Mixed songs")
check(
    "[red] 'any' can pick a Mixed song when Mixed is all there is",
    picked_title(library(mixed=[5]), "any"),
    "Mixed 5",
)
check(
    "[guard] 'any' can pick a Hype song when Hype is all there is",
    picked_title(library(hype=[9]), "any"),
    "Hype 9",
)
check(
    "[guard] 'any' can pick a Chill song when Chill is all there is",
    picked_title(library(chill=[1]), "any"),
    "Chill 1",
)
check(
    "[guard] 'hype' mode never falls back to Chill or Mixed songs",
    picked_title(library(chill=[1], mixed=[5]), "hype"),
    None,
)
check(
    "[guard] 'chill' mode never falls back to Hype or Mixed songs",
    picked_title(library(hype=[9], mixed=[5]), "chill"),
    None,
)
check(
    "[guard] an empty library returns None instead of crashing (Danny's fix, 534e0be)",
    picked_title(library(), "any"),
    None,
)

print()
if FAILURES:
    print(f"{len(FAILURES)} check(s) failed.")
    raise SystemExit(1)
print("All checks passed.")
