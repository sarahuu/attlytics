
import os
import sys
from pathlib import Path

_FROZEN = bool(getattr(sys, "frozen", False))

if _FROZEN:
    _PACKAGE_DIR = Path(sys.executable).resolve().parent
else:
    _PACKAGE_DIR = Path(__file__).resolve().parent

_DATA_ROOT = (Path.home() / ".attlytics") if _FROZEN else _PACKAGE_DIR

# --- Paths -----------------------------------------------------------------
DEFAULT_DB_PATH = _DATA_ROOT / "data" / "activity_events.db"
DB_PATH = Path(os.environ.get("DB_PATH", str(DEFAULT_DB_PATH)))

DEFAULT_IDENTITY_PATH = _DATA_ROOT / "identity.json"
IDENTITY_PATH = Path(os.environ.get("IDENTITY_PATH", str(DEFAULT_IDENTITY_PATH)))

# --- Tracking tuning (non-critical) ---------------------------------------
POLL_INTERVAL_SECONDS = float(os.environ.get("POLL_INTERVAL_SECONDS", 1.0))
HEARTBEAT_INTERVAL_SECONDS = float(
    os.environ.get("HEARTBEAT_INTERVAL_SECONDS", 60.0)
)
IDLE_THRESHOLD_SECONDS = float(
    os.environ.get("IDLE_THRESHOLD_SECONDS", 60.0)
)

# --- Remote Attlytics API (empty = syncing disabled until configured) ------
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

# --- Web app base URL, used to build the "confirm this device" link ---------
DEFAULT_WEB_BASE_URL = "http://localhost:5173"
WEB_BASE_URL = os.environ.get("WEB_BASE_URL", DEFAULT_WEB_BASE_URL).rstrip("/")
