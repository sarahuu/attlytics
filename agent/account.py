import json
import logging
from urllib import request as urlrequest
from urllib.parse import urlparse

import websocket

from agent import config, identity

logger = logging.getLogger(__name__)

# Stored next to identity.json, e.g. ~/.attlytics/secrets.bin
SECRETS_PATH = config.IDENTITY_PATH.parent / "secrets.bin"

_ENROLL_PATH = "/v1/devices/enroll"
_ENROLL_WS_PATH = "/v1/devices/enroll/ws"


# ---- HTTP: enroll ---------------------------------------------------------


def _http_json_post(url: str, payload: dict, timeout: int = 15) -> dict:
    req = urlrequest.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlrequest.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def enroll(server_url: str | None = None) -> dict:
    """POST the local identity metadata -> returns the enrollment response."""
    base = (server_url or config.API_BASE_URL).rstrip("/")
    if not base:
        raise RuntimeError("API_BASE_URL is not configured")

    identity_data = identity.load_or_create_identity()
    meta = identity_data.get("metadata", {})
    payload = {
        "installation_id": identity_data["installation_id"],
        "device_name": meta.get("hostname") or "agent",
        "device_type": meta.get("platform") or "unknown",
    }
    for key in ("hostname", "platform", "os_version", "machine_key", "agent_version"):
        if meta.get(key):
            payload[key] = meta[key]

    return _http_json_post(base + _ENROLL_PATH, payload)


# ---- Websocket ------------------------------------------------------------


def _ws_url(base: str, token: str) -> str:
    parsed = urlparse(base)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}{_ENROLL_WS_PATH}?token={token}"


def await_api_key(token: str, server_url: str | None = None, timeout: int = 60) -> str:
    """Open the enrollment socket and block until the user API key arrives.

    Returns the api key and closes the connection (as requested).
    """
    base = (server_url or config.API_BASE_URL).rstrip("/")
    if not base:
        raise RuntimeError("API_BASE_URL is not configured")

    ws = websocket.create_connection(_ws_url(base, token), timeout=timeout)
    try:
        while True:
            raw = ws.recv()
            message = json.loads(raw)
            if message.get("type") == "api_key" and message.get("api_key"):
                api_key = message["api_key"]
                ws.close()
                return api_key
            # "hello", "ping", "pong" keep-alives are ignored for now.
    except websocket.WebSocketException as exc:
        logger.warning("Enrollment websocket closed unexpectedly: %s", exc)
        raise


# ---- Secure local storage (DPAPI / Windows) -------------------------------


def save_api_key(api_key: str) -> None:
    """Encrypt the api key with DPAPI (bound to this Windows user) and store it."""
    try:
        import win32crypt
    except ImportError as exc:  # pragma: no cover - non-Windows
        raise RuntimeError("DPAPI storage requires pywin32 (Windows)") from exc

    blob = win32crypt.CryptProtectData(
        api_key.encode("utf-16-le"),
        description="attlytics-api-key",
    )
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SECRETS_PATH.with_suffix(".tmp")
    tmp.write_bytes(blob)
    tmp.replace(SECRETS_PATH)


def load_api_key() -> str | None:
    """Return the stored api key, or None if there isn't one."""
    if not SECRETS_PATH.exists():
        return None
    try:
        import win32crypt
    except ImportError:  # pragma: no cover - non-Windows
        return None
    blob = SECRETS_PATH.read_bytes()
    data, _ = win32crypt.CryptUnprotectData(blob)
    return data.decode("utf-16-le")


# ---- End to end -----------------------------------------------------------


def connect_account() -> str:
    """Enroll -> open socket -> store api key -> return it (socket closed)."""
    response = enroll()
    token = response["token"]
    api_key = await_api_key(token)
    save_api_key(api_key)
    logger.info("Account connected; api key stored.")
    return api_key
