# Capturing an `armeabi`-only vendor app in an emulator

The Time2 vendor app (`x.p2p.cam`, "Plug&Play") is **`armeabi` (32-bit ARM) only**. It
will not install on any modern arm64 phone, which is exactly why the WiFi command in
[WIFI.md](WIFI.md) resisted capture for so long.

This page documents how we ran it anyway — in an **x86_64 Android emulator**, on the
**real LAN** — and captured its traffic. It's written up because *"the vendor app is
32-bit only"* is a dead end that stops a lot of people, and it doesn't have to be.

The whole thing is doable on a Linux host with KVM.

---

## TL;DR — the working combination

| Piece | Choice | Why |
|-------|--------|-----|
| System image | `system-images;android-30;google_apis;x86_64` | includes `armeabi-v7a` via translation |
| Emulator | 37.x (current) | |
| GPU | **`-gpu host`** (or `swangle`) | the bundled SwiftShader crashes |
| Display | **Xvfb `:99`** | GL init needs a display, even headless |
| Network | **`-net-tap <tap>`** on a bridge | NAT drops broadcast; we need the real LAN |
| Capture | **`strace -e trace=sendto`** on the device | sees `sendto()` *before* the NIC |

---

## 1. Don't try to emulate 32-bit ARM

The obvious approach is an `armeabi-v7a` system image. **It does not work** with modern
emulators:

```
FATAL | CPU Architecture 'arm' is not supported by the QEMU2 emulator,
        (the classic engine is deprecated!)
```

Full 32-bit ARM TCG emulation was removed (`-engine classic` is gone), and where it still
half-exists it **segfaults during boot**. Don't go down this path.

### The supported path: x86_64 + binary translation

Google's emulator release notes (30.0.0) state the intended approach:

> *"…you can now use the Android 9 x86 system image or any Android 11 system image to run
> your app – it is no longer necessary to download a specific system image to run ARM
> binaries. These Android 9 and Android 11 system images support ARM by default and
> provide dramatically improved performance when compared to those with full ARM
> emulation."*

So: pick an **x86_64** image that ships ARM **translation** (`libndk_translation`). Android
11 (`API 30`) `google_apis` `x86_64` does.

Confirm once booted:

```console
$ adb shell getprop ro.product.cpu.abilist
x86_64,x86,arm64-v8a,armeabi-v7a,armeabi
```

`armeabi-v7a` being present is what lets the app install. After installing it, Android
picks the ARM ABI automatically:

```console
$ adb shell dumpsys package x.p2p.cam | grep -i primaryCpuAbi
    primaryCpuAbi=armeabi
```

---

## 2. The emulator crashes at ~30 s — work around it

With a bleeding-edge host (e.g. Fedora with Mesa 26.x), the emulator's **bundled
SwiftShader** (`emulator/lib64/gles_swiftshader/libGLESv2.so`) **segfaults** during
startup. It affects *every* emulator version and *every* GPU mode that uses SwiftShader:

| `-gpu` mode | Result |
|-------------|--------|
| `host` | ✅ boots |
| `swangle` | ✅ boots |
| `swiftshader` / `swiftshader_indirect` | ❌ SIGSEGV |
| `software` / `lavapipe` | ❌ SIGSEGV |
| `off` / `guest` | ❌ dies |

Use **`-gpu host`**.

### It also needs a display

Even with `-no-window`, GL initialisation wants a display. Over SSH there isn't one, and it
crashes. Run a virtual X server:

```bash
sudo dnf install -y xorg-x11-server-Xvfb      # or apt: xvfb
Xvfb :99 -screen 0 1280x1024x24 -ac +extension GLX +render -noreset &
export DISPLAY=:99
export XDG_RUNTIME_DIR=/run/user/$(id -u)
```

---

## 3. Put the guest on the **real LAN** — `-net-tap`

This is the part people miss. The emulator's default networking is **user-mode NAT**
(`10.0.2.0/24`). It handles outbound unicast, but it **drops broadcast and multicast** —
so the app can *never* discover the camera. From the docs:

> *"each instance of the emulator runs behind a virtual router or firewall service that
> isolates it from your development machine network interfaces… An emulated device can't
> detect your development machine or other emulator instances on the network."*

The emulator's own `-help` gives the fix:

> *"Use `-net-tap <tap interface>` to switch to TAP network mode where Android will use a
> TAP interface to connect to the host network directly… the host is connected to the TAP
> interface should be bridged with another network interface on the host."*

