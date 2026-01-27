"""
Pydantic models for authentication.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class UserRegister(BaseModel):
    """Request model for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    display_name: Optional[str] = None


class UserLogin(BaseModel):
    """Request model for user login."""
    email: EmailStr
    password: str


class TokenRefresh(BaseModel):
    """Request model for token refresh."""
    refresh_token: str


class TenantAccess(BaseModel):
    """User's access to a tenant."""
    tenant_id: int
    role: str


class UserProfile(BaseModel):
    """User profile response."""
    id: str
    email: str
    display_name: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


class AuthResponse(BaseModel):
    """Response for successful authentication."""
    user: UserProfile
    access_token: str
    refresh_token: str
    tenants: List[TenantAccess] = []


class TokenResponse(BaseModel):
    """Response for token refresh."""
    access_token: str
    refresh_token: str


class UserWithTenants(BaseModel):
    """User profile with tenant access list."""
    id: str
    email: str
    display_name: Optional[str] = None
    is_active: bool = True
    user_tenants: List[TenantAccess] = []
