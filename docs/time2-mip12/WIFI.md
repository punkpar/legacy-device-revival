# Time2 MIP12 — setting WiFi over HeKai/HK

> **Status: ✅ SOLVED.** The camera is now running **wirelessly**, configured entirely
> locally. This page documents the exact command, the frame layout, and the two
> non-obvious details that cost us the most time.

The camera's only configuration interface is the HeKai/HK protocol
([PROTOCOL.md](PROTOCOL.md)). WiFi credentials are set with **`MainCmd=700`**
(`SetLanWifi`).

This was solved by capturing the **vendor app itself** ([EMULATOR.md](EMULATOR.md)
has the capture recipe — the app is `armeabi`-only, so it needs an emulator or an
old 32-bit ARM device).

---

## 1. The two things that were wrong

Everything in this project's early notes about "the config channel" was a
reasonable guess that turned out to be **wrong** in two ways. Both are corrected
here.

### 🔴 1. It is a **broadcast to `:2627`** — not a unicast to `:5000`

The single decisive line from the capture:

```
sendto(71, "\0\0p\n2I\35\243\0d\0\0\0d7:MainCmd3:7006:isopen1:15:MacIP…", 167,
       MSG_NOSIGNAL,
       {sin_port=htons(2627), sin_addr=inet_addr("255.255.255.255")})
```

**Destination is `255.255.255.255:2627`.** The bencode body was right for weeks — it
was simply being aimed at the camera's video socket (`:5000`, where the handshake
lives) instead of the discovery broadcast port.

It makes sense in hindsight: `SetLanWifi` is a **provisioning** command. The camera
may not even have a working session yet, so the command rides the same broadcast
channel as discovery.

### 🔴 2. The body is **raw bencode** — no `0xE9` XOR

Everything else in the protocol XORs its dictionary bodies with `0xE9`. The
`SetLanWifi` body does **not**. Sibling commands XOR; this one is plain ASCII.

### And a third, smaller one

Earlier notes described a fixed envelope — `inner_cmd=0x32 / flag1=0x8B /
flag2=0xC5 / extra=51 01 00 00` — with the command id buried in the body. The real
frame is simpler: a **13-byte header whose byte[9] is the command id**, then the
bencode body follows directly.

---

## 2. The exact frame

167 bytes total. **Deterministic** — byte-identical across runs, so there is **no
nonce, session id or timestamp** to reproduce.

```
HEADER (13 bytes)
  00 00 70 0a 32 49 1d a3 00 64 00 00 00
                             ^^^^^
                             byte[9] = 0x64 = 100 = command id (SetLanWifi)

BODY (raw bencode, no XOR)
  d7:MainCmd3:7006:isopen1:15:MacIP17:<wired-mac>9:encrytype4:auto
  7:wifisid8:<ssid>8:safetype4:auto12:wifipassword13:<13 bytes>9:bootproto4:dhcpe
```

Concretely, for SSID `MyNetwork` and wired MAC `aa:bb:cc:dd:ee:ff`:

```text
00 00 70 0a 32 49 1d a3 00 64 00 00 00
d7:MainCmd3:7006:isopen1:15:MacIP17:aa:bb:cc:dd:ee:ff
 9:encrytype4:auto
 7:wifisid8:MyNetwork
 8:safetype4:auto
12:wifipassword13:<13 raw bytes>
 9:bootproto4:dhcpe
```

### Field map

| Key | Type | Value seen | Notes |
|-----|------|------------|-------|
| `MainCmd` | string | `700` | SetLanWifi |
| `isopen` | string | `1` | **a string** `"1"`, not an integer |
| `MacIP` | string | the camera's **wired** MAC | the **wired/Ethernet** MAC — see below |
| `encrytype` | string | `auto` | |
| `wifisid` | string | the SSID | |
| `safetype` | string | `auto` | |
| `wifipassword` | string | 13 bytes | **XOR `0x3C` over the whole string** |
| `bootproto` | string | `dhcp` | |

### 🔴 `MacIP` is the **wired** MAC

This is counter-intuitive and the earlier notes got it backwards. `MacIP` is the
**Ethernet** MAC — the one you get from `arp -a` while the camera is still cabled
(and the one that identifies the device on the LAN). It is *not* the WiFi MAC.

