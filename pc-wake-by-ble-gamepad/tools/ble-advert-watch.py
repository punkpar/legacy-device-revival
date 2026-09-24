#!/usr/bin/env python3
"""Watch Home Assistant's live Bluetooth advertisement stream.

WHY THIS EXISTS
---------------
Home Assistant's *device registry* only lists devices an **integration has
claimed**. A raw BLE advertiser never appears there, so "it's not in the registry"
proves nothing about whether HA can actually *see* it. This tool reads the real
advertisement stream instead.

It subscribes to the websocket command `bluetooth/subscribe_advertisements` and
reports every advertisement whose address or manufacturer ID matches a filter.

⚠️ THE PAYLOAD SHAPE: the single most common source of confusion:
    {"type": "event", "event": {"add": [ {address, rssi, source, ...} ]}}
The adverts are in an **`add` LIST**, not a flat object. And:
  * `source` is the SCANNER/PROXY MAC, not the device's address.
  * `manufacturer_data` keys are DECIMAL company IDs ("6" == 0x0006 == Microsoft).

USAGE
-----
    export HA_URL=http://homeassistant.local:8123
    export HA_TOKEN=<long-lived access token>

    # by address fragment (case-insensitive)
    ./ble-advert-watch.py --address aa:bb:cc --seconds 60

    # by manufacturer ID (decimal) -- finds a device even if its address rotates
    ./ble-advert-watch.py --manufacturer 6 --seconds 120

    # see everything the proxies are relaying
    ./ble-advert-watch.py --seconds 30

Requires `websockets` (`pip install websockets`). No other dependencies.

Nothing is transmitted to the device; this is a passive listener on your own HA.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

try:
    import websockets
except ImportError:
    sys.exit("missing dependency: pip install websockets")


def build_ws_url(base: str) -> str:
    """Turn an http(s) base URL into the HA websocket endpoint."""
    base = base.rstrip("/")
    if base.startswith("https://"):
        return base.replace("https://", "wss://", 1) + "/api/websocket"
    if base.startswith("http://"):
        return base.replace("http://", "ws://", 1) + "/api/websocket"
    return base + "/api/websocket"


async def watch(url: str, token: str, address: str, manufacturer: str, seconds: int) -> None:
    async with websockets.connect(url, max_size=None) as ws:
        # HA requires a two-step handshake: hello -> auth -> auth_ok.
        hello = json.loads(await ws.recv())
        if hello.get("type") != "auth_required":
            sys.exit(f"unexpected first message: {hello}")
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            sys.exit(f"auth failed: {auth}")

        await ws.send(json.dumps({"id": 1, "type": "bluetooth/subscribe_advertisements"}))
        print(f"listening for {seconds}s…\n")

        seen: dict[str, int] = {}
        hits: list[dict] = []
        deadline = time.time() + seconds

        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=seconds)
            except asyncio.TimeoutError:
                break
            msg = json.loads(raw)
            if msg.get("type") != "event":
                continue

            # NOTE: adverts arrive in a LIST under "add".
            for adv in msg.get("event", {}).get("add") or []:
                addr = (adv.get("address") or "").upper()
                if not addr:
                    continue
                seen[addr] = seen.get(addr, 0) + 1

                mfr = adv.get("manufacturer_data") or {}
                match_addr = address and address.upper() in addr
                match_mfr = manufacturer and manufacturer in mfr
                if match_addr or match_mfr:
                    hits.append(adv)
                    stamp = time.strftime("%H:%M:%S")
                    print(
                        f"  [{stamp}] {addr}  rssi={adv.get('rssi')}  "
                        f"src={adv.get('source')}  mfr={sorted(mfr)}  "
                        f"name={adv.get('name') or '-'}"
                    )

        print(f"\n--- summary: {len(seen)} distinct address(es) in {seconds}s ---")
        for addr, n in sorted(seen.items(), key=lambda kv: -kv[1]):
            print(f"    {addr}  x{n}")
        print(f"\nmatches: {len(hits)}")

        if manufacturer:
            matched = {h["address"] for h in hits}
            if len(matched) > 1:
                print(
                    "\n  NOTE: multiple addresses carried that manufacturer ID. That is"
                    "\n  expected when several devices share a vendor -- but if ONE device"
                    "\n  shows up under changing addresses, it is rotating and you need its"
                    "\n  IRK (see docs: 'Rotating addresses')."
                )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=os.environ.get("HA_URL"), help="HA base URL (or $HA_URL)")
    p.add_argument("--token", default=os.environ.get("HA_TOKEN"), help="HA token (or $HA_TOKEN)")
    p.add_argument("--address", default="", help="address fragment to match (case-insensitive)")
    p.add_argument("--manufacturer", default="", help="manufacturer/company ID to match (DECIMAL, e.g. 6)")
    p.add_argument("--seconds", type=int, default=60, help="how long to listen (default 60)")
    args = p.parse_args()

    if not args.url or not args.token:
        sys.exit("set --url/--token or $HA_URL/$HA_TOKEN")

    asyncio.run(watch(build_ws_url(args.url), args.token, args.address, args.manufacturer, args.seconds))


if __name__ == "__main__":
    main()
