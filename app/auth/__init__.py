"""
Authentication module for HybridFlow.

This module provides user authentication using Supabase Auth,
including registration, login, token management, and access control.
"""

from .dependencies import get_current_user, get_optional_user, require_tenant_access
from .service import AuthService
from .routes import router as auth_router

__all__ = [
    "get_current_user",
    "get_optional_user",
    "require_tenant_access",
    "AuthService",
    "auth_router",
]
