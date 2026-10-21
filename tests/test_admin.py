from datetime import date, datetime

import pytest

from deauville.errors import ConflictError, InvalidError, NotFoundError
from deauville.festival import Festival
from deauville.model import Artist, Lineup, SoloShow, Venue, Workshop


@pytest.fixture
def festival() -> Festival:
    festival = Festival("Test festival", date(2027, 6, 10), date(2027, 6, 13))
    festival.add_venue(Venue("Le Kiosque", 120, "Beach"))
    festival.add_venue(Venue("La Cabane", 40, "Beach"))
    for name in ("Nora Lebrun", "Maya Choukri", "Inès Moreau"):
        festival.add_artist(Artist(name))
    festival.schedule(
        SoloShow(
            "Nora Live",
            festival.venue("le-kiosque"),
            datetime(2027, 6, 13, 11, 0),
            45,
            artist=festival.artist("nora-lebrun"),
        )
    )
    festival.schedule(
        SoloShow(
            "Maya Live",
            festival.venue("le-kiosque"),
            datetime(2027, 6, 13, 15, 0),
            60,
            artist=festival.artist("maya-choukri"),
        )
    )
    festival.schedule(
        Workshop(
            "Stand-up Lab",
            festival.venue("la-cabane"),
            datetime(2027, 6, 13, 10, 0),
            120,
            teacher=festival.artist("ines-moreau"),
            max_participants=2,
        )
    )
    return festival


def body(**changes) -> dict:
    """A solo performance body, like the admin sends, with some fields changed."""
    return {
        "kind": "solo",
        "title": "Nora Live",
        "venue": "le-kiosque",
        "start": "2027-06-13T11:00",
        "duration_minutes": 45,
        "artist": "nora-lebrun",
    } | changes


def test_the_schedule_cannot_be_changed_from_outside(festival):
    festival.performances.append("intruder")
    festival.venues.clear()
    festival.artists.clear()
    assert len(festival.performances) == 3
    assert len(festival.venues) == 2 and len(festival.artists) == 3


def test_a_lineup_and_a_workshop_keep_their_lists(festival):
    gala = Lineup(
        "Gala",
        festival.venue("le-kiosque"),
        datetime(2027, 6, 12, 20, 0),
        60,
        host=festival.artist("ines-moreau"),
        acts=[festival.artist("nora-lebrun"), festival.artist("maya-choukri")],
    )
    gala.acts.append(festival.artist("ines-moreau"))
    assert len(gala.acts) == 2
    lab = festival.performance("la-cabane-2027-06-13-1000")
    lab.participants.append("intruder")
    assert lab.participants == []


def test_a_lineup_with_one_act_is_refused_through_the_festival(festival):
    with pytest.raises(InvalidError, match="at least two acts"):
        festival.make_performance(
            body(
                kind="lineup",
                title="Gala",
                start="2027-06-12T20:00",
                duration_minutes=60,
                host="ines-moreau",
                acts=["nora-lebrun"],
            )
        )


def test_a_full_workshop_refuses_the_next_name(festival):
    festival.register("la-cabane-2027-06-13-1000", "Camille R.")
    festival.register("la-cabane-2027-06-13-1000", "Yanis B.")
    with pytest.raises(ConflictError, match="is full"):
        festival.register("la-cabane-2027-06-13-1000", "Lou M.")


def test_the_same_name_cannot_register_twice(festival):
    festival.register("la-cabane-2027-06-13-1000", "Camille R.")
    with pytest.raises(ConflictError, match="already registered"):
        festival.register("la-cabane-2027-06-13-1000", "camille r.")


def test_only_a_workshop_takes_participants(festival):
    with pytest.raises(InvalidError, match="not a workshop"):
        festival.register("le-kiosque-2027-06-13-1100", "Camille R.")


def test_an_artist_with_the_same_slug_already_exists(festival):
    festival.add_artist(Artist("Zoé Tanguy"))
    with pytest.raises(ConflictError, match="already exists"):
        festival.add_artist(Artist("zoe tanguy"))


def test_a_move_changes_the_id(festival):
    moved = festival.replace(
        "le-kiosque-2027-06-13-1100", body(start="2027-06-13T12:00")
    )
    assert moved.id == "le-kiosque-2027-06-13-1200"
    with pytest.raises(NotFoundError):
        festival.performance("le-kiosque-2027-06-13-1100")


def test_a_refused_move_changes_nothing(festival):
    before = [p.id for p in festival.performances]
    with pytest.raises(ConflictError, match="Le Kiosque is busy with Maya Live"):
        festival.replace("le-kiosque-2027-06-13-1100", body(start="2027-06-13T15:00"))
    assert [p.id for p in festival.performances] == before
    assert festival.performance("le-kiosque-2027-06-13-1100").start == datetime(
        2027, 6, 13, 11, 0
    )


def test_the_error_type_says_what_went_wrong(festival):
    with pytest.raises(NotFoundError):
        festival.performance("nope")
    with pytest.raises(ConflictError):
        festival.schedule(
            SoloShow(
                "Clash",
                festival.venue("le-kiosque"),
                datetime(2027, 6, 13, 11, 30),
                30,
                artist=festival.artist("maya-choukri"),
            )
        )
    with pytest.raises(InvalidError):
        SoloShow(
            "",
            festival.venue("le-kiosque"),
            datetime(2027, 6, 13, 18, 0),
            30,
            artist=festival.artist("nora-lebrun"),
        )
