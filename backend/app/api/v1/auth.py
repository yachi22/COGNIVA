from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new user with email, password, and optional full name. Password is securely hashed using bcrypt.",
)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Register a new user account."""
    user = await auth_service.register_user(db=db, user_in=user_in)
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="User login (JSON)",
    description="Authenticates with email and password, returning a signed JWT access token.",
)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Authenticate user with JSON credentials and return JWT."""
    user = await auth_service.authenticate_user(
        db=db,
        email=login_data.email,
        password=login_data.password,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
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
)
async def login_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """OAuth2 compatible token login supporting form-urlencoded requests."""
    user = await auth_service.authenticate_user(
        db=db,
        email=form_data.username,
        password=form_data.password,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
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
