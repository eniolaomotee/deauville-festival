from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .errors import (
    ConflictError,
    FestivalError,
    InvalidError,
    NotFoundError,
    StorageError,
)
from .model import Artist
from .storage import JsonStorage, Storage

STATUS = {NotFoundError: 404, ConflictError: 409, InvalidError: 422, StorageError: 500}


# Base Models
class ArtistIn(BaseModel):
    name: str
    bio: str = ""
    photo_url: str = ""


class PerformanceIn(BaseModel):
    """A performance body: the saved fields only. Each kind uses its own."""

    kind: str
    title: str
    venue: str
    start: datetime
    duration_minutes: int
    description: str = ""
    artist: str | None = None
    min_age: int | None = None
    host: str | None = None
    acts: list[str] | None = None
    teacher: str | None = None
    max_participants: int | None = None
    participants: list[str] | None = None

    def as_data(self) -> dict:
        """The dict the festival builds a performance from: no None fields."""
        return self.model_dump(exclude_none=True)


class ParticipantIn(BaseModel):
    name: str


def festival_error(request: Request, error: FestivalError) -> JSONResponse:
    status = STATUS.get(type(error), 400)
    return JSONResponse(status_code=status, content={"detail": str(error)})


def create_app(storage: Storage, web: Path = Path("web")) -> FastAPI:
    """tHE api over one storage, tests pass a memorystorage; the command a json file"""
    app = FastAPI(title="Deauville Festival du Rire")
    app.add_exception_handler(FestivalError, festival_error)

    @app.get("/api/festival")
    def read_festival() -> dict:
        festival = storage.load()
        return {
            "name": festival.name,
            "first_day": festival.first_day.isoformat(),
            "last_day": festival.last_day.isoformat(),
            "days": [day.isoformat() for day in festival.days],
        }

    @app.get("/api/venues")
    def list_venues() -> list[dict]:
        return [venue.to_view() for venue in storage.load().venues]

    @app.get("/api/artists")
    def list_artists() -> list[dict]:
        return [artist.to_view() for artist in storage.load().artists]

    @app.get("/api/artists/{slug}")
    def read_artist(slug: str) -> dict:
        festival = storage.load()
        artist = festival.artist(slug)
        view = artist.to_view()
        view["performances"] = [p.to_view() for p in festival.performances_of(artist)]
        return view

    @app.get("/api/programme")
    def read_programme(day: date | None = None, venue: str | None = None) -> list[dict]:
        festival = storage.load()
        where = None
        if venue is not None:
            where = festival.venue(venue)
        return [p.to_view() for p in festival.programme(day, where)]

    @app.get("/api/performances/{id}")
    def read_performance(id: str) -> dict:
        return storage.load().performance(id).to_view()

    @app.get("/api/now")
    def read_now(at: datetime | None = None) -> dict:
        festival = storage.load()
        if at is None:
            at = datetime.now()
        return {
            "at": at.isoformat(timespec="minutes"),
            "now_playing": [p.to_view() for p in festival.on_stage(at)],
            "up_next": [p.to_view() for p in festival.up_next(at)],
        }

    @app.post("/api/artists", status_code=201)
    def create_artist(body: ArtistIn) -> dict:
        festival = storage.load()
        artist = Artist(**body.model_dump())
        festival.add_artist(artist)
        storage.save(festival)
        return artist.to_view()

    @app.post("/api/performances", status_code=201)
    def create_performance(body: PerformanceIn) -> dict:
        festival = storage.load()
        new = festival.make_performance(body.as_data())
        festival.schedule(new)
        storage.save(festival)
        return new.to_view()

    @app.put("/api/performances/{id}")
    def replace_performance(id: str, body: PerformanceIn) -> dict:
        festival = storage.load()
        new = festival.replace(id, body.as_data())
        storage.save(festival)
        return new.to_view()

    @app.delete("/api/performances/{id}", status_code=204)
    def delete_performance(id: str) -> Response:
        festival = storage.load()
        festival.cancel(id)
        storage.save(festival)
        return Response(status_code=204)

    @app.post("/api/performances/{id}/participants", status_code=201)
    def register_participant(id: str, body: ParticipantIn) -> dict:
        festival = storage.load()
        workshop = festival.register(id, body.name)
        storage.save(festival)
        return workshop.to_view()

    if (web / "admin").is_dir():
        app.mount("/admin", StaticFiles(directory="web/admin", html=True), name="admin")
    if (web / "public").is_dir():
        app.mount("/", StaticFiles(directory="web/public", html=True), name="public")
    return app


# The app uvicorn finds: the JSON file next to the working directory.
app = create_app(JsonStorage())
