import platform
import time
from datetime import datetime, timezone

from agent.collectors.windows import WindowsCollector
from agent.config import (
    DB_PATH,
    HEARTBEAT_INTERVAL_SECONDS,
    IDLE_THRESHOLD_SECONDS,
    POLL_INTERVAL_SECONDS,
)
from agent.instance_lock import InstanceLock
from agent.storage.database import ActivityDatabase
from agent.tracking.activity_tracker import ActivityTracker


class SystemClock:
    """Real time provider used in production."""

    def now(self):
        return datetime.now(timezone.utc)

    def monotonic(self):
        return time.monotonic()


def create_collector():
    system = platform.system()

    if system == "Windows":
        return WindowsCollector()

    raise RuntimeError(
        f"Unsupported operating system: {system}"
    )


def main():
    collector = create_collector()

    lock = InstanceLock(DB_PATH.parent / f"{DB_PATH.name}.lock")
    if not lock.acquire():
        print("Another instance of the agent is already running. Exiting.")
        return

    storage = ActivityDatabase(DB_PATH)
    storage.initialize()

    tracker = ActivityTracker(
        observer=collector.get_active_application,
        storage=storage,
        clock=SystemClock(),
        heartbeat_interval=HEARTBEAT_INTERVAL_SECONDS,
        idle_threshold=IDLE_THRESHOLD_SECONDS,
    )

    try:
        while True:
            tracker.observe()
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        storage.close()
        lock.release()


if __name__ == "__main__":
    main()