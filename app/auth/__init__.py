"""
Authentication module for Whaply.

Session validation via BetterAuth — FastAPI reads the session token
from the `session` table (Supabase) to identify the user.
"""

from .dependencies import get_current_user, get_optional_user, require_tenant_access
from .routes import router as auth_router

__all__ = [
    "get_current_user",
    "get_optional_user",
    "require_tenant_access",
    "auth_router",
]
