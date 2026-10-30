#!/usr/bin/env python3
"""Convert images to bitmaps (1-bit black/white or 2-bit 4-color) as a C header.

Usage:
  gen_images.py <src_dir> <out_header> [width] [height] [xshift]
                [--tone tone_curve.json] [--palette palette.json] [--preview preview.png]

Per-image options are file name suffixes (see slideshow_src/README.md):
  _bw _color          force the 1-bit or the 4-color format (default: automatic)
  _thr _atk _fs _ord  dithering algorithm for 1-bit images (default: automatic)
  _inv                invert
  _raw                image is already 1-bit at panel size, use as-is

Image format (all numbers little endian):
  byte 0      format: 1 = 1 bit/pixel, 2 = 2 bits/pixel
  bytes 1-2   width, bytes 3-4 height
  then rows, MSB first.
  format 1: bit 1 = black pixel
  format 2: code 0 = white, 1 = black, 2 = red, 3 = yellow
"""
import argparse
import glob
import json
import os
import sys
import zlib

from PIL import Image, ImageDraw, ImageFont, ImageOps

EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
ALGOS = ("thr", "atk", "fs", "ord")
COLOR_SHARE_MIN = 0.10      # share of strongly colored pixels above which an image is stored as color
CHROMA_MIN = 100            # max(R,G,B) - min(R,G,B) above which a pixel counts as colored

KERNEL_FS = [(1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16)]
KERNEL_ATK = [(1, 0, 1 / 8), (2, 0, 1 / 8), (-1, 1, 1 / 8),
              (0, 1, 1 / 8), (1, 1, 1 / 8), (0, 2, 1 / 8)]

# Colors of the panel as a camera sees them (sRGB). Nominal values, replaced by palette.json.
DEFAULT_PALETTE = {
    "white": [205, 205, 198],
    "black": [45, 45, 45],
    "red": [175, 55, 40],
    "yellow": [205, 180, 40],
}
PALETTE_ORDER = ("white", "black", "red", "yellow")        # = pixel codes 0..3
PREVIEW_COLORS = [(255, 255, 255), (0, 0, 0), (200, 30, 30), (240, 210, 0)]


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


def load_palette(path):
    pal = dict(DEFAULT_PALETTE)
    if path and os.path.exists(path):
        with open(path) as f:
            pal.update(json.load(f))
        print("palette: loaded from", path)
    else:
        print("palette: nominal values (no palette file)")
    return pal


def palette_rel(pal):
    """Palette colors as linear RGB relative to the panel: black = 0, white = 1."""
    w = [_srgb_to_linear(v) for v in pal["white"]]
    k = [_srgb_to_linear(v) for v in pal["black"]]
    out = []
    for name in PALETTE_ORDER:
        lin = [_srgb_to_linear(v) for v in pal[name]]
        out.append([min(1.0, max(0.0, (lin[i] - k[i]) / max(1e-6, w[i] - k[i]))) for i in range(3)])
    return out


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


def dither_color(img, W, H, lut, pal):
    """Serpentine Floyd-Steinberg towards the 4 panel colors. Returns rows of codes 0..3."""
    px = img.load()
    R = [[0.0] * (W + 2) for _ in range(H + 1)]
    G = [[0.0] * (W + 2) for _ in range(H + 1)]
    B = [[0.0] * (W + 2) for _ in range(H + 1)]
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            R[y][x], G[y][x], B[y][x] = lut[r], lut[g], lut[b]
    out = [[0] * W for _ in range(H)]
    for y in range(H):
        rev = y & 1
        xs = range(W - 1, -1, -1) if rev else range(W)
        for x in xs:
            r = min(1.0, max(0.0, R[y][x]))
            g = min(1.0, max(0.0, G[y][x]))
            b = min(1.0, max(0.0, B[y][x]))
            best, bd = 0, 1e9
            for i, (pr, pg, pb) in enumerate(pal):
                d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
                if d < bd:
                    bd, best = d, i
            out[y][x] = best
            er, eg, eb = r - pal[best][0], g - pal[best][1], b - pal[best][2]
            for dx, dy, w in KERNEL_FS:
                xx = x + (-dx if rev else dx)
                if 0 <= xx < W:
                    R[y + dy][xx] += er * w
                    G[y + dy][xx] += eg * w
                    B[y + dy][xx] += eb * w
    return out


