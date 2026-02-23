"""
Authentication API routes.

Login, register, logout, and token refresh are handled by BetterAuth
running as Next.js API routes (/api/auth/*).

This module keeps only the /me endpoint, which returns the user profile
and tenant list from the database using the BetterAuth JWT user ID.
"""

from fastapi import APIRouter, Depends

from .dependencies import get_current_user


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/me")
async def get_current_user_profile(user: dict = Depends(get_current_user)):
    """
    Get current user's profile.

    Returns the authenticated user's profile including their tenant access.
    Requires valid BetterAuth JWT in the Authorization header.

    **Authorization**: Bearer token required
    """
    tenants = user.pop("user_tenants", [])

    return {
        "user": user,
        "tenants": tenants
    }
