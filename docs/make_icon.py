"""Generate the FriendMap NL icon as SVG + PNG, and preview it as ASCII.

The mark is two overlapping map pins: "two people, one place". Two shapes is
about all that survives 16x16, and the two brand accents (teal, amber) keep
them separable at that size where two same-coloured pins would merge into one
blob. Cream rounded-square backing so it holds contrast on both light and dark
browser tab bars.

Geometry lives here so the SVG and the PNGs cannot drift: a pin is the exact
union of a circle and the triangle formed by its tip and the two tangent points
from that tip to the circle, which is a true teardrop rather than a circle with
a cone stuck on it.
"""
from __future__ import annotations

import math
import struct
import sys
import zlib

CREAM = (0xFA, 0xF6, 0xF0)
TEAL = (0x2F, 0x7D, 0x6E)
AMBER = (0xB8, 0x75, 0x2E)

BOX = 64.0          # design space
CORNER = 14.0       # background corner radius


class Pin:
    def __init__(self, cx, cy, r, tip_y, hole_r):
        self.c = (cx, cy)
        self.r = r
        self.tip = (cx, tip_y)
        self.hole_r = hole_r
        # Tangent points from the tip to the head circle.
        dx, dy = self.tip[0] - cx, self.tip[1] - cy
        d = math.hypot(dx, dy)
        alpha = math.atan2(dy, dx)
        beta = math.acos(min(1.0, r / d))
        self.t1 = (cx + r * math.cos(alpha + beta), cy + r * math.sin(alpha + beta))
        self.t2 = (cx + r * math.cos(alpha - beta), cy + r * math.sin(alpha - beta))

    def contains(self, x, y):
        if math.hypot(x - self.c[0], y - self.c[1]) <= self.r:
            return True
        return _in_triangle((x, y), self.tip, self.t1, self.t2)

    def in_hole(self, x, y):
        return math.hypot(x - self.c[0], y - self.c[1]) <= self.hole_r


def _sign(a, b, c):
    return (a[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (a[1] - c[1])


def _in_triangle(p, a, b, c):
    d1, d2, d3 = _sign(p, a, b), _sign(p, b, c), _sign(p, c, a)
    neg = d1 < 0 or d2 < 0 or d3 < 0
    pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (neg and pos)


FRONT = Pin(cx=23.0, cy=27.0, r=12.3, tip_y=54.0, hole_r=4.8)
BACK = Pin(cx=44.5, cy=19.5, r=9.43, tip_y=40.2, hole_r=3.68)


def _in_rounded_rect(x, y):
    if x < 0 or y < 0 or x > BOX or y > BOX:
        return False
    for cx, cy in ((CORNER, CORNER), (BOX - CORNER, CORNER),
                   (CORNER, BOX - CORNER), (BOX - CORNER, BOX - CORNER)):
        if ((x < CORNER and y < CORNER) or (x > BOX - CORNER and y < CORNER)
                or (x < CORNER and y > BOX - CORNER)
                or (x > BOX - CORNER and y > BOX - CORNER)):
            if abs(x - cx) < CORNER and abs(y - cy) < CORNER:
                return math.hypot(x - cx, y - cy) <= CORNER
    return True


def sample(x, y):
    """Colour at a point in design space, or None for transparent."""
    if not _in_rounded_rect(x, y):
        return None
    # Front pin last so it sits over the back one.
    if BACK.contains(x, y):
        colour = CREAM if BACK.in_hole(x, y) else AMBER
    else:
        colour = CREAM
    if FRONT.contains(x, y):
        colour = CREAM if FRONT.in_hole(x, y) else TEAL
    return colour


def render(size, ss=4):
    """RGBA rows, supersampled `ss`x`ss` per pixel for antialiasing."""
    rows = []
    for py in range(size):
        row = bytearray()
        for px in range(size):
            r = g = b = a = 0
            for sy in range(ss):
                for sx in range(ss):
                    x = (px + (sx + 0.5) / ss) * BOX / size
                    y = (py + (sy + 0.5) / ss) * BOX / size
                    c = sample(x, y)
                    if c is not None:
                        r += c[0]; g += c[1]; b += c[2]; a += 255
            n = ss * ss
            if a:
                # Un-premultiply so edge pixels keep their hue.
                hits = a // 255
                row += bytes((r // hits, g // hits, b // hits, a // n))
            else:
                row += b"\0\0\0\0"
        rows.append(bytes(row))
    return rows


def write_png(path, size):
    rows = render(size)
    raw = b"".join(b"\0" + r for r in rows)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)


def hexc(c):
    return "#%02X%02X%02X" % c


def pin_svg(pin, colour):
    return (
        f'    <g fill="{hexc(colour)}">\n'
        f'      <circle cx="{pin.c[0]:g}" cy="{pin.c[1]:g}" r="{pin.r:g}"/>\n'
        f'      <polygon points="{pin.tip[0]:.2f},{pin.tip[1]:.2f} '
        f'{pin.t1[0]:.2f},{pin.t1[1]:.2f} {pin.t2[0]:.2f},{pin.t2[1]:.2f}"/>\n'
        f"    </g>\n"
        f'    <circle cx="{pin.c[0]:g}" cy="{pin.c[1]:g}" r="{pin.hole_r:g}" '
        f'fill="{hexc(CREAM)}"/>\n'
    )


def write_svg(path, *, background=True):
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
        'role="img" aria-label="FriendMap NL">\n',
        "  <title>FriendMap NL</title>\n",
    ]
    if background:
        parts.append(
            f'  <rect width="64" height="64" rx="{CORNER:g}" fill="{hexc(CREAM)}"/>\n'
        )
    parts.append("  <!-- back pin -->\n")
    parts.append(pin_svg(BACK, AMBER))
    parts.append("  <!-- front pin, drawn over it -->\n")
    parts.append(pin_svg(FRONT, TEAL))
    parts.append("</svg>\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(parts)


def ascii_preview(size=44):
    """So the design can be checked before it ships."""
    glyph = {None: " ", CREAM: ".", TEAL: "#", AMBER: "o"}
    out = []
    for py in range(size):
        line = ""
        for px in range(size):
            x = (px + 0.5) * BOX / size
            y = (py + 0.5) * BOX / size
            line += glyph[sample(x, y)]
        out.append(line)
    return "\n".join(out)


if __name__ == "__main__":
    print(ascii_preview())
    print("\nlegend: '#' teal front pin   'o' amber back pin   '.' cream   ' ' transparent")
    if len(sys.argv) > 1:
        out = sys.argv[1].rstrip("/")
        write_svg(f"{out}/favicon.svg")
        for s in (16, 32, 180, 512):
            n = write_png(f"{out}/icon-{s}.png", s)
            print(f"  icon-{s}.png  {n} bytes")
        print("  favicon.svg written")
