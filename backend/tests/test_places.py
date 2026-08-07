"""Gazetteer resolution.

The interesting cases are all the messy ways people write where they live. A
regression here doesn't crash anything — it silently moves someone to the
wrong pin or drops them into the unplaced tray, which is exactly the kind of
bug that survives a manual look at the map.
"""
from __future__ import annotations

import pytest

from ingest.places import CITIES, PROVINCE_CENTROIDS, all_places, coords, lookup, normalize


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Plain city names.
        ("Amsterdam", ("city", "Amsterdam", "Noord-Holland")),
        ("amsterdam", ("city", "Amsterdam", "Noord-Holland")),
        ("  Rotterdam  ", ("city", "Rotterdam", "Zuid-Holland")),
        # Aliases people actually type, including area codes.
        ("den bosch", ("city", "'s-Hertogenbosch", "Noord-Brabant")),
        ("The Hague", ("city", "Den Haag", "Zuid-Holland")),
        ("020", ("city", "Amsterdam", "Noord-Holland")),
        ("mokum", ("city", "Amsterdam", "Noord-Holland")),
        ("brainport", ("city", "Eindhoven", "Noord-Brabant")),
        # Hyphens the canonical spelling doesn't have.
        ("Bergen-op-Zoom", ("city", "Bergen op Zoom", "Noord-Brabant")),
        ("'s-Hertogenbosch", ("city", "'s-Hertogenbosch", "Noord-Brabant")),
        # Provinces, their abbreviations, and informal regions.
        ("Friesland", ("province", None, "Friesland")),
        ("NH", ("province", None, "Noord-Holland")),
        ("noord brabant", ("province", None, "Noord-Brabant")),
        ("Twente", ("province", None, "Overijssel")),
        ("Veluwe", ("province", None, "Gelderland")),
        # Country-level: known, but not placeable.
        ("Nederland", ("country", None, None)),
        ("the netherlands", ("country", None, None)),
        # Nothing we can honestly place.
        ("Mars", ("none", None, None)),
        ("", ("none", None, None)),
        (None, ("none", None, None)),
    ],
)
def test_lookup(raw, expected):
    assert lookup(raw) == expected


def test_compound_prefers_the_city():
    """"Zaandam, Noord-Holland" is a city, not a province.

    Both are present, and the more specific one has to win or every
    city-and-province post collapses to a province centroid.
    """
    assert lookup("Zaandam, Noord-Holland") == ("city", "Zaandam", "Noord-Holland")


def test_slash_separated_picks_the_first_known_city():
    assert lookup("Sittard/Maastricht") == ("city", "Sittard", "Limburg")


def test_filler_words_are_split_away():
    assert lookup("ergens in Friesland") == ("province", None, "Friesland")
    assert lookup("omgeving Utrecht") == ("city", "Utrecht", "Utrecht")


def test_place_name_embedded_in_a_sentence():
    """The last-resort path: a known name anywhere in the string."""
    assert lookup("I live in beautiful Rotterdam these days") == (
        "city",
        "Rotterdam",
        "Zuid-Holland",
    )


def test_short_names_do_not_match_as_substrings():
    """The substring fallback is length-gated for a reason.

    "Best" and "Goes" are real towns and also ordinary English words. Matching
    them inside a sentence would place people who never named a town, so the
    fallback only considers names longer than four characters.
    """
    assert lookup("this is the best place to be") == ("none", None, None)


def test_normalize_keeps_the_characters_dutch_names_need():
    # Apostrophe and hyphen survive; accents are folded; punctuation becomes
    # space so adjacent names don't fuse into one token.
    assert normalize("'s-Hertogenbosch") == "'s-hertogenbosch"
    assert normalize("Súdwest-Fryslân") == "sudwest-fryslan"
    assert normalize("Sittard/Maastricht") == "sittard maastricht"
    assert normalize("  MULTIPLE   spaces ") == "multiple spaces"


def test_coords():
    assert coords("Amsterdam", None) == pytest.approx((52.3676, 4.9041))
    # A province with no city falls back to the province centroid.
    assert coords(None, "Zeeland") == pytest.approx((51.45, 3.85))
    # City wins when both are given.
    assert coords("Groningen", "Zeeland") == pytest.approx((53.2194, 6.5665))
    assert coords("Atlantis", None) is None
    assert coords(None, None) is None


def test_every_city_names_a_real_province():
    """A typo'd province on a city row would break the province filter."""
    for name, (_, _, province) in CITIES.items():
        assert province in PROVINCE_CENTROIDS, f"{name} has unknown province {province!r}"


def test_all_places_covers_cities_and_provinces():
    rows = all_places()
    assert len(rows) == len(CITIES) + len(PROVINCE_CENTROIDS)
    # `seed_reference` keys on (name, kind), which the schema enforces unique.
    keys = [(r["name"], r["kind"]) for r in rows]
    assert len(keys) == len(set(keys))
    assert {r["kind"] for r in rows} == {"city", "province"}
