import re
from typing import Dict, List, Optional, Set, Tuple

# Type aliases for song and playlist data structures.

# A song is represented as a dictionary with keys like "title", "artist", "genre", "energy", and "tags".
# A playlist map is a dictionary mapping mood labels ("Hype", "Chill", "Mixed") to lists of songs.
Song = Dict[str, object]
PlaylistMap = Dict[str, List[Song]]

# Default user profile for classification and playlist building.
DEFAULT_PROFILE = {
    "name": "Default",
    "hype_min_energy": 7,
    "chill_max_energy": 3,
    "favorite_genre": "rock",
    "include_mixed": True,
}


def normalize_title(title: str) -> str:
    """Normalize a song title for comparisons."""
    if not isinstance(title, str):
        return ""
    return title.strip()


def normalize_artist(artist: str) -> str:
    """Normalize an artist name for comparisons."""
    if not artist:
        return ""
    return artist.strip().lower()


def normalize_genre(genre: str) -> str:
    """Normalize a genre name for comparisons."""
    return genre.lower().strip()


def normalize_song(raw: Song) -> Song:
    """Return a normalized song dict with expected keys."""
    title = normalize_title(str(raw.get("title", "")))
    artist = normalize_artist(str(raw.get("artist", "")))
    genre = normalize_genre(str(raw.get("genre", "")))
    energy = raw.get("energy", 0)

    if isinstance(energy, str):
        try:
            energy = int(energy)
        except ValueError:
            energy = 0

    # Fix (2026-09-19): `or []` rather than a .get() default, because a "tags"
    # key that is present but None slips past the default and was stored as
    # None, which then crashed rendering in app.py ("can only join an iterable").
    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]

    return {
        "title": title,
        "artist": artist,
        "genre": genre,
        "energy": energy,
        "tags": tags,
    }

# Words that hint at a song's mood. These are hints, not overrides: the energy
# bands decide first (see classify_song). Both lists are matched against the
# same text, so neither mood gets a field the other one doesn't.
HYPE_KEYWORDS = ("rock", "punk", "party")
CHILL_KEYWORDS = ("lofi", "ambient", "sleep")


def mood_keyword_words(song: Song) -> Set[str]:
    """Return the lowercased whole words of a song's genre, title and tags.

    Lowercasing happens here at comparison time rather than in normalize_title()
    because app.py renders song["title"] verbatim and must keep its casing.

    Whole words, not substrings: genre comes from a fixed selectbox, but titles
    and tags are free text, where substring matching misfires -- "Rocket Man"
    would read as a rock song and "Sleepless Nights" as a sleep one. The cost is
    that near-misses no longer match either: "afterparty" is not "party",
    "sleepy" is not "sleep", and hyphenated "Lo-fi" is not "lofi" (it never was;
    the seed song "Lo-fi Rain" is Chill through its genre and energy, not its
    title). Splitting on non-alphanumerics keeps multi-word and hyphenated
    genres working, so "indie rock" and "pop-punk" still match.
    """
    tags = song.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]

    parts = [str(song.get("genre", "")), str(song.get("title", ""))]
    parts.extend(str(tag) for tag in tags)

    return set(re.findall(r"[a-z0-9]+", " ".join(parts).lower()))


# Classification logic for songs based on user profile and song attributes.
def classify_song(song: Song, profile: Dict[str, object]) -> str:
    """Return a mood label given a song and user profile.
       Possible return values are "Hype", "Chill", or "Mixed".
       "Hype" indicates high-energy songs,
       "Chill" indicates low-energy songs,
       and "Mixed" indicates songs that don't clearly fit either category.

       The profile's "favorite_genre" is deliberately not consulted. It used to
       return "Hype" on a genre match, which meant choosing a favorite of
       "ambient" threw every energy-1 sleep track into the Hype playlist.
       Liking a genre says nothing about its energy: it is an affinity signal,
       not a mood one, and belongs in ordering or lucky-pick weighting instead.
       (Danny authorized dropping it, 2026-09-19.)
    """
    # energy level of the song
    # default to 0 if energy is not specified
    energy = song.get("energy", 0)

    # minimum energy threshold for a song to be considered "Hype"
    # 7 is the default minimum energy for "Hype" songs
    hype_min_energy = profile.get("hype_min_energy", 7)
    # maximum energy threshold for a song to be considered "Chill"
    # 3 is the default maximum energy for "Chill" songs
    chill_max_energy = profile.get("chill_max_energy", 3)

    # Fix (2026-09-19): the energy bands are tested on their own, before any
    # keyword test. They are the only mood signal the user actually controls,
    # so they have to outrank everything else. They previously shared one flat
    # `or` chain with the keyword and favorite-genre tests, which pinned a song
    # to "Hype" no matter where the sliders were set: every rock song stayed
    # "Hype" even with Hype min at 10 and Chill max at 9, and Hotel California
    # (energy 6) stayed "Hype" with Chill max raised to 6.
    if energy >= hype_min_energy:
        return "Hype"
    if energy <= chill_max_energy:
        return "Chill"

    # Only songs in the ambiguous middle band reach here, so keywords break the
    # tie rather than overriding the profile. A song that hits both lists (or
    # neither) stays "Mixed" instead of falling through to "Hype".
    words = mood_keyword_words(song)
    is_hype_keyword = any(k in words for k in HYPE_KEYWORDS)
    is_chill_keyword = any(k in words for k in CHILL_KEYWORDS)

    if is_hype_keyword and not is_chill_keyword:
        return "Hype"
    if is_chill_keyword and not is_hype_keyword:
        return "Chill"
    return "Mixed"


