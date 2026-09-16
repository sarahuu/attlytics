import json
import logging
import webbrowser
from urllib import request as urlrequest
from urllib.parse import urlencode, urlparse

import websocket

from agent import config, identity

logger = logging.getLogger(__name__)

# Stored next to identity.json, e.g. ~/.attlytics/secrets.bin
SECRETS_PATH = config.IDENTITY_PATH.parent / "secrets.bin"

_ENROLL_PATH = f"{config.API_V1_PREFIX}/devices/enroll"
_ENROLL_WS_PATH = f"{config.API_V1_PREFIX}/devices/enroll/ws"


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


def _ws_url(base: str) -> str:
    parsed = urlparse(base)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}{_ENROLL_WS_PATH}"


def _display_name(user: dict) -> str:
    if not isinstance(user, dict):
        return ""
    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    return " ".join(part for part in (first, last) if part)


def await_api_key(
    token: str, server_url: str | None = None, timeout: int = 60
) -> tuple[str, str]:
    """Open the enrollment socket and block until the user API key arrives.

    Returns (api_key, account_display_name) and closes the connection.
    """
    base = (server_url or config.API_BASE_URL).rstrip("/")
    if not base:
        raise RuntimeError("API_BASE_URL is not configured")

    ws = websocket.create_connection(_ws_url(base), timeout=timeout,header=[f"Authorization: Bearer {token}"])
    try:
        while True:
            raw = ws.recv()
            message = json.loads(raw)
            if message.get("type") == "api_key" and message.get("api_key"):
                api_key = message["api_key"]
                ws.close()
                return api_key, _display_name(message.get("user") or {})
            # "hello", "ping", "pong" keep-alives are ignored for now.
    except websocket.WebSocketException as exc:
        logger.warning("Enrollment websocket closed unexpectedly: %s", exc)
        raise


# ---- Secure local storage (DPAPI / Windows) -------------------------------


def save_api_key(api_key: str, name: str = "") -> None:
    """Encrypt {api_key, account name} with DPAPI and store it in secrets.bin."""
    try:
        import win32crypt
    except ImportError as exc:  # pragma: no cover - non-Windows
        raise RuntimeError("DPAPI storage requires pywin32 (Windows)") from exc

    payload = json.dumps({"api_key": api_key, "name": name}, ensure_ascii=False)
    blob = win32crypt.CryptProtectData(
        payload.encode("utf-16-le"),
        "attlytics-account",
    )
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SECRETS_PATH.with_suffix(".tmp")
    tmp.write_bytes(blob)
    tmp.replace(SECRETS_PATH)


def load_account() -> dict | None:
    """Return {"api_key", "name"} from DPAPI storage, or None.

    Handles legacy files that only stored the raw key.
    """
    if not SECRETS_PATH.exists():
        logger.info("No stored account at %s", SECRETS_PATH)
        return None
    try:
        import win32crypt
    except ImportError:  # pragma: no cover - non-Windows
        logger.warning("win32crypt unavailable; cannot read the stored account")
        return None
    try:
        _, raw = win32crypt.CryptUnprotectData(SECRETS_PATH.read_bytes())
        text = raw.decode("utf-16-le").strip()
    except Exception:  # noqa: BLE001 - corrupt file -> treat as not connected
        logger.exception("Could not decrypt %s", SECRETS_PATH)
        return None
    try:
        account = json.loads(text)
        if isinstance(account, dict) and account.get("api_key"):
            account.setdefault("name", "")
            return account
    except (ValueError, TypeError):
        pass
    # Legacy file: the blob was just the raw api key.
    return {"api_key": text, "name": ""}


def load_api_key() -> str | None:
    """Back-compat: return just the stored api key, or None."""
    account = load_account()
    return account["api_key"] if account else None


# ---- End to end -----------------------------------------------------------


def confirmation_url(token: str, web_base: str | None = None) -> str:
    """Build the browser URL where the user confirms this device."""
    base = (web_base or config.WEB_BASE_URL).rstrip("/")
    if not base:
        raise RuntimeError("WEB_BASE_URL is not configured")
    return f"{base}/device/register?{urlencode({'token': token})}"


def connect_account(on_link=None) -> dict:
    """Enroll -> show/open confirmation link -> wait on socket -> store key.

    Returns the stored account dict {"api_key", "name"}. on_link(url) is
    called with the confirmation URL before we wait on the socket; if omitted
    the default browser is opened automatically.
    """
    response = enroll()
    token = response["token"]
    url = confirmation_url(token)

    if on_link is not None:
        on_link(url)
    else:
        webbrowser.open(url)

    api_key, name = await_api_key(token)
    save_api_key(api_key, name)
    logger.info("Account connected; api key stored.")
    return {"api_key": api_key, "name": name}
