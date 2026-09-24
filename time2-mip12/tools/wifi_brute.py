#!/usr/bin/env python3
"""Brute-force the Time2 MIP12 WiFi-set envelope (inner_cmd sweep 0x00-0xFF).

Body is known (sid=..;pswd=..;mac=..;satype=..;entype=..;).  We hunt the
envelope: for each candidate `inner_cmd` we send the WiFi body and watch for
either (a) a non-video reply, or (b) the camera stopping its video stream
(reboot indicator).

⚠️ single-client: stop time2-bridge first. Placeholder SSID only.
"""
import select
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "/docker/camera/time2")
from p2pcam.lan_scanner import LanScanner
from p2pcam.lan_video import (
    _build_hk_res_req, _build_icmd1_ack, _build_icmd2_poll, _build_packet,
    _build_ping1, _build_ping2, _build_session_delete, _build_session_start,
    _is_icmd1_poll, _is_session_create, _xor_encode, _DEFAULT_SID,
)

IP, HKID, VID = "<CAMERA-IP>", 5000, 5000
POLL = 0.17


def main() -> int:
    mac = "<CAMERA-MAC>"
    body = f"sid=PROBE-NET;pswd=;mac={mac};satype=auto;entype=auto;"

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", 0))
    s.settimeout(0.05)
    seq = [0]

    def send(b):
        s.sendto(b, (IP, VID))

    def drain(t):
        out = []
        dl = time.monotonic() + t
        last = time.monotonic()
        while time.monotonic() < dl:
            now = time.monotonic()
            if now - last >= POLL:
                seq[0] += 1
                send(_build_icmd2_poll(HKID, seq[0]))
                last = now
            r, _, _ = select.select([s], [], [], 0.03)
            if r:
                d, (src, _) = s.recvfrom(65535)
                if src == IP:
                    out.append(d)
        return out

    # handshake
    for _ in range(3):
        send(_build_ping1()); time.sleep(0.003)
    drain(0.5)
    for _ in range(9):
        send(_build_ping2()); time.sleep(0.001)
    send(_build_hk_res_req(HKID, _DEFAULT_SID))
    for _ in range(3):
        seq[0] += 1; send(_build_icmd2_poll(HKID, seq[0])); time.sleep(0.001)
    ok = False
    dl = time.monotonic() + 10
    while time.monotonic() < dl:
        pk = drain(0.2)
        for d in pk:
            if _is_session_create(d):
                ok = True
                break
            if _is_icmd1_poll(d):
                seq[0] += 1; send(_build_icmd1_ack(HKID, seq[0]))
        if ok:
            break
    if not ok:
        print("❌ no session")
        return 1
    send(_build_session_start(_DEFAULT_SID))
    print("✅ session up: sweeping inner_cmd 0x00..0xff")

    hits = []
    for cmd in range(0x00, 0x100):
        for f1, f2, ex in ((0x51, 0xC4, bytes([0x64, 0, 0, 0])),):
            pkt = _build_packet(counter=3, inner_cmd=cmd, inner_flag1=f1,
                                inner_flag2=f2, inner_extra=ex, body=_xor_encode(body))
            send(pkt)
        obs = drain(0.25)
        nonvid = [d for d in obs if len(d) != 904 and not _is_icmd1_poll(d)]
        if nonvid:
            hits.append((cmd, nonvid))
            print(f"  🔔 cmd={cmd:#04x}: {len(nonvid)} non-video reply → "
                  f"{nonvid[0][:32].hex(' ')}")
        if cmd % 0x20 == 0:
            print(f"  … {cmd:#04x}")
    # any non-video reply across the dark sweep is a candidate
    print(f"\n  {len(hits)} candidate(s)")

    send(_build_session_delete(_DEFAULT_SID))
    s.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
