# Touchscreen and dock trackpad

**Status: the on-display touchscreen does not work on Linux. The dock trackpad
does.** They are two different devices on two different buses, and confusing
them cost a week.

---

## The two devices

The MIIX 520 has **two independent touch input devices**:

| Device | Bus | ACPI HID | Kernel path | Linux |
|---|---|---|---|---|
| **SIPODEV `17EF:60BB`** | USB (PCH xHCI) | — | `hid-multitouch` → `hid-generic` | ✅ works |
| **Wacom WCOM513F** | I²C (`\_SB_.PCI0.I2C1.TPL1`) | `WCOM513F:00`, cid `PNP0C50` | — *nothing* | ❌ unbound |

`17EF:60BB` is the **keyboard dock's trackpad**. The Wacom is the **touchscreen
and pen**. Only one of them is a touchscreen, and it is the one that doesn't work.

---

## Why the Wacom touchscreen is unbound

The device is present and enabled on the ACPI bus. A driver **does** match it and
is **already loaded** — the HID device simply never gets created.

```console
$ cat /sys/bus/acpi/devices/WCOM513F:00/modalias
acpi:WCOM513F:PNP0C50:

$ cat /sys/bus/acpi/devices/WCOM513F:00/status
15                       # present + enabled

$ ls -d /sys/bus/acpi/devices/WCOM513F:00/driver
ls: cannot access ...: No such file or directory    # nothing claims it

$ grep -ci wacom /proc/bus/input/devices
0
```

`PNP0C50` is the generic **I²C HID** device class, so the two candidates are
`wacom` and `i2c_hid`. Both were checked and both are ruled out:

### `wacom` — wrong match table

Present in the kernel as `wacom.ko.xz` (`CONFIG_HID_WACOM=m`), so `modprobe wacom`
succeeds and is not blacklisted. It still won't bind:

```console
$ modinfo wacom | grep -c '^alias:'
165                       # all of the form hid:b....g....v........p....
$ modinfo wacom | sed -n 's/^alias:[[:space:]]*//p' | while read a; do \
      case "acpi:WCOM513F:PNP0C50:" in $a) echo "MATCH $a";; esac; done
                          # no output — no match
```

> ⚠️ **`modprobe hid_wacom` fails** — *"Module hid_wacom not found"*. That is a
> **naming trap, not a missing driver.** In current Fedora kernels the module is
> called **`wacom`**, not `hid_wacom`. Anyone concluding "the Wacom driver isn't
> available" from that error is wrong.

### `i2c-hid-acpi` — **it DOES match, and it's already loaded** ✅

This is the one that matters, and it changes the diagnosis.

The HID-over-I2C stack is split across four modules. The ACPI glue is a
**separate module from the core** — checking only `i2c_hid` proves nothing:

```console
$ ls /lib/modules/$(uname -r)/kernel/drivers/hid/i2c-hid/
i2c-hid.ko.xz        i2c-hid-of.ko.xz        i2c-hid-acpi.ko.xz

$ modinfo i2c-hid-acpi | sed -n 's/^alias:[[:space:]]*//p'
acpi*:PNP0C50:*
acpi*:ACPI0C50:*

$ # does it match our device?
$ case "acpi:WCOM513F:PNP0C50:" in acpi*:PNP0C50:*) echo MATCH;; esac
MATCH

$ lsmod | grep i2c_hid_acpi        # already resident
```

**So the driver is present, loaded, and its alias matches this device — and the
device is still unbound.** The failure is *downstream of driver matching*.

That is a genuinely different (and more interesting) problem than "no driver
exists":

```console
$ ls /sys/bus/i2c/devices/i2c-WCOM513F:00/
firmware_node  modalias  name  power  subsystem  uevent  waiting_for_supplier
# no `hid` child, no `status` — the HID device was never instantiated

$ grep -ciE 'i2c_hid|i2c-hid' <dmesg>
0                                   # i2c-hid never even attempted a probe
```

The i2c client device exists (created from the ACPI node) but no HID child is
produced, and the driver emits nothing. Most likely the HID-over-I2C **descriptor
read fails** — `PNP0C50` alone is a generic class; a real Wacom AES panel is
expected to publish a valid HID report descriptor at a defined address, and this
firmware may not.

### What that rules out

| Module | Aliases | Matches `acpi:WCOM513F:PNP0C50:` |
|---|---|---|
| `i2c-hid-acpi` | `acpi*:PNP0C50:*`, `acpi*:ACPI0C50:*` | ✅ **yes** (loaded, still unbound) |
| `i2c-hid` (core) | 0 | no — correct, it carries no ACPI ID |
| `i2c-hid-of` | `i2c:hid-over-i2c`, `i2c:hid` | no — device-tree only, and there's no `of_node` |
| `wacom` | 165, all `hid:b…` | no |
| `goodix_hid`, `elan_i2c` | — | no |

