# Tesco Hudl 2: root on a hardware-locked Bay Trail tablet

The **Tesco Hudl 2** is a 2014 Android tablet (Pegatron board `octagon`, Intel Atom
Bay Trail, Android 5.1 Lollipop). Tesco discontinued the line and switched off the Hudl
services and app store, so the tablet is fully orphaned: no store, no updates, stuck on
Android 5.1 with a 2013-era WebView.

Stock, it has **no root, no custom recovery and a hardware-locked bootloader** (Intel
Bay Trail). This page documents how it was rooted **without** unlocking the bootloader,
using **Dirty COW (CVE-2016-5195)** to overwrite `/system/bin/run-as`, and, just as
importantly, **where that root stops**. The `runas` SELinux domain is confined by *both*
SELinux *and* Linux capabilities, and that combination is the real ceiling on this device.

**Contents:** [1. Hardware](#1-hardware) · [2. Why `run-as`](#2-why-run-as) ·
[3. The Dirty COW root](#3-the-dirty-cow-root) · [4. The SELinux ceiling](ROOTING.md) ·
[5. Practical fixes](#5-practical-fixes) · [6. Open questions](#6-open-questions)

---

## 1. Hardware

| | |
|---|---|
| Model | **Tesco Hudl 2** (Pegatron board `octagon`; `ro.product.model` = `Hudl 2`) |
| SoC | Intel Atom **Z3735x** (Bay Trail, x86_64, 4 cores) |
| RAM | 1.89 GB |
| Storage | 14.6 GB eMMC (`mmcblk0`) + microSD (`mmcblk1`) |
| OS | Android **5.1** Lollipop, SDK 22, build `LMY47I` |
| Kernel | `3.10.62-x86_64_byt` (2015-09-17) |
| Bootloader | Intel Bay Trail: **hardware-locked**, `fastboot` only |
| WiFi | Broadcom **BCM4334** (2.4 GHz only) |
| Display | 8.9" 1920×1200, density 320 |

> ℹ️ Two sources disagree on the exact Atom part: the on-device build props read back as
> **Z3735G**, while the working notes recorded **Z3735D**. Both are the same Bay Trail
> family with the same kernel; treat the specific suffix as *unverified* until
> `cat /proc/cpuinfo` is compared across units.

### Partition map (from `fastboot getvar all`)

| Partition | Type | Size | Mount |
|-----------|------|------|-------|
| ESP | vfat | 33 MB | (not mounted) |
| boot | emmc | 16 MB | (not mounted) |
| recovery | emmc | 16 MB | (not mounted) |
| fastboot | emmc | 16 MB | (not mounted) |
| misc | emmc | 128 MB | (not mounted) |
| config | ext4 | 128 MB | `/config` |
| system | ext4 | 2 GB | `/system` (`dm-0`, **dm-verity**) |
| cache | ext4 | 1.5 GB | `/cache` |
| data | ext4 | ~9.6 GB | `/data` (`dm-1`, **encrypted**) |
| logs | ext4 | 1 GB | `/logs` |
| factory | ext4 | 128 MB | `/factory` |

**Raw partitions cannot be dumped** from userspace on this device: SELinux is enforcing
with no transition from `runas`/`shell` to a privileged domain, and every `fastboot oem`
command returns *"OEM command not permitted"*. Block-device access needs the `vold`/`init`
domain. The only route to a raw dump is a **hardware SPI flash programmer** (e.g. CH341A).

---

## 2. Why `run-as`

This is the part that was not documented anywhere public for this tablet.

`run-as` is a **setuid-root** binary shipped on every Android build. It exists so `adb
shell` can run as an app's UID; it lives in the `runas` SELinux domain, which is already
allowed to be `root`.

Dirty COW gives you an **arbitrary write to a read-only file** (any file you can open
`O_RDONLY`, even one you cannot write). Point it at `/system/bin/run-as` and you get:

1. Overwrite `/system/bin/run-as` with your own payload.
2. Run `run-as` → the kernel's setuid bit makes you **`uid=0`**, and you are now executing
   **inside the `runas` domain**, not `untrusted_app`.

No bootloader unlock, no custom recovery, no kernel module, no reboot required. That
combination (*setuid-root target + an already-privileged domain*) is what makes this
worth writing down.

The payload used here is a small "run-as" front-end (see
[`hudl2/exploit/run-as-payload.c`](../../hudl2/exploit/run-as-payload.c)) that drops into
`uid=0` and can `run <cmd>` or spawn a shell.

---

## 3. The Dirty COW root

**Vulnerability:** Dirty COW, **CVE-2016-5195**: a race in the Linux kernel's
copy-on-write handling of private read-only memory mappings (`get_user_pages` vs
`/proc/self/mem`). It affects kernels from 2.6.22 to 4.8.3. This device's kernel is
**3.10.62**, squarely in range.

**Why it works here:** Dirty COW is a *local privilege escalation* only if you already
have a foothold. The `adb shell` user is `shell` (`u:r:shell:s0`), which is unprivileged
but can run `run-as`. So the chain is:

```
adb shell (u:r:shell:s0)
   └─ Dirty COW writes payload over /system/bin/run-as (setuid root)
        └─ ./run-as  →  uid=0 inside u:r:runas:s0
```

**Non-persistent.** `/system` is `dm-verity` protected, so the overwrite lives only in
page cache + the underlying ext4 until reboot. Re-apply after every reboot. In practice
the payload is re-applied automatically on login (a boot/`.bashrc` hook re-runs the COW
write), so the device is "rooted" again within seconds of boot.

**The exploit itself is public and *not* our code**: it is the well-known Android port of
the Dirty COW PoC. This repo does **not** vendor it; see
[`THIRD-PARTY.md`](../../THIRD-PARTY.md) and [`docs/REFERENCES.md`](../REFERENCES.md) for
the upstream. What is original here is *what we pointed it at* (`run-as`) and the analysis
of the ceiling it hits.

---

## 4. The SELinux ceiling

Root via `run-as` gets you `uid=0` but **not** an unconfined domain. The `runas` domain is
locked down by both SELinux and the process capability set, and that is a hard ceiling.

**Full analysis, probe results and ruled-out exploits: [`ROOTING.md`](ROOTING.md).**

The headline findings:

- **`exec()` is blocked** from the `runas` domain. Binaries cannot `execve()`/`system()`.
  The workaround is to write payloads that use **inline syscalls only**
  (`open`/`read`/`write`/`ioctl`); see [`hudl2/exploit/optimize-inline.c`](../../hudl2/exploit/optimize-inline.c).
- **`init_module()` returns `EPERM`, not `EACCES`**: SELinux *allows* `module_load`, but
  `CAP_SYS_MODULE` is absent from the capability set. Capabilities cannot be escalated
  from this domain without a kernel exploit.
- **No kernel variable to flip.** `selinux_enforcing` / `selinux_state` are **not exported**
  in `/proc/kallsyms` (static or `__ro_after_init`), so the classic "overwrite the
  enforcing flag" trick has no target.
- **Block devices, sysfs writes, `swapon`, `fstrim`** are all blocked (`/dev/block/*`
  `open()` → `EACCES`; no `sysfs_w`).

So Dirty COW is the **ceiling** for this device. It gives a genuinely useful root (read
anything, run commands as uid=0) but not the write-oriented operations a full root would.

---

## 5. Practical fixes

These are the non-root fixes that made the tablet actually usable.

### WiFi: eero Hybrid (WPA2+WPA3) breaks the BCM4334

The 2013 Broadcom driver cannot parse **mixed-mode** (WPA2+WPA3) beacons. Auth succeeds
but DHCP is then dropped (`NETWORK_DISCONNECTION_EVENT ... reason=1`). Two things were
needed:

1. Clear stale saved networks: root *cannot* touch `/data/misc/wifi/` (SELinux), so a
   tiny APK calling `WifiManager.removeNetwork()` was used instead.
2. Set the access point to **WPA2-only** (not Hybrid) for both bands.

Result: a reliable 2.4 GHz connection. **2.4 GHz only**; 5 GHz band-steering confuses the
same driver.

### TLS: Android 5.1 does not trust modern Let's Encrypt

Android 5.1's CA store predates ISRG Root X1, so modern HTTPS (F-Droid, most sites) fails.
Install the ISRG Root X1 certificate into the user store:

```sh
adb push isrgrootx1.der /sdcard/Download/
adb shell am start -n com.android.certinstaller/.CertInstallerMain \
  -d file:///sdcard/Download/isrgrootx1.der
```

### Charging: the bq24296 sees a CDP, not a DCP

The TI `bq24296` charger IC negotiates input current from the **voltage on the USB D+/D-**
lines. A computer port presents as a *Charging Downstream Port* (CDP) → **500 mA limit**.
With the screen on (~600 to 800 mA draw) the battery barely charges. A *Dedicated Charging
Port* (wall charger with D+/D- shorted) unlocks ~1.7 A. Practical fixes: use a 2 A+
tablet charger and a short, thick cable (or a charge-only cable, which shorts D+ to D-).
The `input_cur_limit` sysfs node is **not writable** from the `runas` domain.

---

## 6. Open questions

- **Persistent root needs hardware.** The only path to a full, persistent root (or a
  Linux install) is a **SPI flash mod**: solder to the Bay Trail SPI flash, dump it with a
  CH341A, and either patch Secure Boot or write a new boot image. That is the honest
  answer for this SoC: there is no software-only route.
- **`fastboot` is read-only here.** `fastboot getvar all` works; every write/flash OEM
  command is refused.
- **The specific Atom suffix** (Z3735D vs Z3735G) is unresolved; see §1.

---

## See also

- [`ROOTING.md`](ROOTING.md): the full SELinux/capability analysis and probe results.
- [`hudl2/exploit/`](../../hudl2/exploit/): original tooling (payload, SELinux probe,
  inline-syscall optimizer, re-root script).
- [`docs/REFERENCES.md`](../REFERENCES.md): Dirty COW upstream and further reading.
