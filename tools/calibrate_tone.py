#!/usr/bin/env python3
"""Measure the tone response of the panel from a photo of cal_tone.zip.

  python tools/calibrate_tone.py photo.jpg [tone_curve.json]

Crop the photo first to the OUTER edge of the black frame around the test image.
"""
import json
import sys

from PIL import Image, ImageOps

COLS, ROWS = 5, 4


def _lin(v):
    c = v / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


LIN8 = [_lin(v) for v in range(256)]


def cell_y(im, idx):
    w, h = im.size
    cw, ch = w / COLS, h / ROWS
    r, c = divmod(idx, COLS)
    box = (int(c * cw + cw * 0.25), int(r * ch + ch * 0.25),
           int(c * cw + cw * 0.75), int(r * ch + ch * 0.75))
    px = im.crop(box).getdata()
    tot = 0.0
    for (R, G, B) in px:
        tot += 0.2126 * LIN8[R] + 0.7152 * LIN8[G] + 0.0722 * LIN8[B]
    return tot / len(px)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    out = sys.argv[2] if len(sys.argv) > 2 else "tone_curve.json"
    im = ImageOps.exif_transpose(Image.open(sys.argv[1])).convert("RGB")
    y = [cell_y(im, i) for i in range(20)]
    yb = (y[0] + y[18]) / 2
    yw = (y[16] + y[17] + y[19]) / 3
    if yw - yb < 0.05:
        sys.exit("ERROR: too little contrast between white and black. Check the crop and lighting.")
    spread = (max(y[16], y[17], y[19]) - min(y[16], y[17], y[19])) / yw
    if spread > 0.15:
        print(f"WARNING: white patches differ by {100 * spread:.0f}% - uneven lighting or glare")

    g = [i / 16 for i in range(17)]
    m = [min(1.0, max(0.0, (y[i] - yb) / (yw - yb))) for i in range(17)]
    m[0], m[16] = 0.0, 1.0
    print("white fraction   measured brightness")
    for gi, mi in zip(g, m):
        print(f"   {gi:5.3f}            {mi:5.3f}")
    with open(out, "w") as f:
        json.dump({"g": [round(v, 4) for v in g], "m": [round(v, 4) for v in m]}, f)
    print("saved", out)


if __name__ == "__main__":
    main()
