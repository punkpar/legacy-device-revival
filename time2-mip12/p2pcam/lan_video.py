import contextlib
import select
import socket
import struct
import threading
import time
from collections.abc import Iterator
from typing import Self

# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------

BROADCAST_PORT = 2627  # LocalData broadcast port (LAN discovery)
VIDEO_PORT = 5000  # UDP port for video exchange

# XOR obfuscation key for dict body (bytes 2+ are XOR'd with this value)
_BODY_XOR_KEY = 0xE9

# Session ID and call ID used in the video handshake.
# These can remain fixed strings since we observed them hard-coded in the SDK.
_DEFAULT_SID = "j882Tm1a108000"
_DEFAULT_CALLID = "I0.JvIZbLTnL7MpGdBuLRVmA1a100ff1"

# Polling intervals
_POLL_INTERVAL = 0.17  # seconds between ICMD2 polls before stream
_ACK_INTERVAL = 0.17  # seconds between ICMD1 acks during stream

# MJPEG reassembly
_MAX_UDP_PAYLOAD = 65535
_MJPEG_HDR_OFFSET = 4  # JPEG SOI is at offset 4 within video UDP payload
_JPEG_SOI = b"\xff\xd8"
_JPEG_EOI = b"\xff\xd9"
_XOR_PREFIX_LEN = 2
_CONTINUE_LIST_STEP = 2
_CONTINUE_DIGITS_3 = 3
_CONTINUE_DIGITS_4 = 4
_MAX_CONTINUE_DIGITS = 5
_MIN_SESSION_CREATE_LEN = 14
_ICMD1_POLL_LEN = 51
_MJPEG_MIN_LEN = 60
_PING_ACK_LEN = 13
_PING_ACK_BYTE = 0x92


# ---------------------------------------------------------------------------
# Low-level packet builders
# ---------------------------------------------------------------------------


def _xor_encode(s: str) -> bytes:
    """Encode a dict-style string: first 2 bytes plain, rest XOR 0xe9."""
    raw = s.encode("ascii")
    if len(raw) <= _XOR_PREFIX_LEN:
        return raw
    return raw[:_XOR_PREFIX_LEN] + bytes(
        b ^ _BODY_XOR_KEY for b in raw[_XOR_PREFIX_LEN:]
    )


def _xor_encode_all(s: str) -> bytes:
    """Encode an ICMD-style string: ALL bytes XOR 0xe9."""
    return bytes(b ^ _BODY_XOR_KEY for b in s.encode("ascii"))


def _build_packet(  # noqa: PLR0917
    counter: int,
    inner_cmd: int,
    inner_flag1: int,
    inner_flag2: int,
    inner_extra: bytes,
    body: bytes,
) -> bytes:
    """
    Build a complete packet with the 2-byte counter prefix.

    Layout (verified byte-by-byte against the Android app dumps):
      [0-1]   packet counter (uint16 LE)
      [2-3]   outer len field: (total_packet_len << 4) as uint16 LE
      [4]     inner_cmd
      [5]     inner_flag1
      [6]     inner_flag2
      [7-8]   inner payload length (9-byte inner header + body) as uint16 LE
      [9-12]  inner_extra (4 bytes)
      [13+]   body
    """
    inner_len = 9 + len(body)  # 9-byte inner header + body
    outer_total = 4 + inner_len  # 4-byte outer header + inner
    outer_len_field = outer_total << 4

    pkt = bytearray()
    pkt += struct.pack("<H", counter)  # [0-1] counter
    pkt += struct.pack("<H", outer_len_field)  # [2-3] outer len
    pkt.append(inner_cmd)  # [4]
    pkt.append(inner_flag1)  # [5]
    pkt.append(inner_flag2)  # [6]
    pkt += struct.pack("<H", inner_len)  # [7-8]
    pkt += inner_extra  # [9-12]
    pkt += body  # [13+]
    return bytes(pkt)


