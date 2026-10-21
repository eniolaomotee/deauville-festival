"""The festival: holds venues, artists and the schedule. Every change goes through it."""

from datetime import date, datetime, timedelta

from .errors import ConflictError, InvalidError, NotFoundError
from .model import PERFORMANCE_KINDS, Artist, Performance, Venue, Workshop


class Festival:
    """Venues, artists and the schedule. The methods are the only way in."""

    def __init__(self, name: str, first_day: date, last_day: date) -> None:
        name = name.strip()
        if not name:
            raise InvalidError("The festival needs a name.")
        if last_day < first_day:
            raise InvalidError(f"The festival cannot end ({last_day}) before it starts")
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
        raise NotFoundError(f"No venue {slug!r}.")

    def artist(self, slug: str) -> Artist:
        for artist in self._artists:
            if artist.slug == slug:
                return artist
        raise NotFoundError(f"No artist {slug!r}.")

    def performance(self, id: str) -> Performance:
        for performance in self._performances:
            if performance.id == id:
                return performance
        raise NotFoundError(f"No performance {id!r}.")

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
            raise ConflictError(f"{venue.name} already exists.")
        self._venues.append(venue)

    def add_artist(self, artist: Artist) -> None:
        if artist in self._artists:
            raise ConflictError(f"{artist.name} already exists.")
        self._artists.append(artist)

    def make_performance(self, data: dict) -> Performance:
        "A performance from a dict (file row or form): the kind that picks the class"
        kind = data.get("kind")
        if kind not in PERFORMANCE_KINDS:
            raise InvalidError(f"{kind!r} is not a kind of performance.")
        return PERFORMANCE_KINDS[kind].from_data(self, data)

    def check(self, new: Performance, ignoring: Performance | None = None) -> None:
        """
        Raise a Festival error with a sentence for the organiser if 'new' breaks
        a rule, 'ignoring' is the performance that 'new' replaces: it does not count as busy.
        """
        if new.venue not in self._venues:
            raise NotFoundError(f"No venue {new.venue.slug!r}.")
        for artist in new.artists:
            if artist not in self._artists:
                raise NotFoundError(f"No artist {artist.slug!r}.")
        if not self.first_day <= new.festival_day <= self.last_day:
            raise ConflictError(f"{new.festival_day} is not a day of the festival.")
        for other in self._performances:
            if other is ignoring or not new.too_close(other):
                continue
            if other.venue == new.venue:
                raise ConflictError(
                    f"{new.venue.name} is busy with {other.title} "
                    f"({other.start:%Y-%m-%d %H:%M}-{other.end:%H:%M})."
                )
            for artist in new.artists:
                if other.involves(artist):
                    raise ConflictError(f"{artist.name} is on stage in {other.title}.")

    def replace(self, id: str, data: dict) -> Performance:
        """Move or edit a performance. If the new version breaks a rule, nothing changes."""
        old = self.performance(id)
        new = self.make_performance(data)
        self.check(new, ignoring=old)  # raises before anything is touched
        self._performances.remove(old)
        self._performances.append(new)
        return new

    def register(self, id: str, name: str) -> Workshop:
        """Register a participant in a workshop."""
        performance = self.performance(id)
        if not isinstance(performance, Workshop):
            raise InvalidError(f"{performance.title} is not a workshop.")
        performance.register(name)
        return performance

    def schedule(self, new: Performance) -> None:
        self.check(new)  # if it raises, nothing is added
        self._performances.append(new)

    def cancel(self, id: str) -> Performance:
        performance = self.performance(id)
        self._performances.remove(performance)
        return performance

    def to_data(self) -> dict:
        return {
            "name": self.name,
            "first_day": self.first_day.isoformat(),
            "last_day": self.last_day.isoformat(),
            "venues": [venue.to_data() for venue in self._venues],
            "artists": [artist.to_data() for artist in self._artists],
            "performances": [p.to_data() for p in self._performances],
        }

    @classmethod
    def from_data(cls, data: dict) -> "Festival":
        """A festival from the dict of the file. Every rule is checked again."""
        festival = cls(
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
