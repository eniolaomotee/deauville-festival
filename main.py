"""Deauville Festival du Rire - the programme from the terminal.

uv run main.py                          the summary of the festival
uv run main.py venues                   each venue with its slug and seats
uv run main.py programme 2027-06-11     the programme of a day
uv run main.py artist max-pellerin      the performances of an artist
"""

import json
import sys
import unicodedata

DATA_FILE = "data/festival.json"


# --- Reading the data 

def load_festival(path: str = DATA_FILE) -> dict:
    with open(path, encoding="utf-8") as file:
        return json.load(file)

# --- Slugs and lookups 

def slugify(name: str) -> str:
    """'Théâtre des Planches' -> 'theatre-des-planches'."""
    decomposed = unicodedata.normalize("NFKD", name)
    plain = decomposed.encode("ascii", "ignore").decode("ascii")
    slug = ""
    for char in plain.lower():
        if char.isalnum():
            slug += char
        elif not slug.endswith("-"):
            slug += "-"
    return slug.strip("-")


def find_venue(festival: dict, slug: str) -> dict | None:
    for venue in festival["venues"]:
        if slugify(venue["name"]) == slug:
            return venue
    return None


def find_artist(festival: dict, slug: str) -> dict | None:
    for artist in festival["artists"]:
        if slugify(artist["name"]) == slug:
            return artist
    return None


def venue_name(festival: dict, slug: str) -> str:
    venue = find_venue(festival, slug)
    return venue["name"] if venue else slug


# --- Questions about the festival ------------------------------------------

def festival_days(festival: dict) -> list[str]:
    days = []
    for performance in festival["performances"]:
        day = performance["start"][:10]
        if day not in days:
            days.append(day)
    return days

def programme(festival: dict, day: str) -> list[dict]:
    """The performances starting on that calendar day (bug of step 02 kept)."""
    result = []
    for performance in festival["performances"]:
        if performance["start"][:10] == day:
            result.append(performance)
    return result


def role_of(performance: dict, artist_slug: str) -> str | None:
    """'solo', 'host', 'act', 'teacher', or None if the artist is not on stage."""
    kind = performance["kind"]
    if kind == "solo" and performance["artist"] == artist_slug:
        return "solo"
    if kind == "lineup":
        if performance["host"] == artist_slug:
            return "host"
        if artist_slug in performance["acts"]:
            return "act"
    if kind == "workshop" and performance["teacher"] == artist_slug:
        return "teacher"
    return None

def artist_performances(festival: dict, artist_slug: str) -> list[tuple[dict, str]]:
    """(performance, role) pairs for one artist, in data order."""
    result = []
    for performance in festival["performances"]:
        role = role_of(performance, artist_slug)
        if role is not None:
            result.append((performance, role))
    return result


# --- Printing: only here, at the end of the chain --------------------------

def show_summary(festival: dict) -> None:
    print(festival["name"])
    print(f"From {festival['first_day']} to {festival['last_day']}")
    print(
        f"{len(festival['venues'])} venues, {len(festival['artists'])} artists, "
        f"{len(festival['performances'])} performances"
    )


def show_venues(festival: dict) -> None:
    total = 0
    for venue in festival["venues"]:
        print(f"{slugify(venue['name'])}: {venue['name']}, {venue['capacity']} seats")
        total += venue["capacity"]
    print(f"Total: {total} seats")


def show_programme(festival: dict, day: str) -> None:
    days = festival_days(festival)
    if day not in days:
        print(f"No performance on {day!r}. Days: {', '.join(days)}")
        return
    print(f"Programme for {day}:")
    for performance in programme(festival, day):
        time = performance["start"][11:]
        venue = venue_name(festival, performance["venue"])
        print(f"{time} | {venue} | {performance['title']} ({performance['kind']})")


def show_artist(festival: dict, slug: str) -> None:
    artist = find_artist(festival, slug)
    if artist is None:
        print(f"No artist {slug!r}.")
        return
    print(artist["name"])
    for performance, role in artist_performances(festival, slug):
        when = performance["start"].replace("T", " ")
        venue = venue_name(festival, performance["venue"])
        print(f"{when} | {venue} | {performance['title']} ({role})")


# --- Commands --------------------------------------------------------------


def main() -> None:
    festival = load_festival()
    arguments = sys.argv[1:]
    if len(arguments) == 0:
        show_summary(festival)
    elif arguments == ["venues"]:
        show_venues(festival)
    elif arguments[0] == "programme" and len(arguments) == 2:
        show_programme(festival, arguments[1])
    elif arguments[0] == "artist" and len(arguments) == 2:
        show_artist(festival, arguments[1])
    else:
        print(__doc__)


main()
