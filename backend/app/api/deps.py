import hmac
import uuid
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.services.auth_service import auth_service

# OAuth2 scheme pointing to our login endpoint for Swagger UI Authorization
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=True,
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency that extracts, decodes, and validates the JWT Bearer token,
    resolving and returning the current authenticated User model.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id_raw: str = payload.get("sub")
        if user_id_raw is None:
            raise credentials_exception
        user_id = uuid.UUID(user_id_raw)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    user = await auth_service.get_by_id(db, user_id=user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account",
        )

    return user


async def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency that enforces the current authenticated user has superuser privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have sufficient privileges",
        )
    return current_user


async def require_admin_access(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Dependency that enforces administrative authorization for maintenance endpoints.
    Accepts either:
    1. Valid 'X-Admin-Key' header matching configured settings.ADMIN_SECRET_KEY, OR
    2. Valid Bearer JWT token belonging to an active superuser account.
    Rejects unauthenticated requests with HTTP 401 Unauthorized.
    Rejects unauthorized requests with HTTP 403 Forbidden.
    """
    admin_key_header = request.headers.get("X-Admin-Key")
    if admin_key_header:
        if not settings.ADMIN_SECRET_KEY:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrative key authorization is not configured.",
            )
        if not hmac.compare_digest(admin_key_header.strip(), settings.ADMIN_SECRET_KEY.strip()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid administrative secret key.",
            )
        return

    # Check Bearer token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrative authorization required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.split(" ", 1)[1].strip()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id_raw: str = payload.get("sub")
        if not user_id_raw:
            raise credentials_exception
        user_id = uuid.UUID(user_id_raw)
    except Exception:
        raise credentials_exception

    user = await auth_service.get_by_id(db, user_id=user_id)
    if not user or not user.is_active:
        raise credentials_exception
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have administrative privileges",
        )


__all__ = [
    "get_db",
    "get_current_user",
    "get_current_active_superuser",
    "require_admin_access",
    "oauth2_scheme",
    "AsyncSession",
    "AsyncGenerator",
]
