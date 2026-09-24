#!/usr/bin/env python3
"""Time2 MIP12 WiFi-set envelope sweeper.

CONTEXT
-------
The camera's WiFi-set op is the HeKai ``SetLanWifi``.  We now know the *body*
exactly (recovered 2026-09-23 from the shipping app `x.p2p.cam`, see
``wifi_setup.py``):

    sid=<ssid>;pswd=<pwd>;mac=<mac>;satype=<security>;entype=<enc>;

What we do NOT know is the *transport envelope* that marks this as a WiFi-set
command.  Normal LAN chat rides the video socket (:5000) as

    [counter u16][inner_cmd u8][flag1 u8][flag2 u8][pad u8][extra 4B][body]

with ``inner_cmd`` = 0x32 for dict-style bodies (XOR 0xe9, first 2 bytes plain)
and 0x10 for ICMD-style bodies (XOR 0xe9, all bytes).  The recorded
``MainCmd=700`` could never be verified statically.

This tool:
  1. Performs the *full* working handshake (copied from LanVideoClient).
  2. Sends one candidate envelope + the real WiFi body.
  3. Watches for (a) a non-video reply, or (b) the camera rebooting.

⚠️ The camera is SINGLE-CLIENT: `docker stop time2-bridge` before running.

⚠️ SAFETY: the WiFi body points the camera at YOUR SSID.  Once it succeeds the
camera **reboots and leaves the cable**.  Sweep candidates are body-only probes
until you explicitly pass ``--real-creds``; by default a harmless placeholder
SSID is used so an accidental hit is reversible.
"""
from __future__ import annotations

import argparse
import select
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from p2pcam.lan_scanner import LanScanner  # noqa: E402
from p2pcam.lan_video import (  # noqa: E402
    _build_hk_res_req,
    _build_icmd1_ack,
    _build_icmd2_poll,
    _build_packet,
    _build_ping1,
    _build_ping2,
    _build_session_delete,
    _build_session_start,
    _is_icmd1_poll,
    _is_session_create,
    _xor_encode,
    _xor_encode_all,
    _DEFAULT_SID,
)

VIDEO_PORT = 5000
MAX_PAYLOAD = 65535


class Camera:
    """A connected, streaming-capable HeKai session (single-client)."""

    def __init__(self, ip: str, hkid: int, sid: str = _DEFAULT_SID):
        self.ip = ip
        self.hkid = hkid
        self.sid = sid
        self.seq = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # 🔴 local_port=0, never bind :5000, it collides with the camera session.
        self.sock.bind(("", 0))
        self.streaming = False

    # -- low level ---------------------------------------------------------
    def send(self, b: bytes) -> None:
        self.sock.sendto(b, (self.ip, VIDEO_PORT))

    def recv(self, timeout: float = 0.05):
        r, _, _ = select.select([self.sock], [], [], timeout)
        if not r:
            return None, None
        d, (src, _) = self.sock.recvfrom(MAX_PAYLOAD)
        return d, src

    # -- handshake ---------------------------------------------------------
    def connect(self, timeout: float = 10.0) -> bool:
        for _ in range(3):
            self.send(_build_ping1())
            time.sleep(0.003)
        # wait for ping-ack
        dl = time.monotonic() + 2.0
        got = False
        while time.monotonic() < dl and not got:
            d, src = self.recv(0.1)
            if d and src == self.ip and len(d) == 13 and d[4] == 0x92:
                got = True
        if not got:
            return False

        for _ in range(9):
            self.send(_build_ping2())
            time.sleep(0.001)

        self.send(_build_hk_res_req(self.hkid, self.sid))
        for _ in range(3):
            self.seq += 1
            self.send(_build_icmd2_poll(self.hkid, self.seq))
            time.sleep(0.001)

        # wait for SessionCreate
        dl = time.monotonic() + timeout
        last = 0.0
        while time.monotonic() < dl:
            now = time.monotonic()
            if now - last >= 0.17:
                self.seq += 1
                self.send(_build_icmd2_poll(self.hkid, self.seq))
                last = now
            d, src = self.recv(0.05)
            if not d or src != self.ip:
                continue
            if _is_session_create(d):
                self.send(_build_session_start(self.sid))
                self.streaming = True
                return True
            if _is_icmd1_poll(d):
                self.seq += 1
                self.send(_build_icmd1_ack(self.hkid, self.seq))
        return False

    # -- config injection --------------------------------------------------
    def send_config(
        self,
        body: str,
        *,
        counter: int = 0x0003,
        inner_cmd: int = 0x32,
        flag1: int = 0x51,
        flag2: int = 0xC4,
        extra: bytes = bytes([0x64, 0, 0, 0]),
        icmd_style: bool = False,
        repeat: int = 1,
        gap: float = 0.02,
    ) -> None:
        enc = _xor_encode_all if icmd_style else _xor_encode
        pkt = _build_packet(
            counter=counter,
            inner_cmd=inner_cmd,
            inner_flag1=flag1,
            inner_flag2=flag2,
            inner_extra=extra,
            body=enc(body),
        )
        for _ in range(repeat):
            self.send(pkt)
            time.sleep(gap)

    def observe(self, seconds: float = 3.0) -> list[tuple[int, int, bytes]]:
        """Collect (size, byte4, head) of every packet for `seconds`."""
        out = []
        dl = time.monotonic() + seconds
        last = time.monotonic()
        while time.monotonic() < dl:
            now = time.monotonic()
            if self.streaming and now - last >= 0.17:
                self.seq += 1
                self.send(_build_icmd2_poll(self.hkid, self.seq))
                last = now
            d, src = self.recv(0.05)
            if d and src == self.ip:
                out.append((len(d), d[4] if len(d) > 4 else -1, d[:32]))
        return out

    def close(self) -> None:
        try:
            self.send(_build_session_delete(self.sid))
        except Exception:  # noqa: BLE001
            pass
        self.sock.close()


