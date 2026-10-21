# Mac display profile for the Xiaomi wireless display (AirPlay receiver)

**Problem** (measured 2026-10-12): com.xiaomi.miralink draws the H.264 stream through its own GL window
and the YUV->RGB step is done as BT.601 limited range, while the Mac sends BT.709 full range.
Result on the tablet: crushed blacks (#101010 -> 0), clipped whites (#EBEBEB -> 252), boosted greens.

**Fix**: a calibrated LUT display profile `XiaomiPadAirPlayCalibrated.icc`, assigned on the Mac to the
"Xiaomi Pad 8 Pro" AirPlay display only.
- Matrix/TRC-only profiles have no effect (the AirPlay encoder converts back to its own colour space).
  The B2A0 LUT does take effect, but adds an unpredictable transform, so the profile is calibrated in a closed loop.
- Result: grey error mean 5.8 -> 2.5 (max 17 -> 6), colour patch error mean 9.4 -> 7.9.
  Fully saturated primaries can't be fixed (would need negative values).

## Use
```
swift setprofile.swift ~/Library/ColorSync/Profiles/XiaomiPadAirPlayCalibrated.icc   # assign
swift setprofile.swift reset                                                          # back to the default
```
Or: System Settings -> Displays -> Xiaomi Pad 8 Pro -> Color profile.

## Recalibrate
1. Open `ramp.html` (via `python3 -m http.server`) on the Xiaomi display, positioned like the Safari window at {1512,908,3111,1878}.
2. `./measure.sh <dir> rN` -> `<dir>/rN.txt` (Mac display 3 + tablet `adb screencap`).
3. `make_icc_iter.py curve.json <dir>/rN.txt new_curve.json out.icc colour_matrix.json`, assign, measure again.
   Damp (average the old and new curve) if it overshoots.

## Update

The real cause turned out to be HWUI rendering the receiver window with Skia/Vulkan. With
`debug.hwui.renderer=skiagl` on the tablet (now built into product; `hyperos/magisk/hwui_gl/`) and **no**
profile on the Mac, grey and colour errors drop to 3.9 / 3.9. LUT profiles desaturate saturated colours, so
they are kept only as an option (`XiaomiPadAirPlayGL_shadows.icc` lifts the shadows slightly).
