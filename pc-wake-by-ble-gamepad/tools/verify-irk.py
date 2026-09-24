#!/usr/bin/env python3
"""Verify a Bluetooth LE Identity Resolving Key (IRK) against an observed address.

WHY THIS EXISTS
---------------
If a BLE device rotates its address (a Resolvable Private Address, RPA), a fixed-MAC
tracker will not hold and you need the device's IRK. IRKs are easy to extract but
**easy to get wrong**, because byte order varies between tools and platforms.

This tool does not guess. It tests the key in BOTH byte orders against an address
you have actually observed, and tells you which one works. That is the only reliable
answer.

THE MATH (Bluetooth Core Spec Vol 6, Part B, 1.3.2.2)
-----------------------------------------------------
A Resolvable Private Address is:      prand (24 bits) || hash (24 bits)
  * addresses are DISPLAYED most-significant-byte first, so prand is the HIGH
    3 bytes and hash is the LOW 3 bytes
  * the two most significant bits of prand MUST be 0b01 for a valid RPA

The resolving function `ah` is:
    ah(k, r) = AES-128-ECB(key=k, plaintext = 13 zero bytes || r)[0:3]
where `r` is the 3-byte prand. The first 3 bytes of the ciphertext must equal
`hash`.

⚠️ Getting prand and hash the wrong way round makes a perfectly good IRK look
broken. This tool asserts the prand type-bits first and will tell you if the address
you supplied is not an RPA at all -- in which case no IRK can resolve it, and you are
probably looking at a PUBLIC address that merely resembles one.

USAGE
-----
    ./verify-irk.py <IRK-hex> <observed-address> [<more addresses>...]

    ./verify-irk.py 00112233445566778899aabbccddeeff AA:BB:CC:DD:EE:FF

Requires `cryptography` (`pip install cryptography`).
"""

from __future__ import annotations

import sys

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except ImportError:
    sys.exit("missing dependency: pip install cryptography")


def aes_ecb_encrypt_block(key: bytes, block: bytes) -> bytes:
    enc = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return enc.update(block) + enc.finalize()


def resolves(irk: bytes, rpa: str) -> bool | None:
    """True/False if resolvable, or None if the input is not a valid RPA."""
    raw = bytes.fromhex(rpa.replace(":", "").replace("-", ""))
    if len(raw) != 6:
        return None

    prand = raw[0:3]          # HIGH 3 bytes = random part
    expected_hash = raw[3:6]  # LOW  3 bytes = AES output

    # A valid RPA's prand has its top two bits set to 0b01.
    if (prand[0] >> 6) != 0b01:
        return None

    plaintext = b"\x00" * 13 + prand  # 13-byte padding, per the spec
    return aes_ecb_encrypt_block(irk, plaintext)[0:3] == expected_hash


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        return

    irk_hex = sys.argv[1].replace(":", "").replace(" ", "").lower()
    addresses = sys.argv[2:]

    try:
        raw = bytes.fromhex(irk_hex)
    except ValueError:
        sys.exit("IRK is not valid hex")
    if len(raw) != 16:
        sys.exit(f"IRK must be 16 bytes (32 hex chars); got {len(raw)}")

    candidates = {
        "as-supplied": raw,
        "byte-reversed": raw[::-1],
    }

    print(f"IRK       : {irk_hex}")
    print(f"addresses : {', '.join(addresses)}\n")

    hit = False
    invalid = []
    for label, key in candidates.items():
        matches = []
        for a in addresses:
            result = resolves(key, a)
            if result is True:
                matches.append(a)
            elif result is None:
                invalid.append(a)
        if matches:
            hit = True
        print(f"  {label:16} {key.hex()}")
        print(f"      -> {'RESOLVES ' + ', '.join(matches) if matches else 'no match'}")

    print()
    if invalid:
        print(f"  WARNING: not structurally valid RPAs (prand bits != 0b01): "
              f"{', '.join(sorted(set(invalid)))}")
        print("           No IRK can resolve these -- the address is not an RPA.")
        print()

    if hit:
        print("VERDICT: IRK confirmed -- it produced at least one observed address.")
    else:
        print("VERDICT: neither byte order resolves these addresses.")
        print("         Either the addresses came from a different device, or this key")
        print("         is not the one that generated them.")


if __name__ == "__main__":
    main()