def parse_flags(path):
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    toks = set(stem.split("_"))
    algo = next((a for a in ALGOS if a in toks), None)
    fmt = "bw" if "bw" in toks else ("color" if "color" in toks else None)
    return algo, ("inv" in toks), ("raw" in toks), fmt


def load_rgb(path, W, H):
    im = ImageOps.exif_transpose(Image.open(path))
    if im.mode in ("RGBA", "LA", "P"):                    # transparency -> white
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    return ImageOps.fit(im.convert("RGB"), (W, H))         # scale + center-crop


def load_gray(path, W, H):
    return load_rgb(path, W, H).convert("L")


def stretch_rgb(im):
    """Stretch the contrast of all channels together (keeps the hues)."""
    hist = im.convert("L").histogram()
    cut = sum(hist) * 0.01
    lo, acc = 0, 0
    for i in range(256):
        acc += hist[i]
        if acc > cut:
            lo = i
            break
    hi, acc = 255, 0
    for i in range(255, -1, -1):
        acc += hist[i]
        if acc > cut:
            hi = i
            break
    if hi - lo < 16:
        return im
    lut = [min(255, max(0, int(round((v - lo) * 255.0 / (hi - lo))))) for v in range(256)]
    return im.point(lut * 3)


def color_share(im, W, H):
    px = im.load()
    n = 0
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            if max(r, g, b) - min(r, g, b) > CHROMA_MIN:
                n += 1
    return n / float(W * H)

LAST_STATS = [0.0, 0.0, 0.0]


def color_stats(im, W, H):
    """Extra numbers for tuning the color/bw decision: chroma shares and hue diversity."""
    import colorsys
    px = im.load()
    n30 = n60 = 0
    bins = [0] * 12
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            c = max(r, g, b) - min(r, g, b)
            if c > 30:
                n30 += 1
                h = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)[0]
                bins[int(h * 12) % 12] += 1
                if c > 60:
                    n60 += 1
    if n30 == 0:
        return 0.0, 0.0, 0.0
    best = max(bins[i] + bins[(i - 1) % 12] + bins[(i + 1) % 12] for i in range(12))
    return n30 / float(W * H), n60 / float(W * H), 1.0 - best / float(n30)

def process(path, W, H, tone, pal_rel):
    """Returns (kind, matrix, label, mid-tone share, colorfulness). kind 1 = bw, 2 = color."""
    algo, inv, raw, fmt = parse_flags(path)
    if raw:
        px = load_gray(path, W, H).load()
        white = [[(px[x, y] >= 128) != inv for x in range(W)] for y in range(H)]
        return 1, white, "raw", 0.0, 0.0

    rgb = load_rgb(path, W, H)
    share = color_share(rgb, W, H)
    LAST_STATS[:] = color_stats(rgb, W, H)
    use_color = (fmt == "color") or (fmt is None and share > COLOR_SHARE_MIN)
    if inv:
        rgb = ImageOps.invert(rgb)

    lut = [coverage_for(LIN[v], tone) for v in range(256)]
    if use_color:
        rgb = stretch_rgb(rgb)
        pal_t = [[coverage_for(c, tone) for c in col] for col in pal_rel]
        return 2, dither_color(rgb, W, H, lut, pal_t), "color", 0.0, share

    gray = ImageOps.autocontrast(rgb.convert("L"), cutoff=1)
    hist = gray.histogram()
    mid = sum(hist[64:192]) / float(W * H)
    chosen = algo or ("atk" if mid < 0.08 else "fs")        # fs for everything except near-binary images
    px = gray.load()
    cov = [[lut[px[x, y]] for x in range(W)] for y in range(H)]
    white = dither(cov, W, H, chosen)
    return 1, white, (chosen if algo else chosen + " (auto)"), mid, share


def roll(mat, W, s):
    s %= W
    if s == 0:
        return mat
    return [row[W - s:] + row[:W - s] for row in mat]


def header(fmt, W, H):
    return [fmt, W & 255, W >> 8, H & 255, H >> 8]


def pack1(white, W, H):
    rb = (W + 7) // 8
    data = header(1, W, H)
    for row in white:
        for bx in range(rb):
            b = 0
            for k in range(8):
                x = bx * 8 + k
                b = (b << 1) | (1 if (x < W and not row[x]) else 0)
            data.append(b)
    return data


