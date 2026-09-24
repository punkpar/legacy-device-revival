#!/usr/bin/env python3
"""Probe the HeKai config channel on a live camera (READ-ONLY experiments).

Goal: find the envelope that carries a *config* command (specifically the WiFi
read, `GetLanSysDevInfo(ihkid, devid, 204)` → `open=..;mac=..;sid=..;satype=..;`).

Everything here is a query. Nothing writes configuration, nothing reboots.

Run with a capture alongside:
    sudo tcpdump -i eth0 -n udp port 5000 -w /tmp/hk.pcap
"""
from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from p2pcam.lan_video import (  # noqa: E402
    _build_hk_res_req,
    _build_icmd1_ack,
    _build_icmd2_poll,
    _build_packet,
    _build_ping1,
    _build_ping2,
    _build_session_start,
    _is_icmd1_poll,
    _is_session_create,
    _xor_encode,
    _xor_encode_all,
    _PING_ACK_BYTE,
)

CAM = "<CAMERA-IP>"
HKID = 5000


def decode_body(data: bytes) -> str:
    """Show a reply body both raw and XOR-0xe9-decoded (dict-style: skip 2 bytes)."""
    out = []
    for label, blob in (
        ("raw", data),
        ("xor-from0", bytes(b ^ 0xE9 for b in data)),
        ("xor-from2", data[:2] + bytes(b ^ 0xE9 for b in data[2:])),
    ):
        txt = "".join(chr(c) for c in blob if 32 <= c < 127)
        if txt:
            out.append(f"      {label:9} {txt[:160]}")
    return "\n".join(out)


class Probe:
    def __init__(self, ip=CAM, hkid=HKID):
        self.ip, self.hkid = ip, hkid
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # 🔴 local_port=0: avoids the :5000 collision documented in the runbook.
        self.sock.bind(("", 0))
        self.seq = 0
        print(f"local port: {self.sock.getsockname()[1]}")

    def send(self, d):
        self.sock.sendto(d, (self.ip, 5000))

    def pump(self, seconds, label):
        """Receive everything for `seconds`, printing anything interesting."""
        print(f"   ── listening {seconds}s [{label}]")
        deadline = time.monotonic() + seconds
        self.sock.settimeout(0.4)
        seen = 0
        while time.monotonic() < deadline:
            try:
                data, addr = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            if addr[0] != self.ip:
                continue
            seen += 1
            kind = "?"
            if _is_session_create(data):
                kind = "SessionCreate"
            elif _is_icmd1_poll(data):
                kind = "ICMD1-poll"
            elif len(data) == 13:
                kind = f"13B(byte4={data[4]:#04x})"
            print(f"   ← {len(data):5}B {kind}")
            if len(data) > 30:  # likely a config reply, not a keepalive
                print(decode_body(data))
                return True, data
        return (seen > 0), None

    def handshake(self):
        print("── handshake")
        for _ in range(3):
            self.send(_build_ping1()); time.sleep(0.002)
        self.pump(2.0, "ping-ack")
        for _ in range(9):
            self.send(_build_ping2()); time.sleep(0.001)
        self.send(_build_hk_res_req(hkid=self.hkid))
        for _ in range(3):
            self.seq += 1
            self.send(_build_icmd2_poll(self.hkid, self.seq)); time.sleep(0.001)
        ok, _ = self.pump(8.0, "SessionCreate")
        return ok


def try_get(p: Probe, label: str, body: str, *, icmd: int = 0x32,
            f1: int = 0x51, f2: int = 0xC4, extra: bytes = bytes([0x64, 0, 0, 0]),
            counter: int = 3, encode="dict"):
    print(f"\n── [{label}] inner_cmd={icmd:#04x} body={body!r}")
    enc = _xor_encode(body) if encode == "dict" else _xor_encode_all(body)
    pkt = _build_packet(counter=counter, inner_cmd=icmd, inner_flag1=f1,
                        inner_flag2=f2, inner_extra=extra, body=enc)
    p.send(pkt)
    got, data = p.pump(4.0, label)
    return got, data


def main():
    p = Probe()
    if not p.handshake():
        print("\n❌ no session: camera not cooperating")
        return 1
    p.send(_build_session_start())

    # Candidate read-only probes for the WiFi/config query.
    candidates = [
        ("A: GetLanSysDevInfo", "MainCmd=GetLanSysDevInfo;nType=204;devid=<DEVICE-ID>;", {}),
        ("B: GetLanInfo 204", "MainCmd=GetLanInfo;nType=204;hkid=5000;", {}),
        ("C: MainCmd=204", "MainCmd=204;hkid=5000;", {}),
        ("D: MainCmd=GetWifi", "MainCmd=GetWifi;hkid=5000;", {}),
        ("E: ICMD2-style", "d4:ICMD2:293:SEQ1:5000:GUARDSEQ1:01", {"encode": "icmd", "icmd": 0x10, "f1": 0x03, "f2": 0x00, "extra": bytes([0xD1, 7, 0, 0])}),
        ("F: MainCmd=700 read", "MainCmd=700;isopen=1;", {}),
    ]
    results = []
    for label, body, kw in candidates:
        try:
            got, data = try_get(p, label, body, **kw)
            results.append((label, got, len(data) if data else 0))
        except Exception as e:  # noqa: BLE001
            results.append((label, f"ERR {e}", 0))

    print("\n═══ results ═══")
    for label, got, n in results:
        print(f"  {label:24} reply={got}  bytes={n}")
    p.sock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
