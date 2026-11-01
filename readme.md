# EFR32xG22 e-paper slideshow (standalone, no AP, no radio)

Turns an OpenEPaperLink-compatible Solum EFR32xG22 tag into a standalone
e-paper photo frame. It shows a set of pictures, in black and white or in four
colors, and changes them on a timer. A phone tap on the tag's NFC area (or a
button press, on tags that have a button) skips to the next picture. No access
point and no radio are needed.

## Features

- Title slide (`00_*`) shown for 15 s after power-up, then the other slides in
  random order without repeats, one every 2 hours (configurable).
- NFC tap or short button press = next slide (red LED flash). Timed change
  flashes blue. Long button press pauses and resumes the automatic change.
- Black-and-white and four-color (black, white, red, yellow) slides, chosen
  automatically per image. Panel-specific tone curve and error-diffusion
  dithering give smooth tones.
- Slides are compressed and checked before they are drawn. A slide that cannot
  be decoded is skipped and the previous picture stays on the screen.
- Low-battery protection for one CR2450: at a critical level the tag stops
  refreshing the screen and flashes red every 10 minutes.
- Hardware watchdog restarts the tag if it ever freezes.
- Images are converted and built into the firmware by GitHub Actions. No local
  toolchain is needed. A contact sheet (`preview.png`) of all converted slides
  is attached to each build.
- One firmware for tags with and without a button.

User manual for the finished tag: [documentation/slideshow_man.md](documentation/slideshow_man.md)

## Supported hardware

| Tag | Display | Status |
|---|---|---|
| Solum EL016F5W4C, 1.6", 200×200, BWRY | JD controller driver | ✅ tested |
| Solum EL016F6W4A, 1.6", 200×200, BWRY | JD controller driver | ✅ tested |
| Other Solum EFR32xG22 tags | – | untested, see "Porting" |

Tested tags use the Silicon Labs EFR32BG22C224F512 (Cortex-M33, 512 KB flash,
32 KB RAM). The 4 Mbit external flash (Fudan Micro, JEDEC ID A1 28 13) is not
used by this firmware.

## Quick start

1. Fork this repository.
2. Put your images into one ZIP archive and place it into `slideshow_src/`
   (replace the existing archive). The first file in alphabetical order is the
   title slide, so name it `00_...`. Rules, file name suffixes, and image
   preparation tips are in [slideshow_src/Readme.md](slideshow_src/Readme.md).
3. Every commit to this branch starts the build. You can also start it with
   Actions → *Run workflow*.
4. Download the firmware artifact of the finished run and unpack it. The file
   to flash is `firmware/out/build/debug/EFR32xG22_OEPL.hex`. Look at the
   `preview.png` artifact to check how the slides will look.
5. Flash the tag (see below).

## Flashing

You need:
- Python 3 with [pyOCD](https://pyocd.io) (`pip install pyocd`, a virtual
  environment is recommended) and `gdb-multiarch`.
- A CMSIS-DAP probe. Tested: Raspberry Pi Pico running the *debugprobe*
  firmware.
- The Silicon Labs EFR32BG22 device family pack (`.pack` file), placed in the
  repository folder. The commands below use
  `SiliconLabs.GeckoPlatform_EFR32BG22_DFP.2025.12.1.pack`.
[CMSIS Packs](https://www.keil.arm.com/packs/): [SiliconLabs.GeckoPlatform_EFR32BG22_DFP.2025.12.1.pack](https://www.silabs.com/documents/public/cmsis-packs/SiliconLabs.GeckoPlatform_EFR32BG22_DFP.2025.12.1.pack) and [SiliconLabs.GeckoPlatform_EFR32FG22_DFP.2025.12.1.pack](https://www.silabs.com/documents/public/cmsis-packs/SiliconLabs.GeckoPlatform_EFR32FG22_DFP.2025.12.1.pack)
 
- Wires to the tag's SWD pads: SWDIO, SWCLK, GND, and 3V3 (the tag can also run
  from its own battery). The RESET wire is optional.

### A. The tag already runs OpenEPaperLink firmware (the bootloader is present)

