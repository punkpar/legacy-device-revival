# Wake a PC with a Bluetooth gamepad: no dongle, no custom firmware

Most gamepads can't wake a PC, sweetie. The PC's Bluetooth stack is asleep and nothing is listening when you press the button.

The fix is to move the listening *outside* the PC. A tiny ESP32 running ESPHome `bluetooth_proxy` sits on a USB port that stays powered when the PC is off, relays the pad's advertisement over WiFi to Home Assistant, and Home Assistant sends a Wake-on-LAN packet. Proven end-to-end on a stock Xbox Series pad waking a fully powered-off (S5) PC.

> Prefer a purpose-built dongle? [`kungaa/PC-wake-dongle`](https://github.com/kungaa/PC-wake-dongle) is excellent. This guide is the no-new-hardware route.

```
[gamepad]  --BLE advertisement-->  [ESP32 BLE proxy]  --WiFi-->  [Home Assistant]
  power on                          on a USB port that            sees the advert
                                    stays live in S5                   |
                                                                       v
[PC boots]  <------------------- magic packet  <------------------  Wake-on-LAN
```

---

## What you need

Two facts have to hold. Test both on your own hardware:

1. **The pad advertises over BLE when it has no host.** Connected = silent. PC off + button press = advertising while it searches. Xbox Series pads do this; many others don't ([which pads](#which-pads-work-and-which-do-not)).
2. **The USB port stays powered when the PC is off.** A BIOS setting (ErP / Deep Sleep), not Windows. This is the single point of failure.

| Need | Notes |
|------|-------|
| BLE-advertising gamepad | Xbox Series X\|S is the known-good case |
| ESP32 with ESPHome `bluetooth_proxy` | Does the listening while the PC is off |
| USB port live in S5 (or a wall charger) | Check BIOS; fallback is any always-on 5 V supply |
| Home Assistant + working Wake-on-LAN | Converts the advert into a magic packet |

No Pico, no custom firmware, no soldering, no vendor account.

---

## Step 0: Confirm USB stays alive in S5

This is the go/no-go test, do it first. Look up your board's standby-USB setting (ErP / Deep Sleep / EuP; names vary by vendor so check your exact model's manual), disable the power-saving mode, then verify empirically:

```bash
# 1. Shut the PC down fully (S5, not sleep). Wait ~60 s.
ping -c 3 <PROXY_IP>
timeout 3 bash -c "echo > /dev/tcp/<PROXY_IP>/6053" && echo "ALIVE" || echo "DEAD"
```

Proxy answers while the PC is off: proceed. Dead: change the BIOS setting, or power the proxy from a wall charger instead ([variant](#variant-a-wall-charger-instead-of-the-pc-usb-port)).

> A lit mouse proves nothing. Only a network response from the proxy counts.

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
| Lock released early / never released | You branched on state and waited inside the branch; see below |
| Changing a YAML option had no effect | The key may be wrong and the config check will not say so (see below) |
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

### ⚠️ A ping sensor can't see sleep

Some NICs keep answering ping in S3 sleep (ours did, Realtek PHY stays up for WOL). A sleeping PC then looks identical to a running one, and any "wait until it's off" rule hangs forever. Check sleep state with the OS, not the network:

```powershell
Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='Microsoft-Windows-Kernel-Power';Id=42,107} -MaxEvents 10 |
  Select-Object TimeCreated,Id | Format-Table -AutoSize
```

And if the PC never sleeps at all, run `powercfg /requests` first. Anything under `SYSTEM:` vetoes sleep unconditionally. A leaked audio stream (ours was a streaming server's mic left open) holds it forever; `Restart-Service Audiosrv -Force` clears it.

---

## Variants

**No live USB port?** Power the proxy from any always-on 5 V supply (phone charger, TV USB, powered hub) and skip Step 0. Only requirement: proxy and pad in range.

**Rotating address?** You need the pad's Identity Resolving Key plus HA's [Private BLE Device](https://www.home-assistant.io/integrations/private_ble_device/) integration. IRK sources: Windows (`BTHPORT\Parameters\Keys`, needs SYSTEM context), rooted Android (`/data/misc/bluedroid/bt_config.conf`, reverse the bytes), macOS Keychain (Remote IRK). Verify with [`tools/verify-irk.py`](../../pc-wake-by-ble-gamepad/tools/verify-irk.py); it tests both byte orders.

---

## Safety

LAN-local only: BLE to WiFi to HA to magic packet on your own subnet. A magic packet is unauthenticated by design, so never port-forward HA or the proxy for this. Use a VPN.

Prior art: [`kungaa/PC-wake-dongle`](https://github.com/kungaa/PC-wake-dongle), [ESPHome `bluetooth_proxy`](https://esphome.io/components/bluetooth_proxy/), [Bermuda](https://github.com/agittins/bermuda). Full sources in [`../REFERENCES.md`](../REFERENCES.md).
