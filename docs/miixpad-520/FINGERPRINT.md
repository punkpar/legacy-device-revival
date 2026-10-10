# Fingerprint: Synaptics HNMF02AF (`SYNA8005`) over SPI

**Status: ⛔ not working on Linux. No driver exists. A naive attempt damages the
machine's embedded controller.**

Everything below is from a custom out-of-tree kernel module written to probe the
SPI path directly. Seven of the nine blockers were solved. The eighth and ninth
are the ones that matter, and the reason the module is not published is
[`EC bricking hazard`](#ec-bricking-hazard-read-this-first).

---

## Hardware

| Property | Value |
|---|---|
| Sensor | Synaptics **HNMF02AF** |
| ACPI HID | `SYNA8005:00` |
| Legacy I²C HID | `06CB2846` — present in DSDT but `_STA=0`, **disabled by BIOS** |
| Bus | **SPI** (LPSS `SSP1`), the active path |
| ACPI status | `15` (present, enabled) — but **no driver claims it** |
| OEM driver (Windows) | `Synaptics FingerPrint, HNMF02AF, 5.5.3.1096` |

The fingerprint sensor appears **twice** in the DSDT. The I²C instance
(`06CB2846`, on `_SB.PCI0.I2C0`) is switched off by a BIOS variable (`SDS0`) and
sets `_STA=0`. The SPI instance is the live one.

### How the DSDT describes it

```
Device (SYNA8005)          ← in TPD0, on the SPI bus
    Name (_HID, "SYNA8005")
    ...
    Device (FPNT)          ← the fingerprint sensor itself
```

---

## EC bricking hazard — read this first

⛔⛔ **Loading a module that drives the sensor's power pins bricks the embedded
controller within ~8 minutes.**

### Reproduced timeline

| Time | Event |
|---|---|
| ~14:20 | Cold reboot — EC healthy (`fan_mode=0` ✅) |
| 16:29 | EC re-verified: fan, conservation mode, camera power all readable ✅ |
| **18:14:11** | **`insmod syna8005_poweron.ko` (v5.0)** |
| **~18:33** | **EC dead** — first `AE_TIME` at kernel uptime 7311 s, ~8 min later |
| 18:37 | Verification: `fan_mode` → **I/O error** ❌ |

### Mechanism

The sensor's power and reset lines are **PCH GPIO pins** (120–123 for power,
134 for reset). To power the sensor you must write them through the PCH GPIO
controller's MMIO window — `INT344B:00` at **`0xFDAF0000`**, Community 2.

That window **shares the LPC bus with the EC**. The writes collide with EC
traffic and the EC locks up.

### Impact

Every `VPC2004` sysfs attribute becomes unreadable:

| Attribute | Symptom |
|---|---|
| `fan_mode` | I/O error — fan profile control gone |
| `conservation_mode` | I/O error — battery protection toggle gone |
| `camera_power` | I/O error — camera power control gone |
| Battery `_BST` | evaluation fails → stale thermal data |

### Recovery

Cold reboot only: power off, wait ~30 s, power on. A warm reboot is not enough,
and the EC dies again shortly after any re-trigger.

### Why this matters beyond this device

The sensor is *not* exotic silicon — it's a fingerprint reader on a mainstream
detachable. Any owner who goes looking for a driver will hit the same GPIO
bring-up. **Driving PCH GPIO power pins via MMIO is fundamentally incompatible
with EC stability on this platform.** That is the transferable finding.

---

## The ACPI firmware gap

The MIIX 520's DSDT defines `SYNA8005` with `_HID`, `_STA`, `_CRS` and `_ADR` —
and **omits `_DSM`, `_RST` and `_CID`**.

The in-tree `spi-hid-acpi` driver depends on all three:

| Method | Used for | Present on SYNA8005? |
|---|---|---|
| `_DSM` | locate the HID descriptor register | ❌ absent |
| `_RST` | assert/deassert hardware reset | ❌ absent |
| `_CID` | match to the correct HID transport | ❌ absent |

*Provenance: this table reflects a source review of the `linux-surface` HID-over-SPI
driver tree in June 2026, not a re-read of upstream `spi-hid-acpi.c` at publish
time — `git.kernel.org` and the common source mirrors were bot-walled during
verification. Treat the `_DSM`/`_RST` pairing as **strongly indicated but not
re-confirmed**; the DSDT omission itself is confirmed by decompiling the
machine's own ACPI tables.*