You can read it before you ever configure WiFi:

```bash
arp -a | grep <camera-ip>      # or: ip neigh | grep <camera-ip>
```

### The password encoding — corrected

The password is XORed with **`0x3C` over every byte** — the whole string, not "from
index 2" as one earlier note claimed. (The "from index 2" theory came from reading a
*different* helper in the disassembly; the *capture* is unambiguous.)

Worked example, password `hunter2`:

```text
plain:    68 75 6e 74 65 72 32         h u n t e r 2
XOR 0x3C: 54 49 52 48 59 4e 0e         T I R H Y N .
```

A nice tell when eyeballing a hex dump: `ord('6') ^ 0x3C == 0x0a`, so **any passphrase
ending in `6` produces trailing `0x0a` (newline-looking) bytes** in the encoded blob.

```python
def encode_password(pw: str) -> bytes:
    return bytes((ord(c) ^ 0x3C) & 0xFF for c in pw)
```

---

## 3. Sending it

The full preamble the app uses before the write:

1. A **`LocalData` discovery broadcast** to `255.255.255.255:2627`:

   ```text
   TIME=3600;endTime=<unix+3600>;MainCmd=LocalData;userType=hkclient;
   status=1;Prot=5000;MacIP=0x0xba007050:<ts>;
   ```

2. 13-byte **handshake pings** to the camera's `:5000`:
   `00 00 d0 00 82 0b 70 09 00 d1 07 00 00`
   — the camera ACKs each with:
   `00 00 d0 00 92 0b 40 09 00 d1 07 00 00`

3. The **`SetLanWifi` broadcast** (the 167-byte frame above).

Reference implementation: [`tools/wifi_setup.py`](../../time2-mip12/tools/wifi_setup.py).

### 🔴 Remove the Ethernet cable to complete it

The camera accepts the write, but per Time2's own manual it only **restarts onto
WiFi once the cable is unplugged**. Observed: the write is silent on the wire (the
camera acks the pings and nothing else) and it comes up on WiFi a few seconds after
the cable is removed.

**Verify:** the wired IP stops answering and a new IP appears from the camera's
**WiFi MAC**:

```bash
# while cabled
ip neigh | grep <camera-wired-ip>

# after the write + unplug — the WiFi MAC appears on a (possibly new) IP
arp -a | grep <camera-oui>
```

---

## 4. Reading WiFi state back (optional)

Two read commands exist on the same channel:

| `MainCmd` | Meaning |
|-----------|---------|
| `703` | `DoLanGetWifiSid` — scan neighbouring SSIDs |
| `204` | read device / video + network info |

These are sent the **dict-style** way (raw bencode, with the first 2 bytes of the
*bencode* plain and the rest XORed with `0xE9`) — i.e. they are **not** laid out
like the `700` write above. You generally don't need them; the write works without
them.

---

## 5. AP-mode fallback (if you ever lose the config)

If the camera has no Ethernet *and* no WiFi credential, it falls back to a setup
access point. Two quirks catch people out:

- The AP is an **ad-hoc / IBSS cell**, not a normal infrastructure AP. `nmcli` will
  refuse it; force it at the driver level (`iw dev <if> set type ibss`, then
  `ibss join`).
- The camera runs a **DHCP server** on a private range; give yourself a client
  address in that range.

Once joined, the full HeKai protocol works (pings, `204`, `700`) — a handy recovery
path.

---

## 6. Timeline of the "solved" claim

For transparency: the earlier state of this page said the command was
*"identified but not working"*. That was accurate at the time. The resolution was
purely a matter of getting a capture:

| Stage | Result |
|-------|--------|
| Static RE of `libcaptetown1.so` | found `MainCmd=700` and the key names — **correct** |
| Live testing on `:5000` | nothing happened — **wrong socket** |
| Emulated the native encode path | recovered the body, still wrong framing |
| **Captured the vendor app** | revealed **broadcast `:2627`** + `MacIP`-is-wired — **done** |

The lesson, if there is one: the static work found the *what*; only a capture found
the *where*.