def discover(uid: str | None):
    for d in LanScanner().refresh(timeout=6):
        if uid is None or uid.lower() in (d.device_id or "").lower() or str(d.hkid) == str(uid):
            return d
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uid", default="<DEVICE-ID>")
    ap.add_argument("--ip")
    ap.add_argument("--hkid", type=int, default=5000)
    ap.add_argument("--ssid", default="PROBE-NET", help="SSID in the body (placeholder by default)")
    ap.add_argument("--password", default="")
    ap.add_argument("--satype", default="auto")
    ap.add_argument("--entype", default="auto")
    ap.add_argument("--real-creds", action="store_true", help="allow a real SSID/password (dangerous)")
    ap.add_argument("--candidates", help="comma list of envelopes cmd:f1:f2:extrahex, else built-in list")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--observe", type=float, default=3.0)
    args = ap.parse_args()

    # resolve camera
    ip, hkid, devid, mac = args.ip, args.hkid, args.uid, ""
    if not ip:
        d = discover(args.uid)
        if d is None:
            print("❌ camera not found by LAN discovery")
            return 2
        ip, hkid, devid = d.ip, d.hkid or hkid, d.device_id or devid
    import subprocess
    try:
        neigh = subprocess.run(["ip", "neigh", "show", ip], capture_output=True, text=True).stdout
        if "lladdr" in neigh:
            mac = neigh.split("lladdr")[1].split()[0]
    except Exception:  # noqa: BLE001
        pass

    if not args.real_creds and args.ssid != "PROBE-NET":
        print("⚠️  refusing to use a real-looking SSID without --real-creds")
        return 2

    body = f"sid={args.ssid};pswd={args.password};mac={mac};satype={args.satype};entype={args.entype};"
    print("═══ target ═══")
    print(f"  camera : {devid} @ {ip} (hkid={hkid}, mac={mac or '?'})")
    print(f"  body   : {body}")

    # candidate envelopes
    if args.candidates:
        cands = []
        for c in args.candidates.split(","):
            cmd, f1, f2, ex = c.split(":")
            cands.append((int(cmd, 0), int(f1, 0), int(f2, 0), bytes.fromhex(ex)))
    else:
        cands = [
            (0x32, 0x51, 0xC4, bytes([0x64, 0, 0, 0])),   # same as SessionStart
            (0x32, 0x8B, 0xC5, bytes([0x51, 1, 0, 0])),   # same as HK_RES_REQ
            (0x10, 0x03, 0x00, bytes([0xD1, 7, 0, 0])),   # ICMD2 style
        ]
    print(f"\n  {len(cands)} candidate envelope(s)")

    cam = Camera(ip, hkid)
    if not cam.connect(timeout=args.timeout):
        print("❌ handshake failed: is time2-bridge stopped? is the camera awake?")
        cam.close()
        return 1
    print("✅ session established\n")

    baseline = cam.observe(2.0)
    print(f"  baseline: {len(baseline)} packets in 2s "
          f"(video sizes: {sorted({s for s, _, _ in baseline})[:4]}…)")

    for i, (cmd, f1, f2, ex) in enumerate(cands, 1):
        print(f"\n── candidate {i}: inner_cmd={cmd:#04x} f1={f1:#04x} f2={f2:#04x} extra={ex.hex(' ')}")
        cam.send_config(body, inner_cmd=cmd, flag1=f1, flag2=f2, extra=ex, repeat=3, gap=0.03)
        obs = cam.observe(args.observe)
        sizes = sorted({s for s, _, _ in obs})
        nonvid = [o for o in obs if o[0] != 904]
        print(f"     replies: {len(obs)} packets; sizes={sizes[:6]}{'…' if len(sizes) > 6 else ''}")
        if nonvid:
            print("     🔔 NON-VIDEO reply(ies):")
            for sz, b4, head in nonvid[:6]:
                print(f"        len={sz} b4={b4:#04x} {head.hex(' ')}")
        else:
            print("     (video only, no visible config ack)")

    cam.close()
    print("\n═══ sweep complete ═══")
    print("If nothing replied, try --candidates with a wider grid, or accept the")
    print("camera is silent-by-design and detect the reboot instead.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