So the standard HID-over-SPI path **cannot bind this device without firmware
changes**, and there is no spare path. Two independent gaps, both verified
against upstream rather than assumed:

**1. The transport isn't in the kernel.** The Fedora 7.2.9-200.fc44 config
contains **no HID-over-SPI symbol at all**:

```console
$ grep -iE 'SPI_HID|HID_SPI' /boot/config-$(uname -r)
(nothing)
$ grep -E '^CONFIG_HID_GOODIX_SPI=' /boot/config-$(uname -r)
CONFIG_HID_GOODIX_SPI=m         # the only SPI HID driver present
```

`modprobe spi-hid` → *not found*.

**2. libfprint has no driver for this sensor.** The upstream
[supported-devices list](https://fprint.freedesktop.org/supported-devices.html)
has a dedicated **SPI devices** section. Its **complete** contents are two
ElanTech parts:

| ACPI ID | USB ID | Device |
|---|---|---|
| `ELAN7001` | `04f3:241f` … | ElanTech Embedded Fingerprint Sensor |
| `ELAN70A1` | `04f3:30b2` … | ElanTech Embedded Fingerprint Sensor |

**No Synaptics entry, and no `SYNA8005`.** Synaptics sensors *are* in libfprint —
but only as **USB** devices (`06cb:00bd` … `06cb:01a4`). This device is SPI, and
its legacy I²C ID (`06cb:2846`) isn't listed either, so **neither** ACPI path is
covered.

> The list covers libfprint's **development** version; a distro build may be
> older still, so it can only ever be *smaller* than the above.

That is the real blocker. Everything below it is solvable; this is not.

---

## Root causes found

Nine distinct problems were isolated by MMIO probing and iterative module
development. Seven are resolved.

### ✅ 1. Wrong `padno` calculation

`padno = pin - 96` targeted the wrong pins. Correct formula is
`padno = pin - community_start`, where **Community 2 starts at pin 120**.

### ✅ 2. SPI1 pins left in GPIO mode

Pins **72–75** (`SPI1_CSB/CLK/MISO/MOSI`) boot with `PADMODE=0, GPIODIS=1` —
plain GPIO outputs. The BIOS never configures them for their SPI function.

Verified by writing `PADCFG0` directly:

```
Before: PADCFG0=0x44000101   GPIODIS=1 (output)  PADMODE=0 (GPIO)
After:  PADCFG0=0x04000001   GPIODIS=0 (func)    PADMODE=1 (SPI1)
```

### ✅ 3. Power pins had `GPIODIS=3`

Pins 120–123 and 134 booted with `GPIODIS=3` — **input and output both
disabled**. Setting `TXSTATE=1` wrote the register but drove nothing; the pin was
electrically disconnected.

The fix needs the bits in the right order: clear `PADMODE` (→ 0 = GPIO
function), set `GPIODIS=2` (output enabled, input disabled), then `TXSTATE=1`.

> ⚠️ `GPIODIS=1` is **input-only** — it is not "output on". Confirmed via
> `/sys/kernel/debug/gpio` showing `out lo` → `out hi`.

### ✅ 4. LPSS SPI1 controller uninitialised

`pxa2xx-spi` initialises the controller properly, but only when `spidev` is
bound. Register dump at the **correct** private offset (**`0x200`**, not
`0x800`):

```
LPSS private at 0x200 (NOT 0x800):
  +0x200: 0x80000001  ← LPSS_CAPS
  +0x204: 0x00000007  ← RESETS = FUNC|IDMA (already deasserted)
  +0x220: 0x00000001  ← SSP_REG
  +0x224: 0x0000F003  ← CS_CONTROL (SW_MODE + CS_HIGH)

After pxa2xx-spi init:
  SSCR0 = 0x00007787  ← SSE=1 (enabled)
  SSCR1 = 0x00000007  ← normal mode, SPI master
  SSSR  = 0x0000A06C  ← RNE=1 (RX FIFO has data)
```

The controller generates clock and MOSI correctly. Reads returned `0xFF`
because the sensor was unpowered — root cause 3.

### ✅ 5. PCI D3hot state

The SPI1 controller (`0000:00:1e.3`) drops to **D3hot** when idle. In D3hot
**every MMIO read returns `0xFFFFFFFF`** and the SPI engine is dead — while the
device still appears present in sysfs, which is what makes this so confusing.

Fix: `pci_set_power_state(pdev, PCI_D0)` during module init, then a 10 ms delay.
The `pci_get_device()` reference must be held for the module's lifetime (never
`pci_dev_put()` before exit).

