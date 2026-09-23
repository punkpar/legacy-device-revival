from dataclasses import dataclass

ONLINE_STATUSES = {1, 2}


@dataclass(frozen=True)
class LanDevice:
    """Device entry returned by the SDK LAN callback."""

    device_id: str
    device_type: str
    hkid: int
    channel_count: int
    status: int
    audio_type: str
    ip: str = ""

    @property
    def online(self) -> bool:
        """True when the SDK reports the device as online."""
        return self.status in ONLINE_STATUSES
