import sys
from datetime import date, datetime

from festival import (
    add_performance,
    artist_performances,
    cancel_performance,
    end_of,
    festival_days,
    find_artist,
    load_festival,
    on_stage,
    performance_id,
    programme,
    save_festival,
    slugify,
    start_of,
    up_next,
    venue_name,
)

"""Deauville Festival du Rire - the programme from the terminal.

uv run main.py                          the summary of the festival
uv run main.py venues                   each venue with its slug and seats
uv run main.py programme 2027-06-11     the programme of a festival day
uv run main.py artist max-pellerin      the performances of an artist
uv run main.py now 2027-06-11T21:00     what is on stage, and the next 3 shows
uv run main add                         schedule a solo show (asks the details)
uv run main.py cancel ID.               cancel a performance by its ID (asks for confirmation)
"""


DATA_FILE = "data/festival.json"


# --- Reading the data ------------------------------------------------------


def parse_day(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{text!r} is not a day, use YYYY-MM-DD format") from None


def parse_datetime(text: str) -> datetime:
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(
            f"{text!r} is not a date and time, use YYYY-MM-DDTHH:MM format"
        ) from None


def parse_minutes(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise ValueError(f"{text!r} is not a number of minutes") from None


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


def ask_solo() -> dict:
    """Ask the details of a solo show; raise ValueError on a wrong answer."""
    title = input("Title: ").strip()
    artist = input("Artist (slug): ").strip()
    venue = input("Venue (slug): ").strip()
    start = parse_datetime(input("Start (YYYY-MM-DDTHH:MM): ").strip())
    minutes = parse_minutes(input("Duration (minutes): ").strip())
    return {
        "kind": "solo",
        "title": title,
        "venue": venue,
        "start": f"{start:%Y-%m-%dT%H:%M}",
        "duration_minutes": minutes,
        "description": "",
        "artist": artist,
        "min_age": 0,
    }


# --- Commands --------------------------------------------------------------


def run(arguments: list[str]) -> None:
    festival = load_festival()
    if len(arguments) == 0:
        show_summary(festival)
    elif arguments == ["venues"]:
        show_venues(festival)
    elif arguments[0] == "programme" and len(arguments) == 2:
        show_programme(festival, parse_day(arguments[1]))
    elif arguments[0] == "artist" and len(arguments) == 2:
        show_artist(festival, arguments[1])
    elif arguments[0] == "now" and len(arguments) == 2:
        show_now(festival, parse_datetime(arguments[1]))
    elif arguments == ["add"]:
        new = ask_solo()
        add_performance(festival, new)
        save_festival(festival)
        print(f"Added: {performance_id(new)}")
    elif arguments[0] == "cancel" and len(arguments) == 2:
        cancelled = cancel_performance(festival, arguments[1])
        save_festival(festival)
        print(f"Cancelled: {cancelled['title']}")
    else:
        print(__doc__)


def main() -> None:
    try:
        run(sys.argv[1:])
    except ValueError as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