def build_playlists(songs: List[Song], profile: Dict[str, object]) -> PlaylistMap:
    """Group songs into playlists based on mood and profile."""
    playlists: PlaylistMap = {
        "Hype": [],
        "Chill": [],
        "Mixed": [],
    }

    for song in songs:
        normalized = normalize_song(song)
        mood = classify_song(normalized, profile)
        normalized["mood"] = mood
        playlists[mood].append(normalized)

    return playlists


def merge_playlists(a: PlaylistMap, b: PlaylistMap) -> PlaylistMap:
    """Merge two playlist maps into a new map."""
    merged: PlaylistMap = {}
    for key in set(list(a.keys()) + list(b.keys())):
        merged[key] = a.get(key, [])
        merged[key].extend(b.get(key, []))
    return merged


def compute_playlist_stats(playlists: PlaylistMap) -> Dict[str, object]:
    """Compute statistics across all playlists."""
    all_songs: List[Song] = []
    for songs in playlists.values():
        all_songs.extend(songs)

    hype = playlists.get("Hype", [])
    chill = playlists.get("Chill", [])
    mixed = playlists.get("Mixed", [])

    # Fix (2026-09-19): both figures are over the whole library, not just Hype.
    # hype_ratio divided the Hype count by itself, so it read 1.00 whenever a
    # single Hype song existed and never moved no matter what was added.
    total = len(all_songs)
    hype_ratio = len(hype) / total if total > 0 else 0.0

    # Fix (2026-09-19): avg_energy summed the Hype list but divided by every
    # song, so it was not an average of anything -- the seed library read 4.05
    # (89 / 22) instead of 5.73 (126 / 22).
    avg_energy = 0.0
    if all_songs:
        total_energy = sum(song.get("energy", 0) for song in all_songs)
        avg_energy = total_energy / len(all_songs)

    top_artist, top_count = most_common_artist(all_songs)

    return {
        "total_songs": len(all_songs),
        "hype_count": len(hype),
        "chill_count": len(chill),
        "mixed_count": len(mixed),
        "hype_ratio": hype_ratio,
        "avg_energy": avg_energy,
        "top_artist": top_artist,
        "top_artist_count": top_count,
    }


def most_common_artist(songs: List[Song]) -> Tuple[str, int]:
    """Return the most common artist and count."""
    counts: Dict[str, int] = {}
    for song in songs:
        artist = str(song.get("artist", ""))
        if not artist:
            continue
        counts[artist] = counts.get(artist, 0) + 1

    if not counts:
        return "", 0

    items = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return items[0]


def search_songs(
    songs: List[Song],
    query: str,
    field: str = "artist",
) -> List[Song]:
    """Return songs matching the query on a given field."""
    if not query:
        return songs

    q = query.lower().strip()
    filtered: List[Song] = []

    for song in songs:
        value = str(song.get(field, "")).lower()
        if value and q in value:
            filtered.append(song)

    return filtered


def lucky_pick(
    playlists: PlaylistMap,
    mode: str = "any",
) -> Optional[Song]:
    """Pick a song from the playlists according to mode.

    "any" means any song in the library, Mixed included. It is deliberately not
    tied to the profile's "Include Mixed playlist in views" checkbox: that box
    controls which tabs render, not what the library contains. (Danny decided
    this 2026-09-19; before that, "any" drew from Hype + Chill only, so the 5
    Mixed seed songs could never be picked and a Mixed-only library reported
    "No songs available".)

    Any mode that is not "hype" or "chill" is treated as "any", typos included.
    """
    if mode == "hype":
        songs = playlists.get("Hype", [])
    elif mode == "chill":
        songs = playlists.get("Chill", [])
    else:
        # Fix (2026-09-19): Mixed included -- see the docstring.
        songs = (
            playlists.get("Hype", [])
            + playlists.get("Chill", [])
            + playlists.get("Mixed", [])
        )

    return random_choice_or_none(songs)


def random_choice_or_none(songs: List[Song]) -> Optional[Song]:
    """Return a random song or None."""
    import random

    if not songs:
        return None

    return random.choice(songs)


def history_summary(history: List[Song]) -> Dict[str, int]:
    """Return a summary of moods seen in the history."""
    counts = {"Hype": 0, "Chill": 0, "Mixed": 0}
    for song in history:
        mood = song.get("mood", "Mixed")
        if mood not in counts:
            counts["Mixed"] += 1
        else:
            counts[mood] += 1
    return counts
