"""Pixelate the person-list panel in a screenshot before publishing it.

The Explore screenshot is the clearest single explanation of what this app does,
so it belongs in the README. But the list panel shows real people's post titles
and summaries verbatim, and a verbatim Dutch title is searchable — pasting one
into a search engine finds the author. Publishing that in a public repository is
the same act the rest of this project goes to some length to avoid, and it would
make the README's "ships no personal data" claim false.

So: mosaic the card region, keep everything else. The layout, the cards, the tag
chips and the map all stay legible; the text does not.

No image library is available here, so this decodes and re-encodes PNG directly.
Only what this one file needs: 8-bit truecolour, non-interlaced.
"""
from __future__ import annotations

import pathlib
import struct
import sys
import zlib

BPP = 3  # RGB, 8 bits per channel


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode(path: pathlib.Path) -> tuple[int, int, bytearray]:
    """-> (width, height, raw RGB rows concatenated)."""
    blob = path.read_bytes()
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")

    idat = bytearray()
    width = height = 0
    i = 8
    while i < len(blob):
        length = struct.unpack(">I", blob[i : i + 4])[0]
        tag = blob[i + 4 : i + 8]
        data = blob[i + 8 : i + 8 + length]
        if tag == b"IHDR":
            width, height, depth, ctype, _, _, interlace = struct.unpack(
                ">IIBBBBB", data
            )
            if (depth, ctype, interlace) != (8, 2, 0):
                raise ValueError(
                    f"only 8-bit non-interlaced RGB supported, got "
                    f"depth={depth} colour={ctype} interlace={interlace}"
                )
        elif tag == b"IDAT":
            idat += data
        elif tag == b"IEND":
            break
        i += 12 + length

    stride = width * BPP
    raw = zlib.decompress(bytes(idat))
    out = bytearray(stride * height)
    pos = 0
    for y in range(height):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos : pos + stride])
        pos += stride
        base = y * stride
        prev = base - stride

        if ftype == 1:  # Sub
            for x in range(BPP, stride):
                line[x] = (line[x] + line[x - BPP]) & 0xFF
        elif ftype == 2:  # Up
            for x in range(stride):
                line[x] = (line[x] + out[prev + x]) & 0xFF
        elif ftype == 3:  # Average
            for x in range(stride):
                a = line[x - BPP] if x >= BPP else 0
                b = out[prev + x] if y else 0
                line[x] = (line[x] + ((a + b) >> 1)) & 0xFF
        elif ftype == 4:  # Paeth
            for x in range(stride):
                a = line[x - BPP] if x >= BPP else 0
                b = out[prev + x] if y else 0
                c = out[prev + x - BPP] if (y and x >= BPP) else 0
                line[x] = (line[x] + _paeth(a, b, c)) & 0xFF
        elif ftype != 0:
            raise ValueError(f"bad filter type {ftype} on row {y}")

        out[base : base + stride] = line
    return width, height, out


def encode(path: pathlib.Path, width: int, height: int, pixels: bytearray) -> int:
    stride = width * BPP
    # Filter 0 on every row: bigger than optimal filtering, but this runs once
    # and correctness is worth more here than a few hundred KB.
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += pixels[y * stride : (y + 1) * stride]

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    blob = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(blob)
    return len(blob)


def mosaic(
    pixels: bytearray, width: int, x0: int, y0: int, x1: int, y1: int, block: int
) -> None:
    """Average each block*block cell, in place."""
    stride = width * BPP
    for by in range(y0, y1, block):
        for bx in range(x0, x1, block):
            ys = range(by, min(by + block, y1))
            xs = range(bx, min(bx + block, x1))
            r = g = b = n = 0
            for y in ys:
                row = y * stride
                for x in xs:
                    p = row + x * BPP
                    r += pixels[p]
                    g += pixels[p + 1]
                    b += pixels[p + 2]
                    n += 1
            if not n:
                continue
            r, g, b = r // n, g // n, b // n
            for y in ys:
                row = y * stride
                for x in xs:
                    p = row + x * BPP
                    pixels[p] = r
                    pixels[p + 1] = g
                    pixels[p + 2] = b


def preview(pixels: bytearray, width: int, height: int, cols: int = 78) -> str:
    """Coarse luminance map, to confirm the redaction landed where intended."""
    stride = width * BPP
    rows = max(1, int(cols * height / width / 2.2))
    ramp = " .:-=+*#%@"
    lines = []
    for ry in range(rows):
        line = ""
        for rx in range(cols):
            x = int((rx + 0.5) * width / cols)
            y = int((ry + 0.5) * height / rows)
            p = y * stride + x * BPP
            lum = (pixels[p] * 299 + pixels[p + 1] * 587 + pixels[p + 2] * 114) // 1000
            line += ramp[min(9, (255 - lum) * 10 // 256)]
        lines.append(line)
    return "\n".join(lines)


if __name__ == "__main__":
    src = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs/image.png")
    w, h, px = decode(src)
    print(f"decoded {w}x{h}")

    # The list panel starts at the divider right of the map and runs to the edge.
    # Fractions of the width/height so the same numbers survive a re-shot
    # screenshot at a different resolution.
    x0 = int(w * 0.7075)   # left edge of the person-list panel
    y0 = int(h * 0.2450)   # below the "N people / Newest / All time" header
    print(f"mosaic region: x {x0}..{w}, y {y0}..{h}  (block 20px)")
    mosaic(px, w, x0, y0, w, h, block=20)

    print(preview(px, w, h))
    dest = src.with_name(src.stem + "-redacted.png")
    print(f"\nwrote {dest} ({encode(dest, w, h, px)} bytes)")
