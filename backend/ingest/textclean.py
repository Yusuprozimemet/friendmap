"""Cleanup for text that arrives wrapped in feed boilerplate."""
from __future__ import annotations

import re

# Reddit's Atom <content> closes every entry with the poster's handle and two
# link stubs:
#
#     submitted by
#     /u/some_handle
#     [link]
#     [comments]
#
# It isn't part of what anyone wrote, and it's the only place a username
# reaches the UI, so it comes off before the text is ever stored or served.
_FOOTER_LINE = re.compile(
    r"(?:\n|\A)[ \t]*(?:submitted by|/?u/[A-Za-z0-9_-]{1,32}|\[link\]|\[comments\])[ \t]*\Z",
    re.IGNORECASE,
)

_MAX_FOOTER_LINES = 4


def strip_feed_footer(body: str) -> str:
    """Peel the feed footer off the end of a post body.

    Anchored to the end and capped at the footer's own length, so a post that
    happens to mention a handle mid-sentence keeps it.
    """
    text = (body or "").rstrip()
    for _ in range(_MAX_FOOTER_LINES):
        trimmed = _FOOTER_LINE.sub("", text).rstrip()
        if trimmed == text:
            break
        text = trimmed
    return text