def _build_ping1() -> bytes:
    """Build the first connection ping (``82 0c 00 09 00 d1 07 00 00``)."""
    # Exactly as seen in frames 2-4 of the dump, with counter=0x0000
    return bytes.fromhex("0000d000820c000900d1070000")


def _build_ping2() -> bytes:
    """Build the second connection ping (``a2 0c 40 09 00 d1 07 00 00``)."""
    # Exactly as seen in frames 8-16 of the dump, with counter=0x0000
    return bytes.fromhex("0000d000a20c400900d1070000")


def _build_hk_res_req(
    hkid: int, sid: str = _DEFAULT_SID, callid: str = _DEFAULT_CALLID
) -> bytes:
    """
    Build the HK_RES_REQ video-init packet (counter=0x0001).

    Exact layout from frame 17 of the dump:
      counter    = 0x0001
      inner_cmd  = 0x32
      inner_flag1= 0x8B
      inner_flag2= 0xC5
      inner_extra= 51 01 00 00
    """
    body_str = (
        f"id={hkid};ftN0=video.vbVideo.MPEG4;ftN1=net.0;"
        f"ftN2=HKPCPresent.HKPCPresent;opN2={sid};"
        f"Callid={callid};sidN={sid};"
        "AsCode=337;MainCmd=HK_RES_REQ;user=Lan user;"
    )
    body = _xor_encode(body_str)
    return _build_packet(
        counter=0x0001,
        inner_cmd=0x32,
        inner_flag1=0x8B,
        inner_flag2=0xC5,
        inner_extra=bytes([0x51, 0x01, 0x00, 0x00]),
        body=body,
    )


def _build_icmd2_poll(hkid: int, seq: int, session_id: int = 293) -> bytes:
    """
    Build the 47-byte ICMD2 poll packet sent while waiting for SessionCreate.

    Frame 18 layout:
      counter    = 0x0000
      inner_cmd  = 0x10
      inner_flag1= 0x03
      inner_flag2= 0x00
      inner_extra= 00 d1 07 00
    Body (XOR 0xe9 from byte 2): ``d4:ICMD2:293:SEQ1:<hkid>:GUARDSEQ1:<seq>``
    """
    body_str = f"d4:ICMD2:{session_id}:SEQ1:{hkid}:GUARDSEQ1:{seq:02x}"
    body = _xor_encode_all(body_str) + bytes([0xE9 ^ 0x00])  # trailing null, XOR'd
    return _build_packet(
        counter=0x0000,
        inner_cmd=0x10,
        inner_flag1=0x03,
        inner_flag2=0x00,
        inner_extra=bytes([0xD1, 0x07, 0x00, 0x00]),
        body=body,
    )


def _build_session_start(sid: str = _DEFAULT_SID) -> bytes:
    """
    Build the SessionStart packet (counter=0x0002).

    Frame 25 layout:
      counter    = 0x0002
      inner_cmd  = 0x32
      inner_flag1= 0x51
      inner_flag2= 0xC4
      inner_extra= 64 00 00 00
    """
    body_str = (
        f"MainCmd=SessionStart;sidN={sid};"
        "ftN0=HKPCPresent.HKPCPresent;FD0=4;ftN1=net.1024;FD1=1024;"
    )
    body = _xor_encode(body_str)
    return _build_packet(
        counter=0x0002,
        inner_cmd=0x32,
        inner_flag1=0x51,
        inner_flag2=0xC4,
        inner_extra=bytes([0x64, 0x00, 0x00, 0x00]),
        body=body,
    )


