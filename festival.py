"""The festival: data, rules and questions. No printing here."""

import json
import unicodedata
from datetime import date, datetime, timedelta

DATA_FILE = "data/festival.json"
DAY_CHANGE = timedelta(hours=6)
GAP = timedelta(minutes=30)


def load_festival(path: str = DATA_FILE) -> dict:
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        raise ValueError(f"{path} is not found")
    except json.JSONDecodeError as error:
        raise ValueError(
            f"{path} is damaged: {error.msg} at line {error.lineno}, column {error.colno}"
        )


def save_festival(festival: dict, path: str = DATA_FILE) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(festival, file, indent=2, ensure_ascii=False)
        file.write("\n")


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


def performance_id(performance: dict) -> str:
    """The ID of a performance, used to cancel it."""
    return f"{performance['venue']}-{start_of(performance):%Y-%m-%d-%H%M}"


def find_performance(festival: dict, id: str) -> dict | None:
    for performance in festival["performances"]:
        if performance_id(performance) == id:
            return performance
    return None


def start_of(performance: dict) -> datetime:
    return datetime.fromisoformat(performance["start"])


def end_of(performance: dict) -> datetime:
    return start_of(performance) + timedelta(minutes=performance["duration_minutes"])


def festival_day_of(performance: dict) -> date:
    """The festival day: the date of the start, moved back 6 hours."""
    return (start_of(performance) - DAY_CHANGE).date()


def too_close(a: dict, b: dict) -> bool:
    """True when less than GAP separates the two performances."""
    return start_of(a) < end_of(b) + GAP and start_of(b) < end_of(a) + GAP


def check_performance(festival: dict, new: dict) -> None:
    """Raise ValueError, with a sentence for the organiser, if `new` breaks a rule."""
    if not new["title"]:
        raise ValueError("A performance needs a title.")
    if find_venue(festival, new["venue"]) is None:
        raise ValueError(f"No venue {new['venue']!r}.")
    for slug in artists_of(new):
        if find_artist(festival, slug) is None:
            raise ValueError(f"No artist {slug!r}.")
    if not 1 <= new["duration_minutes"] <= 360:
        raise ValueError(
            f"A performance lasts from 1 to 360 minutes, not {new['duration_minutes']}."
        )
    first = date.fromisoformat(festival["first_day"])
    last = date.fromisoformat(festival["last_day"])
    day = festival_day_of(new)
    if not first <= day <= last:
        raise ValueError(f"{day} is not a day of the festival.")
    for other in festival["performances"]:
        if other is new or not too_close(new, other):
            continue
        if other["venue"] == new["venue"]:
            raise ValueError(
                f"{venue_name(festival, new['venue'])} is busy with {other['title']} "
                f"({start_of(other):%Y-%m-%d %H:%M}-{end_of(other):%H:%M})."
            )
        for slug in artists_of(new):
            if slug in artists_of(other):
                name = find_artist(festival, slug)["name"]
                raise ValueError(f"{name} is on stage in {other['title']}.")


def add_performance(festival: dict, new: dict) -> None:
    check_performance(festival, new)  # if it raises, nothing is added
    festival["performances"].append(new)


def cancel_performance(festival: dict, id: str) -> dict:
    performance = find_performance(festival, id)
    if performance is None:
        raise ValueError(f"No performance {id!r}.")
    festival["performances"].remove(performance)
    return performance


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


def artist_performances(festival: dict, artist_slug: str) -> list[tuple[dict, str]]:
    """(performance, role) pairs for one artist, in order of start."""
    result = []
    for performance in sorted(festival["performances"], key=start_of):
        role = role_of(performance, artist_slug)
        if role is not None:
            result.append((performance, role))
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


def artists_of(performance: dict) -> list[str]:
    """The slugs of the artists on stage in a performance."""
    kind = performance["kind"]
    if kind == "solo":
        return [performance["artist"]]
    if kind == "lineup":
        return [performance["host"]] + performance["acts"]
    if kind == "workshop":
        return [performance["teacher"]]
    return []
