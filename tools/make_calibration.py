#!/usr/bin/env python3
"""Make test archives for the slideshow.

  python tools/make_calibration.py tone                    -> cal_tone.zip
  python tools/make_calibration.py compare a.png b.png ... -> compare.zip
"""
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
    # 17 steps of white fraction + extra white/black references
    levels = [i / 16 for i in range(17)] + [1.0, 0.0, 1.0]
    for idx, g in enumerate(levels):
        r, c = divmod(idx, COLS)
        white = diffuse([[g] * cw for _ in range(ch)], cw, ch, KERNEL_FS, True)
        cell = Image.new("L", (cw, ch))
        cell.putdata([255 if v else 0 for row in white for v in row])
        img.paste(cell, (c * cw, r * ch))
    ImageDraw.Draw(img).rectangle([0, 0, W - 1, H - 1], outline=0, width=3)
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


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "tone":
        save_zip("cal_tone.zip", [("00_cal_raw.png", tone_slide())])
    elif len(sys.argv) >= 3 and sys.argv[1] == "compare":
        compare(sys.argv[2:], "compare.zip")
    else:
        sys.exit(__doc__)
