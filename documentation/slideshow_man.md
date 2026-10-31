# Using your e-paper slideshow tag

This tag is a small digital picture frame. It shows a fixed set of pictures
and changes them by itself. It runs on one CR2450 coin cell. No app, Wi-Fi,
or cables are needed.

## What it does

- **Power-up.** When a battery is inserted, the LED flashes **blue** and the
  screen redraws the **title picture**. About 30 seconds later the slideshow starts.
- **Automatic change.** Every 60 minutes the LED flashes **blue** and the screen
  shows the next picture. Pictures come in random order, and every picture is
  shown once before any repeats. The title picture appears only after power-up.
- **Manual change.** Hold the back of your phone against the tag for one or two
  seconds (NFC must be turned on in your phone settings, and most phones only
  scan with the screen on). The LED flashes **red** to confirm, then the screen
  shows the next picture. No app is needed. Your phone may show an NFC
  notification; you can ignore it.

A screen refresh takes about 25 seconds. The picture flickers between black,
white, and colors while it updates. This is normal. Touches during a refresh
are ignored, and so are repeated touches within about 5 seconds.
The picture stays on the screen without power, so removing the battery does
not erase it.

## LED signals

| LED | Meaning |
|---|---|
| One short **blue** flash | Timed change. A new picture is about to be drawn. |
| One short **red** flash | Your touch was recognized. A new picture is about to be drawn. |
| **Five red** flashes in a row, repeating every 10 minutes (also after a touch) | The battery is critically low. The tag stops refreshing the screen and the last picture stays on display. Replace the battery. |
| **Two long red** flashes | The picture could not be shown. The previous picture stays on the screen. This should not happen in normal use. |

## Replacing the battery

Insert one fresh CR2450 coin cell with the correct polarity. The tag restarts
with the title picture.

## Tips

- If a touch does nothing, move the phone slowly over the tag to find the best
  spot, remove thick cases or metal objects, and make sure the previous
  refresh has finished.
- Faint traces of the previous picture are normal for e-paper and fade after
  the next refresh.
- In the cold the screen may refresh more slowly and look paler. Room
  temperature works best.
- Do not press on the screen or bend the tag.
