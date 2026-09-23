#!/usr/bin/env python3
"""Time2 MIP12 — SetLanWifi sender, reconstructed from the vendor app's own frame.

✅ SOLVED 2026-09-23. The camera now joins WiFi and streams from its new DHCP
address; the Ethernet cable is gone.

🔴 KEY FACTS (the whole point of this file)
  * The frame is sent as a BROADCAST to 255.255.255.255:2627 — NOT unicast :5000.
    That was the missing piece; the bencode body had been correct for weeks.
  * Body is RAW bencode (no 0xE9 XOR — that encoder is only used in the
    dictionary/handshake phase of the video socket).
  * The Wi-Fi password is XOR 0x3C over the WHOLE string.
  * The frame is deterministic (byte-identical across runs) — no nonce/session.
  * `MacIP` is the camera's *wired* (Ethernet) MAC, not the WiFi MAC.
  * Per the vendor guide the camera only reboots onto WiFi AFTER the Ethernet
    cable is removed; it accepts the write silently.

The frame was recovered by capturing the vendor app (`x.p2p.cam`) live with
strace inside an x86_64 Android emulator on the real LAN:

    sendto(71, "\\0\\0p\\n2I\\35\\243\\0d\\0\\0\\0d7:MainCmd3:7006:isopen1:1…",
           167, MSG_NOSIGNAL,
           {sin_port=htons(2627), sin_addr=inet_addr("255.255.255.255")})

⚠️ Nothing is sent unless you run it — there is no hidden "apply".

Usage:
    python3 wifi_setup.py --ssid MyNet --password hunter2
    python3 wifi_setup.py --ssid MyNet --password hunter2 --mac aa:bb:cc:dd:ee:ff
    python3 wifi_setup.py --dry-run --ssid MyNet --password hunter2
"""
from __future__ import annotations

import argparse
import socket
import sys
import time

XOR_KEY = 0x3C
DISCOVERY_PORT = 2627
VIDEO_PORT = 5000

# 13-byte header captured verbatim from the app.
# Layout: 00 00 | 70 0a | 32 49 1d a3 | 00 64 | 00 00 00
#   byte[4]    = 0x32   (the constant "inner_cmd" seen across the protocol)
#   byte[9]    = 0x64   (100 — the command id the app uses for this write)
SETWIFI_HEADER = bytes.fromhex("0000700a32491da30064000000")

# 13-byte keepalive ping the app sends to the camera's :5000 before the write
HANDSHAKE_PING = bytes.fromhex("0000d000820b700900d1070000")


def encode_password(password: str) -> bytes:
    """XOR every byte with 0x3C — verified byte-for-byte against the capture.

    Proof: ``'hunter2'`` -> ``54 49 52 48 59 4e 0e``.
    """
    return bytes((ord(ch) ^ XOR_KEY) & 0xFF for ch in password)


def build_frame(ssid: str, password: str, mac: str) -> bytes:
    """Reconstruct the exact 167-byte SetLanWifi frame the vendor app emits."""
    body = (
        b"d"
        b"7:MainCmd3:700"
        b"6:isopen1:1"
        b"5:MacIP" + f"{len(mac)}:{mac}".encode()
        + b"9:encrytype4:auto"
        + b"7:wifisid" + f"{len(ssid)}:{ssid}".encode()
        + b"8:safetype4:auto"
        + b"12:wifipassword" + f"{len(password)}:".encode() + encode_password(password)
        + b"9:bootproto4:dhcp"
        + b"e"
    )
    return SETWIFI_HEADER + body


def main() -> int:
    ap = argparse.ArgumentParser(description="Time2 MIP12 SetLanWifi sender")
    ap.add_argument("--ssid", required=True, help="target WiFi SSID")
    ap.add_argument("--password", required=True, help="target WiFi PSK")
    ap.add_argument("--mac", default="",
                    help="camera WIRED (Ethernet) MAC — what ARP reports while cabled")
    ap.add_argument("--camera", default="",
                    help="camera's current IP (for the keepalive ping); optional")
    ap.add_argument("--listen", type=float, default=6.0,
                    help="seconds to wait for a camera reply")
    ap.add_argument("--dry-run", action="store_true", help="print the frame, send nothing")
    args = ap.parse_args()

    frame = build_frame(args.ssid, args.password, args.mac)
    print(f"ssid={args.ssid!r} mac={args.mac!r} frame_len={len(frame)}")
    print(f"frame={frame.hex()}")

    if len(frame) != 167:
        print(f"⚠️  expected 167 bytes, got {len(frame)} — check mac length",
              file=sys.stderr)

    if args.dry_run:
        print("dry-run: nothing sent.")
        return 0

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("", 0))
    sock.settimeout(2.0)

    if args.camera:
        print("1) handshake ping -> camera:5000 x3")
        for _ in range(3):
            sock.sendto(HANDSHAKE_PING, (args.camera, VIDEO_PORT))
            time.sleep(0.3)

    print("2) SetLanWifi -> 255.255.255.255:2627 x5")
    for _ in range(5):
        sock.sendto(frame, ("255.255.255.255", DISCOVERY_PORT))
        time.sleep(0.4)

    print(f"3) listening {args.listen:.0f}s for camera reply...")
    deadline = time.time() + args.listen
    replies = 0
    try:
        while time.time() < deadline:
            data, addr = sock.recvfrom(4096)
            replies += 1
            print(f"   <- {addr}: {len(data)} bytes: {data[:64]!r}")
    except socket.timeout:
        pass
    finally:
        sock.close()

    print(f"replies={replies}  (the camera acks the pings and accepts the write "
          f"silently; it reboots onto WiFi once the Ethernet cable is removed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
