# Wake a PC with a Bluetooth gamepad, no dongle, no custom firmware

> **Status: ✅ proven end-to-end.** A stock Xbox Series pad powers on a fully
> powered-off (S5) Windows PC in well under a second of logic latency, using
> **only hardware you already own**: a cheap ESP32 BLE proxy, Home Assistant, and
> the PC's own Wake-on-LAN.

Most Bluetooth gamepads **cannot** wake a sleeping or powered-off PC. You press the
button, the pad tries to reconnect, and nothing happens: the PC's Bluetooth stack
is asleep and nothing is listening. The usual fix is to build or buy a dedicated
**USB wake dongle** (the excellent
[`kungaa/PC-wake-dongle`](https://github.com/kungaa/PC-wake-dongle) is one). This
document is the *other* route: **you probably already own every part.**

The trick is to move the listening **outside the PC**. A tiny ESP32 running
ESPHome's `bluetooth_proxy` sits on a USB port that stays powered when the PC is
off, relays the pad's advertisement over WiFi to Home Assistant, and Home Assistant
sends a Wake-on-LAN packet. Nothing inside the PC needs to be awake.

```
[gamepad]  --BLE advertisement-->  [ESP32 BLE proxy]  --WiFi-->  [Home Assistant]
  power on                          on a USB port that            sees the advert
                                    stays live in S5                   |
                                                                       v
[PC boots]  <------------------- magic packet  <------------------  Wake-on-LAN
```

---

## Why this works at all

Two facts have to hold. Both are testable, and you should test them on your own
hardware rather than take them on faith:

1. **The gamepad advertises when it has no host.** A pad that is *connected* to a PC
   is silent: it has no reason to advertise. The moment it loses its host (because
   the PC is off) and you press the button, it starts advertising while it searches.
   This is the signal we exploit.
2. **The USB port stays powered when the PC is off.** This is a **BIOS setting**, not
   a Windows one, and it is the single point of failure for the whole scheme.

> **This only works for gamepads that advertise over Bluetooth LE.** Xbox Series
> controllers do. Many others do **not**; see
> [Which pads work](#which-pads-work-and-which-do-not).

---

## Requirements

| Need | Why |
|------|-----|
| A **BLE-advertising** gamepad | Xbox Series (X\|S) pads are the known-good case |
| An **ESP32** running ESPHome `bluetooth_proxy` | Does the listening while the PC is off |
| A **USB port that stays powered in S5** | Powers the proxy when the PC is off; **check your BIOS** |
| **Home Assistant** | Converts the advert into a Wake-on-LAN packet |
| **Wake-on-LAN working from S5** | The actual wake mechanism |

You do **not** need: a Raspberry Pi Pico, a custom `.uf2`, soldering, or a vendor
account. If you already run ESPHome and Home Assistant, this is a configuration
exercise.

---

## Step 0: Decide whether your board keeps USB alive in S5

This is the **go/no-go test**, and it is free. Do it before anything else.

### Look up your board's setting

The setting has different names across vendors: it is a **toggle**, and the
default is usually "USB stays powered":

| Vendor | Where | What to look for |
|--------|-------|------------------|
| **ASRock** | Advanced → ACPI Configuration | **Deep Sleep**: `[Disabled]` / `[Enabled in S5]` / `[Enabled in S4 & S5]`. Enabling it **turns USB power OFF** in S5. |
| **ASRock** (some boards) | Advanced → Onboard Devices Configuration | *"USB Power Delivery in Soft Off State (S5)"*: enabling it **keeps USB powered** |
| **ASUS** | Advanced → APM Configuration | **ErP Ready**: `[Disabled]` keeps USB powered; `[Enabled (S4+S5)]` kills it |
| **MSI** | Settings → Advanced → Power Management | **ErP Ready** |
| **Gigabyte** | Settings → Platform Power | **ErP** / *Power Loading* |

The general rule: **"ErP", "Deep Sleep" and "EuP" are energy regulations that
require near-zero standby draw; enabling them removes USB power.** Disable them if
you want a live port.

> 🔴 **Find your exact model's manual.** These names are *not* consistent even
> within one vendor's product line. A wrong guess here wastes an afternoon. Search
> `"<your board>" manual "Deep Sleep"` or `"<your board>" "ErP Ready"` and read the
> ACPI section.

### Verify it empirically: the only test that matters

Never trust the setting name. Measure it:

```bash
# 1. Shut the PC down fully (S5, "power off", not sleep).
# 2. From another machine on the same network, wait ~60 s, then ping the proxy:
ping -c 3 <PROXY_IP>

# 3. If it answers, confirm its API port is open too:
#    (ESPHome's API is 6053 by default)
timeout 3 bash -c "echo > /dev/tcp/<PROXY_IP>/6053" && echo "ALIVE" || echo "DEAD"
```

- **Proxy answers while the PC is off → proceed.** ✅
- **Proxy is dead → stop.** Change the BIOS setting (or use a wall charger; see
  [the wall-charger variant](#variant-a-wall-charger-instead-of-the-pc-usb-port)).

> **A lit mouse is not proof.** Many boards feed standby 5 V to USB *and* light up
> peripheral LEDs, so a glowing mouse means nothing either way. Only a network
> response from the proxy proves the port is live.

---

## Step 1: Identify the gamepad's BLE address

You need the **exact** address, because a second controller or a nearby phone will
otherwise trigger your automation.

### The trap that wastes hours

**Do not look in Home Assistant's device registry.** That list only contains devices
an *integration has claimed*. A raw BLE advertiser **never appears there**; so
"it's not in the registry" proves nothing about whether HA can *see* it.

Use the actual advertisement stream instead. With the pad in **pairing mode** (hold
the pair button until the light flashes fast) and sitting near the proxy:

```python
# Tools are in ../../pc-wake-by-ble-gamepad/tools/; see ble-advert-watch.py
# Subscribe to Home Assistant's bluetooth advertisement stream and filter by name
# or manufacturer ID. Requires: pip install websockets, and a long-lived token.
```

⚠️ **The websocket event payload nests adverts in an `add` list**, not a flat object:

```json
{"type": "event", "event": {"add": [
    {"address": "AA:BB:CC:DD:EE:FF", "rssi": -25, "source": "11:22:33:44:55:66",
     "manufacturer_data": {"6": "0109..."}}
]}}
```

Two fields people get wrong:

- **`source`** is the **scanner/proxy** MAC, *not* the device's address.
- **`manufacturer_data`** keys are **decimal** company IDs. `"6"` is `0x0006` =
  Microsoft. This is how you spot a gamepad even if it rotates its address.

### Confirm the address is stable

A **resolvable private address (RPA) rotates** (~every 15 minutes), and a fixed
address will then stop matching. Check before you build on it:

| Test | Stable (good) | Rotating (bad) |
|------|---------------|----------------|
| Watch for 30+ min | Same address every time | Address changes |
| Two units of the same model | Share a 3-byte **OUI prefix** | No shared prefix |
| Vendor lookup | The prefix is a **registered OUI** | Unregistered |
| OS reports the type | *Public* / *Random static* | *Random resolvable* |

> ⚠️ **A "resolvable" bit pattern is not proof of rotation.** Addresses whose first
> byte has bits 7 and 6 = `01` *look* resolvable, but a **public** address with a
> registered OUI can have the same bits. Confirm with the OUI check and by watching
> over time. Xbox pads use public addresses; some tools mislabel them.

If your pad genuinely rotates, you need its **Identity Resolving Key (IRK)** and
Home Assistant's core **Private BLE Device** integration: a different (and more
involved) path. See [Rotating addresses](#rotating-addresses-the-irk-path).

---

## Step 2: Put the proxy on the PC's USB port

Move (or add) an ESPHome `bluetooth_proxy` onto a USB port that stays live in S5.

> ⚠️ **Powering an ESP32 from the PC's USB port means the PC's port is the proxy's
> only supply.** If the PC is unplugged at the wall, the proxy dies. If that port is
> in a room you rely on for presence tracking, you have made a single point of
> failure. In our setup the PC and the room's TV share a room, so nothing was lost;
> check yours.

You may need to reduce the proxy's WiFi transmit power if it sits in a metal case
next to the PC, and you should confirm the proxy still associates to WiFi with the
PC off (Step 0 already tests this).

---

## Step 3: Add the pad to your presence tracker

The bridge from "BLE advert" to "a state change" is a presence integration. This
repo's reference setup uses **Bermuda BLE Trilateration**, which turns proxy-relayed
adverts into a `device_tracker` entity.

> 🔴 **Bermuda has no websocket API for adding devices.** `bermuda/get_devices`
> does not exist. It is an **OptionsFlow** (config-flow) operation only:
>
> ```
> POST /api/config/config_entries/options/flow            {"handler":"<ENTRY_ID>"}
> POST /api/config/config_entries/options/flow/<flow_id>  {"next_step_id":"selectdevices"}
> POST /api/config/config_entries/options/flow/<flow_id>  {"configured_devices":[<MACs>]}
> ```
>
> Two gotchas: the schema nests its options under
> `data_schema[0].selector.select.options` (not a top-level `options` key), and
> `configured_devices` is the **full list** every time: it **replaces**, it does
> not append. See [`pc-wake-by-ble-gamepad/tools/bermuda-add-tracker.py`](../../pc-wake-by-ble-gamepad/tools/bermuda-add-tracker.py).

Once added, you get a tracker entity. The pad will read **`not_home`** while it is
connected to the PC (it is not advertising) and flip to **`home`** when it powers on
with no host.

---

## Step 4: The automation

Trigger on the tracker going `not_home → home`, and gate it on the PC being off so
you don't spam packets while it's running:

```yaml
# Home Assistant package. See ../../pc-wake-by-ble-gamepad/tools/pc-wake-automation.yaml
automation:
  - id: pc_wake_on_gamepad
    alias: "PC - wake on gamepad"
    triggers:
      - trigger: state
        entity_id: device_tracker.YOUR_PAD_TRACKER
        from: "not_home"
        to: "home"
    conditions:
      # Only wake if the PC is actually off. The magic packet is harmless when the
      # PC is up, but this keeps the log clean and avoids pointless traffic.
      - condition: template
        value_template: >-
          {{ states('binary_sensor.YOUR_PC_STATUS') in ['off','unknown','unavailable'] }}
    actions:
      - action: wake_on_lan.send_magic_packet
        data:
          mac: "AA:BB:CC:DD:EE:FF"          # your PC's NIC MAC
          broadcast_address: "192.168.1.255" # your LAN broadcast
    mode: single
    max_exceeded: silent
```

### Tuning: presence integrations time out fast

Bermuda's `devtracker_nothome_timeout` defaults to **30 seconds**, and its distance
sensors go stale after the same period. A pad's power-on flash lasts only a few
seconds, so the tracker may flap `home → not_home → home` as the pad searches.

- `mode: single` plus a cooldown keeps flapping from spamming WOL.
- If your integration allows it, **raise the not-home timeout**; Bermuda's own
  docs suggest ~300 s for "automate arriving home" use.
- Trigger on the **transition to `home`**, not on the device *staying* home.

---

## Step 5: Test it for real

Do not trust the trigger path in isolation. Test the whole chain:

1. **Confirm the action works** by triggering the automation manually and checking
   that the WOL packet actually wakes the machine.
2. **Shut the PC down fully (S5).** Not sleep.
3. **Confirm the proxy is still alive** (Step 0's ping).
4. **Press the gamepad button.**
5. Watch the tracker flip and the machine boot.

A successful run looks like this; note the latency:

```
tracker: not_home -> home
automation.pc_wake_on_gamepad   FIRED
script.pc_wake                  WOL sent       (0.7 ms after the trigger)
PC reachable via ping: YES
```

---

## Which pads work (and which do not)

The dividing line is **whether the pad advertises over Bluetooth LE when it loses
its host.**

| Pad | Works? | Why |
|-----|--------|-----|
| **Xbox Series X\|S** | ✅ **Yes** | Advertises over BLE; uses a public/static address |
| Xbox One (later models) | ⚠️ Often | Some use BLE, some Classic; test it |
| **DualSense (PS5)** | ❌ No | Bluetooth Classic only; it *pages* the host, which a passive observer cannot see |
| **DualShock 4 (PS4)** | ❌ No | Bluetooth Classic only |
| **Switch Pro** | ❌ No | Bluetooth Classic only |
| 8BitDo pads | ⚠️ Some modes | Works in BLE modes, not Classic modes |
| Most BLE mice/keyboards | ✅ Often | If they advertise, they qualify |

> This is a **protocol limitation, not a bug.** A Classic-only pad never broadcasts
> its intent, so no passive listener can see it, which is also why the community
> wake-dongles list exactly the same "works / doesn't work" split.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Tracker never leaves `not_home` | Pad is connected (silent), or it's out of range, or not a BLE pad |
| Proxy is dead when the PC is off | **BIOS standby-USB setting** (Step 0) |
| Wakes, but the pad then won't connect | Unrelated to this scheme; see the note below |
| False wakes | Another device shares the manufacturer ID; trigger on the exact address |
| Tracker flaps constantly | Presence timeout too short for a brief advert |
| Pad stopped waking the PC, no error anywhere | A lock/helper got stuck `on`; check whether your "PC is off" sensor can even see sleep (see below) |
| PC display sleeps but the PC never does | `powercfg /requests` has a `SYSTEM:` entry vetoing sleep |

### ⚠️ A landmine: don't disable the radio to "simulate" a powered-off PC

While testing, it is tempting to disable the Bluetooth adapter to make the pad lose
its host. **Do not use `pnputil /disable-device` for this.**

On Windows, `pnputil /disable-device "<instance-id>"` can print *"Failed to disable
device… pending system reboot"* and *"not supported on this OS product"*, **and
queue the disable anyway.** The next boot brings the radio up in a PnP **Error**
state (`problemCode=22`, `CM_PROB_DISABLED`), and the pad then cannot connect at all.
It looks *exactly* like a faulty controller. It is not.

`Disable-PnpDevice` is no better: it fails outright on many adapters (`Generic
failure`, HRESULT `0x80041001`).

**Recovery** (no reboot needed):

```powershell
# Re-enable the adapter by its instance ID. This alone usually clears it.
pnputil /enable-device "<instance-id>"
```

If that fails, cycle it, then restart the Bluetooth service (`bthserv`), then reboot.
**Use a real shutdown to test S5 behaviour**: never a device-disable.

### ⚠️ A ping probe cannot see S3 sleep

You will eventually want the PC to sleep rather than stay powered off, and the
usual shortcut is to reuse an existing "is the PC up?" ping sensor for the wake
automation's condition. **Do not, and if you already do, read this.**

On the machine this was built for, the Realtek NIC keeps its PHY powered in S3 so
that Wake-on-LAN keeps working, and Windows still services ICMP. So during sleep:

- `ping` answers, every time.
- `ssh` connects and returns a shell.
- The monitor reports `Active=True` (the TV is still on, just showing no signal).

A sleeping PC is therefore **indistinguishable from a running one** to a ping. If
you have ever written a "wait until the machine is off, then re-arm something"
rule against that sensor, it will hang forever. Here it silently wedged a lock
that was supposed to block wake-during-shutdown, which meant **the pad stopped
waking the PC at all** and nothing in the UI said why.

Check the truth with the OS rather than the network:

```powershell
# Did it actually go to sleep? (42 = entering sleep, 107 = resumed)
Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='Microsoft-Windows-Kernel-Power';Id=42,107} -MaxEvents 10 |
  Select-Object TimeCreated,Id | Format-Table -AutoSize
```

The fix is to make any "wait for it to settle" rule **release on either state**
after a dwell, rather than only on the quiet one. Hold the lock only while the
machine is genuinely flapping between the two, which is the case the dwell exists
to catch.

> **Measure at a higher resolution than the system you are measuring.** A
> 60-second ping sensor will happily convince you that a 23-second shutdown took
> three and a half minutes. It did not. Sample the machine directly at 1-2 s while
> you diagnose, and only then set your automation intervals.

### ⚠️ An orphaned audio stream will stop a PC from ever sleeping

Unrelated to Bluetooth, but it bit us here and it is invisible, so it is worth
knowing about.

If the PC's display goes off but the machine never sleeps, run this **first**:

```powershell
powercfg /requests
```

Anything listed under `SYSTEM:` is an unconditional veto on automatic sleep. A
streaming server that opens a microphone and then exits without closing it will
leave a driver-level entry behind **forever**, and the machine will never sleep
again no matter how the power settings are configured. In our case a
`Steam Streaming Microphone` entry survived long after the application that
created it had exited.

The fix is to restart the audio service, which tears down every open stream:

```powershell
Restart-Service Audiosrv -Force
powercfg /requests      # the SYSTEM: block should now be empty
```

If the application that opened the stream installs its own virtual audio
device, also turn that off in the application's own configuration. A manual
`Disable-PnpDevice` is not a fix here for two reasons: the stream lives in the
audio service rather than the device, and the application re-installs the driver
on every start, silently undoing your change.

---

## Variant: a wall charger instead of the PC USB port

If your board cannot keep USB alive in S5, or you would rather not put the proxy on
the PC at all, **put the proxy on any always-on 5 V supply** near the PC (a phone
charger, a TV USB port, a powered hub) and skip Step 0 entirely.

The only requirement is that the proxy and the pad are in range of each other. This
is strictly simpler and removes the single-point-of-failure risk; it just costs one
spare charger.

---

## Rotating addresses: the IRK path

If your pad genuinely rotates its address, a fixed-address tracker will not hold. You
need the pad's **Identity Resolving Key** and Home Assistant's core
[Private BLE Device](https://www.home-assistant.io/integrations/private_ble_device/)
integration, which resolves the rotating addresses back to one logical device.

You can obtain an IRK from a host the device has paired with:

- **Windows:** `HKLM\SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Keys\<adapter>\<device>`.
  This key is ACL'd to **SYSTEM**, so an ordinary (even elevated) read returns an
  *empty listing* rather than an error. You need SYSTEM context.
- **Android (rooted):** `/data/misc/bluedroid/bt_config.conf`, first 16 bytes of
  `LE_KEY_PID`; **little-endian, reverse the bytes**.
- **macOS:** Keychain Access → *Bluetooth* → find the record → *Show password* →
  **Remote IRK** (base64).

> 🔴 **Verify the IRK before trusting it.** A BLE RPA is
> `prand (high 3 bytes) || hash (low 3 bytes)`, and the IRK resolves it via
> `ah(k, r) = AES-128-ECB(k, 13 zero bytes || prand)[0:3] == hash`. Getting the
> prand/hash order backwards makes a perfectly good key look broken. See
> [`pc-wake-by-ble-gamepad/tools/verify-irk.py`](../../pc-wake-by-ble-gamepad/tools/verify-irk.py), which tests **both byte
> orders** and tells you which one actually works.

⚠️ Note the two most significant bits of `prand` must be `0b01` for an address to be
a valid RPA at all. If they are not, no IRK can resolve it; you are probably looking
at a **public** address that merely resembles an RPA.

---

## Security notes

- **This does not expose anything to the internet.** Everything is LAN-local: BLE
  advertisement → WiFi → Home Assistant → a magic packet on your own subnet.
- **A magic packet is unauthenticated.** Anyone on your LAN can wake the PC. That is
  inherent to Wake-on-LAN, not to this scheme.
- **Do not port-forward Home Assistant or the proxy** to make this work from outside.
  If you want that, use a VPN.
- **The proxy's ESPHome API** should stay on your LAN. If you enable its fallback
  hotspot, give it a password.

---

## Credits & prior art

The idea of waking a PC from a BLE device is not new; this document exists because the
*implementation* can reuse hardware most self-hosters already have:

- [`kungaa/PC-wake-dongle`](https://github.com/kungaa/PC-wake-dongle): a Pico W / Pico 2 W
  USB dongle that does this with custom firmware (TinyUSB HID + BTstack). Its
  "what works / what doesn't" table is the clearest statement anywhere of the
  Classic-vs-BLE limitation, and it is what confirmed an unhosted Xbox Series pad
  advertises.
- [ESPHome `bluetooth_proxy`](https://esphome.io/components/bluetooth_proxy/)
- [Bermuda BLE Trilateration](https://github.com/agittins/bermuda)
- [Home Assistant `private_ble_device`](https://www.home-assistant.io/integrations/private_ble_device/)

See [`../REFERENCES.md`](../REFERENCES.md) for the full source list.
