"""Checks for app.py's UI: the mood-profile sidebar and the stats tiles.

Run with:

    .venv/bin/python -B test_app.py

(-B just avoids writing bytecode nobody reads. Until 2026-09-19 it also kept test
runs from dirtying git-tracked .pyc files, but __pycache__/ is gitignored now.)

Written 2026-09-19 alongside the range-slider fix. Uses st.testing.v1.AppTest,
which runs app.py in-process and headless -- no browser, no server, no port --
so the wiring from slider to profile to playlist is actually asserted rather
than eyeballed once. tester1's review (agent_messages/2026-09-19-01) verified
the classification logic but explicitly ran nothing in Streamlit; this file
covers that gap.

The classification rules and the stats arithmetic are tested in
test_playlist_logic.py. What this file tests is that the UI feeds them the right
inputs and renders the right numbers back.

Renamed from test_app_sidebar.py on 2026-09-19, when the stats-tile checks were
added: those tiles are on the main page, so "sidebar" no longer described the file.
"""

from streamlit.testing.v1 import AppTest

FAILURES = []


def check(label, actual, expected):
    """Record a comparison instead of raising, so one run reports every failure."""
    if actual == expected:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}\n          expected {expected!r}, got {actual!r}")
        FAILURES.append(label)


def bands(at):
    """Return the mood-energy-bands range slider, found by label not index."""
    for slider in at.slider:
        if slider.label == "Mood energy bands":
            return slider
    raise AssertionError(
        f"no slider labeled 'Mood energy bands'; found {[s.label for s in at.slider]}"
    )


def selectbox(at, label):
    """Return a selectbox by label.

    Not by index: AppTest orders main-page elements before sidebar ones, so
    at.selectbox[0] is the Lucky pick control, not the profile's. Two of the
    three also share the same options list.
    """
    for box in at.selectbox:
        if box.label == label:
            return box
    raise AssertionError(
        f"no selectbox labeled {label!r}; found {[b.label for b in at.selectbox]}"
    )


def metric(at, label):
    """Return a stats tile's rendered value by label."""
    for tile in at.metric:
        if tile.label == label:
            return tile.value
    raise AssertionError(
        f"no metric labeled {label!r}; found {[t.label for t in at.metric]}"
    )


def mood_of(at, title):
    """Return the mood app.py rendered for a song, read back out of the page."""
    for md in at.markdown:
        if f"**{title}**" in md.value:
            return md.value.split("mood ")[1].split(")")[0]
    return None


print("\nSidebar wiring")
at = AppTest.from_file("app.py").run()
check("[guard] the app runs without raising", list(at.exception), [])
check("[guard] the two energy sliders are replaced by one range slider",
      sum(1 for s in at.slider if s.label == "Mood energy bands"), 1)
check("[guard] it opens on the profile defaults (chill_max 3, hype_min 7)",
      tuple(bands(at).value), (3, 7))
check("[guard] the dead st.sidebar.columns(2) block is gone",
      len(at.sidebar.columns), 0)

print("\nMoving the handles rewrites both profile keys")
bands(at).set_range(6, 9).run()
check("[guard] no exception after moving the handles", list(at.exception), [])
check("[guard] the left handle writes chill_max_energy",
      at.session_state.profile["chill_max_energy"], 6)
check("[guard] the right handle writes hype_min_energy",
      at.session_state.profile["hype_min_energy"], 9)

print("\nThe profile actually moves songs (the reported bug)")
check("[guard] Hotel California (rock, energy 6) is Chill with Chill max at 6",
      mood_of(at, "Hotel California"), "Chill")

at = AppTest.from_file("app.py").run()
bands(at).set_range(9, 10).run()
check("[guard] no exception under the mellow profile", list(at.exception), [])
for title in ("Thunderstruck", "Bohemian Rhapsody", "Smells Like Teen Spirit",
              "Sweet Child O' Mine", "Hotel California"):
    check(f"[guard] {title} is Chill when the bands are 9 and 10",
          mood_of(at, title), "Chill")
check("[guard] Sandstorm (energy 10) is still Hype there",
      mood_of(at, "Sandstorm"), "Hype")

at = AppTest.from_file("app.py").run()
check("[guard] Hotel California is back in Hype at the defaults (Danny, "
      "2026-09-19: a mid-energy rock song stays Hype at the default profile)",
      mood_of(at, "Hotel California"), "Hype")

print("\nOverlapping bands are unreachable")
at = AppTest.from_file("app.py").run()
bands(at).set_range(5, 5).run()
check("[guard] handles can sit together without raising", list(at.exception), [])
check("[guard] together means an empty Mixed band, and a tie goes Hype",
      at.session_state.profile["chill_max_energy"] == 5
      and at.session_state.profile["hype_min_energy"] == 5
      and mood_of(at, "Fly Me to the Moon") == "Hype",
      True)

print("\nFavorite genre no longer changes any playlist")
at = AppTest.from_file("app.py").run()
before = {t: mood_of(at, t) for t in ("Weightless", "Clair de Lune", "Soft Piano")}
selectbox(at, "Favorite genre").select("ambient").run()
check("[guard] the selectbox still records the choice in the profile",
      at.session_state.profile["favorite_genre"], "ambient")
check("[guard] but energy-1 ambient songs stay Chill instead of turning Hype",
      {t: mood_of(at, t) for t in before}, before)

print("\nStats tiles read back from the rendered page")
at = AppTest.from_file("app.py").run()
check("[red] the Hype ratio tile shows 0.50, not 1.00 (11 of 22 seed songs)",
      metric(at, "Hype ratio"), "0.50")
check("[red] the Average energy tile shows 5.73 (126 / 22), not 4.05",
      metric(at, "Average energy"), "5.73")

print()
if FAILURES:
    print(f"{len(FAILURES)} check(s) failed.")
    raise SystemExit(1)
print("All checks passed.")
