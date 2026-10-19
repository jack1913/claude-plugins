"""Minimal PNG reader and ICO writer (standard library only). Reads 8-bit non-interlaced PNGs as RGBA."""
from __future__ import annotations

import struct
import zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def png_size(data: bytes) -> tuple[int, int]:
    if data[:8] != PNG_SIG or data[12:16] != b"IHDR":
        raise ValueError("not a PNG")
    return struct.unpack(">II", data[16:24])


def png_color_type(data: bytes) -> int:
    return data[25]


def read_png(data: bytes) -> tuple[int, int, bytearray]:
    """-> (width, height, RGBA bytes). Supports colour types 0, 2, 3, 4, 6 at 8 bits, no interlace."""
    if data[:8] != PNG_SIG:
        raise ValueError("not a PNG")
    pos, idat, plte, trns = 8, b"", b"", b""
    w = h = bd = ct = il = 0
    while pos < len(data):
        n, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if typ == b"IHDR":
            w, h, bd, ct, _c, _f, il = struct.unpack(">IIBBBBB", body)
        elif typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
    if bd != 8 or il != 0 or ct not in (0, 2, 3, 4, 6):
        raise ValueError(f"unsupported PNG (bit depth {bd}, colour type {ct}, interlace {il})")
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    raw = zlib.decompress(idat)
    stride = w * ch
    out = bytearray()
    prev = bytearray(stride)
    p = 0
    for _y in range(h):
        f = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        elif f != 0:
            raise ValueError(f"bad PNG filter {f}")
        prev = line
        if ct == 6:
            out += line
        elif ct == 2:
            key = bytes((trns[1], trns[3], trns[5])) if len(trns) == 6 else None  # tRNS: one transparent colour
            for i in range(0, stride, 3):
                out += line[i:i + 3] + (b"\x00" if key is not None and bytes(line[i:i + 3]) == key else b"\xff")
        elif ct == 0:
            key = trns[1] if len(trns) == 2 else None
            for v in line:
                out += bytes((v, v, v, 0 if v == key else 255))
        elif ct == 4:
            for i in range(0, stride, 2):
                out += bytes((line[i], line[i], line[i], line[i + 1]))
        else:  # palette
            for v in line:
                r, g, b = plte[v * 3:v * 3 + 3]
                a = trns[v] if v < len(trns) else 255
                out += bytes((r, g, b, a))
    return w, h, out


def write_ico(pngs: list[bytes]) -> bytes:
    """ICO with PNG-compressed entries, in the order given. Sizes are read from each PNG; 256 is stored as 0."""
    hdr = struct.pack("<HHH", 0, 1, len(pngs))
    off = 6 + 16 * len(pngs)
    ents = b""
    for d in pngs:
        w, h = png_size(d)
        ents += struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(d), off)
        off += len(d)
    return hdr + ents + b"".join(pngs)


def read_ico_sizes(data: bytes) -> list[tuple[int, int]]:
    reserved, typ, n = struct.unpack("<HHH", data[:6])
    if reserved != 0 or typ != 1:
        raise ValueError("not an ICO")
    out = []
    for i in range(n):
        w, h = struct.unpack("<BB", data[6 + 16 * i:8 + 16 * i])
        out.append((w or 256, h or 256))
    return out
