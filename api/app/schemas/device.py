import uuid

from pydantic import BaseModel, Field


class DeviceEnroll(BaseModel):
    """Metadata sent by the agent when it enrolls a device."""

    installation_id: uuid.UUID = Field(description="Agent-generated installation id")
    device_name: str = Field(..., min_length=1, max_length=255)
    device_type: str = Field(..., min_length=1, max_length=255)
    hostname: str | None = Field(default=None, max_length=255)
    platform: str | None = Field(default=None, max_length=64)
    os_version: str | None = Field(default=None, max_length=64)
    machine_key: str | None = Field(default=None, max_length=128)
    agent_version: str | None = Field(default=None, max_length=32)


class DeviceEnrollResponse(BaseModel):
    token: str
    token_type: str = "device"
    expires_in: int = Field(description="Seconds until the token expires")


class DeviceConfirmRequest(BaseModel):
    token: str = Field(description="The enrollment token from /enroll")


class DeviceConfirmResponse(BaseModel):
    status: str
    detail: str
    installation_id: uuid.UUID | None = Field(
        default=None, description="The registered device's installation id"
    )
