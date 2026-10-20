from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from festival import festival_days, load_festival, slugify

app = FastAPI(title="Deauville Festival du Rire")

# --- Views: the JSON objects of API.md -------------------------------------
# The data file has no slug: the view adds it. Field names are the contract
# the website reads, so they are spelled exactly as in API.md.


def venue_view(venue: dict) -> dict:
    return {
        "slug": slugify(venue["name"]),
        "name": venue["name"],
        "capacity": venue["capacity"],
        "address": venue["address"],
    }


def artist_view(artist: dict) -> dict:
    return {
        "slug": slugify(artist["name"]),
        "name": artist["name"],
        "bio": artist["bio"],
        "photo_url": artist["photo_url"],
    }


# --- Routes: a decorator, a function, and what it returns becomes JSON -------
# Each route loads the file, so a change made from the terminal shows up on
# the next request.

@app.get("/api/festival")
def read_festival() -> dict:
    festival = load_festival()
    return {
        "name": festival["name"],
        "first_day": festival["first_day"],
        "last_day": festival["last_day"],
        "days": [str(day) for day in festival_days(festival)]
    }


@app.get("/api/venues")
def list_venues() -> list[dict]:
    festival = load_festival()
    return [venue_view(venue) for venue in festival["venues"]]



@app.get("/api/artists")
def list_artists() -> list[dict]:
    festival = load_festival()
    artists = sorted(festival["artists"], key=lambda artist: slugify(artist["name"]))
    return [artist_view(artist) for artist in artists]


app.mount("/", StaticFiles(directory="web/public", html=True), name="public")
