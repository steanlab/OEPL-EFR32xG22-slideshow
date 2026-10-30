#!/usr/bin/env python3
"""Convert images to 1-bit bitmaps and write them as a C header.

Usage:
  gen_images.py <src_dir> <out_header> [width] [height] [xshift]
                [--tone tone_curve.json] [--preview preview.png]

Per-image options are file name suffixes (see slideshow_src/README.md):
  _thr _atk _fs _ord  dithering algorithm (default: chosen automatically)
  _inv                invert
  _raw                image is already 1-bit at panel size, use as-is

Bitmap format of every image: [width, height, rows...], each row is
ceil(width / 8) bytes, MSB first, bit 1 = black pixel.
"""
import argparse
import glob
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont, ImageOps

EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
ALGOS = ("thr", "atk", "fs", "ord")

KERNEL_FS = [(1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16)]
KERNEL_ATK = [(1, 0, 1 / 8), (2, 0, 1 / 8), (-1, 1, 1 / 8),
              (0, 1, 1 / 8), (1, 1, 1 / 8), (0, 2, 1 / 8)]


def _srgb_to_linear(v):
    c = v / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


LIN = [_srgb_to_linear(v) for v in range(256)]


def bayer(n):
    m = [[0]]
    s = 1
    while s < n:
        top = [[4 * v for v in r] + [4 * v + 2 for v in r] for r in m]
        bot = [[4 * v + 3 for v in r] + [4 * v + 1 for v in r] for r in m]
        m = top + bot
        s *= 2
    return m


BAYER8 = bayer(8)


def load_tone(path):
    """Tone curve measured on the panel: g = white fraction, m = measured brightness."""
    if not path or not os.path.exists(path):
        return None
    with open(path) as f:
        d = json.load(f)
    g, m = d["g"], list(d["m"])
    for i in range(1, len(m)):
        m[i] = max(m[i], m[i - 1])
    return g, m


def coverage_for(L, tone):
    """Linear brightness 0..1 -> white pixel fraction that really gives it on the panel."""
    if tone is None:
        return L
    g, m = tone
    if L <= m[0]:
        return g[0]
    for i in range(1, len(m)):
        if L <= m[i]:
            span = m[i] - m[i - 1]
            t = 0.0 if span < 1e-9 else (L - m[i - 1]) / span
            return g[i - 1] + t * (g[i] - g[i - 1])
    return g[-1]


def diffuse(cov, W, H, kernel, serpentine):
    """Error diffusion on a field of white fractions. Returns rows of bool (True = white)."""
    buf = [list(row) + [0.0, 0.0] for row in cov] + [[0.0] * (W + 2) for _ in range(2)]
    out = [[False] * W for _ in range(H)]
    for y in range(H):
        rev = serpentine and (y & 1)
        xs = range(W - 1, -1, -1) if rev else range(W)
        row = buf[y]
        for x in xs:
            old = row[x]
            new = 1.0 if old >= 0.5 else 0.0
            out[y][x] = new > 0.5
            err = old - new
            if err:
                for dx, dy, w in kernel:
                    buf[y + dy][x + (-dx if rev else dx)] += err * w
    return out


def dither(cov, W, H, algo):
    if algo == "thr":
        return [[v >= 0.5 for v in row] for row in cov]
    if algo == "ord":
        return [[cov[y][x] > (BAYER8[y % 8][x % 8] + 0.5) / 64.0 for x in range(W)]
                for y in range(H)]
    if algo == "atk":
        return diffuse(cov, W, H, KERNEL_ATK, False)
    return diffuse(cov, W, H, KERNEL_FS, True)


def parse_flags(path):
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    toks = set(stem.split("_"))
    algo = next((a for a in ALGOS if a in toks), None)
    return algo, ("inv" in toks), ("raw" in toks)


def load_gray(path, W, H):
    im = ImageOps.exif_transpose(Image.open(path))
    if im.mode in ("RGBA", "LA", "P"):                    # transparency -> white
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    return ImageOps.fit(im.convert("L"), (W, H))           # scale + center-crop


