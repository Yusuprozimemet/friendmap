"""Saved-search deserialisation.

Saved searches are stored as the query string the browser built, so every value
comes back a *string*. The coercion here is what stops the nightly alert job
from dying on `timedelta(days="0")` — and what stops `"0"` (truthy!) from being
read as a zero-day window that matches nobody.
"""
from __future__ import annotations

from app.search import SearchParams


def test_defaults_round_trip():
    params = SearchParams()
    assert SearchParams.from_dict(params.to_dict()) == params


def test_to_dict_drops_empty_values_but_keeps_false_and_zero():
    """`0` and `False` are meaningful: all-time, and "exclude hidden"."""
    params = SearchParams(period=0, include_hidden=False, genders=None, search="")
    data = params.to_dict()
    assert data["period"] == 0
    assert data["include_hidden"] is False
    assert "genders" not in data
    assert "search" not in data


def test_string_period_becomes_an_int():
    assert SearchParams.from_dict({"period": "7"}).period == 7


def test_string_zero_period_becomes_int_zero_not_a_truthy_string():
    """The bug this exists for: "0" means all time, and `if params.period`
    must therefore be False."""
    params = SearchParams.from_dict({"period": "0"})
    assert params.period == 0
    assert not params.period


def test_empty_period_becomes_none():
    assert SearchParams.from_dict({"period": ""}).period is None
    assert SearchParams.from_dict({"period": None}).period is None


def test_unparseable_period_becomes_none():
    assert SearchParams.from_dict({"period": "abc"}).period is None


def test_unparseable_ages_fall_back_to_the_defaults():
    """Ages have no null meaning — `BETWEEN NULL AND NULL` matches nobody."""
    params = SearchParams.from_dict({"age_min": "abc", "age_max": None})
    assert params.age_min == SearchParams().age_min
    assert params.age_max == SearchParams().age_max


def test_string_ages_become_ints():
    params = SearchParams.from_dict({"age_min": "21", "age_max": "45"})
    assert (params.age_min, params.age_max) == (21, 45)


def test_booleans_from_query_string_spellings():
    for truthy in ("1", "true", "True", "yes", "on", True):
        assert SearchParams.from_dict({"include_hidden": truthy}).include_hidden is True
    for falsy in ("0", "false", "no", "off", "", None, False, "banana"):
        assert SearchParams.from_dict({"include_hidden": falsy}).include_hidden is False


def test_unknown_keys_are_ignored():
    """A saved search from an older version must not crash the alert job."""
    params = SearchParams.from_dict({"period": "7", "retired_filter": "x"})
    assert params.period == 7
    assert not hasattr(params, "retired_filter")


def test_empty_and_none_input():
    assert SearchParams.from_dict({}) == SearchParams()
    assert SearchParams.from_dict(None) == SearchParams()


def test_scalars_are_stringified():
    """Numbers stored in a text filter still have to compare as text."""
    assert SearchParams.from_dict({"search": 2024}).search == "2024"
