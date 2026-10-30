from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.rate_limiter import rate_limit_auth
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.services.auth_service import auth_service
from app.services.audit_service import audit_service

router = APIRouter(prefix="/auth", tags=["authentication"])


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new user with email, password, and optional full name. Password is securely hashed using bcrypt.",
    dependencies=[Depends(rate_limit_auth)],
)
async def register(
    user_in: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Register a new user account."""
    user = await auth_service.register_user(db=db, user_in=user_in)
    client_ip = _get_client_ip(request)
    await audit_service.log_event(
        db=db,
        action="AUTH_REGISTER",
        resource_type="user",
        user_id=user.id,
        resource_id=str(user.id),
        ip_address=client_ip,
        details={"email": user.email},
    )
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="User login (JSON)",
    description="Authenticates with email and password, returning a signed JWT access token.",
    dependencies=[Depends(rate_limit_auth)],
)
async def login(
    login_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Authenticate user with JSON credentials and return JWT."""
    client_ip = _get_client_ip(request)
    user = await auth_service.authenticate_user(
        db=db,
        email=login_data.email,
        password=login_data.password,
    )
    if not user:
        await audit_service.log_event(
            db=db,
            action="AUTH_LOGIN_FAILURE",
            resource_type="user",
            ip_address=client_ip,
            status="FAILURE",
            details={"attempted_email": str(login_data.email)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await audit_service.log_event(
        db=db,
        action="AUTH_LOGIN_SUCCESS",
        resource_type="user",
        user_id=user.id,
        resource_id=str(user.id),
        ip_address=client_ip,
        details={"email": user.email},
    )

    access_token = create_access_token(subject=user.id)
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/token",
    response_model=Token,
    summary="OAuth2 compatible token login",
    description="OAuth2 password flow endpoint for Swagger UI and form-based authentication.",
    dependencies=[Depends(rate_limit_auth)],
)
async def login_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """OAuth2 compatible token login supporting form-urlencoded requests."""
    client_ip = _get_client_ip(request)
    user = await auth_service.authenticate_user(
        db=db,
        email=form_data.username,
        password=form_data.password,
    )
    if not user:
        await audit_service.log_event(
            db=db,
            action="AUTH_LOGIN_FAILURE",
            resource_type="user",
            ip_address=client_ip,
            status="FAILURE",
            details={"attempted_email": form_data.username},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await audit_service.log_event(
        db=db,
        action="AUTH_LOGIN_SUCCESS",
        resource_type="user",
        user_id=user.id,
        resource_id=str(user.id),
        ip_address=client_ip,
        details={"email": user.email},
    )

    access_token = create_access_token(subject=user.id)
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user",
    description="Resolves and returns the authenticated user from the validated JWT token.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve profile of currently authenticated user."""
    return current_user


@router.get(
    "/protected",
    summary="Protected route check",
    description="Demonstrates protected resource access requiring a valid Bearer token.",
)
async def protected_route(
    current_user: User = Depends(get_current_user),
) -> Any:
    """Protected test endpoint confirming valid authorization."""
    return {
        "status": "authenticated",
        "message": f"Welcome, {current_user.email}!",
        "user_id": str(current_user.id),
    }