**Net result:** the correct driver matches and fails to instantiate the device.
This is not a missing-driver problem, and not a misconfiguration — it is a
firmware/interop gap at the HID-descriptor stage.

> **Note on the ACPI HID string.** Some documentation for this machine refers to
> the panel as **Wacom HID 513B**. The ACPI table actually reports
> **`WCOM513F`**. If you go looking for 513B you will not find it.

---

## The fix that broke the trackpad

Worth recording because it's a clean example of a fix that made things worse for
a reason that had nothing to do with the fix.

The hypothesis was that libinput was misclassifying the touch device:

```
Capabilities: pointer gesture
Size: 85x43mm
```

A touchpad reports `PROP=5`; a touchscreen should report `PROP=2`
(`INPUT_PROP_DIRECT`). Two things were tried:

### Attempt 1 — udev rule ❌

`99-sipodev-touchscreen.rules` set `ID_INPUT_TOUCHSCREEN` on the SIPODEV device.
Wrong device, and harmless-but-misleading, so it was **deleted**.

### Attempt 2 — `udev-hid-bpf` descriptor patch ❌ **broke the trackpad**

A BPF program rewrote the HID report descriptor, changing
`Usage (Touch Pad)` → `Usage (Touch Screen)`, flipping the PROP bits from 5 to 7.

**This made the trackpad stop working.** By relabelling the dock's trackpad as a
touchscreen, `hid-multitouch` stopped applying pointer semantics — cursor
movement and click behaviour both broke. The rule was reverted immediately.

### Why it failed — the actual lesson

The patch was aimed at the **trackpad** because the trackpad was the device
**reporting touch-like symptoms**. Those are different things.

> **Always verify which physical device a HID interface corresponds to before
> modifying its descriptor.** `libinput list-devices` gives you the kernel name;
> it does not tell you whether that name refers to the trackpad or the display.

**Kernel PROP bits are also immutable from userspace.** A udev rule can set
`ID_INPUT_TOUCHSCREEN=1` and libinput will still show `pointer gesture`, because
it reads the kernel `PROP` bits set by `hid-multitouch` from
`bInterfaceProtocol`, not udev properties. That's why "the rule is right but
nothing changed" happens — and it means there is no userspace fix for this
class of problem.

---

## What actually works ✅

The one shipped fix, for the **trackpad**:

```udev
# 80-sipodev-no-autosuspend.rules
# Disable USB autosuspend for the SIPODEV keyboard dock.
# Without this the device suspends after ~2s idle, causing wake-up latency and
# missed input on resume.
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="17ef", ATTR{idProduct}=="60bb", \
  ATTR{power/autosuspend_delay_ms}="-1", \
  ATTR{power/control}="on"
```

Shipped in [`../../miixpad-520/udev/`](../../miixpad-520/udev/).

### Why

Without it the dock suspends almost immediately after idle, and input appears to
"sometimes work, sometimes do nothing":

| Symptom | Cause |
|---|---|
| Works perfectly | USB active, clean reports, low load |
| Laggy / sluggish | `PROP=5` → acceleration + gesture processing (15–40 ms overhead) |
| Nothing at all | autosuspend suspended the device |
| Cursor jumps / drops | libinput "touch jump detected and discarded" — hardware noise |

### Known remaining issues (unfixed)

- libinput still reports the dock as `pointer gesture` — **expected and correct**,
  it *is* a trackpad
- touch data quality: occasional same-frame begin/end events discarded as kernel
  bugs
- touchpad acceleration/gesture overhead of 15–40 ms is inherent to `PROP=5`

---

## Verifying which device you actually have

```console
$ libinput list-devices | grep -E 'Device: |Kernel: '
Device:   SIPODEV Lenovo HID Device Touchpad
Kernel:   /dev/input/event7          # ← dock trackpad

$ grep -ci wacom /proc/bus/input/devices
0                                     # ← touchscreen: absent
```

If `grep` returns `0` and a `Wacom` device doesn't appear, the touchscreen has not
bound — regardless of what the dock's trackpad is doing.

---

## References

- [Linux Surface #171 — touchscreen smoothness, `hid-multitouch` ≈35 FPS, fixed
  userspace via `iptsd`](https://github.com/linux-surface/linux-surface/issues/171)
- [ArchWiki: Touchscreen](https://wiki.archlinux.org/title/Touchscreen)
- [`brotfessor/sipodev`](https://github.com/brotfessor/sipodev) — SIPODEV SP1064
  patch (**trackpad only** — it does not address the Wacom panel)