def _build_icmd1_ack(hkid: int, seq: int, session_id: int = 293) -> bytes:
    """
    Build the 47-byte ICMD1 ACK sent during streaming.

    counter = 0x0000, inner_cmd = 0x10, inner_flag1 = 0x00, inner_flag2 = 0x00
    Body (XOR 0xe9): ``d4:ICMD1:<session_id>:lastreq1:<hkid>:SEQ3:<seq>e``
    """
    body_str = f"d4:ICMD1:{session_id}:lastreq1:{hkid}:SEQ3:{seq:x}e"
    body = _xor_encode_all(body_str) + bytes([0xE9 ^ 0x00])  # trailing null, XOR'd
    return _build_packet(
        counter=0x0000,
        inner_cmd=0x10,
        inner_flag1=0x00,
        inner_flag2=0x00,
        inner_extra=bytes([0xD1, 0x07, 0x00, 0x00]),
        body=body,
    )


# ---------------------------------------------------------------------------
# Continue-packet state machine.
# ---------------------------------------------------------------------------

_CONTINUE_LIST_1 = bytes(
    [
        0xD8,
        0xDF,  # index 0,1
        0xDB,
        0xDE,  # index 2,3
        0xDA,
        0xD1,  # index 4,5
        0xDD,
        0xD0,  # index 6,7
        0xDC,
        0xD9,  # index 8,9
        0xDF,
        0xD8,  # index 10,11
        0xDE,
        0xDB,  # index 12,13
        0xD1,
        0xDA,  # index 14,15
        0xD0,
        0xDD,  # index 16,17
        0xD9,
        0xDC,  # index 18,19
    ]
)
_CONTINUE_LIST_2 = bytes([0xD9, 0xD8, 0xDB, 0xDA, 0xDD, 0xDC, 0xDF, 0xDE, 0xD1, 0xD0])

# Fixed prefix (bytes 0-23) and suffix (bytes 25+) of every continue packet.
# Bytes [2] and [7] are overwritten by _ContinueState.next_packet() to signal
# the digit count to the camera.
_CONT_BEGIN = bytearray(
    [
        0x00,
        0x00,
        0xFF,  # [2]  overwritten: 0x20/0x30/0x40/0x50/0x60 for nbDigits 1..5
        0x02,
        0x12,
        0x00,
        0x00,
        0xFF,  # [7]  overwritten: 0x1e/0x1f/0x20/0x21/0x22 for nbDigits 1..5
        0x00,
        0x01,
        0x00,
        0x00,
        0x00,
        0xA0,
        0xAA,
        0xA4,
        0xAD,
        0xD4,
        0xD8,
        0xD2,
        0xBA,
        0xAC,
        0xB8,
        0xD4,
    ]
)
_CONT_END = bytes([0xD2, 0xBD, 0xA0, 0xA4, 0xAC, 0xD4, 0xD9, 0xD2, 0xE9])


