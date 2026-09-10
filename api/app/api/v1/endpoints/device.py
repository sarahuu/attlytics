import json

from fastapi import APIRouter, Depends, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.core.dependencies import get_current_user
from app.core.exceptions import ConflictError
from app.core.security import SecurityUtils
from app.core.ws import enrollment_sockets
from app.db.session import get_db
from app.models.users import User
from app.schemas.device import (
    DeviceConfirmRequest,
    DeviceConfirmResponse,
    DeviceEnroll,
    DeviceEnrollResponse,
)
from app.services import device as service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["devices"])


@router.post(
    "/enroll",
    response_model=DeviceEnrollResponse,
    summary="Enroll a device and receive a signed device token (no auth)",
)
def enroll_device(payload: DeviceEnroll) -> DeviceEnrollResponse:
    return service.enroll_device(payload)


@router.websocket("/enroll/ws")
async def enrollment_socket(websocket: WebSocket):
    """Agent keeps this open after enrolling; API accepts only valid tokens."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401, reason="Missing enrollment token")
        return

    try:
        payload = SecurityUtils.verify_token(token, expected_type="device")
    except ValueError:
        await websocket.close(code=4401, reason="Invalid or expired enrollment token")
        return

    installation_id = payload["sub"]
    await websocket.accept()
    enrollment_sockets.register(installation_id, websocket)
    await websocket.send_text(
        json.dumps(
            {
                "type": "hello",
                "installation_id": installation_id,
                "status": "waiting_for_confirmation",
            }
        )
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        enrollment_sockets.unregister(installation_id, websocket)


@router.post(
    "/confirm",
    response_model=DeviceConfirmResponse,
    summary="Confirm enrollment: link device + deliver API key to the agent",
)
async def confirm_enrollment(
    payload: DeviceConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeviceConfirmResponse:
    api_key, device = await service.confirm_enrollment(db, current_user, payload.token)

    sent = await enrollment_sockets.send_json(
        str(device.installation_id),
        {
            "type": "api_key",
            "api_key": api_key,
            "user": {
                "first_name": current_user.first_name,
                "last_name": current_user.last_name,
            },
        },
    )
    if not sent:
        raise ConflictError("Device linked, but the agent socket closed before delivery.")

    return DeviceConfirmResponse(
        status="confirmed",
        detail="Device linked and API key sent to the agent.",
        installation_id=device.installation_id,
    )
