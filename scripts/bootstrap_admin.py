#!/usr/bin/env python3
"""
Bootstrap Admin Script

Creates the initial admin user and assigns all existing tenants to them.
This script should be run once after deploying the auth system to migrate
existing tenants to the new user management system.

Usage:
    python scripts/bootstrap_admin.py <email> <password>

Example:
    python scripts/bootstrap_admin.py admin@example.com MySecurePassword123
"""

import sys
import os
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client


async def bootstrap_admin(email: str, password: str, display_name: str = "Admin"):
    """
    Create initial admin user and assign all existing tenants.

    Args:
        email: Admin user's email address
        password: Admin user's password (min 8 characters)
        display_name: Display name for the admin user

    Returns:
        Created user dict
    """
    # Initialize Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    client = create_client(supabase_url, supabase_key)

    print(f"Creating admin user: {email}")

    # 1. Check if user already exists
    existing_user = client.table("users").select("id, email").eq("email", email).limit(1).execute()
    if existing_user.data:
        print(f"User {email} already exists with id: {existing_user.data[0]['id']}")
        user_id = existing_user.data[0]["id"]
    else:
        # 2. Create user in Supabase Auth
        try:
            auth_response = client.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,  # Auto-confirm email
            })

            if not auth_response.user:
                raise ValueError("Failed to create user in Supabase Auth")

            auth_user_id = str(auth_response.user.id)
            print(f"Created auth user: {auth_user_id}")

        except Exception as e:
            # Try sign_up if admin API fails
            print(f"Admin create failed, trying sign_up: {e}")
            auth_response = client.auth.sign_up({
                "email": email,
                "password": password,
            })

            if not auth_response.user:
                raise ValueError("Failed to create user in Supabase Auth")

            auth_user_id = str(auth_response.user.id)
            print(f"Created auth user via sign_up: {auth_user_id}")

        # 3. Create user profile in users table
        user_data = {
            "auth_user_id": auth_user_id,
            "email": email,
            "display_name": display_name,
            "is_active": True,
        }

        user_result = client.table("users").insert(user_data).execute()

        if not user_result.data:
            raise ValueError("Failed to create user profile in users table")

        user_id = user_result.data[0]["id"]
        print(f"Created user profile: {user_id}")

    # 4. Get all existing tenants
    tenants = client.table("tenants").select("id, instance_name").execute()
    tenant_count = len(tenants.data) if tenants.data else 0

    print(f"Found {tenant_count} existing tenants")

    if tenant_count == 0:
        print("No tenants to assign. Admin user created successfully.")
        return {"user_id": user_id, "email": email, "tenants_assigned": 0}

    # 5. Assign all tenants to admin user
    assigned_count = 0
    for tenant in tenants.data:
        tenant_id = tenant["id"]
        instance_name = tenant["instance_name"]

        # Check if already assigned
        existing = client.table("user_tenants").select("id").eq(
            "user_id", user_id
        ).eq("tenant_id", tenant_id).limit(1).execute()

        if existing.data:
            print(f"  - {instance_name} (id:{tenant_id}): Already assigned")
            continue

        # Create user_tenants record
        try:
            client.table("user_tenants").insert({
                "user_id": user_id,
                "tenant_id": tenant_id,
                "role": "owner",
            }).execute()

            # Update tenant owner
            client.table("tenants").update({
                "owner_user_id": user_id
            }).eq("id", tenant_id).execute()

            print(f"  - {instance_name} (id:{tenant_id}): Assigned as owner")
            assigned_count += 1

        except Exception as e:
            print(f"  - {instance_name} (id:{tenant_id}): Failed to assign - {e}")

    print(f"\nBootstrap complete!")
    print(f"  User: {email}")
    print(f"  User ID: {user_id}")
    print(f"  Tenants assigned: {assigned_count}/{tenant_count}")

    return {
        "user_id": user_id,
        "email": email,
        "tenants_assigned": assigned_count,
        "total_tenants": tenant_count
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/bootstrap_admin.py <email> <password> [display_name]")
        print()
        print("Arguments:")
        print("  email        Admin user's email address")
        print("  password     Admin user's password (min 8 characters)")
        print("  display_name Optional display name (default: 'Admin')")
        print()
        print("Example:")
        print("  python scripts/bootstrap_admin.py admin@example.com MySecurePassword123")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]
    display_name = sys.argv[3] if len(sys.argv) > 3 else "Admin"

    if len(password) < 8:
        print("Error: Password must be at least 8 characters")
        sys.exit(1)

    try:
        asyncio.run(bootstrap_admin(email, password, display_name))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