class _ContinueState:
    """
    Stateful generator for the continue-packet payload sequence.

    Mirrors the MANAGE "CONTINUE" PACKETS SEQUENCE block from jheyman.
    Call next_packet() to obtain the next raw UDP bytes to send.
    """

    def __init__(self) -> None:
        self.nb_digits: int = 1
        self.idx: list[int] = [0, 0, 0, 0, 0]  # continue_index
        self.base_index: int = 0
        self._fragment_index: int = 0  # total calls to next_packet()

    def next_packet(self) -> bytes:  # noqa: PLR0912, PLR0915
        """Advance the state and return the complete continue packet bytes."""
        self._fragment_index += 1

        # Rotate base_index every 100 calls (experimentally determined)
        if self._fragment_index % 100 == 0:
            self.base_index = (self.base_index + 2) % 20

        hdr = bytearray(_CONT_BEGIN)  # mutable copy
        tmp = bytearray()

        nd = self.nb_digits
        list_len_2 = len(_CONTINUE_LIST_2)

        if nd == 1:
            hdr[2] = 0x20
            hdr[7] = 0x1E
            tmp.append(_CONTINUE_LIST_1[self.base_index + self.idx[0]])
            self.idx[0] += 1
            if self.idx[0] == _CONTINUE_LIST_STEP:
                self.nb_digits += 1
                self.idx[1] = 1  # start at d8
                self.idx[0] = 0

        elif nd == _CONTINUE_LIST_STEP:
            hdr[2] = 0x30
            hdr[7] = 0x1F
            tmp.append(_CONTINUE_LIST_2[self.idx[1]])
            tmp.append(_CONTINUE_LIST_1[self.base_index + self.idx[0]])
            self.idx[0] += 1
            if self.idx[0] == _CONTINUE_LIST_STEP:
                self.idx[1] += 1
                self.idx[0] = 0
            if self.idx[1] == list_len_2:
                self.nb_digits += 1
                self.idx[2] = 1
                self.idx[1] = 0
                self.idx[0] = 0

        elif nd == _CONTINUE_DIGITS_3:
            hdr[2] = 0x40
            hdr[7] = 0x20
            tmp.append(_CONTINUE_LIST_2[self.idx[2]])
            tmp.append(_CONTINUE_LIST_2[self.idx[1]])
            tmp.append(_CONTINUE_LIST_1[self.base_index + self.idx[0]])
            self.idx[0] += 1
            if self.idx[0] == _CONTINUE_LIST_STEP:
                self.idx[1] += 1
                self.idx[0] = 0
            if self.idx[1] == list_len_2:
                self.idx[2] += 1
                self.idx[1] = 0
                self.idx[0] = 0
            if self.idx[2] == list_len_2:
                self.nb_digits += 1
                self.idx[3] = 1
                self.idx[2] = 0
                self.idx[1] = 0
                self.idx[0] = 0

        elif nd == _CONTINUE_DIGITS_4:
            hdr[2] = 0x50
            hdr[7] = 0x21
            tmp.append(_CONTINUE_LIST_2[self.idx[3]])
            tmp.append(_CONTINUE_LIST_2[self.idx[2]])
            tmp.append(_CONTINUE_LIST_2[self.idx[1]])
            tmp.append(_CONTINUE_LIST_1[self.base_index + self.idx[0]])
            self.idx[0] += 1
            if self.idx[0] == _CONTINUE_LIST_STEP:
                self.idx[1] += 1
                self.idx[0] = 0
            if self.idx[1] == list_len_2:
                self.idx[2] += 1
                self.idx[1] = 0
                self.idx[0] = 0
            if self.idx[2] == list_len_2:
                self.idx[3] += 1
                self.idx[2] = 0
                self.idx[1] = 0
                self.idx[0] = 0
            if self.idx[3] == list_len_2:
                self.nb_digits += 1
                self.idx[4] = 1
                self.idx[3] = 0
                self.idx[2] = 0
                self.idx[1] = 0

        elif nd == _MAX_CONTINUE_DIGITS:
            hdr[2] = 0x60
            hdr[7] = 0x22
            tmp.append(_CONTINUE_LIST_2[self.idx[4]])
            tmp.append(_CONTINUE_LIST_2[self.idx[3]])
            tmp.append(_CONTINUE_LIST_2[self.idx[2]])
            tmp.append(_CONTINUE_LIST_2[self.idx[1]])
            tmp.append(_CONTINUE_LIST_1[self.base_index + self.idx[0]])
            self.idx[0] += 1
            if self.idx[0] == _CONTINUE_LIST_STEP:
                self.idx[1] += 1
                self.idx[0] = 0
            if self.idx[1] == list_len_2:
                self.idx[2] += 1
                self.idx[1] = 0
                self.idx[0] = 0
            if self.idx[2] == list_len_2:
                self.idx[3] += 1
                self.idx[2] = 0
                self.idx[1] = 0
                self.idx[0] = 0
            if self.idx[3] == list_len_2:
                self.idx[4] += 1
                self.idx[3] = 0
                self.idx[2] = 0
                self.idx[1] = 0
                self.idx[0] = 0
            if self.idx[4] == list_len_2:
                self.nb_digits = 1  # restart
                self.idx = [0, 0, 0, 0, 0]

        # Horrible reverse-engineered condition: restart at 1 digit
        if len(tmp) == _MAX_CONTINUE_DIGITS and tmp[:4] == bytes(
            [0xDF, 0xDC, 0xDD, 0xD0]
        ):
            self.nb_digits = 1

        return bytes(hdr) + bytes(tmp) + _CONT_END


