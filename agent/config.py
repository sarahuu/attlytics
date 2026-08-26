import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_FROZEN = bool(getattr(sys, "frozen", False))

if _FROZEN:
    _PACKAGE_DIR = Path(sys.executable).resolve().parent
    _REPO_ROOT = _PACKAGE_DIR
else:
    _PACKAGE_DIR = Path(__file__).resolve().parent
    _REPO_ROOT = _PACKAGE_DIR.parent

load_dotenv(_REPO_ROOT / ".env")
load_dotenv(_PACKAGE_DIR / ".env")

# Where persistent data (the event log and lock file) lives.
_DATA_ROOT = (Path.home() / ".attlytics") if _FROZEN else _PACKAGE_DIR

DEFAULT_DB_PATH = _DATA_ROOT / "data" / "activity_events.db"

DB_PATH = Path(os.environ.get("DB_PATH", DEFAULT_DB_PATH))
POLL_INTERVAL_SECONDS = float(
    os.environ.get("POLL_INTERVAL_SECONDS", 1.0)
)
HEARTBEAT_INTERVAL_SECONDS = float(
    os.environ.get("HEARTBEAT_INTERVAL_SECONDS", 60.0)
)
IDLE_THRESHOLD_SECONDS = float(
    os.environ.get("IDLE_THRESHOLD_SECONDS", 60.0)
)
