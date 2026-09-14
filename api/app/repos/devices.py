import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.users import Device


async def get_by_installation_id(
    db: AsyncSession, installation_id: uuid.UUID
) -> Device | None:
    return await db.scalar(
        select(Device).where(Device.installation_id == installation_id)
    )


async def get_by_id(db: AsyncSession, device_id: uuid.UUID) -> Device | None:
    return await db.get(Device, device_id)


async def create(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    installation_id: uuid.UUID,
    device_name: str,
    device_type: str,
    hostname: str | None = None,
    platform: str | None = None,
    os_version: str | None = None,
    machine_key: str | None = None,
    agent_version: str | None = None,
) -> Device:
    device = Device(
        user_id=user_id,
        installation_id=installation_id,
        device_name=device_name,
        device_type=device_type,
        hostname=hostname,
        platform=platform,
        os_version=os_version,
        machine_key=machine_key,
        agent_version=agent_version,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


async def update_metadata(
    db: AsyncSession,
    device: Device,
    *,
    device_name: str,
    device_type: str,
    hostname: str | None = None,
    platform: str | None = None,
    os_version: str | None = None,
    machine_key: str | None = None,
    agent_version: str | None = None,
) -> Device:
    """Refresh a re-connecting device in place instead of creating a new row."""
    device.device_name = device_name
    device.device_type = device_type
    device.hostname = hostname
    device.platform = platform
    device.os_version = os_version
    device.machine_key = machine_key
    device.agent_version = agent_version
    device.is_active = True
    device.last_seen_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(device)
    return device
