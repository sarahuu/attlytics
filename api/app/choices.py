from enum import Enum


class Source(str, Enum):
    """Where an observation came from."""

    OS = "os"


class EventType(str, Enum):
    """The kinds of events a device can emit."""

    STATE_START = "STATE_START"
    HEARTBEAT = "HEARTBEAT"
    STATE_END = "STATE_END"


class SyncStatus(str, Enum):
    """Local delivery state of an event (agent-side concern)."""

    PENDING = "PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"
