"""Deauville Festival du Rire - the programme from the terminal.

uv run main.py                          the summary of the festival
uv run main.py venues                   each venue with its slug and seats
uv run main.py programme 2027-06-11     the programme of a festival day
uv run main.py artist max-pellerin      the performances of an artist
uv run main.py now 2027-06-11T21:00     what is on stage, and the next 3 shows
"""

import json
import sys
import unicodedata
from datetime import date, datetime, timedelta

DATA_FILE = "data/festival.json"

# A festival day ends at 06:00: a show at 01:00 belongs to the day before.
DAY_CHANGE = timedelta(hours=6)


# --- Reading the data ------------------------------------------------------


def load_festival(path: str = DATA_FILE) -> dict:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


# --- Slugs and lookups -----------------------------------------------------


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


# --- Time of a performance -------------------------------------------------


def start_of(performance: dict) -> datetime:
    return datetime.fromisoformat(performance["start"])


def end_of(performance: dict) -> datetime:
    return start_of(performance) + timedelta(minutes=performance["duration_minutes"])


def festival_day_of(performance: dict) -> date:
    """The festival day: the date of the start, moved back 6 hours."""
    return (start_of(performance) - DAY_CHANGE).date()


# --- Questions about the festival ------------------------------------------


def festival_days(festival: dict) -> list[date]:
    days = []
    for performance in festival["performances"]:
        day = festival_day_of(performance)
        if day not in days:
            days.append(day)
    return sorted(days)


def programme(festival: dict, day: date) -> list[dict]:
    """The performances of one festival day, in order of start."""
    result = []
    for performance in festival["performances"]:
        if festival_day_of(performance) == day:
            result.append(performance)
    return sorted(result, key=start_of)


def on_stage(festival: dict, at: datetime) -> list[dict]:
    result = []
    for performance in festival["performances"]:
        if start_of(performance) <= at < end_of(performance):
            result.append(performance)
    return sorted(result, key=start_of)


def up_next(festival: dict, at: datetime, count: int = 3) -> list[dict]:
    result = []
    for performance in festival["performances"]:
        if start_of(performance) > at:
            result.append(performance)
    return sorted(result, key=start_of)[:count]


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
    """(performance, role) pairs for one artist, in order of start."""
    result = []
    for performance in sorted(festival["performances"], key=start_of):
        role = role_of(performance, artist_slug)
        if role is not None:
            result.append((performance, role))
    return result


# --- Printing: only here, at the end of the chain --------------------------


def describe(festival: dict, performance: dict) -> str:
    """'10:30-12:30 | La Cabane | Improv for Beginners (workshop)'."""
    start, end = start_of(performance), end_of(performance)
    venue = venue_name(festival, performance["venue"])
    return f"{start:%H:%M}-{end:%H:%M} | {venue} | {performance['title']} ({performance['kind']})"


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


def show_programme(festival: dict, day: date) -> None:
    days = festival_days(festival)
    if day not in days:
        print(f"No performance on {day}. Days: {', '.join(str(d) for d in days)}")
        return
    print(f"Programme for {day:%A %d %B}:")
    for performance in programme(festival, day):
        print(describe(festival, performance))


def show_artist(festival: dict, slug: str) -> None:
    artist = find_artist(festival, slug)
    if artist is None:
        print(f"No artist {slug!r}.")
        return
    print(artist["name"])
    for performance, role in artist_performances(festival, slug):
        start, end = start_of(performance), end_of(performance)
        venue = venue_name(festival, performance["venue"])
        print(
            f"{start:%a %d %H:%M}-{end:%H:%M} | {venue} | "
            f"{performance['title']} ({role})"
        )


def show_now(festival: dict, at: datetime) -> None:
    print(f"On stage at {at:%Y-%m-%d %H:%M}:")
    current = on_stage(festival, at)
    if not current:
        print("- nothing")
    for performance in current:
        venue = venue_name(festival, performance["venue"])
        print(f"- {performance['title']} at {venue}, until {end_of(performance):%H:%M}")
    print("Up next:")
    for performance in up_next(festival, at):
        print(f"- {describe(festival, performance)}")


# --- Commands --------------------------------------------------------------


def main() -> None:
    festival = load_festival()
    arguments = sys.argv[1:]
    if len(arguments) == 0:
        show_summary(festival)
    elif arguments == ["venues"]:
        show_venues(festival)
    elif arguments[0] == "programme" and len(arguments) == 2:
        show_programme(festival, date.fromisoformat(arguments[1]))
    elif arguments[0] == "artist" and len(arguments) == 2:
        show_artist(festival, arguments[1])
    elif arguments[0] == "now" and len(arguments) == 2:
        show_now(festival, datetime.fromisoformat(arguments[1]))
    else:
        print(__doc__)


main()