### ✅ 6. LPSS functional reset still asserted

After D3hot → D0, all PXA2xx registers still read `0x00000000` because the
functional and IDMA resets remain asserted.

Fix: write `0x03` (`FUNC_RST|IDMA_RST`) to `LPSS_RESETS` at `BAR0+0x204`, then
wait 5 ms. `SSCR0` becomes readable immediately after.

### ✅ 7. IRQ 23 storm

Enabling `SSCR0 |= SSE` directly, without `pxa2xx-spi` managing the controller,
makes IRQ 23 (SPI1's assigned IRQ) fire continuously. The handler spins, pegs
100 % CPU, and the machine becomes unresponsive.

Fix: `disable_irq()` + `free_irq()` **before** enabling the SPI engine, then
restore after the reads complete.

### ❌ 8. `pxa2xx-spi` re-probe resets the GPIO pins — OPEN

When `pxa2xx-spi` re-probes (unbind/rebind to get userspace `spidev`), the ACPI
`_PS0` callback re-runs pinctrl setup and **resets all GPIO power-on state back
to defaults**. The sensor powers off again the instant the re-probe completes.

Evidence: `/sys/kernel/debug/gpio` shows `out lo` for 120–134 *after* the
re-probe; `PADCFG0` readback confirms `TX=1` was written before it.

*Partial mitigation:* v5.0 does SPI reads entirely in kernel space, so no
userspace `spidev` is needed and the re-probe never happens.

### ❌ 9. Module cannot be unloaded — OPEN

After the SPI engine is enabled and reads complete, the module refcount stays at
1 with no visible holder. `rmmod -f syna8005_poweron` → `Device or resource
busy`. Getting a rebuilt module onto the machine requires a reboot.

> **Development consequence:** you get one build per boot. Plan experiments
> accordingly, and keep a known-good module aside to compare against.

---

## Where this ended

| Layer | Status |
|---|---|
| SPI electrical path | ✅ **Functionally proven** — controller clocks and reads |
| Sensor power | ✅ (driving it is what bricks the EC) |
| Sensor response | ❌ reads `0xFF` — **not driving MISO** |
| HID transport | ❌ `spi-hid` absent from kernel; ACPI missing `_DSM`/`_RST`/`_CID` |
| Userspace stack | ❌ libfprint's SPI list is ElanTech-only — no `SYNA8005` |

The chain breaks at the transport layer, not the electrical one. A working
solution needs **all** of: firmware additions to the DSDT, a `spi-hid` driver
in the kernel, and a `libfprint` driver on top. The first of those is a
firmware-modification project.

### If you want to continue

> ⚠️ **Order matters.** SPI mode 3 is not the first thing to try — it's only
> meaningful **once the transport binds**, because without a working HID device
> you have no way to observe whether a read succeeded. Today the transport
> cannot bind at all (see above), so mode 3 is unreachable.
>
> The real first task is a **firmware** change, not a kernel one: add `_DSM`,
> `_RST` and `_CID` to the DSDT for `SYNA8005`.

Once the transport can bind:

1. Try **SPI mode 3** (`SPO=1, SPH=1`) — some Synaptics sensors need it, and the
   bus here was only ever driven in mode 0.
2. Capture real traffic from the OEM driver on Windows with a logic analyser
   and compare against what the sensor expects. The
   [Microsoft HID-over-SPI specification](https://learn.microsoft.com/windows-hardware/drivers/spi/spi-hid)
   describes the command format the Linux driver assumes.
3. **Have a cold-reboot path ready** before touching power pins — see the
   [EC hazard](#ec-bricking-hazard-read-this-first).

> **Reproducing the probe:** the original out-of-tree module is **not published
> here**, deliberately — loading it bricks the EC. It also lived in `/tmp` and
> was wiped by a reboot, so it is a rewrite rather than a resume. A useful
> starting point is `CONFIG_HID_GOODIX_SPI`, the only SPI HID driver in this
> kernel and the closest structural analogue.

---

## References

- [libfprint supported devices](https://fprint.freedesktop.org/supported-devices.html)
  — SPI section (authoritative for the ElanTech-only finding)
- [Microsoft HID over SPI protocol specification](https://learn.microsoft.com/windows-hardware/drivers/spi/spi-hid)
- `drivers/hid/spi-hid/spi-hid-acpi.c` — the ACPI method dependencies
- `drivers/hid/hid-goodix-spi.c` — in-tree SPI fingerprint driver, the closest
  structural reference, and the only SPI HID driver in this kernel