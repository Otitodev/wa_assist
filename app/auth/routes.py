"""
Authentication API routes.

These routes handle user registration, login, token refresh, and profile retrieval.
"""

from fastapi import APIRouter, HTTPException, Depends

from .service import AuthService, AuthError
from .models import UserRegister, UserLogin, TokenRefresh
from .dependencies import get_current_user
from ..logger import log_info, log_error


router = APIRouter(prefix="/api/auth", tags=["Authentication"])
auth_service = AuthService()


@router.post("/register")
async def register(data: UserRegister):
    """
    Register a new user account.

    Creates a new user with the provided email and password.
    Returns the user profile along with access and refresh tokens.

    - **email**: Valid email address (will be used for login)
    - **password**: Minimum 8 characters
    - **display_name**: Optional display name (defaults to email prefix)
    """
    try:
        result = await auth_service.register(
            email=data.email,
            password=data.password,
            display_name=data.display_name
        )

        log_info(
            "New user registered via API",
            email=data.email,
            action="api_register_success"
        )

        return result

    except AuthError as e:
        log_error(
            "Registration failed via API",
            email=data.email,
            error=str(e),
            action="api_register_failed"
        )
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
async def login(data: UserLogin):
    """
    Authenticate user and get tokens.

    Validates credentials and returns access/refresh tokens for API access.

    - **email**: User's email address
    - **password**: User's password
    """
    try:
        result = await auth_service.login(
            email=data.email,
            password=data.password
        )

        log_info(
            "User logged in via API",
            email=data.email,
            action="api_login_success"
        )

        return result

    except AuthError as e:
        log_error(
            "Login failed via API",
            email=data.email,
            action="api_login_failed"
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")


@router.post("/refresh")
async def refresh_token(data: TokenRefresh):
    """
    Refresh access token.

    Use this endpoint to get a new access token when the current one expires.
    Access tokens expire after 1 hour by default.

    - **refresh_token**: Valid refresh token from login/register response
    """
    try:
        result = await auth_service.refresh_token(data.refresh_token)

        log_info(
            "Token refreshed via API",
            action="api_refresh_success"
        )

        return result

    except AuthError as e:
        log_error(
            "Token refresh failed via API",
            error=str(e),
            action="api_refresh_failed"
        )
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")


@router.post("/logout")
async def logout(user: dict = Depends(get_current_user)):
    """
    Sign out current user.

    Invalidates the current session. Requires valid access token.
    """
    await auth_service.logout("")
    return {"ok": True, "message": "Logged out successfully"}


@router.get("/me")
async def get_current_user_profile(user: dict = Depends(get_current_user)):
    """
    Get current user's profile.

    Returns the authenticated user's profile including their tenant access.
    Requires valid access token in Authorization header.

    **Authorization**: Bearer token required
    """
    # user_tenants is already included from get_current_user dependency
    tenants = user.pop("user_tenants", [])

    return {
        "user": user,
        "tenants": tenants
    }
