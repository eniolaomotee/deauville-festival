from datetime import date, datetime

import pytest

from deauville.errors import ConflictError, InvalidError, NotFoundError
from deauville.festival import Festival
from deauville.model import Artist, Lineup, SoloShow, Venue


@pytest.fixture
def festival() -> Festival:
    festival = Festival("Test festival", date(2027, 6, 10), date(2027, 6, 13))
    festival.add_venue(Venue("Le Kiosque", 120, "Beach"))
    festival.add_venue(Venue("La Cabane", 40, "Beach"))
    for name in ("Nora Lebrun", "Tom Vasseur", "Hugo Lemaire", "Maya Choukri"):
        festival.add_artist(Artist(name))
    festival.schedule(
        solo(festival, "Late Laughs", "2027-06-11T23:30", 60, "nora-lebrun")
    )
    festival.schedule(
        Lineup(
            "After Hours",
            festival.venue("le-kiosque"),
            datetime(2027, 6, 12, 1, 0),
            60,
            host=festival.artist("tom-vasseur"),
            acts=[festival.artist("hugo-lemaire"), festival.artist("maya-choukri")],
        )
    )

    return festival


def solo(festival, title, start, minutes, artist, venue="le-kiosque") -> SoloShow:
    return SoloShow(
        title,
        festival.venue(venue),
        datetime.fromisoformat(start),
        minutes,
        artist=festival.artist(artist),
    )


def test_a_venue_needs_30_minutes_between_two_shows(festival):
    with pytest.raises(ConflictError, match="Le Kiosque is busy with After Hours"):
        festival.schedule(
            solo(festival, "Too Close", "2027-06-12T02:15", 30, "nora-lebrun")
        )
    assert len(festival.performances) == 2


def test_an_artist_cannot_be_in_two_venues_at_once(festival):
    with pytest.raises(ConflictError, match="Nora Lebrun is on stage in Late Laughs"):
        festival.schedule(
            solo(
                festival,
                "Elsewhere",
                "2027-06-11T23:00",
                30,
                "nora-lebrun",
                "la-cabane",
            )
        )


def test_an_act_of_a_lineup_is_busy_too(festival):
    with pytest.raises(ConflictError, match="Hugo Lemaire is on stage in After Hours"):
        festival.schedule(
            solo(
                festival,
                "Side Show",
                "2027-06-12T02:00",
                30,
                "hugo-lemaire",
                "la-cabane",
            )
        )


def test_a_show_at_one_am_belongs_to_the_previous_day(festival):
    after_hours = festival.performance("le-kiosque-2027-06-12-0100")
    assert after_hours.festival_day == date(2027, 6, 11)
    assert after_hours in festival.programme(date(2027, 6, 11))
    assert after_hours not in festival.programme(date(2027, 6, 12))


def test_a_day_outside_the_festival_is_refused(festival):
    with pytest.raises(ConflictError, match="not a day of the festival"):
        festival.schedule(
            solo(festival, "Too Late", "2027-06-14T20:00", 60, "nora-lebrun")
        )


@pytest.mark.parametrize("minutes", [0, 361])
def test_duration_out_of_range_is_refused(festival, minutes):
    with pytest.raises(InvalidError, match="1 to 360 minutes"):
        solo(festival, "Odd", "2027-06-12T10:00", minutes, "nora-lebrun")


def test_an_unknown_venue_is_refused(festival):
    with pytest.raises(NotFoundError, match="No venue 'nowhere'"):
        festival.make_performance(
            {
                "kind": "solo",
                "title": "X",
                "venue": "nowhere",
                "start": "2027-06-12T10:00",
                "duration_minutes": 30,
                "artist": "nora-lebrun",
            }
        )


def test_an_unknown_artist_is_refused(festival):
    with pytest.raises(NotFoundError, match="No artist 'nobody'"):
        festival.make_performance(
            {
                "kind": "solo",
                "title": "X",
                "venue": "le-kiosque",
                "start": "2027-06-12T10:00",
                "duration_minutes": 30,
                "artist": "nobody",
            }
        )
