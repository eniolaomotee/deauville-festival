"""each kind of perfomance checks its own rules"""

from datetime import date, datetime

import pytest

from deauville.errors import ConflictError, InvalidError
from deauville.festival import Festival
from deauville.model import Artist, Lineup, Performance, SoloShow, Venue, Workshop
from deauville.storage import JsonStorage


@pytest.fixture
def festival() -> Festival:
    festival = Festival("Test festival", date(2027, 6, 10), date(2027, 6, 13))
    festival.add_venue(Venue("Grand Casino", 650, "Seafront"))
    festival.add_venue(Venue("La Cabane", 40, "Beach"))
    for name in ("Nora Lebrun", "Tom Vasseur", "Hugo Lemaire", "Maya Choukri"):
        festival.add_artist(Artist(name))
    return festival


def lineup(festival, minutes, *acts, host="tom-vasseur") -> Lineup:
    return Lineup(
        "Gala",
        festival.venue("grand-casino"),
        datetime(2027, 6, 11, 20, 0),
        minutes,
        host=festival.artist(host),
        acts=[festival.artist(slug) for slug in acts],
    )


def workshop(festival, places, venue="la-cabane", participants=()) -> Workshop:
    return Workshop(
        "Lab",
        festival.venue(venue),
        datetime(2027, 6, 11, 10, 0),
        120,
        teacher=festival.artist("nora-lebrun"),
        max_participants=places,
        participants=list(participants),
    )


# The group
def test_a_bare_performance_cannot_be_created(festival):
    with pytest.raises(TypeError):
        Performance("X", festival.venue("la-cabane"), datetime(2027, 6, 11, 10, 0), 30)


def test_the_kind_picks_the_class(festival):
    data = {
        "kind": "solo",
        "title": "X",
        "venue": "la-cabane",
        "start": "2027-06-11T10:00",
        "duration_minutes": 30,
        "artist": "nora-lebrun",
    }
    assert isinstance(festival.make_performance(data), SoloShow)
    with pytest.raises(InvalidError, match="not a kind of performance"):
        festival.make_performance(data | {"kind": "opera"})


def test_summaries_from_the_data_file():
    festival = JsonStorage("data/festival.json").load()
    assert festival.performance("le-kiosque-2027-06-12-0100").summary == (
        "hosted by Tom Vasseur, with Hugo Lemaire, Maya Choukri"
    )
    assert festival.performance("la-cabane-2027-06-11-1030").summary == (
        "with Inès Moreau, 3/12 places taken"
    )
    assert (
        festival.performance("grand-casino-2027-06-11-2030").summary == "Léa Fontaine"
    )


# solo
@pytest.mark.parametrize("age", [-1, 19])
def test_minimum_age_goes_from_0_to_18(festival, age):
    with pytest.raises(InvalidError, match="0 to 18"):
        SoloShow(
            "X",
            festival.venue("la-cabane"),
            datetime(2027, 6, 11, 10, 0),
            30,
            artist=festival.artist("nora-lebrun"),
            min_age=age,
        )


# Lineup
def test_a_lineup_needs_two_acts(festival):
    with pytest.raises(InvalidError, match="at least two acts"):
        lineup(festival, 60, "nora-lebrun")


def test_an_act_appears_once(festival):
    with pytest.raises(InvalidError, match="cannot appear twice"):
        lineup(festival, 60, "nora-lebrun", "nora-lebrun")


def test_the_host_is_not_an_act(festival):
    with pytest.raises(InvalidError, match="hosts this lineup"):
        lineup(festival, 60, "nora-lebrun", "tom-vasseur")


def test_three_acts_need_36_minutes(festival):
    with pytest.raises(InvalidError, match="at least 36 minutes"):
        lineup(festival, 35, "nora-lebrun", "hugo-lemaire", "maya-choukri")
    gala = lineup(festival, 36, "nora-lebrun", "hugo-lemaire", "maya-choukri")
    assert gala.role_of(festival.artist("hugo-lemaire")) == "act"
    assert gala.role_of(festival.artist("tom-vasseur")) == "host"


# Workshop
def test_places_are_limited_by_the_venue(festival):
    assert workshop(festival, 999, venue="grand-casino").capacity == 650
    assert workshop(festival, 12).capacity == 12


def test_a_workshop_needs_one_place(festival):
    with pytest.raises(InvalidError, match="at least one place"):
        workshop(festival, 0)


def test_registration_until_full_and_once_per_name(festival):
    lab = workshop(festival, 2, participants=["Camille R."])
    with pytest.raises(ConflictError, match="already registered"):
        lab.register("camille r.")
    lab.register("Yanis B.")
    assert lab.places_left == 0
    with pytest.raises(ConflictError, match="is full"):
        lab.register("Lou M.")
    assert lab.participants == ["Camille R.", "Yanis B."]
