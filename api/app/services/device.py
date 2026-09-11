import secrets
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import SecurityUtils
from app.core.ws import enrollment_sockets
from app.models.users import Device, User
from app.repos import api_keys as api_keys_repo
from app.repos import devices as devices_repo
from app.schemas.device import DeviceEnroll, DeviceEnrollResponse


def enroll_device(payload: DeviceEnroll) -> DeviceEnrollResponse:
    settings = get_settings()

    claims = {
        "installation_id": str(payload.installation_id),
        "device_name": payload.device_name,
        "device_type": payload.device_type,
    }
    for field in ("hostname", "platform", "os_version", "machine_key", "agent_version"):
        value = getattr(payload, field)
        if value:
            claims[field] = value

    token = SecurityUtils.create_device_token(
        str(payload.installation_id),
        extra_data=claims,
        expires_minutes=settings.enroll_token_expire_min,
    )
    return DeviceEnrollResponse(
        token=token,
        expires_in=settings.enroll_token_expire_min * 60,
    )


async def confirm_enrollment(
    db: AsyncSession, user: User, token: str
) -> tuple[str, Device]:
    try:
        payload = SecurityUtils.verify_token(token, expected_type="device")
        installation_id = UUID(payload["sub"])
    except (ValueError, KeyError):
        raise UnauthorizedError("Invalid or expired enrollment token") from None

    installation = str(installation_id)
    if not enrollment_sockets.is_connected(installation):
        raise ConflictError(
            "Agent is not connected. Run \u201cConnect account\u201d in the agent first."
        )

    meta = {
        "device_name": payload.get("device_name") or "Device",
        "device_type": payload.get("device_type") or "unknown",
        "hostname": payload.get("hostname"),
        "platform": payload.get("platform"),
        "os_version": payload.get("os_version"),
        "machine_key": payload.get("machine_key"),
        "agent_version": payload.get("agent_version"),
    }

    # Idempotent by installation_id: re-confirming the same agent must not
    # create a second Device row.
    device = await devices_repo.get_by_installation_id(db, installation_id)
    if device is None:
        device = await devices_repo.create(
            db, user_id=user.id, installation_id=installation_id, **meta
        )
    elif device.user_id != user.id:
        raise ConflictError(
            "This device is already registered to another account. "
            "Remove it from that account or re-install the agent."
        )
    else:
        device = await devices_repo.update_metadata(db, device, **meta)

    # Rotate: revoke this device's previous key, then issue a fresh one that
    # is delivered to the agent over the socket.
    api_key = secrets.token_urlsafe(32)
    api_key_hash = SecurityUtils.hash_api_key(api_key)

    try:
        await api_keys_repo.revoke_active_for_device(
            db, user_id=user.id, device_id=device.id
        )
        await api_keys_repo.create(
            db, user_id=user.id, device_id=device.id, key_hash=api_key_hash
        )
    except IntegrityError:
        await db.rollback()
        raise ConflictError("Device or API key already exists") from None

    return api_key, device
