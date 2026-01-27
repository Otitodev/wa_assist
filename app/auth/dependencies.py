"""
FastAPI dependencies for authentication and authorization.

These dependencies can be used with FastAPI's Depends() to protect routes
and validate user access to resources.
"""

from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Callable

from ..db import supabase
from ..logger import log_info, log_warning, log_error


# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=True)
optional_security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Validate JWT token and return current user with tenant access.

    This dependency:
    1. Extracts the JWT token from the Authorization header
    2. Validates the token with Supabase Auth
    3. Retrieves the user profile with their tenant access

    Args:
        credentials: JWT token from Authorization header

    Returns:
        User dict with profile data and user_tenants list

    Raises:
        HTTPException 401: If token is invalid or expired
    """
    token = credentials.credentials

    try:
        # Verify JWT with Supabase Auth
        user_response = supabase.auth.get_user(token)

        if not user_response or not user_response.user:
            log_warning(
                "Invalid or expired token",
                action="auth_invalid_token"
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )

        auth_user = user_response.user

        # Get user profile from our users table with tenant access
        user_result = supabase.table("users").select(
            "*, user_tenants(tenant_id, role)"
        ).eq("auth_user_id", str(auth_user.id)).limit(1).execute()

        if not user_result.data:
            log_warning(
                "User profile not found",
                auth_user_id=str(auth_user.id),
                action="auth_user_not_found"
            )
            raise HTTPException(
                status_code=401,
                detail="User profile not found"
            )

        user = user_result.data[0]

        log_info(
            "User authenticated",
            user_id=user["id"],
            email=user["email"],
            action="auth_success"
        )

        return user

    except HTTPException:
        raise
    except Exception as e:
        log_error(
            "Authentication failed",
            error=str(e),
            action="auth_error"
        )
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {str(e)}"
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security)
) -> Optional[dict]:
    """
    Optional authentication - returns None if no token provided.

    Use this for endpoints that work with or without authentication,
    providing different behavior based on auth status.

    Args:
        credentials: Optional JWT token from Authorization header

    Returns:
        User dict if authenticated, None otherwise
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
    except Exception:
        return None


def require_tenant_access(required_role: str = "member") -> Callable:
    """
    Factory function that creates a dependency for checking tenant access.

    This validates that the authenticated user has access to the specified
    tenant with at least the required role level.

    Role hierarchy (highest to lowest):
    - owner: Full control (delete tenant, transfer ownership)
    - admin: Management (edit settings, invite/remove users)
    - member: Operations (view sessions, pause/resume)

    Usage:
        @app.get("/api/tenants/{tenant_id}/sessions")
        async def list_sessions(
            tenant_id: int,
            user: dict = Depends(get_current_user),
            _: None = Depends(require_tenant_access("member"))
        ):
            ...

    Args:
        required_role: Minimum role required ("owner", "admin", or "member")

    Returns:
        Dependency function that checks tenant access
    """
    async def check_tenant_access(
        tenant_id: int,
        user: dict = Depends(get_current_user)
    ) -> None:
        user_tenants = user.get("user_tenants", [])

        # Find user's access to this specific tenant
        access = next(
            (ut for ut in user_tenants if ut["tenant_id"] == tenant_id),
            None
        )

        if not access:
            log_warning(
                "Tenant access denied - no access",
                user_id=user["id"],
                tenant_id=tenant_id,
                action="auth_tenant_denied"
            )
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this tenant"
            )

        # Check role hierarchy
        role_hierarchy = {"owner": 3, "admin": 2, "member": 1}
        user_level = role_hierarchy.get(access["role"], 0)
        required_level = role_hierarchy.get(required_role, 0)

        if user_level < required_level:
            log_warning(
                "Tenant access denied - insufficient role",
                user_id=user["id"],
                tenant_id=tenant_id,
                user_role=access["role"],
                required_role=required_role,
                action="auth_role_denied"
            )
            raise HTTPException(
                status_code=403,
                detail=f"This action requires {required_role} role or higher"
            )

        log_info(
            "Tenant access granted",
            user_id=user["id"],
            tenant_id=tenant_id,
            role=access["role"],
            action="auth_tenant_granted"
        )

        return None

    return check_tenant_access


def get_user_tenant_ids(user: dict) -> list:
    """
    Extract list of tenant IDs the user has access to.

    Args:
        user: User dict from get_current_user

    Returns:
        List of tenant IDs
    """
    return [ut["tenant_id"] for ut in user.get("user_tenants", [])]
