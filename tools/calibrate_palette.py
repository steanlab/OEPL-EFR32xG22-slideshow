#!/usr/bin/env python3
"""Measure the real colors of the panel from photos of cal_palette.zip.

  python calibrate_palette.py photo1.jpg [photo2.jpg ...]   -> palette.json

Every photo is normalized by its own white and black patches (this removes the
differences in exposure and white balance between photos); the median over all
photos is used. Crop every photo to the OUTER edge of the black frame first.
Layout: top-left white, top-right black, bottom-left red, bottom-right yellow.
"""
import json
import statistics
import sys

from PIL import Image, ImageOps

NAMES = [("white", 0, 0), ("black", 1, 0), ("red", 0, 1), ("yellow", 1, 1)]


def _lin(v):
    c = v / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


LIN8 = [_lin(v) for v in range(256)]


def _srgb(c):
    c = min(1.0, max(0.0, c))
    v = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
    return int(round(255 * v))


def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def measure(path):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    w, h = im.size
    out = {}
    for name, qx, qy in NAMES:
        cw, ch = w / 2.0, h / 2.0
        box = (int(qx * cw + cw * 0.25), int(qy * ch + ch * 0.25),
               int(qx * cw + cw * 0.75), int(qy * ch + ch * 0.75))
        raw = im.crop(box).tobytes()
        n = len(raw) // 3
        s = [0.0, 0.0, 0.0]
        for i in range(0, len(raw), 3):
            s[0] += LIN8[raw[i]]
            s[1] += LIN8[raw[i + 1]]
            s[2] += LIN8[raw[i + 2]]
        out[name] = [v / n for v in s]
    return out


def fmt(v):
    return "[" + " ".join(f"{x:5.2f}" for x in v) + "]"


def main():
    paths = sys.argv[1:]
    if not paths:
        sys.exit(__doc__)
    shots = [measure(p) for p in paths]

    rels = []
    print("photo                          white-lum   red (rel R G B)         yellow (rel R G B)")
    for p, s in zip(paths, shots):
        w, k = s["white"], s["black"]
        if lum(w) - lum(k) < 0.03:
            print(f"{p[:30]:30s}  SKIPPED: too little contrast between white and black")
            continue
        rel = {n: [(s[n][i] - k[i]) / max(1e-6, w[i] - k[i]) for i in range(3)]
               for n in ("red", "yellow")}
        rels.append(rel)
        print(f"{p[:30]:30s}  {lum(w):7.3f}    {fmt(rel['red'])}    {fmt(rel['yellow'])}")
    if len(rels) < 2:
        sys.exit("ERROR: need at least 2 usable photos")

    med = {n: [statistics.median(r[n][i] for r in rels) for i in range(3)] for n in ("red", "yellow")}
    wl = [statistics.median(s["white"][i] for s in shots) for i in range(3)]
    kl = [statistics.median(s["black"][i] for s in shots) for i in range(3)]

    if not (lum(wl) > lum(kl) + 0.03):
        sys.exit("ERROR: white is not brighter than black. Check the crop and the orientation.")
    for n in ("red", "yellow"):
        spread = max(max(r[n][i] for r in rels) - min(r[n][i] for r in rels) for i in range(3))
        if spread > 0.25:
            print(f"WARNING: photos disagree on the {n} patch (spread {spread:.2f}); "
                  f"shoot again with fixed exposure and white balance")
    if med["red"][0] < 2.0 * max(med["red"][1], 0.01):
        print("WARNING: the red patch is not clearly red")
    if med["yellow"][2] > 0.5 * med["yellow"][0]:
        print("WARNING: the yellow patch is not clearly yellow")

    pal = {"white": [_srgb(c) for c in wl], "black": [_srgb(c) for c in kl]}
    for n in ("red", "yellow"):
        rel = [min(1.0, max(0.0, v)) for v in med[n]]
        pal[n] = [_srgb(kl[i] + rel[i] * (wl[i] - kl[i])) for i in range(3)]

    print()
    print("median over", len(rels), "photos (relative to the panel white/black, linear):")
    for n in ("red", "yellow"):
        print(f"  {n:7s} {fmt(med[n])}")
    print("palette:", pal)
    with open("palette.json", "w") as f:
        json.dump(pal, f)
    print("saved palette.json")


if __name__ == "__main__":
    main()
