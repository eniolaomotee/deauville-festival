from datetime import date, datetime

from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles

from festival import load_festival

app = FastAPI(title="Deauville Festival du Rire")


@app.get("/api/festival")
def read_festival() -> dict:
    festival = load_festival()
    return {
        "name": festival.name,
        "first_day": festival.first_day.isoformat(),
        "last_day": festival.last_day.isoformat(),
        "days": [day.isoformat() for day in festival.days],
    }


@app.get("/api/venues")
def list_venues() -> list[dict]:
    return [venue.to_view() for venue in load_festival().venues]


@app.get("/api/artists")
def list_artists() -> list[dict]:
    return [artist.to_view() for artist in load_festival().artists]


@app.get("/api/artists/{slug}")
def read_artist(slug: str) -> dict:
    festival = load_festival()
    try:
        artist = festival.artist(slug)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    view = artist.to_view()
    view["performances"] = [p.to_view() for p in festival.performances_of(artist)]
    return view


@app.get("/api/programme")
def read_programme(day: date | None = None, venue: str | None = None) -> list[dict]:
    festival = load_festival()
    where = None
    if venue is not None:
        try:
            where = festival.venue(venue)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from None
    return [p.to_view() for p in festival.programme(day, where)]


@app.get("/api/performances/{id}")
def read_performance(id: str) -> dict:
    try:
        return load_festival().performance(id).to_view()
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None


@app.get("/api/now")
def read_now(at: datetime | None = None) -> dict:
    festival = load_festival()
    if at is None:
        at = datetime.now()
    return {
        "at": at.isoformat(timespec="minutes"),
        "now_playing": [p.to_view() for p in festival.on_stage(at)],
        "up_next": [p.to_view() for p in festival.up_next(at)],
    }


app.mount("/", StaticFiles(directory="web/public", html=True), name="public")
