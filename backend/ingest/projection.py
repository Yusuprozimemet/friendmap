"""lat/lon -> position on the design's Netherlands SVG.

The design ships a hand-drawn NL silhouette on a 460x552 viewBox plus a lookup
table of pixel coords for 21 cities. Fitting those pairs showed the artwork is a
plain Web-Mercator projection; the constants below reproduce the design's own
numbers to within 0.05px, so any city we geocode lands exactly where the
designer would have put it.

Kept server-side so the frontend never has to know about projections — the API
hands out ready-to-use percentages.
"""
import math

VIEWBOX_W = 460.0
VIEWBOX_H = 552.0

_LON_SCALE = 117.665405
_LON_OFFSET = -390.576615
_MERC_SCALE = -6742.112204
_MERC_OFFSET = 7504.715244


def _mercator_y(lat: float) -> float:
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def to_pixels(lat: float, lon: float) -> tuple[float, float]:
    """Project to the SVG's 460x552 pixel space."""
    return (
        _LON_SCALE * lon + _LON_OFFSET,
        _MERC_SCALE * _mercator_y(lat) + _MERC_OFFSET,
    )


def to_percent(lat: float, lon: float) -> tuple[float, float]:
    """Project to 0-100 percentages, which is how the pins are positioned."""
    px, py = to_pixels(lat, lon)
    return (px / VIEWBOX_W) * 100.0, (py / VIEWBOX_H) * 100.0
