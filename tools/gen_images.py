#!/usr/bin/env python3
"""Convert images to 1-bit bitmaps and write them as a C header.

Usage: gen_images.py <src_dir> <out_header> [width] [height] [xshift]

  src_dir     folder with the images (PNG, JPG/JPEG, WebP, BMP)
  out_header  C header to generate (firmware/images.h)
  width       panel width in px   (default 200)
  height      panel height in px  (default 200)
  xshift      columns to shift the picture right with wrap-around, to
              compensate for the panel's own shift (default 16 for the
              Solum EL016F5W4C)

Bitmap format of every image: [width, height, rows...], each row is
ceil(width / 8) bytes, MSB first, bit 1 = black pixel.
"""
import glob
import os
import sys

from PIL import Image, ImageChops, ImageOps

EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

src = sys.argv[1]
out = sys.argv[2]
W = int(sys.argv[3]) if len(sys.argv) > 3 else 200
H = int(sys.argv[4]) if len(sys.argv) > 4 else 200
XSHIFT = int(sys.argv[5]) if len(sys.argv) > 5 else 16

if W > 255 or H > 255:
    sys.exit("ERROR: width and height must be <= 255 (they are stored in one byte each).")

files = sorted(
    (p for p in glob.glob(os.path.join(src, "*"))
     if p.lower().endswith(EXT) and not os.path.basename(p).startswith(".")),
    key=lambda p: os.path.basename(p).lower(),
)
if not files:
    sys.exit("ERROR: no images found. Put a single images.zip into slideshow_src/ "
             "(see slideshow_src/README.md).")


def load_gray(path):
    im = ImageOps.exif_transpose(Image.open(path))      # honor phone rotation
    if im.mode in ("RGBA", "LA", "P"):                   # transparency -> white background
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    gray = ImageOps.fit(im.convert("L"), (W, H))         # scale + center-crop
    return ImageOps.autocontrast(gray, cutoff=1)         # stretch contrast


row_bytes = (W + 7) // 8

with open(out, "w") as f:
    f.write("#pragma once\n#include <stdint.h>\n")
    f.write(f"#define IMG_COUNT {len(files)}\n")

    for i, path in enumerate(files):
        gray = ImageChops.offset(load_gray(path), XSHIFT, 0)   # panel shift compensation
        px = gray.convert("1").load()                          # Floyd-Steinberg dithering

        data = [W, H]
        black = 0
        for y in range(H):
            for bx in range(row_bytes):
                b = 0
                for k in range(8):
                    x = bx * 8 + k
                    dark = x < W and px[x, y] == 0
                    black += dark
                    b = (b << 1) | (1 if dark else 0)
                data.append(b)

        pct = 100.0 * black / (W * H)
        note = ""
        if pct < 0.5:
            note = "  <-- ALMOST BLANK"
        elif pct > 99.5:
            note = "  <-- ALMOST ALL BLACK"
        print(f"[{i + 1:2d}] {os.path.basename(path)}: black {pct:5.1f}%{note}")

        f.write(f"static const uint8_t img{i}[] = {{{','.join(map(str, data))}}};\n")

    f.write("static const uint8_t* const images[IMG_COUNT] = {"
            + ",".join(f"img{i}" for i in range(len(files))) + "};\n")

print(f"{len(files)} images -> {out} ({W}x{H}, xshift={XSHIFT})")
