import shutil

import pytest
from fastapi.testclient import TestClient

from deauville.api import create_app
from deauville.storage import JsonStorage


@pytest.fixture
def data_file(tmp_path):
    """A fresh copy of data/festival.json for each test."""
    path = tmp_path / "festival.json"
    shutil.copy("data/festival.json", path)
    return path


@pytest.fixture
def client(data_file, tmp_path) -> TestClient:
    return TestClient(create_app(JsonStorage(data_file), web=tmp_path))


def tmp_path_without_web():
    """No static files in tests: only the API."""
    from pathlib import Path

    return Path("/nonexistent")


SOLO = {
    "kind": "solo",
    "title": "Nora Live",
    "venue": "le-kiosque",
    "start": "2027-06-13T11:00",
    "duration_minutes": 45,
    "artist": "nora-lebrun",
    "min_age": 0,
}


def performance_body(**changes) -> dict:
    """A solo body like the admin sends, with some fields changed"""
    return SOLO | changes


def reopen(data_file) -> TestClient:
    """A second client on the same file: what the first one saved."""
    return TestClient(create_app(JsonStorage(data_file), web=data_file.parent))


def test_create_artist(client, data_file):
    response = client.post("/api/artists", json={"name": "Zoé Tanguy"})
    assert response.status_code == 201
    assert response.json()["slug"] == "zoe-tanguy"
    assert reopen(data_file).get("/api/artists/zoe-tanguy").status_code == 200  # saved


def test_create_performance_is_saved(client, data_file):
    response = client.post("/api/performances", json=SOLO)
    assert response.status_code == 201
    assert response.json()["id"] == "le-kiosque-2027-06-13-1100"
    sunday = reopen(data_file).get("/api/programme?day=2027-06-13").json()
    assert "Nora Live" in [p["title"] for p in sunday]


def test_put_moves_and_changes_the_id(client):
    client.post("/api/performances", json=SOLO)
    response = client.put(
        "/api/performances/le-kiosque-2027-06-13-1100",
        json=performance_body(start="2027-06-13T12:00"),
    )
    assert response.status_code == 200
    assert response.json()["id"] == "le-kiosque-2027-06-13-1200"
    assert client.get("/api/performances/le-kiosque-2027-06-13-1100").status_code == 404


def test_put_refused_changes_nothing(client):
    client.post("/api/performances", json=SOLO)
    before = client.get("/api/programme").json()
    response = client.put(
        "/api/performances/le-kiosque-2027-06-13-1100",
        json=performance_body(start="2027-06-13T15:00"),
    )
    assert response.status_code == 409
    assert "Le Kiosque is busy with First Time Here" in response.json()["detail"]
    assert client.get("/api/programme").json() == before


def test_delete_twice(client):
    assert (
        client.delete("/api/performances/le-kiosque-2027-06-12-0100").status_code == 204
    )
    assert (
        client.delete("/api/performances/le-kiosque-2027-06-12-0100").status_code == 404
    )
    assert len(client.get("/api/programme").json()) == 22


def test_register_participants_until_full(client):
    # Stand-up Lab, 10 places, 4 taken
    url = "/api/performances/la-cabane-2027-06-12-1030/participants"
    response = client.post(url, json={"name": "Zoé D."})
    assert response.status_code == 201 and response.json()["places_left"] == 5
    assert client.post(url, json={"name": "zoé d."}).status_code == 409
    for n in range(5):
        assert client.post(url, json={"name": f"Guest {n}"}).status_code == 201
    response = client.post(url, json={"name": "One Too Many"})
    assert response.status_code == 409 and "is full" in response.json()["detail"]


def test_404_unknown_artist_venue_performance(client):
    for url in (
        "/api/artists/nobody",
        "/api/programme?venue=nowhere",
        "/api/performances/nope",
    ):
        response = client.get(url)
        assert response.status_code == 404
        assert response.json()["detail"].startswith("No ")


def test_409_conflicts(client):
    busy_venue = performance_body(start="2027-06-12T02:15", artist="karim-benali")
    assert (
        "is busy with After Hours"
        in client.post("/api/performances", json=busy_venue).json()["detail"]
    )
    busy_artist = performance_body(
        venue="la-cabane", start="2027-06-11T23:00", artist="max-pellerin"
    )
    assert (
        "Max Pellerin is on stage"
        in client.post("/api/performances", json=busy_artist).json()["detail"]
    )
    outside = performance_body(start="2027-06-14T08:00")
    assert client.post("/api/performances", json=outside).status_code == 409
    assert client.post("/api/artists", json={"name": "nora lebrun"}).status_code == 409


