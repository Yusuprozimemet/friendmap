"""Feed-footer stripping.

Reddit's Atom feed appends the poster's handle to every entry. It's the only
place a username would reach the UI, and the username was deliberately removed
from the API — so a regression here is a privacy regression, not a cosmetic one.
"""
from __future__ import annotations

from ingest.textclean import strip_feed_footer

FOOTER = "submitted by\n/u/some_handle\n[link]\n[comments]"


def test_strips_the_whole_footer():
    body = f"Hi, I'm new to Utrecht and looking for climbing partners.\n\n{FOOTER}"
    assert strip_feed_footer(body) == "Hi, I'm new to Utrecht and looking for climbing partners."


def test_strips_a_partial_footer():
    assert strip_feed_footer("Text here\n[link]\n[comments]") == "Text here"
    assert strip_feed_footer("Text here\n/u/someone") == "Text here"


def test_keeps_a_handle_mentioned_mid_sentence():
    """Anchored to the end so a post that credits someone keeps the credit."""
    body = "Thanks /u/helpful_person for the tip! I'm in Leiden."
    assert strip_feed_footer(body) == body


def test_keeps_a_handle_on_its_own_line_mid_post():
    body = "Message me\n\n/u/someone\n\nI'm in Breda and I bake."
    assert strip_feed_footer(body) == body


def test_handles_empty_and_none():
    assert strip_feed_footer("") == ""
    assert strip_feed_footer(None) == ""


def test_is_idempotent():
    """Applied at ingest *and* at read time, so running twice must be safe."""
    once = strip_feed_footer(f"Real text.\n\n{FOOTER}")
    assert strip_feed_footer(once) == once


def test_leaves_a_body_that_is_only_a_footer_empty_rather_than_wrong():
    assert strip_feed_footer(FOOTER) == ""


def test_trailing_whitespace_does_not_hide_the_footer():
    assert strip_feed_footer("Text here\n[comments]   \n  ") == "Text here"
