"""Deauville Festival du Rire - the programme from the terminal.

uv run main.py                          the summary of the festival
uv run main.py venues                   each venue with its slug and seats
uv run main.py programme 2027-06-11     the programme of a festival day
uv run main.py artist max-pellerin      the performances of an artist
uv run main.py now 2027-06-11T21:00     what is on stage, and the next 3 shows
uv run main add                         schedule a solo show (asks the details)
uv run main.py cancel ID.               cancel a performance by its ID (asks for confirmation)
"""

import sys
from datetime import date, datetime

from errors import FestivalError, InvalidError
from festival import Festival, load_festival, save_festival

# --- Reading the data ------------------------------------------------------


def parse_day(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise InvalidError(f"{text!r} is not a day, use YYYY-MM-DD format") from None


def parse_datetime(text: str) -> datetime:
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise InvalidError(
            f"{text!r} is not a date and time, use YYYY-MM-DDTHH:MM format"
        ) from None


def parse_minutes(text: str) -> int:
    try:
        return int(text)
    except InvalidError:
        raise ValueError(f"{text!r} is not a number of minutes") from None


def show_summary(festival: Festival) -> None:
    print(festival.name)
    print(f"From {festival.first_day} to {festival.last_day}")
    print(
        f"{len(festival.venues)} venues, {len(festival.artists)} artists, "
        f"{len(festival.performances)} performances"
    )


def show_venues(festival: Festival) -> None:
    total = 0
    for venue in festival.venues:
        print(f"{venue.slug}: {venue.name}, {venue.capacity} seats")
        total += venue.capacity
    print(f"Total: {total} seats")


def show_programme(festival: Festival, day: date) -> None:
    if day not in festival.days:
        print(
            f"No performance on {day}. Days: {', '.join(str(d) for d in festival.days)}"
        )
        return
    print(f"Programme for {day:%A %d %B}:")
    for performance in festival.programme(day):
        print(performance)


def show_artist(festival: Festival, slug: str):
    artist = festival.artist(slug)
    print(artist.name)
    for performance in festival.performances_of(artist):
        print(
            f"{performance.start:%a %d %H:%M}-{performance.end:%H:%M} | "
            f"{performance.venue.name} | {performance.title} "
            f"({performance.role_of(artist)})"
        )


def show_now(festival: Festival, at: datetime) -> None:
    print(f"On stage at {at:%Y-%m-%d %H:%M}:")
    current = festival.on_stage(at)
    if not current:
        print("- nothing")
    for performance in current:
        print(
            f"- {performance.title} at {performance.venue.name}, "
            f"until {performance.end:%H:%M}"
        )
    for performance in festival.up_next(at):
        print(f"- {performance}")


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
        new = festival.make_performance(ask_solo())
        festival.schedule(new)
        save_festival(festival)
        print(f"Added: {new.id}")
    elif arguments[0] == "cancel" and len(arguments) == 2:
        cancelled = festival.cancel(arguments[1])
        save_festival(festival)
        print(f"Cancelled: {cancelled.title}")
    else:
        print(__doc__)


def main() -> None:
    try:
        run(sys.argv[1:])
    except FestivalError as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