def test_422_invalid_values(client):
    assert client.post("/api/artists", json={"name": "   "}).status_code == 422
    assert (
        client.post(
            "/api/performances", json=performance_body(duration_minutes=0)
        ).status_code
        == 422
    )
    assert (
        client.post("/api/performances", json=performance_body(min_age=19)).status_code
        == 422
    )
    one_act = performance_body(
        kind="lineup",
        host="paul-kerbrat",
        acts=["nora-lebrun"],
        venue="grand-casino",
        start="2027-06-12T10:00",
    )
    assert (
        "at least two acts"
        in client.post("/api/performances", json=one_act).json()["detail"]
    )
    assert (
        client.post(
            "/api/performances", json=performance_body(kind="opera")
        ).status_code
        == 422
    )
    not_a_workshop = client.post(
        "/api/performances/le-kiosque-2027-06-12-0100/participants", json={"name": "X"}
    )
    assert (
        not_a_workshop.status_code == 422
        and "not a workshop" in not_a_workshop.json()["detail"]
    )


def test_422_wrong_shape_is_fastapis(client):
    response = client.post("/api/performances", json={"kind": "solo", "title": "X"})
    assert response.status_code == 422
    assert isinstance(
        response.json()["detail"], list
    )  # a list of problems, not a sentence
    assert (
        client.post(
            "/api/performances", json=performance_body(start="June 13")
        ).status_code
        == 422
    )
    assert client.get("/api/programme?day=June%2011").status_code == 422


def test_500_when_the_file_is_damaged(client, data_file):
    data_file.write_text("[{", encoding="utf-8")
    response = client.get("/api/venues")
    assert response.status_code == 500
    assert "is damaged" in response.json()["detail"]


def test_festival(client):
    response = client.get("/api/festival")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Deauville Festival du Rire 2027"
    assert body["days"] == ["2027-06-10", "2027-06-11", "2027-06-12", "2027-06-13"]


def test_venues_in_file_order(client):
    slugs = [v["slug"] for v in client.get("/api/venues").json()]
    assert slugs == ["grand-casino", "theatre-des-planches", "le-kiosque", "la-cabane"]


def test_artists_in_slug_order(client):
    artists = client.get("/api/artists").json()
    assert len(artists) == 12
    assert artists[0]["slug"] == "elodie-marchal"
    assert set(artists[0]) == {"slug", "name", "bio", "photo_url"}


def test_one_artist_with_performances(client):
    body = client.get("/api/artists/max-pellerin").json()
    assert [p["title"] for p in body["performances"]] == [
        "Opening Gala",
        "Late Laughs",
        "Deauville Comedy Club",
        "Closing Gala",
    ]


def test_programme_filters(client):
    assert len(client.get("/api/programme").json()) == 23
    friday = client.get("/api/programme?day=2027-06-11").json()
    assert friday[-1]["title"] == "After Hours"  # 01:00 belongs to Friday
    assert len(client.get("/api/programme?venue=le-kiosque").json()) == 7
    both = client.get("/api/programme?day=2027-06-13&venue=grand-casino").json()
    assert [p["title"] for p in both] == ["Closing Gala"]


def test_one_performance_has_every_field_of_the_contract(client):
    body = client.get("/api/performances/le-kiosque-2027-06-12-0100").json()
    common = {
        "id",
        "kind",
        "title",
        "venue",
        "venue_name",
        "start",
        "end",
        "duration_minutes",
        "festival_day",
        "description",
        "summary",
        "capacity",
        "artists",
    }
    assert common <= set(body)
    assert body["end"] == "2027-06-12T02:00" and body["festival_day"] == "2027-06-11"
    assert body["host"] == "tom-vasseur" and body["acts"] == [
        "hugo-lemaire",
        "maya-choukri",
    ]
    workshop = client.get("/api/performances/la-cabane-2027-06-11-1030").json()
    assert workshop["places_left"] == 9 and workshop["capacity"] == 12


def test_now(client):
    body = client.get("/api/now?at=2027-06-11T21:00").json()
    assert body["at"] == "2027-06-11T21:00"
    assert [p["title"] for p in body["now_playing"]] == ["Tall Tales"]
    assert [p["title"] for p in body["up_next"]] == [
        "Straight Face",
        "Late Laughs",
        "After Hours",
    ]
