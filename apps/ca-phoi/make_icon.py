"""Writes tai-phoi-california.ico: a blue tile with a white down-arrow (no image libraries)."""
import struct
from pathlib import Path


def tile(n):
    px = []
    for y in range(n - 1, -1, -1):          # BMP rows bottom-up
        for x in range(n):
            u, v = (x + .5) / n, (y + .5) / n
            r = .18                          # rounded corners
            cx, cy = min(max(u, r), 1 - r), min(max(v, r), 1 - r)
            inside = (u - cx) ** 2 + (v - cy) ** 2 <= r * r
            shaft = .42 <= u <= .58 and .18 <= v <= .55
            head = .52 <= v <= .74 and abs(u - .5) <= (.74 - v) * 1.15
            tray = .80 <= v <= .86 and .24 <= u <= .76
            if not inside:
                px.append((0, 0, 0, 0))
            elif shaft or head or tray:
                px.append((255, 255, 255, 255))
            else:
                px.append((0xC8, 0x6A, 0x1E, 255))  # BGRA: #1E6AC8
    return px


def bmp(n):
    hdr = struct.pack("<IiiHHIIiiII", 40, n, n * 2, 1, 32, 0, n * n * 4, 0, 0, 0, 0)
    pixels = b"".join(struct.pack("BBBB", *p) for p in tile(n))
    mask = b"\x00" * (((n + 31) // 32) * 4 * n)
    return hdr + pixels + mask


sizes = [16, 32, 48, 256]
blobs = [bmp(n) for n in sizes]
out = struct.pack("<HHH", 0, 1, len(sizes))
off = 6 + 16 * len(sizes)
for n, b in zip(sizes, blobs):
    out += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32, len(b), off)
    off += len(b)
out += b"".join(blobs)
Path(__file__).with_name("tai-phoi-california.ico").write_bytes(out)
print("ok", len(out))
