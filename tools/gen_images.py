import sys, glob, os
from PIL import Image, ImageOps, ImageChops

src, out = sys.argv[1], sys.argv[2]
W = int(sys.argv[3]) if len(sys.argv) > 3 else 200
H = int(sys.argv[4]) if len(sys.argv) > 4 else 200
XSHIFT = int(sys.argv[5]) if len(sys.argv) > 5 else 16
files = sorted(glob.glob(f"{src}/*.png") + glob.glob(f"{src}/*.jpg"))
if not files:
    sys.exit("no images in " + src)

def load_gray(path):
    im = ImageOps.exif_transpose(Image.open(path))
    if im.mode in ("RGBA", "LA", "P"):                     # прозрачность -> белый фон
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    g = ImageOps.fit(im.convert("L"), (W, H))
    return ImageOps.autocontrast(g, cutoff=1)              # растянуть контраст

rb = (W + 7) // 8
with open(out, "w") as f:
    f.write("#pragma once\n#include <stdint.h>\n")
    f.write(f"#define IMG_COUNT {len(files)}\n")
    for i, p in enumerate(files):
        g = ImageChops.offset(load_gray(p), XSHIFT, 0)     # компенсация сдвига панели
        px = g.convert("1").load()                         # Floyd-Steinberg
        black = 0
        data = [W, H]
        for y in range(H):
            for bx in range(rb):
                b = 0
                for k in range(8):
                    x = bx * 8 + k
                    dark = x < W and px[x, y] == 0
                    black += dark
                    b = (b << 1) | (1 if dark else 0)
                data.append(b)
        pct = 100.0 * black / (W * H)
        note = "  <-- ПОЧТИ ПУСТО" if pct < 0.5 else ("  <-- ПОЧТИ ВСЁ ЧЁРНОЕ" if pct > 99.5 else "")
        print(f"[{i+1:2d}] {os.path.basename(p)}: black {pct:5.1f}%{note}")
        f.write(f"static const uint8_t img{i}[] = {{{','.join(map(str, data))}}};\n")
    f.write("static const uint8_t* const images[IMG_COUNT] = {"
            + ",".join(f"img{i}" for i in range(len(files))) + "};\n")
print(f"{len(files)} images -> {out} (xshift={XSHIFT})")
