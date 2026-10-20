"""The festival: data, rules and questions. No printing here."""

import json
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta

DATA_FILE = "data/festival.json"
DAY_CHANGE = timedelta(hours=6)
GAP = timedelta(minutes=30)

KINDS = ("solo", "lineup", "workshop")


@dataclass(eq=False)
class Artist:
    name: str
    bio: str = ""
    photo_url: str = ""

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("A venue needs a name.")

    @property
    def slug(self) -> str:
        return slugify(self.name)

    def __eq__(self, other: object) -> bool:
        """Same slug: same artist."""
        return isinstance(other, Artist) and self.slug == other.slug

    def __hash__(self) -> int:
        return hash(self.slug)

    def to_view(self) -> str:
        return {
            "slug": self.slug,
            "name": self.name,
            "bio": self.bio,
            "photo_url": self.photo_url,
        }

    def to_data(self) -> dict:
        return {"name": self.name, "bio": self.bio, "photo_url": self.photo_url}


@dataclass(eq=False)
class Venue:
    name: str
    capacity: int
    address: str = ""

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("A venue needs a name.")
        if self.capacity < 1:
            raise ValueError(f"{self.name} needs at least one seat.")

    @property
    def slug(self) -> str:
        return slugify(self.name)

    def __eq__(self, other: object) -> bool:
        """Same slug: same venue."""
        return isinstance(other, Venue) and self.slug == other.slug

    def __hash__(self) -> int:
        return hash(self.slug)

    def to_view(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "capacity": self.capacity,
            "address": self.address,
        }

    def to_data(self) -> dict:
        return {"name": self.name, "capacity": self.capacity, "address": self.address}


class Performance:
    def __init__(
        self,
        kind: str,
        title: str,
        venue: Venue,
        start: datetime,
        duration_minutes: int,
        description: str = "",
        *,
        artist: Artist | None = None,
        min_age: int = 0,
        host: Artist | None = None,
        acts: list[Artist] | None = None,
        teacher: Artist | None = None,
        max_participants: int | None = None,
        participants: list[str] | None = None,
    ) -> None:
        if kind not in KINDS:
            raise ValueError(f"{kind!r} is not a kind of performance.")
        title = title.strip()
        if not title:
            raise ValueError("A performance needs a title.")
        if not 1 <= duration_minutes <= 360:
            raise ValueError(
                f"A performance lasts from 1 to 360 minutes, not {duration_minutes}."
            )
        self.kind = kind
        self.title = title
        self.venue = venue
        self.start = start
        self.duration_minutes = duration_minutes
        self.description = description
        self.artist = artist
        self.min_age = min_age
        self.host = host
        self.acts = acts or []
        self.teacher = teacher
        self.max_participants = max_participants
        self.participants = participants or []

    def __lt__(self, other: "Performance") -> bool:
        """sorted() orders performance by start, then venue name"""
        return (self.start, self.venue.name) < (other.start, other.venue.name)

    def __str__(self) -> str:
        """'10:30-12:30 | La cabane | Improv for begineers (workshop)'."""
        return (
            f"{self.start:%H:%M}-{self.end:%H:%M} | {self.venue.name} | "
            f"{self.title} ({self.kind})"
        )

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.duration_minutes)

    @property
    def festival_day(self) -> date:
        """The festival day: the date of the start, moved back 6 hours."""
        return (self.start - DAY_CHANGE).date()

    @property
    def id(self) -> str:
        """'le-kiosque-2027-06-12-0100': the venue slug and the start."""
        return f"{self.venue.slug}-{self.start:%Y-%m-%d-%H%M}"

    @property
    def artists(self) -> list[Artist]:
        """Everyone on stage, in order of appearance."""
        if self.kind == "solo":
            return [self.artist]
        if self.kind == "lineup":
            return [self.host] + self.acts
        return [self.teacher]

    @property
    def capacity(self) -> int:
        """Seats of the venue, or places for a workshop."""
        if self.kind == "workshop":
            return min(self.max_participants, self.venue.capacity)
        return self.venue.capacity

    @property
    def places_left(self) -> int:
        return self.capacity - len(self.participants)

    @property
    def summary(self) -> str:
        """One line for the programme."""
        if self.kind == "solo":
            age = f", {self.min_age}+" if self.min_age else ""
            return f"{self.artist.name}{age}"
        if self.kind == "lineup":
            acts = ", ".join(act.name for act in self.acts)
            return f"hosted by {self.host.name}, with {acts}"
        return f"with {self.teacher.name}, {self.places_left} place(s) left"

    def role_of(self, artist: Artist) -> str | None:
        """'solo', 'host', 'act', 'teacher', or None if the artist is not on stage."""
        if self.kind == "solo" and self.artist == artist:
            return "solo"
        if self.kind == "lineup":
            if self.host == artist:
                return "host"
            if artist in self.acts:
                return "act"
        if self.kind == "workshop" and self.teacher == artist:
            return "teacher"
        return None

    def involves(self, artist: Artist) -> bool:
        return self.role_of(artist) is not None

    def is_on_stage(self, at: datetime) -> bool:
        return self.start <= at < self.end

    def too_close(self, other: "Performance") -> bool:
        """True when less than GAP separates the two performances."""
        return self.start < other.end + GAP and other.start < self.end + GAP

    def to_view(self) -> dict:
        """The Performance object of API.md, computed fields included."""
        view = {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue.slug,
            "venue_name": self.venue.name,
            "start": self.start.isoformat(timespec="minutes"),
            "end": self.end.isoformat(timespec="minutes"),
            "duration_minutes": self.duration_minutes,
            "festival_day": self.festival_day.isoformat(),
            "description": self.description,
            "summary": self.summary,
            "capacity": self.capacity,
            "artists": [{"slug": a.slug, "name": a.name} for a in self.artists],
        }
        if self.kind == "solo":
            view |= {"artist": self.artist.slug, "min_age": self.min_age}
        elif self.kind == "lineup":
            view |= {"host": self.host.slug, "acts": [a.slug for a in self.acts]}
        else:
            view |= {
                "teacher": self.teacher.slug,
                "max_participants": self.max_participants,
                "participants": self.participants,
                "places_left": self.places_left,
            }
        return view

    def to_data(self) -> dict:
        """The performance as written in the data file: slugs, no computed field."""
        data = {
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue.slug,
            "start": self.start.isoformat(timespec="minutes"),
            "duration_minutes": self.duration_minutes,
            "description": self.description,
        }
        if self.kind == "solo":
            data |= {"artist": self.artist.slug, "min_age": self.min_age}
        elif self.kind == "lineup":
            data |= {"host": self.host.slug, "acts": [a.slug for a in self.acts]}
        else:
            data |= {
                "teacher": self.teacher.slug,
                "max_participants": self.max_participants,
                "participants": self.participants,
            }
        return data


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