def _build_session_delete(sid: str = _DEFAULT_SID) -> bytes:
    """
    Build the SessionDelete packet to cleanly stop the stream.

    Frame 558 layout (client->camera, len=60):
      counter    = 0x0003
      inner_cmd  = 0xC0
      inner_flag1= 0x03
      inner_flag2= 0x32
      inner_extra= 1c c7 38 00
    """
    body_str = f"sidN={sid};MainCmd=SessionDelete;coz=;"
    body = _xor_encode(body_str)
    return _build_packet(
        counter=0x0003,
        inner_cmd=0x32,
        inner_flag1=0x1C,
        inner_flag2=0xC7,
        inner_extra=bytes([0x64, 0x00, 0x00, 0x00]),
        body=body,
    )


# ---------------------------------------------------------------------------
# MJPEG frame reassembly
# ---------------------------------------------------------------------------


class _FrameAssembler:
    """
    Reassemble fragmented JPEG frames from camera UDP packets.

    From the dump, each video UDP payload begins with a 4-byte header:
      [0-1]  chunk sequence number (uint16 LE, increases per chunk)
      [2-3]  0x84 0x3d  (magic)
    Then at byte 4 onwards is raw JPEG data.  A new frame starts when
    ``ff d8`` appears at offset 4.  The frame ends when ``ff d9`` is seen.
    """

    def __init__(self) -> None:
        self._buf: bytearray = bytearray()
        self._in_frame: bool = False

    def feed(self, data: bytes) -> bytes | None:
        """Feed one raw UDP payload.  Returns a complete JPEG if assembled."""
        if len(data) < _MJPEG_HDR_OFFSET + 2:
            return None

        payload = data[_MJPEG_HDR_OFFSET:]
        frame = None

        if self._in_frame:
            self._buf.extend(payload)
            # Check if we now have the EOI for the current frame
            eoi_idx = self._buf.find(_JPEG_EOI)
            if eoi_idx != -1:
                frame = bytes(self._buf[: eoi_idx + 2])
                payload = self._buf[eoi_idx + 2 :]
                self._buf = bytearray()
                self._in_frame = False

        # If we are not in a frame, or we just finished one, look for the next SOI
        if not self._in_frame:
            soi_idx = payload.find(_JPEG_SOI)
            if soi_idx != -1:
                self._buf = bytearray(payload[soi_idx:])
                self._in_frame = True

                # Check if this same payload also contains the EOI for the new frame
                eoi_idx2 = self._buf.find(_JPEG_EOI)
                if eoi_idx2 != -1:
                    frame = bytes(self._buf[: eoi_idx2 + 2])
                    self._buf = bytearray()
                    self._in_frame = False

        return frame


# ---------------------------------------------------------------------------
# Session-layer response parser
# ---------------------------------------------------------------------------


def _decode_camera_msg(data: bytes) -> str | None:
    """Try to XOR-decode a camera message body (offset 13, key 0xe9)."""
    if len(data) < _MIN_SESSION_CREATE_LEN:
        return None
    body = data[13:]
    decoded = body[:2] + bytes(b ^ _BODY_XOR_KEY for b in body[2:])
    return decoded.decode("ascii", "ignore")


def _is_session_create(data: bytes) -> bool:
    """Return True if this packet is the camera's ``SessionCreate`` response."""
    msg = _decode_camera_msg(data)
    if msg is None:
        return False
    return "SessionCreate" in msg


def _is_icmd1_poll(data: bytes) -> bool:
    """Return True if this is a camera ICMD1 poll during streaming."""
    # Camera ICMD1 polls are 51 bytes; header starts with 00 00 30 03
    return len(data) == _ICMD1_POLL_LEN and data[2:4] == bytes([0x30, 0x03])


