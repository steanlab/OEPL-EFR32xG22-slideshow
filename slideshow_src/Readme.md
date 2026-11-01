# Slideshow image set

This folder holds the images that get built into the firmware.
Put **exactly one ZIP archive** here. Do not delete this folder.

## How it works

On every build, GitHub Actions unpacks the ZIP, scales and center-crops each
image to 200×200 px, converts it for the panel (black and white, or four
colors), compresses it when that saves space, and embeds it in the firmware.
Flash the resulting `.hex` file to the tag. A contact sheet of all converted
slides (`preview.png`) is attached to the build as an artifact, so you can
check the result before flashing.

## Archive rules

- **One ZIP only.** The name does not matter (for example `images.zip`).
  If the folder contains more than one ZIP, the build stops with an error.
- **To change the image set**, delete the old ZIP and upload a new one, or
  upload a ZIP with the same file name to replace it. Then commit. The build
  starts automatically.
- Put the image files in the ZIP itself, not inside a subfolder. Subfolders
  are flattened, so every file name must be unique.
- Supported formats: PNG, JPG/JPEG, WebP, BMP.
- Hidden files (names starting with a dot) and `__MACOSX` junk are ignored.

## File names and order

- Images are sorted **alphabetically by file name** (case-insensitive).
  Use zero-padded numbers so the order is what you expect:
  `00_title.png`, `01.png`, `02.png`, ..., `10.png`, `11.png`.
  Without padding, `10.png` would come before `2.png`.
- The **first file** (`00_...`) is the **title slide**. It is shown once after
  power-up or reset and stays for 15 seconds. It is not part of the regular
  rotation.
- All other images are shown in **random order without repeats** (the order is
  reshuffled each time every image has been shown), one every 2 hours by
  default.
- Tapping a phone on the tag's NFC area (or pressing the button, on tags that
  have one) skips to the next image.

## Image guidelines

**Size and format**
- The display is 200×200 px, so square images work best. Other shapes are
  center-cropped to a square.
- For the best result, resize to exactly 200×200 yourself (for example with
  *Bicubic Sharper* in Photoshop). Images that already have the right size are
  not resampled again.
- Use 8-bit sRGB PNG without transparency. Transparent areas are filled with
  white. Resolution (dpi) does not matter, only pixels.
- Do not dither or reduce colors yourself. The converter does it with a
  panel-specific tone curve.

**Tone and detail**
- The panel compresses contrast: shadows merge into black. Keep the darkest
  details lighter than about 10% gray and add some local contrast
  (sharpen slightly *after* downscaling).
- Remove noise and JPEG artifacts before downscaling. Noise is amplified by
  dithering and makes the image larger in flash.
- Lines thinner than 1–2 px are lost. Text is readable from about 12 px high.
- Very light or low-contrast images can end up almost blank. The build log
  warns about slides that are almost blank or almost all black.

**Color**
- The panel shows black, white, red, and yellow. Warm tones (reds, yellows,
  browns, skin) and logos or posters in these colors work best. Blues and
  greens turn into dark and gray tones.
- The converter decides per image whether to store it in color or in black
  and white. An image is stored in color if it contains a noticeable share of
  clearly colored pixels (roughly 5% or more). Gray photos therefore stay
  black and white. Toned or sepia engravings can go either way: try both with
  the `_bw` and `_color` suffixes and keep the one you like better.

## Per-image options (file name suffixes)

Add one or more of these words to a file name, separated by underscores,
anywhere after the leading number: `05_goya_color.png`, `07_inv_fs.png`.
Without any suffix the converter chooses automatically.

| Suffix | Meaning |
|---|---|
| `_bw` | Force black and white (1 bit per pixel, 5 KB before compression). |
| `_color` | Force the 4-color mode (black, white, red, yellow; 10 KB before compression). |
| `_fs` | Black-and-white dithering: serpentine Floyd–Steinberg in linear light. The default for almost every black-and-white image. |
| `_atk` | Atkinson dithering. Used automatically only for nearly two-tone images (line art, solid shapes). On tonal images it looks grainy and dark. |
| `_thr` | Hard threshold, no dithering. High contrast, loses detail. For clean line art and text. |
| `_ord` | Ordered (Bayer 8×8) dithering. Visible regular pattern, not recommended. |
| `_inv` | Invert the image (negative). |
| `_raw` | The image is already black and white at panel size and is used as-is. |
| `_raw4` | The image is already dithered with the four panel colors (black, white, red `200,30,30`, yellow `240,210,0`) and is used as-is. Used by the comparison archives of `make_calibration.py`. |
| `_v1`, `_v2` | Choose the color dithering method for this image: `_v1` is the older method, `_v2` the newer one. The default for images without a suffix is set by `--color-mode` in the workflow. |

The `_fs`, `_atk`, `_thr`, and `_ord` suffixes affect black-and-white images
only. The build log lists every slide with the format and method that were
used.

## Tone calibration

E-paper black dots spread into neighboring white dots, so midtones look
darker than they should. `tools/tone_curve.json` stores the measured response
of the panel, and the converter compensates for it automatically.

To recalibrate (different panel, lighting, or batch):
1. `python make_calibration.py tone` creates `cal_tone.zip`.
2. Put it into `slideshow_src/` instead of your images, build, and flash.
3. Photograph the panel in even light and crop to the outer edge of the black frame.
4. `python calibrate_tone.py photo.jpg` writes `tone_curve.json`. Do it twice and
   average the two curves (measurements differ by a few percent).
5. Upload the file to `tools/` and restore your image archive.

## Limits

- Slide sizes: a black-and-white slide takes up to 5 KB and a color slide up
  to 10 KB. Compression (used automatically when it saves at least 10%)
  typically reduces this to about 4–7 KB.
- Free flash for slides is about 257 KB, so roughly 40–48 slides fit,
  depending on the content. The build log prints the total size of all slides
  and warns above the budget (240,000 bytes, set with `--budget` in the
  workflow). If you add too many, the build can also fail with a message like
  `region 'FLASH' overflowed`. Remove a few images and try again.
- The GitHub web upload limit is 25 MB per file.

## Creating the ZIP

Select the image files themselves (not their parent folder) and compress them:
Windows: right-click → *Send to* → *Compressed (zipped) folder*.
macOS: right-click → *Compress*. Linux: `zip images.zip 0*.png 1*.png`.

## Privacy

If this repository is public, everything you upload here is public, including
the history of earlier ZIPs. Do not upload private photos.