Only the application at 0x6000 is replaced. The bootloader and the screen data
are kept. Start the debug server in one terminal:

    pyocd gdbserver --target efr32bg22c224f512im32 \
      --pack ./SiliconLabs.GeckoPlatform_EFR32BG22_DFP.2025.12.1.pack \
      -O frequency=100000 --persist

and in another one:

    gdb-multiarch
    (gdb) target remote localhost:3333
    (gdb) monitor reset
    (gdb) load firmware/out/build/debug/EFR32xG22_OEPL.hex
    (gdb) monitor reset
    (gdb) quit

Do not erase the whole chip. That removes the bootloader.

### B. A new tag with the original Solum firmware (debug-locked)

A tag that still has its original firmware is locked against debugging.
It must be unlocked first, and it needs the OpenEPaperLink bootloader.

1. **Save the user data (UD) area first.** It identifies the display of your
   tag. The unlock keeps it, but a copy is cheap insurance, and OpenEPaperLink
   developers can use it to support new tag variants:

       python3 reflash.py --dump-ud-bin ud_dump1.bin \
         --pack ./SiliconLabs.GeckoPlatform_EFR32BG22_DFP.2025.12.1.pack -v

   If you share the dump (for example in an issue of the OpenEPaperLink
   repository), you can describe it like this: *UD area (1024 bytes) read from
   an e-paper tag EL016F6W4A with EFR32xG22 while the device was debug-locked.
   Made before running a debug unlock (`-u`), which erases the flash but keeps
   UD.* The dump may contain identifiers of your tag. Share it only if you are
   fine with that.

2. **Unlock the tag.** This erases the original firmware **permanently**:

       python reflash.py -u \
         --pack ./SiliconLabs.GeckoPlatform_EFR32BG22_DFP.2025.12.1.pack -v

3. **Flash the latest OpenEPaperLink full image** (bootloader plus
   application) from `full_binaries/` to get the bootloader, which detects the
   display type:

       python reflash.py -e -f full_binaries/vNN/SOLUM_AUTODETECT_FULL_vNN.s37 \
         --pack ./SiliconLabs.GeckoPlatform_EFR32BG22_DFP.2025.12.1.pack -v

   Use the newest `vNN` folder. `python reflash.py -h` lists all options.

4. **Flash the slideshow** with the commands from part A.

### Connection problems

If pyOCD reports `Target not detected` or `No ACK`:
- Check power and the common ground, and keep the wires short.
- Try another USB port or cable. Re-solder or re-press the contacts. Remove
  flux residue with isopropyl alcohol.
- Lower the clock and, if the RESET wire is connected, connect under reset.
  Create a file `pyocd.yaml` in the folder where you run the commands:

      frequency: 25000
      connect_mode: under-reset

  (try `10000` if `25000` is still unstable).
- A tag in deep sleep does not answer on SWD. Remove its battery for 10 seconds
  and connect right after power-up.

## Configuration

Firmware settings are constants at the top of `firmware/oepl_slideshow.c`.
After a change, commit and let the build run.

| What | Constant | Default |
|---|---|---|
| Slide period (counted from the end of a refresh) | `SLIDE_PERIOD_MS` | 120 min |
| Title slide hold after power-up | `TITLE_HOLD_MS` | 15 s |
| NFC debounce | `TAP_IGNORE_MS` | 5 s |
| Long press threshold | `LONG_PRESS_MS` | 1.5 s |
| Long press action (1 previous slide, 2 title slide, 3 pause/resume) | `LONG_PRESS_ACTION` | 3 |
| Button level when pressed | `BTN_PRESSED_LEVEL` | 0 |
| Critical battery voltage | `BATT_CRIT_MV` | 2400 mV |
| Battery check period | `BATT_CHECK_PERIOD_MS` | 10 min |
| Flash the battery voltage at power-up (green) | `BATT_READOUT_AT_BOOT` | off |
| Watchdog and its limit for one processing step | `WATCHDOG_ENABLE`, `PROCESS_LIMIT_MS` | on, 150 s |

