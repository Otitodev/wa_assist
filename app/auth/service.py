"""
Authentication service for Whaply.

This service handles user registration, login, and token management
using Supabase Auth as the backend.
"""

from typing import Optional, Dict, Any

from ..db import supabase
from ..logger import log_info, log_warning, log_error


class AuthError(Exception):
    """Custom exception for authentication errors."""
    pass


class AuthService:
    """
    Service class for authentication operations.

    Uses Supabase Auth for secure password handling and JWT management.
    User profiles are stored in our users table, linked via auth_user_id.
    """

    def __init__(self):
        self.client = supabase

    async def register(
        self,
        email: str,
        password: str,
        display_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register a new user account.

        This method:
        1. Creates the user in Supabase Auth (handles password hashing)
        2. Creates a user profile in our users table
        3. Returns the user with access tokens

        Args:
            email: User's email address
            password: User's password (min 8 characters)
            display_name: Optional display name

        Returns:
            Dict with user profile, access_token, and refresh_token

        Raises:
            AuthError: If registration fails
        """
        try:
            log_info(
                "Registering new user",
                email=email,
                action="auth_register_start"
            )

            # 1. Create user in Supabase Auth
            auth_response = self.client.auth.sign_up({
                "email": email,
                "password": password,
            })

            if not auth_response.user:
                raise AuthError("Failed to create user in Supabase Auth")

            auth_user = auth_response.user

            # 2. Create user profile in our users table
            user_data = {
                "auth_user_id": str(auth_user.id),
                "email": email,
                "display_name": display_name or email.split("@")[0],
                "is_active": True,
            }

            log_info(
                "Attempting to create user profile",
                auth_user_id=str(auth_user.id),
                email=email,
                action="auth_register_profile_start"
            )

            try:
                user_result = self.client.table("users").insert(user_data).execute()
                log_info(
                    "User insert result",
                    data=str(user_result.data),
                    action="auth_register_profile_result"
                )
            except Exception as insert_error:
                log_error(
                    "User insert exception",
                    error=str(insert_error),
                    error_type=type(insert_error).__name__,
                    action="auth_register_profile_exception"
                )
                raise AuthError(f"Failed to create user profile: {str(insert_error)}")

            if not user_result.data:
                # Rollback: This is tricky with Supabase Auth
                # In production, consider a more robust approach
                log_error(
                    "Failed to create user profile after auth signup",
                    auth_user_id=str(auth_user.id),
                    action="auth_register_profile_failed"
                )
                raise AuthError("Failed to create user profile")

            user = user_result.data[0]

            log_info(
                "User registered successfully",
                user_id=user["id"],
                email=email,
                action="auth_register_success"
            )

            return {
                "user": user,
                "access_token": auth_response.session.access_token if auth_response.session else None,
                "refresh_token": auth_response.session.refresh_token if auth_response.session else None,
                "tenants": [],  # New user has no tenants yet
            }

        except AuthError:
            raise
        except Exception as e:
            log_error(
                "Registration failed",
                email=email,
                error=str(e),
                action="auth_register_error"
            )
            raise AuthError(f"Registration failed: {str(e)}")

    async def login(
        self,
        email: str,
        password: str
    ) -> Dict[str, Any]:
        """
        Authenticate user and return tokens.

        Args:
            email: User's email address
            password: User's password

        Returns:
            Dict with user profile, access_token, refresh_token, and tenants

        Raises:
            AuthError: If credentials are invalid
        """
        try:
            log_info(
                "User login attempt",
                email=email,
                action="auth_login_start"
            )

            # Authenticate with Supabase Auth
            auth_response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password,
            })

            if not auth_response.user:
                log_warning(
                    "Invalid credentials",
                    email=email,
                    action="auth_login_invalid"
                )
                raise AuthError("Invalid email or password")

            # Get user profile with tenant access
            user_result = self.client.table("users").select(
                "*, user_tenants(tenant_id, role)"
            ).eq("auth_user_id", str(auth_response.user.id)).limit(1).execute()

            if not user_result.data:
                # User exists in auth but not in our users table
                # This shouldn't happen normally, but handle it gracefully
                log_warning(
                    "Auth user exists but no profile found",
                    auth_user_id=str(auth_response.user.id),
                    action="auth_login_no_profile"
                )
                raise AuthError("User profile not found. Please contact support.")

            user = user_result.data[0]
            tenants = user.pop("user_tenants", [])

            log_info(
                "User logged in successfully",
                user_id=user["id"],
                email=email,
                tenant_count=len(tenants),
                action="auth_login_success"
            )

            return {
                "user": user,
                "access_token": auth_response.session.access_token,
                "refresh_token": auth_response.session.refresh_token,
                "tenants": tenants,
            }

        except AuthError:
            raise
        except Exception as e:
            error_msg = str(e)
            log_error(
                "Login failed",
                email=email,
                error=error_msg,
                error_type=type(e).__name__,
                action="auth_login_error"
            )
            # Check for specific Supabase errors
            if "Email not confirmed" in error_msg:
                raise AuthError("Please confirm your email before logging in")
            raise AuthError(f"Login failed: {error_msg}")

    async def refresh_token(
        self,
        refresh_token: str
    ) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            Dict with new access_token and refresh_token

        Raises:
            AuthError: If refresh token is invalid
        """
        try:
            log_info(
                "Token refresh attempt",
                action="auth_refresh_start"
            )

            response = self.client.auth.refresh_session(refresh_token)

            if not response.session:
                raise AuthError("Invalid or expired refresh token")

            log_info(
                "Token refreshed successfully",
                action="auth_refresh_success"
            )

            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
            }

        except AuthError:
            raise
        except Exception as e:
            log_error(
                "Token refresh failed",
                error=str(e),
                action="auth_refresh_error"
            )
            raise AuthError("Failed to refresh token")

    async def logout(self, access_token: str) -> bool:
        """
        Sign out user and invalidate tokens.

        Note: Supabase handles token invalidation on their end.

        Args:
            access_token: Current access token

        Returns:
            True if logout successful
        """
        try:
            self.client.auth.sign_out()
            log_info("User logged out", action="auth_logout_success")
            return True
        except Exception as e:
            log_warning(
                "Logout failed",
                error=str(e),
                action="auth_logout_error"
            )
            return False

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile by user ID.

        Args:
            user_id: User's UUID

        Returns:
            User dict or None if not found
        """
        try:
            result = self.client.table("users").select(
                "*, user_tenants(tenant_id, role)"
            ).eq("id", user_id).limit(1).execute()

            return result.data[0] if result.data else None
        except Exception:
            return None
