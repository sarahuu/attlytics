from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, UTC
import uuid
from uuid import UUID
from typing import Optional, Dict
from app.core.config import get_settings, ACCESS_TOKEN_EXPIRE, REFRESH_TOKEN_EXPIRE

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class SecurityUtils:

    @staticmethod
    def verify_password(plain_password:str, hashed_password:str):
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password:str):
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(user_id:UUID, extra_data: Optional[Dict]=None):
        jti = str(uuid.uuid4())
        payload = {
            "sub": str(user_id),
            "exp": datetime.now(UTC) + ACCESS_TOKEN_EXPIRE,
            "type": "access",
            "jti": jti,
            "iat": datetime.now(UTC)
        }
        if extra_data:
            payload.update(extra_data)
        return jwt.encode(payload, get_settings().secret_key, algorithm=get_settings().algorithm)

    @staticmethod
    def create_refresh_token(user_id:UUID, extra_data: Optional[Dict]=None):
        jti = str(uuid.uuid4())
        payload = {
            "sub": str(user_id),
            "exp": datetime.now(UTC) + REFRESH_TOKEN_EXPIRE,
            "type": "refresh",
            "jti": jti,
            "iat": datetime.now(UTC)
        }
        if extra_data:
            payload.update(extra_data)
        return jwt.encode(payload, get_settings().secret_key, algorithm=get_settings().algorithm)

    @staticmethod
    def decode_token(token:str):
        try:
            payload = jwt.decode(
                token,
                get_settings().secret_key,
                algorithms=[get_settings().algorithm],
                options={"verify_exp":True}
            )
            return payload
        except JWTError as e:
            raise ValueError(f"Invalid token: {str(e)}")


    @staticmethod
    def verify_token(token: str, expected_type: str = "access"):
        try:
            payload = SecurityUtils.decode_token(token)
            if payload.get("type") != expected_type:
                raise ValueError(f"Invalid token type. Expected: {expected_type}")
            return payload
        except ValueError:
            raise