The image converter is called in the *Generate slideshow images* step of the
workflow. Its arguments are the panel size (`200 200`), the column shift
(`0`), the tone curve, the color dithering method (`--color-mode`), the preview
sheet, and the flash budget (`--budget`). Debug messages are disabled with
`GLOBAL_DEBUG_ENABLE=0` in `firmware/EFR32xG22_OEPL.slcp`.

## LED signals

| LED | Meaning |
|---|---|
| One short blue flash | Timed change |
| One short red flash | Manual change (NFC tap or short button press) |
| Five red flashes, repeating every 10 minutes | Critical battery, screen refreshes stopped |
| Two long red flashes | The slide could not be shown, the previous picture stays |
| Green flashes | Long button press (3 = paused, 1 = resumed) |

## Limits

- Roughly 40–48 slides fit (about 257 KB of flash for slides). Black-and-white
  slides take 4–5 KB, color slides 5–7 KB after compression.
- The slides are built for a 200×200 panel. A slide whose size does not match
  the panel is skipped (two long red flashes).
- NFC field detect is polled every 200 ms (the pin on port D cannot wake the
  MCU from sleep), which costs a little standby current. Standby current and
  battery life have not been measured.
- The radio is not built into this firmware, so there are no over-the-air
  updates. The tag is flashed over SWD.

## Tools

| File | Purpose |
|---|---|
| `tools/gen_images.py` | Image converter used by the build |
| `tools/make_calibration.py` | Makes test archives (`tone`, `palette`, `compare`, `colorcmp2`) for checking the panel and comparing methods on the tag |
| `tools/calibrate_tone.py` | Computes the tone curve from a photo of the `tone` test slide |
| `tools/tone_curve.json` | Measured tone response of the 1.6" panel |
| `tools/calibrate_palette.py` | Experimental: measures ink colors from photos. Palette values measured by a phone camera made the colors worse, so the converter uses nominal ink colors and this script is not used. |

## Porting to another panel

1. Set the panel size in the converter arguments of the workflow. Slides may be
   larger than 255 px, because the slide header stores sizes in 16 bits.
2. Draw a test slide with a frame and an asymmetric letter. Flash it and check
   that nothing is shifted, wrapped, or mirrored.
3. Recalibrate the tone curve for the new panel (see
   `slideshow_src/Readme.md`).
4. The slideshow reads slide rows directly from flash and hands them to the
   display driver (`slideshow_render_line` in `firmware/oepl_display.c`, used
   through `RENDER_LINE` in the driver). Only the JD driver (BWRY panels) does
   this so far. Other drivers need the same small change.

## How it works

The `SLIDESHOW` define makes `firmware/oepl_slideshow.c` replace the
OpenEPaperLink application loop. A slide is decompressed into RAM and checked
before the panel is touched, then the existing JD display driver draws it row
by row. Sleep timers drive the period, the battery check, and the long-press
timing. The NFC field-detect and button interrupts are taken from the existing
OpenEPaperLink hardware layer. The radio libraries and the protocol code are
not part of the build.

Slide format (little endian): format byte (1 = 1 bit per pixel, 2 = 2 bits per
pixel, +0x80 = compressed), 16-bit width, 16-bit height, then the rows. Color
slides use the codes 0 white, 1 black, 2 red, 3 yellow. Compressed slides
carry a Fletcher-16 checksum and a raw deflate stream.

## Warning

Unlocking a Solum tag for SWD erases the original firmware permanently.
You do this at your own risk; there is no warranty.

## License and credits

Based on [OpenEPaperLink / Tag_FW_EFR32xG22](https://github.com/OpenEPaperLink/Tag_FW_EFR32xG22).
Licensed under CC BY-NC-SA 4.0 (same as upstream); files from the Silicon Labs
SDK keep their own license headers.

The original firmware documentation and the OpenEPaperLink project are described in the
[upstream repository](https://github.com/OpenEPaperLink/Tag_FW_EFR32xG22) and in the
[OpenEPaperLink wiki](https://github.com/OpenEPaperLink/OpenEPaperLink/wiki).
