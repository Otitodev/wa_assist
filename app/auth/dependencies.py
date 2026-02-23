"""
FastAPI dependencies for authentication and authorization.

Sessions are issued by BetterAuth (Next.js) and stored in the Supabase
'session' table. FastAPI validates requests by looking up the session token
directly in the database — no JWT crypto needed.
"""

from datetime import datetime, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Callable

from ..db import supabase
from ..logger import log_info, log_warning, log_error


# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=True)
optional_security = HTTPBearer(auto_error=False)


def _parse_iso(ts: str) -> datetime:
    """Parse ISO-8601 timestamp to aware datetime (handles both Z and +00:00)."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Validate BetterAuth session token and return current user with tenant access.

    The client sends the raw BetterAuth session token (from authClient.getSession())
    as the Bearer value. We look it up in the 'session' table to get the user ID,
    then fetch the user profile and tenant memberships.

    Args:
        credentials: Session token from Authorization header

    Returns:
        User dict with profile data and user_tenants list

    Raises:
        HTTPException 401: If token is invalid or session has expired
    """
    token = credentials.credentials

    try:
        # Look up session by token
        session_result = supabase.table("session").select(
            "userId, expiresAt"
        ).eq("token", token).limit(1).execute()

        if not session_result.data:
            log_warning("Session token not found", action="auth_invalid_token")
            raise HTTPException(status_code=401, detail="Invalid session token")

        session_row = session_result.data[0]

        # Check expiry
        expires_at = _parse_iso(session_row["expiresAt"])
        if expires_at < datetime.now(timezone.utc):
            log_warning("Session token expired", action="auth_expired_token")
            raise HTTPException(status_code=401, detail="Session expired")

        user_id = session_row["userId"]

        # Fetch user profile + tenant memberships
        user_result = supabase.table("user").select(
            "*, user_tenants(tenant_id, role)"
        ).eq("id", user_id).limit(1).execute()

        if not user_result.data:
            log_warning(
                "User profile not found",
                user_id=user_id,
                action="auth_user_not_found"
            )
            raise HTTPException(status_code=401, detail="User profile not found")

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
        log_error("Authentication failed", error=str(e), action="auth_error")
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {str(e)}"
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security)
) -> Optional[dict]:
    """
    Optional authentication - returns None if no token provided.
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

    Role hierarchy (highest to lowest): owner > admin > member
    """
    async def check_tenant_access(
        tenant_id: int,
        user: dict = Depends(get_current_user)
    ) -> None:
        user_tenants = user.get("user_tenants", [])

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
    """Extract list of tenant IDs the user has access to."""
    return [ut["tenant_id"] for ut in user.get("user_tenants", [])]
