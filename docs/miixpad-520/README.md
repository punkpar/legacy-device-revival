# Lenovo MIIX 520: an honest negative result

This one isn't orphaned by a dead cloud. It's orphaned by silicon Linux never solved: the fingerprint sensor and touchscreen are both driverless, and one bring-up trick bricks the EC. Written down so you don't repeat the week it cost us.

2018 detachable (i5-8250U). Method: none that works. [`FINGERPRINT.md`](FINGERPRINT.md) and [`TOUCHSCREEN.md`](TOUCHSCREEN.md) record exactly where each path dies.

| | |
|---|---|
| Model | MIIX 520-12IKB (machine type **20M3**) |
| BIOS | `6NCN39WW`, dated 2019-10-10 |
| Board | `LNVNB161216` |
| CPU | Intel Core i5-8250U (Kaby Lake, 4C/8T) |
| Tested on | Fedora 44, KDE Plasma, kernel **7.2.9-200.fc44** |
| Previous kernel tested | 7.0.12-201.fc44 |

Both touch-capable subsystems (the **fingerprint sensor** and the **on-display
touchscreen**) work under the Lenovo OEM drivers on the Windows side. **Neither
works on Linux.** What this directory documents is *why*, how far the reverse
engineering got, and one hardware hazard that will cost you your fan control if
you walk into it blind.

---

## Status at a glance

| Subsystem | Device | Bus | Linux | Windows |
|---|---|---|---|---|
| Fingerprint | Synaptics **HNMF02AF** (`SYNA8005`) | SPI (LPSS) | ❌ **No driver exists** | ✅ works |
| Touchscreen | Wacom **WCOM513F** | I²C-HID | ❌ **Driver matches, fails to instantiate** | ✅ works |
| Stylus (pen) | Wacom AES (same device) | I²C-HID | ❌ same as above | ✅ works |
| Dock trackpad | **SIPODEV `17EF:60BB`** | USB HID | ✅ **works** (see [`TOUCHSCREEN.md`](TOUCHSCREEN.md)) | ✅ works |

> **The dock trackpad is not a touchscreen.** That distinction is the single
> most expensive mistake in this document's history, see
> [`TOUCHSCREEN.md`](TOUCHSCREEN.md).

---

## Read this before you touch the fingerprint sensor

⛔ **Loading a custom power-on module for the fingerprint sensor will brick the
embedded controller on this machine within about 8 minutes.** Fan control,
battery-conservation mode and camera power all die, and only a cold reboot
(power off → 30 s → on) recovers them.

This is not theoretical and it is not a near-miss. It was reproduced with a
timestamped timeline. Details and the mechanism are in
[`FINGERPRINT.md`](FINGERPRINT.md#ec-bricking-hazard-read-this-first).

The short version: the sensor's power pins are PCH GPIO pins, and poking them
through the PCH's MMIO window shares the LPC bus with the EC. The EC locks up.

---

## What's here

| File | Contents |
|---|---|
| [`FINGERPRINT.md`](FINGERPRINT.md) | `SYNA8005` SPI reverse engineering: 9 root causes, 7 solved, the ACPI firmware gap, and the EC hazard |
| [`TOUCHSCREEN.md`](TOUCHSCREEN.md) | Why the dock trackpad is not the touchscreen; the `udev-hid-bpf` fix that broke it; the one fix that works |
| [`../../miixpad-520/udev/`](../../miixpad-520/udev/) | The USB autosuspend rule (the only change here that ships) |

---

## Why publish a partial result

The fingerprint work did not end in a working scanner. It ended in a documented
answer to *"is this even possible?"*, and that answer is **no, not on current
Linux**, for reasons that are worth an afternoon of someone's time to not
rediscover.

The touchscreen result is the same: the hardware is fine, the correct kernel
driver (`i2c-hid-acpi`) matches it and is already loaded, yet the HID device
never gets created. The guide shows exactly which modules were checked, which
one matched, and where the failure actually sits.

What *is* shipped is real: a working fix for the dock, and enough negative
results to save the next person from the same two dead ends.