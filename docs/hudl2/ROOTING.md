# Hudl 2: what `run-as` root can and cannot do

Dirty COW over `/system/bin/run-as` gives `uid=0` inside the **`u:r:runas:s0`** SELinux
domain. That is real root for *reading*, but the `runas` domain is confined by **both**
SELinux **and** the Linux capability set, and no kernel-level escalation is available. This
page records the exact probe results so nobody has to rediscover the ceiling.

> 🔎 **How to reproduce the probes.** Each probe is a small C file compiled
> `x86_64-linux-android22-clang -Os -s`, then Dirty-COW'd over `/system/bin/run-as` and
> executed. They use **inline syscalls only**: `exec()` is blocked from this domain.
> Sources: [`hudl2/exploit/selinux-probe.c`](../../hudl2/exploit/selinux-probe.c),
> [`hudl2/exploit/optimize-inline.c`](../../hudl2/exploit/optimize-inline.c).

---

## 1. Confirmed capabilities from `u:r:runas:s0`

| Capability | Works? | Evidence |
|-----------|--------|----------|
| `uid=0` | ✅ | `setresuid(0,0,0)` returns 0 after the COW overwrite |
| `open()` / `read()` / `write()` on **readable** files | ✅ | Inline syscalls succeed |
| `ioctl()` | ✅ | Used by the fstrim/scheduler probes |
| `/proc/kallsyms` | ✅ readable | All kernel symbols exposed (see §3) |
| `/proc/modules` | ✅ readable | Shows the kernel *can* load modules |
| `/sys/fs/selinux/enforce` | ✅ readable → `1` | SELinux is **enforcing** |

## 2. Confirmed blocks

| Operation | Result | Meaning |
|-----------|--------|---------|
| `execve()` / `execvp()` / `system()` | 🚫 blocked | **No `exec` from the `runas` domain.** Payloads must use inline syscalls. |
| write to `/data/local/tmp/` from direct `runas` execution | 🚫 `EACCES` | File *writes* are restricted |
| `/sys/fs/selinux/policy` | 🚫 `EACCES` | Policy binary unreadable from this domain |
| `/sys/fs/selinux/enforce` write | 🚫 | Cannot set permissive |
| `/dev/block/*` `open()` | 🚫 `EACCES` | No block-device access |
| sysfs writes (`/sys/block/*`, `/sys/class/*`) | 🚫 | No `sysfs_w` permission |
| `swapon()` | 🚫 | Needs block-device access |
| `FITRIM` ioctl (fstrim) | 🚫 | Needs block-device `open()` |
| `pm disable-user` / `pm hide` | 🚫 | Cannot disable system packages |
| `/data/misc/wifi/` | 🚫 | `wpa_supplicant` socket/config inaccessible |
| `/data/data/com.termux/` (other apps' data) | 🚫 | Cross-app data blocked |

## 3. The module-loading trap: SELinux allows it, capabilities don't

The most useful finding. The classic "load a kernel module" escalation fails **not**
because of SELinux, but because of a missing capability:

| Test | Result | Interpretation |
|------|--------|----------------|
| `init_module()` with a garbage buffer | **`EPERM`** | SELinux `module_load` **passed**; the **capability** check failed |
| `finit_module()` | **`EACCES`** | Blocked earlier: needs a temp file the domain can't write |
| `/proc/kallsyms` grep `selinux_*` | **not found** | No exported `selinux_enforcing` / `selinux_state` to overwrite |

So:

- `init_module()` returning **`EPERM` (not `EACCES`)** proves the `runas` policy *does*
  include `module_load`. If SELinux had blocked it, we'd see `EACCES`.
- But `CAP_SYS_MODULE` is absent from the process's **effective and bounding** sets, so the
  syscall still fails.
- **Capabilities cannot be raised from `runas` without a kernel exploit.**
- And there is **no `selinux_enforcing` symbol** to flip anyway: it is static /
  `__ro_after_init` / compiled out, so the "overwrite the enforcing flag via `/proc/kallsyms`"
  trick has no target.

> 💡 **Learning lesson.** SELinux and capabilities are *independent* gates. A domain can be
> granted a SELinux permission (`module_load`) and still be denied by the capability check
> (`CAP_SYS_MODULE`). When debugging an Android escalation, check **errno**: `EACCES`
> usually means SELinux; `EPERM` often means the capability set.

## 4. Ruled-out exploits

| Exploit | CVE | Why not applicable |
|---------|-----|--------------------|
| Dirty Pipe | CVE-2022-0847 | Kernel **5.8+** only (this is 3.10) |
| Mutagen Astronomy | CVE-2018-14634 | Needs **32 GB+ RAM** (ELF arg-count overflow); device has 1.89 GB |
| ELF PIE / stack | CVE-2017-1000253 | Targets RHEL/CentOS ELF-loader behaviour |
| Copy Fail | CVE-2026-31431 | Affects kernels **≥ 4.0** (needs `algif_aead`, added 2017) |
| Binder exploits | various | All target `untrusted_app`, not the ADB `shell`/`runas` domain |
| `recowvery` boot flash | (none) | Needs **block-device write** to the boot partition |
| Samsung RKP bypass | (none) | Samsung-specific hypervisor; irrelevant to Intel Bay Trail |

## 5. Bottom line

```
u:r:runas:s0  (uid=0)
   ├─ read anything            ✅
   ├─ run commands as uid=0    ✅  (inline-syscall payloads only)
   ├─ exec()                   🚫
   ├─ write sysfs / block dev  🚫
   ├─ swapon / fstrim          🚫
   └─ load a kernel module     🚫  (SELinux OK, CAP_SYS_MODULE missing)
```

The `runas` domain is fenced by **SELinux and Linux capabilities together**. Without an
arbitrary kernel write there is **no path to an unconfined root**, and Dirty COW is the
ceiling. A **hardware SPI flash mod** is the only route to a persistent, unrestricted root
on this SoC; see [`README.md` §6](README.md#6-open-questions).

---

## See also

- [`README.md`](README.md): hardware, the `run-as` technique, practical fixes.
- [`hudl2/exploit/`](../../hudl2/exploit/): the probe and payload sources.
