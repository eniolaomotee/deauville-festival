"""The festival: data, rules and questions. No printing here."""

import json
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta

DATA_FILE = "data/festival.json"
DAY_CHANGE = timedelta(hours=6)
GAP = timedelta(minutes=30)


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


class Performance(ABC):
    "What every performance shares. Performance itself cannot be created."

    kind = "performance"

    def __init__(
        self,
        title: str,
        venue: Venue,
        start: datetime,
        duration_minutes: int,
        description: str = "",
    ) -> None:
        title = title.strip()
        if not title:
            raise ValueError("A performance needs a title")
        if not 1 <= duration_minutes <= 360:
            raise ValueError(
                f"A perfromance lasts from 1 to 360 minutes, not {duration_minutes}."
            )
        self.title = title
        self.venue = venue
        self.start = start
        self.duration_minutes = duration_minutes
        self.description = description

    @property
    @abstractmethod
    def artists(self) -> list[Artist]:
        """Everyone on stage, in order of appearance."""

    @property
    @abstractmethod
    def summary(self) -> str:
        """One line for the programme."""

    @abstractmethod
    def role_of(self, artist: Artist) -> str | None:
        """'solo', 'host', 'act', 'teacher', or None if the artist is not on stage."""

    @abstractmethod
    def own_view(self) -> dict:
        """The fields of this kind in API.md."""

    @abstractmethod
    def own_data(self) -> dict:
        """The fields of this kind in the data file."""

    @classmethod
    @abstractmethod
    def own_args(cls, festival: "Festival", data: dict) -> dict:
        """The kind's own arguments, slugs turned into objects."""

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
    def capacity(self) -> int:
        """Seats of the venue; a workshop says otherwise."""
        return self.venue.capacity

    def involves(self, artist: Artist) -> bool:
        return self.role_of(artist) is not None

    def is_on_stage(self, at: datetime) -> bool:
        return self.start <= at < self.end

    def too_close(self, other: "Performance") -> bool:
        """True when less than GAP separates the two performances."""
        return self.start < other.end + GAP and other.start < self.end + GAP

    def __lt__(self, other: "Performance") -> bool:
        """sorted() orders performances by start, then venue name."""
        return (self.start, self.venue.name) < (other.start, other.venue.name)

    def __str__(self) -> str:
        """'10:30-12:30 | La Cabane | Improv for Beginners (workshop)'."""
        return (
            f"{self.start:%H:%M}-{self.end:%H:%M} | {self.venue.name} | "
            f"{self.title} ({self.kind})"
        )

    def to_view(self) -> dict:
        """The Performance object of API.md: common fields, then the kind's own."""
        return {
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
        } | self.own_view()

    def to_data(self) -> dict:
        """As written in the data file: slugs, no computed field."""
        return {
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue.slug,
            "start": self.start.isoformat(timespec="minutes"),
            "duration_minutes": self.duration_minutes,
            "description": self.description,
        } | self.own_data()

    @classmethod
    def from_data(cls, festival: "Festival", data: dict) -> "Performance":
        """Build this kind from a dict of the file or of a form."""
        return cls(
            data["title"],
            festival.venue(data["venue"]),
            datetime.fromisoformat(data["start"]),
            data["duration_minutes"],
            data.get("description", ""),
            **cls.own_args(festival, data),
        )


class SoloShow(Performance):
    kind = "solo"

    def __init__(self, *common, artist: Artist, min_age: int = 0, **rest) -> None:
        super().__init__(*common, **rest)
        if not 0 <= min_age <= 18:
            raise ValueError(f"The minimum age goes from 0 to 18, not {min_age}")
        self.artist = artist
        self.min_age = min_age

    @property
    def artists(self) -> list[Artist]:
        return [self.artist]

    @property
    def summary(self) -> str:
        return self.artist.name

    def role_of(self, artist: Artist) -> str | None:
        return "solo" if artist == self.artist else None

    def own_view(self) -> dict:
        return {"artist": self.artist.slug, "min_age": self.min_age}

    def own_data(self) -> dict:
        return self.own_view()

    @classmethod
    def own_args(cls, festival: "Festival", data: dict) -> dict:
        return {
            "artist": festival.artist(data["artist"]),
            "min_age": data.get("min_age", 0),
        }