def pack2(codes, W, H):
    rb = (W + 3) // 4
    data = header(2, W, H)
    for row in codes:
        for bx in range(rb):
            b = 0
            for k in range(4):
                x = bx * 4 + k
                b = (b << 2) | (row[x] if x < W else 0)
            data.append(b)
    return data


def to_preview(kind, mat, W, H):
    im = Image.new("RGB", (W, H))
    px = im.load()
    for y in range(H):
        for x in range(W):
            if kind == 1:
                px[x, y] = (255, 255, 255) if mat[y][x] else (0, 0, 0)
            else:
                px[x, y] = PREVIEW_COLORS[mat[y][x]]
    return im


def make_preview(items, W, H, path):
    cols = 6
    font = ImageFont.load_default()
    cw, chh = W + 8, H + 24
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * chh), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for i, (name, label, im) in enumerate(items):
        x0 = (i % cols) * cw + 4
        y0 = (i // cols) * chh + 4
        sheet.paste(im, (x0, y0 + 14))
        d.text((x0, y0), f"{i + 1:02d} {name[:18]} {label}"[:34], fill=(0, 0, 0), font=font)
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser(description="Convert images to bitmaps (C header).")
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("width", nargs="?", type=int, default=200)
    ap.add_argument("height", nargs="?", type=int, default=200)
    ap.add_argument("xshift", nargs="?", type=int, default=0)
    ap.add_argument("--tone", default=None)
    ap.add_argument("--palette", default=None)
    ap.add_argument("--preview", default=None)
    a = ap.parse_args()
    W, H = a.width, a.height

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
    pal_rel = palette_rel(load_palette(a.palette))

    preview = []
    total = n_bw = n_color = 0
    with open(a.out, "w") as f:
        f.write("#pragma once\n#include <stdint.h>\n")
        f.write(f"#define IMG_COUNT {len(files)}\n")
        for i, path in enumerate(files):
            kind, mat, label, mid, share = process(path, W, H, tone, pal_rel)
            rolled = roll(mat, W, a.xshift)
            data = pack1(rolled, W, H) if kind == 1 else pack2(rolled, W, H)

            if kind == 1:
                black = sum(1 for row in mat for v in row if not v)
                pct = 100.0 * black / (W * H)
                stat = f"black {pct:5.1f}%"
                note = "  <-- ALMOST BLANK" if pct < 0.5 else ("  <-- ALMOST ALL BLACK" if pct > 99.5 else "")
                n_bw += 1
            else:
                cnt = [0, 0, 0, 0]
                for row in mat:
                    for c in row:
                        cnt[c] += 1
                n = float(W * H)
                stat = f"black {100 * cnt[1] / n:4.1f}% red {100 * cnt[2] / n:4.1f}% yellow {100 * cnt[3] / n:4.1f}%"
                note = "  <-- ALMOST BLANK" if cnt[0] == W * H else ""
                n_color += 1

            payload = bytes(data[5:])
            co = zlib.compressobj(9, zlib.DEFLATED, -12)
            comp = len(co.compress(payload) + co.flush())
            total += len(data)
            name = os.path.basename(path)
            c30, c60, hue = LAST_STATS
            print(f"[{i + 1:2d}] {name}: {label}, colorfulness {100 * share:3.0f}%, "
                  f"c30 {100 * c30:3.0f}% c60 {100 * c60:3.0f}% hue {100 * hue:3.0f}%, {stat}, "
                  f"{len(data)} B, deflate {100.0 * comp / len(payload):.0f}%{note}")

            f.write(f"static const uint8_t img{i}[] = {{{','.join(map(str, data))}}};\n")
            preview.append((name, label.split(" ")[0], to_preview(kind, mat, W, H)))
        f.write("static const uint8_t* const images[IMG_COUNT] = {"
                + ",".join(f"img{i}" for i in range(len(files))) + "};\n")

    if a.preview:
        make_preview(preview, W, H, a.preview)
        print("preview sheet ->", a.preview)
    print(f"{len(files)} images ({n_bw} b/w, {n_color} color), {total} bytes of flash -> {a.out} "
          f"({W}x{H}, xshift={a.xshift})")


if __name__ == "__main__":
    main()
