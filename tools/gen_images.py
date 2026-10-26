import sys, glob
from PIL import Image, ImageOps

src, out = sys.argv[1], sys.argv[2]
W = int(sys.argv[3]) if len(sys.argv) > 3 else 200
H = int(sys.argv[4]) if len(sys.argv) > 4 else 200
files = sorted(glob.glob(f"{src}/*.png") + glob.glob(f"{src}/*.jpg"))
if not files:
    sys.exit("no images in " + src)

rb = (W + 7) // 8
with open(out, "w") as f:
    f.write("#pragma once\n#include <stdint.h>\n")
    f.write(f"#define IMG_COUNT {len(files)}\n")
    for i, p in enumerate(files):
        im = ImageOps.fit(Image.open(p).convert("L"), (W, H)).convert("1")
        px = im.load()
        data = [W, H]
        for y in range(H):
            for bx in range(rb):
                b = 0
                for k in range(8):
                    x = bx * 8 + k
                    b = (b << 1) | (1 if x < W and px[x, y] == 0 else 0)
                data.append(b)
        f.write(f"static const uint8_t img{i}[] = {{{','.join(map(str, data))}}};\n")
    f.write("static const uint8_t* const images[IMG_COUNT] = {"
            + ",".join(f"img{i}" for i in range(len(files))) + "};\n")
print(f"{len(files)} images -> {out}")