So bridge a physical NIC and attach a TAP. With NetworkManager:

```bash
S="sudo"
MAC=$(cat /sys/class/net/enp1s0f1/address)

# bridge claims the NIC's MAC so DHCP keeps the same lease
$S nmcli con add type bridge con-name br0 ifname br0 stp no ipv4.method auto
$S nmcli con mod br0 ethernet.cloned-mac-address "$MAC"
$S nmcli con add type ethernet con-name enp1s0f1-br ifname enp1s0f1 master br0
$S nmcli con down "Wired connection 1"
$S nmcli con up enp1s0f1-br
$S nmcli con up br0

# tap owned by the user, attached to the bridge
$S ip tuntap add dev tap0 mode tap user "$USER"
$S ip link set tap0 master br0
$S ip link set tap0 up
```

> ⚠️ **Keep a second path to the host.** If you bridge your SSH NIC, a mistake locks you
> out. Have WiFi (or console) as a fallback before you start. Do the whole thing in a
> `setsid` script so a dropped SSH can't kill it mid-way.

The guest then appears **on your real subnet** (`192.168.x.y`), same broadcast domain as
the camera. That's what makes discovery work.

Boot:

```bash
emulator -avd camre -memory 2048 -no-window -no-audio -no-boot-anim -no-snapshot \
         -gpu host -net-tap tap0
```

> ℹ️ `-net-tap` disables `-tcpdump` and the other user-mode net options. Capture on the
> **bridge** instead (next section).

---

## 4. Capturing — `strace` beats `tcpdump`

You can `tcpdump -i br0`, but for a **UDP broadcast to a port nobody's listening on**, the
packet can vanish before it's visible (the kernel may not emit it if no interface has the
broadcast address in scope — which is exactly the NAT case).

The reliable method is to trace the app's **syscalls** on the device. `strace` is present on
the emulator image:

```bash
adb root; adb wait-for-device
PID=$(adb shell pidof x.p2p.cam)

adb shell "strace -f -tt -s 700 -e trace=sendto -p $PID -o /data/local/tmp/s.trace" &

# ...drive the app UI...

adb shell pkill strace
adb shell cat /data/local/tmp/s.trace | grep 2627
```

`-s 700` matters — it prints the **whole payload**, not the first 32 bytes:

```
sendto(71, "\0\0p\n2I\35\243\0d\0\0\0d7:MainCmd3:7006:isopen1:15:MacIP…", 167,
       MSG_NOSIGNAL, {sin_family=AF_INET, sin_port=htons(2627),
                      sin_addr=inet_addr("255.255.255.255")}, 16) = 167
```

That one line is the entire answer: **payload, length, destination**.

---

## 5. Driving the UI headlessly

No window needed — drive it with `input tap` and read state with `uiautomator`.

```bash
# where is the button?
adb shell uiautomator dump /sdcard/ui.xml >/dev/null
adb shell cat /sdcard/ui.xml | tr '>' '\n' \
  | grep -oE 'text="[^"]+"[^>]*bounds="[^"]+"' | grep -i ok

# tap its centre (x,y)
adb shell input tap 153 969

# type into a focused field
adb shell input text 'the-password'
adb shell input keyevent 4        # dismiss the soft keyboard
```

Screenshot with `adb exec-out screencap -p > shot.png` to see where you are.

### Legacy-app permissions

An app targeting SDK < 23 (like this one) gets a **"Choose what to allow …"** review screen
on first run. Tick the toggles and press **Continue**, or pre-grant:

```bash
for p in CAMERA RECORD_AUDIO ACCESS_COARSE_LOCATION \
         READ_EXTERNAL_STORAGE WRITE_EXTERNAL_STORAGE; do
  adb shell pm grant x.p2p.cam android.permission.$p
done
```

---

## 6. Cleanup

```bash
# stop the emulator
adb emu kill

# undo the bridge
sudo ip link set tap0 nomaster && sudo ip link del dev tap0
sudo ip link set enp1s0f1 nomaster && sudo ip link del dev br0
sudo nmcli con up "Wired connection 1"
```

---

## Notes on stealth/ethics

This is interoperability work on **hardware you own**, to avoid depending on a
discontinued cloud service. The vendor app is used as a **reference client** — its traffic
is observed, not modified, and **no vendor binaries are redistributed** (see
[THIRD-PARTY](../../THIRD-PARTY.md)).
