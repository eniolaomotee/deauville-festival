"""The festival: data, rules and questions. No printing here."""

import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from .errors import ConflictError, InvalidError

if TYPE_CHECKING:
    from .festival import Festival

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
            raise InvalidError("An artist needs a name.")

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
            raise InvalidError("A venue needs a name.")
        if self.capacity < 1:
            raise InvalidError(f"{self.name} needs at least one seat.")

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
            raise InvalidError("A performance needs a title.")
        if not 1 <= duration_minutes <= 360:
            raise InvalidError(
                f"A performance lasts from 1 to 360 minutes, not {duration_minutes}."
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
            parse_start(data["start"]),
            data["duration_minutes"],
            data.get("description", ""),
            **cls.own_args(festival, data),
        )


class SoloShow(Performance):
    kind = "solo"

    def __init__(self, *common, artist: Artist, min_age: int = 0, **rest) -> None:
        super().__init__(*common, **rest)
        if not 0 <= min_age <= 18:
            raise InvalidError(f"The minimum age goes from 0 to 18, not {min_age}.")
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
            raise InvalidError("A lineup needs at least two acts.")
        if len(set(acts)) != len(acts):
            raise InvalidError("An act cannot appear twice in a lineup.")
        if host in acts:
            raise InvalidError(f"{host.name} hosts this lineup and cannot be an act.")
        shortest = (
            len(acts) * self.MINUTES_PER_ACT + (len(acts) - 1) * self.MINUTES_FOR_HOST
        )
        if self.duration_minutes < shortest:
            raise InvalidError(
                f"{len(acts)} acts need at least {shortest} minutes, "
                f"not {self.duration_minutes}."
            )
        self.host = host
        self._acts = list(acts)

    @property
    def acts(self) -> list[Artist]:
        "A copy: the lineup changes only through it's methods"
        return list(self._acts)

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
            raise InvalidError("A workshop needs at least one place.")
        self.teacher = teacher
        self.max_participants = max_participants
        self._participants: list[str] = []
        for name in participants or []:
            self.register(name)

    @property
    def participants(self) -> list[str]:
        "A copy: register() is the only way in."
        return list(self._participants)

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
            raise InvalidError("A participant needs a name.")
        if name.lower() in (other.lower() for other in self._participants):
            raise ConflictError(f"{name} is already registered in {self.title}.")
        if self.places_left < 1:
            raise ConflictError(f"{self.title} is full ({self.capacity} places).")
        self._participants.append(name)

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


def parse_start(value: str | datetime) -> datetime:
    """'2027-06-12T01:00' -> datetime; a datetime passes through."""
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise InvalidError(
            f"{value!r} is not a date and time, use YYYY-MM-DDTHH:MM."
        ) from None


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
