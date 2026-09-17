from typing import Dict, List, Optional, Tuple

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

    tags = raw.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    return {
        "title": title,
        "artist": artist,
        "genre": genre,
        "energy": energy,
        "tags": tags,
    }

# Classification logic for songs based on user profile and song attributes.
def classify_song(song: Song, profile: Dict[str, object]) -> str:
    """Return a mood label given a song and user profile.
       Possible return values are "Hype", "Chill", or "Mixed".
       "Hype" indicates high-energy songs,
       "Chill" indicates low-energy songs,
       and "Mixed" indicates songs that don't clearly fit either category.
    """

    # Extract relevant song and profile attributes for classification.

    # energy level of the song
    # default to 0 if energy is not specified
    energy = song.get("energy", 0)

    # genre of the song
    # default to empty string if genre is not specified
    genre = song.get("genre", "")

    # title of the song
    # default to empty string if title is not specified
    title = song.get("title", "")

    # Extract relevant profile attributes for classification.

    # minimum energy threshold for a song to be considered "Hype"
    # 7 is the default minimum energy for "Hype" songs
    hype_min_energy = profile.get("hype_min_energy", 7)

    # maximum energy threshold for a song to be considered "Chill"
    # 3 is the default maximum energy for "Chill" songs
    chill_max_energy = profile.get("chill_max_energy", 3)


    # user's favorite genre
    favorite_genre = profile.get("favorite_genre", "")

    # keywords associated with "Hype" songs
    hype_keywords = ["rock", "punk", "party"]

    # keywords associated with "Chill" songs
    chill_keywords = ["lofi", "ambient", "sleep"]

    # check if the song's genre contains any "Hype" keywords
    # for k in hype_keywords: check if k is in genre
    is_hype_keyword = any(k in genre for k in hype_keywords)

    # check if the song's title contains any "Chill" keywords
    # for k in chill_keywords: check if k is in title
    is_chill_keyword = any(k in title for k in chill_keywords)

    if genre == favorite_genre or energy >= hype_min_energy or is_hype_keyword:
        return "Hype"
    if energy <= chill_max_energy or is_chill_keyword:
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

    total = len(hype)
    hype_ratio = len(hype) / total if total > 0 else 0.0

    avg_energy = 0.0
    if all_songs:
        total_energy = sum(song.get("energy", 0) for song in hype)
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
    """Pick a song from the playlists according to mode."""
    if mode == "hype":
        songs = playlists.get("Hype", [])
    elif mode == "chill":
        songs = playlists.get("Chill", [])
    else:
        songs = playlists.get("Hype", []) + playlists.get("Chill", [])

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