class Lineup(Performance):
    kind = "lineup"

    MINUTES_PER_ACT = 10
    MINUTES_FOR_HOST = 3

    def __init__(self, *common, host: Artist, acts: list[Artist], **rest) -> None:
        super().__init__(*common, **rest)
        if len(acts) < 2:
            raise ValueError("A lineup needs at least two acts.")
        if len(set(acts)) != len(acts):
            raise ValueError("An act cannot appear twice in a lineup.")
        if host in acts:
            raise ValueError(f"{host.name} hosts this lineup and cannot be an act.")
        shortest = (
            len(acts) * self.MINUTES_PER_ACT + (len(acts) - 1) * self.MINUTES_FOR_HOST
        )
        if self.duration_minutes < shortest:
            raise ValueError(
                f"{len(acts)} acts need at least {shortest} minutes, "
                f"not {self.duration_minutes}."
            )
        self.host = host
        self.acts = list(acts)

    @property
    def artists(self) -> list[Artist]:
        return [self.host] + self.acts

    @property
    def summary(self) -> str:
        names = ", ".join(act.name for act in self.acts)
        return f"hosted by {self.host.name}, with {names}"

    def role_of(self, artist: Artist) -> str | None:
        if artist == self.host:
            return "host"
        if artist in self.acts:
            return "act"
        return None

    def own_view(self) -> dict:
        return {"host": self.host.slug, "acts": [act.slug for act in self.acts]}

    def own_data(self) -> dict:
        return self.own_view()

    @classmethod
    def own_args(cls, festival: "Festival", data: dict) -> dict:
        return {
            "host": festival.artist(data["host"]),
            "acts": [festival.artist(slug) for slug in data["acts"]],
        }


class Workshop(Performance):
    kind = "workshop"

    def __init__(
        self,
        *common,
        teacher: Artist,
        max_participants: int,
        participants: list[str] | None = None,
        **rest,
    ) -> None:
        super().__init__(*common, **rest)
        if max_participants < 1:
            raise ValueError("A workshop needs at least one place.")
        self.teacher = teacher
        self.max_participants = max_participants
        self.participants: list[str] = []
        for name in participants or []:
            self.register(name)

    @property
    def capacity(self) -> int:
        """Places: the smaller of max_participants and the venue's seats."""
        return min(self.max_participants, self.venue.capacity)

    @property
    def places_left(self) -> int:
        return self.capacity - len(self.participants)

    @property
    def artists(self) -> list[Artist]:
        return [self.teacher]

    @property
    def summary(self) -> str:
        taken = len(self.participants)
        return f"with {self.teacher.name}, {taken}/{self.capacity} places taken"

    def role_of(self, artist: Artist) -> str | None:
        return "teacher" if artist == self.teacher else None

    def register(self, name: str) -> None:
        """Add a participant by name, until the workshop is full."""
        name = name.strip()
        if not name:
            raise ValueError("A participant needs a name.")
        if name.lower() in (other.lower() for other in self.participants):
            raise ValueError(f"{name} is already registered in {self.title}.")
        if self.places_left < 1:
            raise ValueError(f"{self.title} is full ({self.capacity} places).")
        self.participants.append(name)

    def own_view(self) -> dict:
        return self.own_data() | {"places_left": self.places_left}

    def own_data(self) -> dict:
        return {
            "teacher": self.teacher.slug,
            "max_participants": self.max_participants,
            "participants": list(self.participants),
        }

    @classmethod
    def own_args(cls, festival: "Festival", data: dict) -> dict:
        return {
            "teacher": festival.artist(data["teacher"]),
            "max_participants": data["max_participants"],
            "participants": data.get("participants", []),
        }


# The "kind" field of the file chooses the class: here and nowhere else
PERFORMANCE_KINDS: dict[str, type[Performance]] = {
    cls.kind: cls for cls in (SoloShow, Lineup, Workshop)
}


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
        "A performance from a dict (file row or form): the kind that picks the class"
        kind = data.get("kind")
        if kind not in PERFORMANCE_KINDS:
            raise ValueError(f"{kind!r} is not a kind of performance.")
        return PERFORMANCE_KINDS[kind].from_data(self, data)

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
