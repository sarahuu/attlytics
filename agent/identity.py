import json
import platform
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent.config import IDENTITY_PATH

IDENTITY_VERSION = 1


def _machine_key() -> str | None:
    try:
        import hashlib
        import winreg
    except ImportError:  # pragma: no cover - non-Windows
        return None

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
    except OSError:
        return None

    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def collect_metadata() -> dict:
    return {
        "hostname": socket.gethostname(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "os_version": platform.version(),
        "machine_key": _machine_key(),
    }


def _write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def load_or_create_identity(path: Path | None = None) -> dict:
    """Return the stored identity, creating it (id + metadata) if missing."""
    path = Path(path) if path is not None else IDENTITY_PATH

    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("version", IDENTITY_VERSION)
        data.setdefault("installation_id", str(uuid.uuid4()))
        data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        data.setdefault("metadata", collect_metadata())
        return data

    identity = {
        "version": IDENTITY_VERSION,
        "installation_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": collect_metadata(),
    }
    _write_atomic(path, identity)
    return identity
