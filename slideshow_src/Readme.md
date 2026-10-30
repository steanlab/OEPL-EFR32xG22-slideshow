# Slideshow image set

This folder holds the images that get built into the firmware.
Put **exactly one ZIP archive** here. Do not delete this folder.

## How it works

On every build, GitHub Actions unpacks the ZIP, scales and center-crops each
image to 200×200 px, converts it to black and white with dithering, and
embeds it in the firmware. Flash the resulting `.hex` file to the tag.

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
  power-up or reset and stays for 30 seconds. It is not part of the regular
  rotation.
- All other images are shown in **random order without repeats** (the order is
  reshuffled each time every image has been shown), one every hour by default.
- Tapping a phone on the tag's NFC area skips to the next image.

## Image guidelines

- The display is 200×200 px, so square images work best. Other shapes are
  center-cropped to a square.
- | `_bw` | Force black-and-white (1 bit per pixel, 5 KB). Use for sepia-toned engravings or photos that should stay monochrome. |
- | `_color` | Force the 4-color mode (black, white, red, yellow; 10 KB per slide). Without a suffix the converter decides by the share of strongly colored pixels. |
- High-contrast pictures, logos, and line art look best. Very light or
  low-contrast photos can end up almost blank.
- Transparent PNGs are placed on a white background.

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

- Each image takes about 5 KB of flash. Roughly 34 images fit with a safety
  margin. If you add too many, the build fails with a message like
  `region 'FLASH' overflowed`. Remove a few images and try again.
- The GitHub web upload limit is 25 MB per file.

## Creating the ZIP

Select the image files themselves (not their parent folder) and compress them:
Windows: right-click → *Send to* → *Compressed (zipped) folder*.
macOS: right-click → *Compress*. Linux: `zip images.zip 0*.png 1*.png`.

## Privacy

If this repository is public, everything you upload here is public, including
the history of earlier ZIPs. Do not upload private photos.