def process(path, W, H, tone):
    """Returns (white matrix, algorithm label, mid-tone share)."""
    algo, inv, raw = parse_flags(path)
    gray = load_gray(path, W, H)
    if raw:
        px = gray.load()
        white = [[(px[x, y] >= 128) != inv for x in range(W)] for y in range(H)]
        return white, "raw", 0.0
    gray = ImageOps.autocontrast(gray, cutoff=1)
    if inv:
        gray = ImageOps.invert(gray)
    hist = gray.histogram()
    mid = sum(hist[64:192]) / float(W * H)
    chosen = algo or ("atk" if mid < 0.08 else "fs")       # simple heuristic, tunable
    lut = [coverage_for(LIN[v], tone) for v in range(256)]
    px = gray.load()
    cov = [[lut[px[x, y]] for x in range(W)] for y in range(H)]
    white = dither(cov, W, H, chosen)
    return white, (chosen if algo else chosen + " (auto)"), mid


def roll(white, W, s):
    s %= W
    if s == 0:
        return white
    return [row[W - s:] + row[:W - s] for row in white]


def pack(white, W, H):
    rb = (W + 7) // 8
    data = [W, H]
    black = 0
    for row in white:
        for bx in range(rb):
            b = 0
            for k in range(8):
                x = bx * 8 + k
                dark = x < W and not row[x]
                black += dark
                b = (b << 1) | (1 if dark else 0)
            data.append(b)
    return data, black


def make_preview(items, W, H, path):
    cols = 6
    font = ImageFont.load_default()
    cw, chh = W + 8, H + 24
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("L", (cols * cw, rows * chh), 255)
    d = ImageDraw.Draw(sheet)
    for i, (name, label, white) in enumerate(items):
        x0 = (i % cols) * cw + 4
        y0 = (i // cols) * chh + 4
        im = Image.new("L", (W, H))
        im.putdata([255 if v else 0 for row in white for v in row])
        sheet.paste(im, (x0, y0 + 14))
        d.text((x0, y0), f"{i + 1:02d} {name[:18]} {label}"[:34], fill=0, font=font)
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser(description="Convert images to 1-bit bitmaps (C header).")
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("width", nargs="?", type=int, default=200)
    ap.add_argument("height", nargs="?", type=int, default=200)
    ap.add_argument("xshift", nargs="?", type=int, default=0)
    ap.add_argument("--tone", default=None)
    ap.add_argument("--preview", default=None)
    a = ap.parse_args()
    W, H = a.width, a.height
    if W > 255 or H > 255:
        sys.exit("ERROR: width and height must be <= 255 (stored in one byte each).")

    files = sorted(
        (p for p in glob.glob(os.path.join(a.src, "*"))
         if p.lower().endswith(EXT) and not os.path.basename(p).startswith(".")),
        key=lambda p: os.path.basename(p).lower(),
    )
    if not files:
        sys.exit("ERROR: no images found. Put a single images.zip into slideshow_src/ "
                 "(see slideshow_src/README.md).")

    tone = load_tone(a.tone)
    print("tone curve:", ("loaded from " + a.tone) if tone else "none (identity)")

    preview = []
    with open(a.out, "w") as f:
        f.write("#pragma once\n#include <stdint.h>\n")
        f.write(f"#define IMG_COUNT {len(files)}\n")
        for i, path in enumerate(files):
            white, label, mid = process(path, W, H, tone)
            data, black = pack(roll(white, W, a.xshift), W, H)
            pct = 100.0 * black / (W * H)
            note = ""
            if pct < 0.5:
                note = "  <-- ALMOST BLANK"
            elif pct > 99.5:
                note = "  <-- ALMOST ALL BLACK"
            name = os.path.basename(path)
            print(f"[{i + 1:2d}] {name}: {label}, mid {100 * mid:3.0f}%, black {pct:5.1f}%{note}")
            f.write(f"static const uint8_t img{i}[] = {{{','.join(map(str, data))}}};\n")
            preview.append((name, label.split(" ")[0], white))
        f.write("static const uint8_t* const images[IMG_COUNT] = {"
                + ",".join(f"img{i}" for i in range(len(files))) + "};\n")

    if a.preview:
        make_preview(preview, W, H, a.preview)
        print("preview sheet ->", a.preview)
    print(f"{len(files)} images -> {a.out} ({W}x{H}, xshift={a.xshift})")


if __name__ == "__main__":
    main()
