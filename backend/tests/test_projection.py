"""lat/lon → the design's SVG pixel space."""
from __future__ import annotations

import pytest

from ingest.places import CITIES, PROVINCE_CENTROIDS
from ingest.projection import VIEWBOX_H, VIEWBOX_W, to_percent, to_pixels


def test_percent_is_pixels_over_the_viewbox():
    px, py = to_pixels(52.3676, 4.9041)
    x, y = to_percent(52.3676, 4.9041)
    assert x == pytest.approx(px / VIEWBOX_W * 100)
    assert y == pytest.approx(py / VIEWBOX_H * 100)


def test_north_is_up_and_east_is_right():
    """Mercator y grows downward, which is easy to invert by accident."""
    groningen_x, groningen_y = to_percent(*CITIES["Groningen"][:2])
    maastricht_x, maastricht_y = to_percent(*CITIES["Maastricht"][:2])
    # Groningen is north of Maastricht → smaller y.
    assert groningen_y < maastricht_y
    # Enschede is east of Den Haag → larger x.
    assert to_percent(*CITIES["Enschede"][:2])[0] > to_percent(*CITIES["Den Haag"][:2])[0]
    # Groningen (6.57°E) is also east of Maastricht (5.69°E).
    assert groningen_x > maastricht_x


@pytest.mark.parametrize("name", sorted(CITIES))
def test_every_city_lands_inside_the_map(name):
    """A bad gazetteer coordinate shows as a pin off the edge of the artwork.

    The silhouette fills the viewBox, so anything outside 0-100% is either a
    typo'd lat/lon or a place that isn't in the Netherlands.
    """
    lat, lon, _ = CITIES[name]
    x, y = to_percent(lat, lon)
    assert 0.0 <= x <= 100.0, f"{name} x={x:.1f}"
    assert 0.0 <= y <= 100.0, f"{name} y={y:.1f}"


@pytest.mark.parametrize("name", sorted(PROVINCE_CENTROIDS))
def test_every_province_centroid_lands_inside_the_map(name):
    lat, lon = PROVINCE_CENTROIDS[name]
    x, y = to_percent(lat, lon)
    assert 0.0 <= x <= 100.0, f"{name} x={x:.1f}"
    assert 0.0 <= y <= 100.0, f"{name} y={y:.1f}"


def test_projection_is_injective_over_the_gazetteer():
    """Two different cities must not share a pixel.

    They would overlap exactly on the map, which reads as one person rather
    than two. Duplicate *coordinates* in the table are the real cause — this
    catches them at their effect.
    """
    seen: dict[tuple[float, float], str] = {}
    for name, (lat, lon, _) in CITIES.items():
        key = tuple(round(v, 3) for v in to_percent(lat, lon))
        if key in seen:
            # Known duplicates: aliases kept as separate rows with the same
            # coordinates on purpose. Assert the set doesn't grow silently.
            assert {seen[key], name} in (
                {"Hoorn", "Hoorn NH"},
                {"Winschoten", "Oldambt"},
                {"Emmeloord", "Noordoostpolder"},
            ), f"{seen[key]} and {name} project to the same point"
        seen[key] = name
