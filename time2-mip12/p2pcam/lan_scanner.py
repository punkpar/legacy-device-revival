import random
import select
import socket
import struct
import time

from .lan_device import LanDevice

SOURCE_PORT = 2726
BROADCAST_PORT = 2627
LISTEN_PORT = 5000
COMMAND_LAN_REFRESH = 0x0B
DISCOVERY_HEADER_SIZE = 13
DISCOVERY_MIN_PACKET_LEN = 12
MIN_DISCOVERY_PACKET_SIZE = 9
ACK_PACKET_SIZE = 13
IP_OCTET_COUNT = 4


class LanScanner:
    """
    Scan the local network for compatible P2P camera devices.

    This class broadcasts discovery packets on the local network and listens
    for device responses. It decodes responses into LanDevice instances.
    """

    def __init__(
        self,
        listen_port: int = LISTEN_PORT,
        source_port: int = SOURCE_PORT,
        broadcast_port: int = BROADCAST_PORT,
        encoding: str = "utf-8",
    ) -> None:
        """Initialize scanner networking ports and payload encoding."""
        self.listen_port = listen_port
        self.source_port = source_port
        self.broadcast_port = broadcast_port
        self.encoding = encoding
        self.mac_ip = self._make_mac_ip()

    def refresh(self, timeout: float = 3.0) -> list[LanDevice]:
        """Broadcast a LAN refresh packet and collect device responses."""
        devices: dict[str, LanDevice] = {}
        source_sock = self._open_socket(self.source_port)
        listen_sock = None
        if self.listen_port != self.source_port:
            listen_sock = self._open_socket(self.listen_port)
        sockets = [source_sock] + ([listen_sock] if listen_sock is not None else [])
        try:
            packet = self._build_refresh_packet()
            source_sock.sendto(packet, ("255.255.255.255", self.broadcast_port))
            for broadcast in self._interface_broadcasts():
                source_sock.sendto(packet, (broadcast, self.broadcast_port))

            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                readable, _, _ = select.select(sockets, [], [], remaining)
                if not readable:
                    break
                data, (host, _port) = readable[0].recvfrom(65535)

                ack = self._decode_ack(data)
                if ack is not None:
                    devices.setdefault(
                        f"{host}:0:0",
                        LanDevice(
                            device_id=host,
                            device_type="",
                            hkid=0,
                            channel_count=0,
                            status=ack,
                            audio_type="",
                            ip=host,
                        ),
                    )

                for fields in self._extract_dicts(data):
                    if fields.get("MacIP") == self.mac_ip:
                        continue
                    fields.setdefault("Ip", host)
                    device = self._device_from_fields(fields)
                    if device is not None:
                        devices[
                            f"{device.device_id}:{device.hkid}:{device.channel_count}"
                        ] = device
        finally:
            for sock in sockets:
                sock.close()

        return sorted(devices.values(), key=lambda item: (item.device_id, item.hkid))

    def _open_socket(self, port: int) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.bind(("", port))
        except OSError:
            sock.bind(("", 0))
            if port == self.source_port:
                self.source_port = sock.getsockname()[1]
        return sock

    def _build_refresh_packet(self) -> bytes:
        end_time = int(time.time()) + 3600
        body = self._encode_old_dict(
            {
                "TIME": "3600",
                "endTime": str(end_time),
                "MainCmd": "LocalData",
                "userType": "hkclient",
                "status": "1",
                "Prot": str(self.listen_port),
                "MacIP": self.mac_ip,
            }
        )
        inner = self._build_inner_packet(COMMAND_LAN_REFRESH, body)
        total_len = len(inner) + 4
        return b"\x00\x00" + struct.pack("<H", total_len << 4) + inner

    @staticmethod
    def _build_inner_packet(command: int, body: bytes) -> bytes:
        inner_len = len(body) + 9
        header = bytearray(9)
        header[0] = (command << 4) | 0x02
        header[1] = 0x0C
        header[2] = 0x1D
        header[3] = inner_len & 0xFF
        header[4] = (inner_len >> 8) & 0xFF
        return bytes(header) + body

    @staticmethod
    def _build_ack_packet(
        command: int = 0x08, flag: int = 0x0B, pipe: int = 0x07D1
    ) -> bytes:
        return (
            b"\x00\x00\xd0\x00"
            + bytes([(command << 4) | 0x02, flag, 0x20, 0x09, 0x00])
            + struct.pack("<H", pipe)
            + b"\x00\x00"
        )

    @staticmethod
    def _encode_old_dict(fields: dict[str, str]) -> bytes:
        return "".join(f"{key}={value};" for key, value in fields.items()).encode(
            "ascii"
        )

    def _extract_dicts(self, data: bytes) -> list[dict[str, str]]:
        candidates = []
        if len(data) >= DISCOVERY_HEADER_SIZE and data[0:2] == b"\x00\x00":
            packet_len = struct.unpack_from("<H", data, 2)[0] >> 4
            if DISCOVERY_MIN_PACKET_LEN < packet_len <= len(data):
                candidates.append(data[DISCOVERY_HEADER_SIZE:packet_len])
        if len(data) >= MIN_DISCOVERY_PACKET_SIZE:
            command = data[0] >> 4
            if command == COMMAND_LAN_REFRESH:
                candidates.append(data[9:])
        candidates.append(data)

        decoded = []
        seen = set()
        for candidate in candidates:
            fields = self._decode_old_dict(candidate)
            marker = tuple(sorted(fields.items()))
            if fields and marker not in seen:
                decoded.append(fields)
                seen.add(marker)
        return decoded

    def _decode_ack(self, data: bytes) -> int | None:
        if len(data) != ACK_PACKET_SIZE or data[:4] != b"\x00\x00\xd0\x00":
            return None
        if data[4] >> 4 in {0x08, 0x09, 0x0A} and data[7:9] == b"\x09\x00":
            return 1
        return None

    def _decode_old_dict(self, data: bytes) -> dict[str, str]:
        text = data.split(b"\x00", 1)[0].decode(self.encoding, errors="replace")
        fields: dict[str, str] = {}
        for part in text.split(";"):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip()
            if key:
                fields[key] = self._unescape_old_value(value.strip())
        return fields

    @staticmethod
    def _unescape_old_value(value: str) -> str:
        return (
            value.replace("^equal", "=").replace("^scolon", ";").replace("^vivi", "^")
        )

    @staticmethod
    def _make_mac_ip() -> str:
        return f"0x0x{random.getrandbits(32):08x}:{random.randint(0, 0x7FFFFFFF)}"

    def _device_from_fields(self, fields: dict[str, str]) -> LanDevice | None:
        hkid = self._int_field(fields, "HKID", "hkid", "DevID", "DSTHKID")
        port = self._int_field(fields, "Prot", "UDPPort", "Port", "port")
        status = self._int_field(fields, "status", "Status", default=1)
        device_id = self._first_field(fields, "devid", "DevID", "HKID", "id", "Ip")
        if not device_id and hkid:
            device_id = str(hkid)
        if not device_id and not hkid:
            return None

        return LanDevice(
            device_id=device_id or "unknown",
            device_type=self._first_field(
                fields, "DevFlag", "devtype", "type", "Protocol"
            ),
            hkid=hkid or port,
            channel_count=self._int_field(fields, "Count", "count", default=0),
            status=status,
            audio_type=self._first_field(fields, "audio", "audiotype", "AudioType"),
            ip=fields.get("Ip", ""),
        )

    @staticmethod
    def _first_field(fields: dict[str, str], *names: str) -> str:
        for name in names:
            value = fields.get(name)
            if value:
                return value
        return ""

    @classmethod
    def _int_field(cls, fields: dict[str, str], *names: str, default: int = 0) -> int:
        value = cls._first_field(fields, *names)
        try:
            return int(value, 0)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _interface_broadcasts() -> list[str]:
        broadcasts = set()
        hostname = socket.gethostname()
        try:
            for item in socket.getaddrinfo(hostname, None, socket.AF_INET):
                ip = item[4][0]
                parts = ip.split(".")
                if len(parts) == IP_OCTET_COUNT and not ip.startswith("127."):
                    broadcasts.add(".".join([*parts[:3], "255"]))
        except OSError:
            pass
        return sorted(broadcasts)