def _is_mjpeg(data: bytes) -> bool:
    """
    Return True if this looks like a video data chunk from the camera.

    We just check the packet size to ignore 51-byte ICMD polls.
    """
    return len(data) > _MJPEG_MIN_LEN


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


class LanVideoClient:
    """
    Connect to a HeKai/HK P2P camera on the LAN and receive MJPEG frames.

    Usage::

        client = LanVideoClient("<CAMERA-IP>", hkid=12)
        for frame_jpeg in client.stream(timeout=15):
            with open("frame.jpg", "wb") as f:
                f.write(frame_jpeg)

    Parameters
    ----------
    camera_ip:
        LAN IP address of the camera (from ``LanScanner``).
    hkid:
        Device HKID from ``LanScanner``.  Sent in handshake packets.
    port:
        UDP port for video exchange (default 5000).
    session_id:
        Arbitrary session identifier (default 293, as observed in dumps).
    local_port:
        Local UDP port to bind.  0 = let the OS choose.
    sid:
        Session string used in protocol messages (default ``j882Tm1a108000``).

    """

    def __init__(  # noqa: PLR0917
        self,
        camera_ip: str,
        hkid: int = 0,
        port: int = VIDEO_PORT,
        session_id: int = 293,
        local_port: int = VIDEO_PORT,
        sid: str = _DEFAULT_SID,
    ) -> None:
        """Initialize the LAN video client with the camera handshake settings."""
        self.camera_ip = camera_ip
        self.camera_port = port
        self.hkid = hkid
        self.session_id = session_id
        self.local_port = local_port
        self.sid = sid

        self._sock: socket.socket | None = None
        self._running = False
        self._lock = threading.Lock()
        self._seq = 0

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> Self:
        """Enter the client context by opening the UDP socket."""
        self._open()
        return self

    def __exit__(self, *_: object) -> None:
        """Exit the context manager and close the client socket."""
        self.close()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def stream(self, timeout: float = 60.0) -> Iterator[bytes]:  # noqa: PLR0912, PLR0915
        """
        Yield complete JPEG frames from the camera.

        Performs the full handshake, waits for ``SessionCreate``, sends
        ``SessionStart``, then enters the receive / ACK loop.

        Parameters
        ----------
        timeout:
            Seconds to wait for a response at each blocking step before
            giving up.

        """
        self._open()
        self._running = True
        assembler = _FrameAssembler()

        try:
            # -------------------------------------------------------
            # Phase 1: Connection pings (mirror frames 2-7 from dump)
            # -------------------------------------------------------
            # Send 3x ping-type-1, wait for camera to respond
            for _ in range(3):
                self._send(_build_ping1())
                time.sleep(0.002)

            self._wait_for_ping_ack(timeout=2.0)

            # Send 9x ping-type-2 (as seen in frames 8-16)
            for _ in range(9):
                self._send(_build_ping2())
                time.sleep(0.001)

            # -------------------------------------------------------
            # Phase 2: Send HK_RES_REQ + ICMD2 polls, wait for SessionCreate
            # -------------------------------------------------------
            self._send(
                _build_hk_res_req(
                    hkid=self.hkid,
                    sid=self.sid,
                )
            )

            # Send a few immediate ICMD2 polls (as seen in frames 18-20)
            for _ in range(3):
                self._seq += 1
                self._send(_build_icmd2_poll(self.hkid, self._seq, self.session_id))
                time.sleep(0.001)

            # Wait for SessionCreate with polling to keep camera happy
            session_created = self._wait_for_session_create(timeout=timeout)
            if not session_created:
                return  # camera never replied

            # -------------------------------------------------------
            # Phase 3: Send SessionStart
            # -------------------------------------------------------
            self._send(_build_session_start(self.sid))

            # -------------------------------------------------------
            # Phase 4: Streaming loop
            # -------------------------------------------------------
            last_poll = time.monotonic()
            deadline = time.monotonic() + timeout
            fragments_received = 0
            cont_state = _ContinueState()

            while self._running:
                now = time.monotonic()
                if now > deadline:
                    break

                # Periodic ICMD1 ACK to keep the session alive
                if now - last_poll >= _ACK_INTERVAL:
                    self._seq += 1
                    self._send(_build_icmd1_ack(self.hkid, self._seq, self.session_id))
                    last_poll = now

                readable, _, _ = select.select(
                    [self._sock], [], [], min(0.05, deadline - now)
                )
                if not readable:
                    continue

                data, (src_ip, _) = self._sock.recvfrom(_MAX_UDP_PAYLOAD)
                if src_ip != self.camera_ip:
                    continue

                # Extend deadline whenever the camera speaks to us
                deadline = time.monotonic() + timeout

                # Camera ICMD1 poll → reply with ICMD1 ACK immediately
                if _is_icmd1_poll(data):
                    self._seq += 1
                    self._send(_build_icmd1_ack(self.hkid, self._seq, self.session_id))
                    last_poll = time.monotonic()
                    continue

                fragments_received += 1
                # Send continue packet every 5 received fragments using the
                # faithful port of the reverse-engineered state machine.
                if fragments_received % 5 == 0:
                    self._send(cont_state.next_packet())

                # Video chunk → try to assemble a full JPEG
                if _is_mjpeg(data):
                    frame = assembler.feed(data)
                    if frame is not None:
                        yield frame

        finally:
            # Cleanly close the session before exiting
            if self._running:
                with contextlib.suppress(Exception):
                    self._send(_build_session_delete(self.sid))
            self._running = False

    def close(self) -> None:
        """Stop the stream and close the UDP socket."""
        self._running = False
        with self._lock:
            if self._sock is not None:
                self._sock.close()
                self._sock = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open(self) -> None:
        with self._lock:
            if self._sock is not None:
                return
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("", self.local_port))
            except OSError:
                sock.bind(("", 0))
            self._sock = sock

    def _send(self, data: bytes) -> None:
        with self._lock:
            if self._sock is not None:
                self._sock.sendto(data, (self.camera_ip, self.camera_port))

    def _wait_for_ping_ack(self, timeout: float = 2.0) -> bool:
        """Wait for camera's ``92 0c`` ping-ack response."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            readable, _, _ = select.select([self._sock], [], [], min(0.1, remaining))
            if not readable:
                continue
            data, (src_ip, _) = self._sock.recvfrom(_MAX_UDP_PAYLOAD)
            if src_ip != self.camera_ip:
                continue
            # Camera ping-ack: 13 bytes starting with 00 00 d0 00 92
            if len(data) == _PING_ACK_LEN and data[4] == _PING_ACK_BYTE:
                return True
        return False

    def _wait_for_session_create(self, timeout: float = 10.0) -> bool:
        """Poll the camera with ICMD2 while waiting for ``SessionCreate``."""
        deadline = time.monotonic() + timeout
        last_poll = 0.0

        while time.monotonic() < deadline:
            now = time.monotonic()
            remaining = deadline - now

            # Keep sending ICMD2 polls
            if now - last_poll >= _POLL_INTERVAL:
                self._seq += 1
                self._send(_build_icmd2_poll(self.hkid, self._seq, self.session_id))
                last_poll = now

            readable, _, _ = select.select([self._sock], [], [], min(0.05, remaining))
            if not readable:
                continue

            data, (src_ip, _) = self._sock.recvfrom(_MAX_UDP_PAYLOAD)
            if src_ip != self.camera_ip:
                continue

            if _is_session_create(data):
                return True

            # If we get an ICMD1 poll, reply to keep camera happy
            if _is_icmd1_poll(data):
                self._seq += 1
                self._send(_build_icmd1_ack(self.hkid, self._seq, self.session_id))

        return False
