import sys, glob
from PIL import Image
src, out = sys.argv[1], sys.argv[2]
W = H = 200
files = sorted(glob.glob(f"{src}/*.png"))
with open(out, "w") as f:
    f.write(f"#pragma once\n#include <stdint.h>\n#define IMG_COUNT {len(files)}\n")
    f.write(f"static const uint8_t images[IMG_COUNT][{W*H//8}] = {{\n")
    for p in files:
        im = Image.open(p).convert("L").resize((W, H)).convert("1")  # Floyd–Steinberg
        px = im.load(); data = []
        for y in range(H):
            for x in range(0, W, 8):
                b = 0
                for k in range(8):
                    b = (b << 1) | (1 if px[x+k, y] else 0)  # 1 = белый; MSB слева
                data.append(b)
        f.write("{" + ",".join(map(str, data)) + "},\n")
    f.write("};\n")
