"""The LLM output contract.

`_coerce` and `_parse` are the boundary between a model that will occasionally
say anything and a database with a fixed vocabulary. They're tested directly —
no network — because that boundary is where a bad day for the model becomes bad
data forever.
"""
from __future__ import annotations

import pytest

from app.models import INTEREST_VOCAB
from ingest.extractor import _build_prompt, _coerce, _parse


def test_coerce_a_well_formed_object():
    item = _coerce(
        {
            "n": 3,
            "post_type": "profile",
            "age": 28,
            "gender": "F",
            "location": "Zaandam",
            "lang": "nl",
            "interests": ["hiking", "coffee"],
            "looking_for": "someone to walk with",
            "summary": "Walks the dunes most weekends.",
            "confidence": 0.8,
        }
    )
    assert item is not None
    assert item.index == 3
    assert item.age == 28
    assert item.gender == "F"
    assert item.location_raw == "Zaandam"
    assert item.lang == "nl"
    assert item.interests == ["hiking", "coffee"]
    assert item.confidence == 0.8
    assert item.needs_review is False


def test_missing_or_unparseable_index_is_dropped():
    """`n` is how a result is matched back to its post. No `n`, no result."""
    assert _coerce({"age": 30}) is None
    assert _coerce({"n": "not a number"}) is None
    assert _coerce({"n": None}) is None


def test_string_index_is_accepted():
    """Models quote numbers often enough that rejecting "3" would lose rows."""
    item = _coerce({"n": "3"})
    assert item is not None and item.index == 3


@pytest.mark.parametrize(
    "given,expected",
    [
        ("M", "M"),
        ("F", "F"),
        ("NB", "NB"),
        ("couple", "couple"),
        ("m", "M"),          # lowercased by the model
        ("f", "F"),
        ("nb", "NB"),
        ("male", "unknown"),  # not in the vocabulary — not guessed at
        ("", "unknown"),
        (None, "unknown"),
    ],
)
def test_gender_is_mapped_or_unknown(given, expected):
    assert _coerce({"n": 1, "gender": given}).gender == expected


@pytest.mark.parametrize(
    "given,expected",
    [
        (30, 30),
        ("30", 30),
        (13, 13),   # inclusive lower bound
        (99, 99),   # inclusive upper bound
        (12, None),  # below the plausible range → a misparse, not an age
        (100, None),
        (0, None),
        (-5, None),
        (1995, None),  # a birth year, which models do return
        ("abc", None),
        (None, None),
    ],
)
def test_age_is_range_checked(given, expected):
    assert _coerce({"n": 1, "age": given}).age == expected


def test_interests_are_filtered_to_the_vocabulary_and_capped():
    item = _coerce(
        {
            "n": 1,
            # Two valid, one invented, plus enough valid ones to exceed the cap.
            "interests": ["Gaming", "COFFEE", "underwater basket weaving",
                          "books", "film", "pets"],
        }
    )
    assert all(i in INTEREST_VOCAB for i in item.interests)
    assert "underwater basket weaving" not in item.interests
    assert item.interests[:2] == ["gaming", "coffee"]  # lowercased
    assert len(item.interests) == 4  # capped


def test_interests_tolerates_junk_types():
    item = _coerce({"n": 1, "interests": [None, 5, {"a": 1}, "books"]})
    assert item.interests == ["books"]


@pytest.mark.parametrize(
    "given,expected",
    [("nl", "nl"), ("en", "en"), ("NL", "nl"), ("de", "en"), (None, "en")],
)
def test_lang_falls_back_to_english(given, expected):
    assert _coerce({"n": 1, "lang": given}).lang == expected


@pytest.mark.parametrize(
    "given,expected",
    [(0.9, 0.9), (1.5, 1.0), (-2, 0.0), ("0.5", 0.5), ("nonsense", 0.0), (None, 0.0)],
)
def test_confidence_is_clamped(given, expected):
    assert _coerce({"n": 1, "confidence": given}).confidence == pytest.approx(expected)


def test_needs_review_tracks_low_confidence():
    assert _coerce({"n": 1, "confidence": 0.49}).needs_review is True
    assert _coerce({"n": 1, "confidence": 0.5}).needs_review is False


@pytest.mark.parametrize("given", ["null", "none", "unknown", "NULL", "", None])
def test_placeholder_locations_become_none(given):
    """The model writes "null" as a string often enough to matter.

    Stored literally it would become a location nobody can resolve, and the
    person would sit in the unplaced tray with a location that looks set.
    """
    assert _coerce({"n": 1, "location": given}).location_raw is None


def test_unknown_post_type_defaults_to_profile():
    assert _coerce({"n": 1, "post_type": "advertisement"}).post_type == "profile"
    assert _coerce({"n": 1, "post_type": "EVENT"}).post_type == "event"


def test_parse_extracts_json_lines():
    reply = (
        '{"n": 1, "age": 25, "gender": "M"}\n'
        '{"n": 2, "age": 31, "gender": "F"}\n'
    )
    parsed = _parse(reply)
    assert set(parsed) == {1, 2}
    assert parsed[1].age == 25
    assert parsed[2].gender == "F"


def test_parse_tolerates_prose_and_code_fences():
    """Models wrap output in explanations no matter what the prompt says."""
    reply = (
        "Sure! Here are the extractions:\n"
        "```json\n"
        '{"n": 1, "age": 40}\n'
        "```\n"
        "Let me know if you need anything else."
    )
    assert set(_parse(reply)) == {1}
    assert _parse(reply)[1].age == 40


def test_parse_skips_malformed_objects_without_losing_the_rest():
    reply = '{"n": 1, "age": 22}\n{"n": 2, "age": }\n{"n": 3, "age": 44}'
    parsed = _parse(reply)
    assert set(parsed) == {1, 3}


def test_parse_returns_empty_on_nothing_usable():
    assert _parse("I could not process these posts.") == {}
    assert _parse("") == {}


def test_parse_keeps_the_last_object_for_a_repeated_index():
    """A duplicate `n` is the model contradicting itself; one has to win."""
    parsed = _parse('{"n": 1, "age": 20}\n{"n": 1, "age": 55}')
    assert parsed[1].age == 55


def test_build_prompt_numbers_posts_from_one_and_truncates_bodies():
    items = [
        {"id": "a1", "title": "First", "body": "x" * 3000},
        {"id": "a2", "title": "Second", "body": "short"},
    ]
    prompt = _build_prompt(items)
    assert "### POST 1" in prompt and "### POST 2" in prompt
    assert "### POST 3" not in prompt
    # Bodies are capped so a long post can't push the batch over the token
    # budget and take its seven neighbours down with it.
    assert "x" * 1500 in prompt
    assert "x" * 1501 not in prompt


def test_build_prompt_handles_a_missing_body():
    prompt = _build_prompt([{"id": "a1", "title": "Title only", "body": None}])
    assert "Title only" in prompt
