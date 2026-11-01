#!/usr/bin/env python3
"""Make test archives for the slideshow.

  python make_calibration.py tone                    -> cal_tone.zip
  python make_calibration.py palette                 -> cal_palette.zip
  python make_calibration.py compare a.png b.png ... -> compare.zip
  python make_calibration.py colorcmp a.png b.png .. -> colorcmp.zip  (3 color methods per image)
"""
import os
import sys
import zipfile
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from gen_images import KERNEL_FS, diffuse, load_gray

COLS, ROWS = 5, 4
W = H = 200


def tone_slide():
    cw, ch = W // COLS, H // ROWS                       # 40 x 50 px cells
    img = Image.new("L", (W, H), 255)
    levels = [i / 16 for i in range(17)] + [1.0, 0.0, 1.0]
    for idx, g in enumerate(levels):
        r, c = divmod(idx, COLS)
        white = diffuse([[g] * cw for _ in range(ch)], cw, ch, KERNEL_FS, True)
        cell = Image.new("L", (cw, ch))
        cell.putdata([255 if v else 0 for row in white for v in row])
        img.paste(cell, (c * cw, r * ch))
    ImageDraw.Draw(img).rectangle([0, 0, W - 1, H - 1], outline=0, width=3)
    return img


def palette_slide():
    """Four solid quadrants: white / black on top, red / yellow at the bottom."""
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    half = W // 2
    d.rectangle([half, 0, W - 1, half - 1], fill=(0, 0, 0))
    d.rectangle([0, half, half - 1, H - 1], fill=(255, 0, 0))
    d.rectangle([half, half, W - 1, H - 1], fill=(255, 255, 0))
    d.rectangle([0, 0, W - 1, H - 1], outline=(0, 0, 0), width=3)
    return img


def save_zip(out, entries):
    with zipfile.ZipFile(out, "w") as z:
        for name, im in entries:
            buf = BytesIO()
            im.save(buf, "PNG")
            z.writestr(name, buf.getvalue())
    print(f"{out}: {len(entries)} slides")


def compare(files, out):
    algos = ["thr", "atk", "fs", "ord"]
    font = ImageFont.load_default()
    entries = []
    for k, path in enumerate(files, 1):
        for a in algos:
            im = load_gray(path, W, H)
            d = ImageDraw.Draw(im)
            d.rectangle([0, 0, 40, 13], fill=255)
            d.text((2, 1), f"{k}-{a}", fill=0, font=font)
            entries.append((f"{len(entries):02d}_c{k}_{a}.png", im))
    save_zip(out, entries)
    print("Labels on the slides: <image number>-<algorithm>")


def colorcmp(files, out):
    import gen_images as g
    tone = g.load_tone("tone_curve.json")
    nominal = g.palette_rel(g.load_palette(None))
    measured = g.palette_rel(g.load_palette("palette.json" if os.path.exists("palette.json") else None))
    variants = [("A", nominal, "old"), ("B", nominal, "v2"), ("C", measured, "v2")]
    font = ImageFont.load_default()
    entries = []
    for k, path in enumerate(files, 1):
        for tag, pal, mode in variants:
            kind, mat, _label, _mid, _stats = g.process(path, W, H, tone, pal, mode=mode, force_color=True)
            im = g.to_preview(kind, mat, W, H)
            d = ImageDraw.Draw(im)
            d.rectangle([0, 0, 24, 13], fill=(255, 255, 255))
            d.text((2, 1), f"{k}-{tag}", fill=(0, 0, 0), font=font)
            entries.append((f"{len(entries):02d}_c{k}_{tag}_raw4.png", im))
    save_zip(out, entries)
    print("Labels: <image number>-<variant>:")
    print("  A = old method + nominal palette (the look you liked)")
    print("  B = new method + nominal palette")
    print("  C = new method + measured palette")

def colorcmp2(files, out):
    import gen_images as g
    tone = g.load_tone("tone_curve.json")
    nominal = g.palette_rel(g.load_palette(None))
    variants = [("A", "old", 0.0, 1.0),     # old method (the reference)
                ("D", "v2", 0.6, 1.0),      # current favorite
                ("F", "v2", 0.6, 0.9),      # D with a little less grain
                ("G", "v2", 0.8, 1.0)]      # D with more tone correction (lighter)
    font = ImageFont.load_default()
    entries = []
    for k, path in enumerate(files, 1):
        for tag, mode, mix, gain in variants:
            g.V2_TONE_MIX = mix
            g.V2_ERR_GAIN = gain
            kind, mat, _l, _m, _s = g.process(path, W, H, tone, nominal, mode=mode, force_color=True)
            im = g.to_preview(kind, mat, W, H)
            d = ImageDraw.Draw(im)
            d.rectangle([0, 0, 24, 13], fill=(255, 255, 255))
            d.text((2, 1), f"{k}-{tag}", fill=(0, 0, 0), font=font)
            entries.append((f"{len(entries):02d}_c{k}_{tag}_raw4.png", im))
    save_zip(out, entries)
    print("Labels: <image number>-<variant>:")
    print("  A = old method, D = new method (current favorite),")
    print("  F = D with less grain, G = D with more tone correction (lighter)")
    
if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "tone":
        save_zip("cal_tone.zip", [("00_cal_raw.png", tone_slide())])
    elif len(sys.argv) >= 2 and sys.argv[1] == "palette":
        save_zip("cal_palette.zip", [("00_cal_palette_color.png", palette_slide())])
    elif len(sys.argv) >= 3 and sys.argv[1] == "compare":
        compare(sys.argv[2:], "compare.zip")
    elif len(sys.argv) >= 3 and sys.argv[1] == "colorcmp":
        colorcmp(sys.argv[2:], "colorcmp.zip")
    elif len(sys.argv) >= 3 and sys.argv[1] == "colorcmp2":
        colorcmp2(sys.argv[2:], "colorcmp2.zip")
    else:
        sys.exit(__doc__)
