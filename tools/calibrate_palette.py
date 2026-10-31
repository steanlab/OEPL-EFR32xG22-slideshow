#!/usr/bin/env python3
"""Measure the real colors of the panel from photos of cal_palette.zip.

  python calibrate_palette.py photo1.jpg [photo2.jpg ...]   -> palette.json

Crop every photo to the OUTER edge of the black frame around the test image first.
Layout: top-left white, top-right black, bottom-left red, bottom-right yellow.
"""
import json
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
        px = list(im.crop(box).getdata())
        s = [0.0, 0.0, 0.0]
        for p in px:
            for i in range(3):
                s[i] += LIN8[p[i]]
        out[name] = [v / len(px) for v in s]
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    shots = [measure(p) for p in sys.argv[1:]]
    avg = {n: [sum(s[n][i] for s in shots) / len(shots) for i in range(3)] for n, _, _ in NAMES}

    if len(shots) > 1:
        for n, _, _ in NAMES:
            dev = max(abs(_srgb(s[n][i]) - _srgb(avg[n][i])) for s in shots for i in range(3))
            if dev > 12:
                print(f"WARNING: photos differ by up to {dev} levels on the {n} patch "
                      f"(uneven light, glare or different exposure)")

    w, k, r, y = avg["white"], avg["black"], avg["red"], avg["yellow"]
    if not (lum(w) > lum(y) > lum(r) > lum(k)):
        sys.exit("ERROR: expected brightness order white > yellow > red > black. "
                 "Check the crop, the orientation and the slide layout.")
    if max(_srgb(c) for c in w) > 250:
        print("WARNING: the white patch is overexposed; lock a lower exposure and shoot again")

    rel = {n: [(avg[n][i] - k[i]) / max(1e-6, w[i] - k[i]) for i in range(3)]
           for n in ("red", "yellow")}
    if rel["red"][0] < 2.0 * max(rel["red"][1], 0.01):
        print("WARNING: the red patch is not clearly red (check white balance and light)")
    if rel["yellow"][2] > 0.5 * rel["yellow"][0]:
        print("WARNING: the yellow patch is not clearly yellow")

    pal = {n: [_srgb(c) for c in avg[n]] for n, _, _ in NAMES}
    print("color        as seen by the camera (sRGB)     relative to panel white/black (linear)")
    for n, _, _ in NAMES:
        rl = rel.get(n, [1, 1, 1] if n == "white" else [0, 0, 0])
        print(f"{n:8s}     {pal[n]}      [{rl[0]:.2f} {rl[1]:.2f} {rl[2]:.2f}]")
    with open("palette.json", "w") as f:
        json.dump(pal, f)
    print("saved palette.json")


if __name__ == "__main__":
    main()