class Festival:
    """Venues, artists and the schedule. The methods are the only way in."""

    def __init__(self, name: str, first_day: date, last_day: date) -> None:
        name = name.strip()
        if not name:
            raise ValueError("The festival needs a name.")
        if last_day < first_day:
            raise ValueError(f"The festival cannot end ({last_day}) before it starts")
        self.name = name
        self.first_day = first_day
        self.last_day = last_day
        self._venues: list[Venue] = []
        self._artists: list[Artist] = []
        self._performances: list[Performance] = []

    @property
    def days(self) -> list[date]:
        """Every day from the first to the last included"""
        count = (self.last_day - self.first_day).days + 1
        return [self.first_day + timedelta(days=n) for n in range(count)]

    @property
    def venues(self) -> list[Venue]:
        """In the otder they were added."""
        return list(self._venues)

    @property
    def artists(self) -> list[Artist]:
        """Alphabetical order of a slug"""
        return sorted(self._artists, key=lambda artist: artist.slug)

    @property
    def performances(self) -> list[Performance]:
        """Programme order: start, then venue name (Performance.__lt__)."""
        return sorted(self._performances)

    def venue(self, slug: str) -> Venue:
        for venue in self._venues:
            if venue.slug == slug:
                return venue
        raise ValueError(f"No venue {slug!r}.")

    def artist(self, slug: str) -> Artist:
        for artist in self._artists:
            if artist.slug == slug:
                return artist
        raise ValueError(f"No artist {slug!r}.")

    def performance(self, id: str) -> Performance:
        for performance in self._performances:
            if performance.id == id:
                return performance
        raise ValueError(f"No performance {id!r}. ")

    def programme(
        self, day: date | None = None, venue: Venue | None = None
    ) -> list[Performance]:
        """The performances, in order, of one day and/or one venue"""
        result = []
        for performance in self._performances:
            if day is not None and performance.festival_day != day:
                continue
            if venue is not None and performance.venue != venue:
                continue
            result.append(performance)
        return sorted(result)

    def on_stage(self, at: datetime) -> list[Performance]:
        return sorted(p for p in self._performances if p.is_on_stage(at))

    def up_next(self, at: datetime, count: int = 3) -> list[Performance]:
        return sorted(p for p in self._performances if p.start > at)[:count]

    def performances_of(self, artist: Artist) -> list[Performance]:
        return sorted(p for p in self._performances if p.involves(artist))

    def add_venue(self, venue: Venue) -> None:
        if venue in self._venues:
            raise ValueError(f"{venue.name} already exists.")
        self._venues.append(venue)

    def add_artist(self, artist: Artist) -> None:
        if artist in self._artists:
            raise ValueError(f"{artist.name} already exists.")
        self._artists.append(artist)

    def make_performance(self, data: dict) -> Performance:
        """A Performance from a dict (file row or form): slugs become objects."""
        kind = data["kind"]
        people = {}
        if kind == "solo":
            people = {
                "artist": self.artist(data["artist"]),
                "min_age": data.get("min_age", 0),
            }
        elif kind == "lineup":
            people = {
                "host": self.artist(data["host"]),
                "acts": [self.artist(slug) for slug in data["acts"]],
            }
        elif kind == "workshop":
            people = {
                "teacher": self.artist(data["teacher"]),
                "max_participants": data["max_participants"],
                "participants": list(data.get("participants", [])),
            }
        return Performance(
            kind,
            data["title"],
            self.venue(data["venue"]),
            datetime.fromisoformat(data["start"]),
            data["duration_minutes"],
            data.get("description", ""),
            **people,
        )

    def check(self, new: Performance) -> None:
        """Raise ValueError, with a sentence for the organiser, if `new` breaks a rule."""
        if new.venue not in self._venues:
            raise ValueError(f"No venue {new.venue.slug!r}.")
        for artist in new.artists:
            if artist not in self._artists:
                raise ValueError(f"No artist {artist.slug!r}.")
        if not self.first_day <= new.festival_day <= self.last_day:
            raise ValueError(f"{new.festival_day} is not a day of the festival.")
        for other in self._performances:
            if other is new or not new.too_close(other):
                continue
            if other.venue == new.venue:
                raise ValueError(
                    f"{new.venue.name} is busy with {other.title} "
                    f"({other.start:%Y-%m-%d %H:%M}-{other.end:%H:%M})."
                )
            for artist in new.artists:
                if other.involves(artist):
                    raise ValueError(f"{artist.name} is on stage in {other.title}.")

    def schedule(self, new: Performance) -> None:
        self.check(new)  # if it raises, nothing is added
        self._performances.append(new)

    def cancel(self, id: str) -> Performance:
        performance = self.performance(id)
        self._performances.remove(performance)
        return performance

    # -- the shape of the file --------------------------------------------------

    def to_data(self) -> dict:
        return {
            "name": self.name,
            "first_day": self.first_day.isoformat(),
            "last_day": self.last_day.isoformat(),
            "venues": [venue.to_data() for venue in self._venues],
            "artists": [artist.to_data() for artist in self._artists],
            "performances": [p.to_data() for p in self._performances],
        }


# --- Reading and writing the data ------------------------------------------


def load_festival(path: str = DATA_FILE) -> dict:
    """The file as objects. After this, nobody touches the dicts of the file."""
    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        raise ValueError(f"{path} is not found") from None
    except json.JSONDecodeError as error:
        raise ValueError(
            f"{path} is damaged: {error.msg} at line {error.lineno}, column {error.colno}"
        ) from None
    festival = Festival(
        data["name"],
        date.fromisoformat(data["first_day"]),
        date.fromisoformat(data["last_day"]),
    )
    for row in data["venues"]:
        festival.add_venue(Venue(**row))
    for row in data["artists"]:
        festival.add_artist(Artist(**row))
    for row in data["performances"]:
        festival.schedule(festival.make_performance(row))
    return festival


def save_festival(festival: Festival, path: str = DATA_FILE) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(festival.to_data(), file, indent=2, ensure_ascii=False)
        file.write("\n")
