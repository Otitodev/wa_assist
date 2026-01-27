#!/usr/bin/env python3
"""
Seed Data Script for HybridFlow

This script populates the database with sample data for development and testing.

Usage:
    python scripts/seed_data.py [--clean]

Options:
    --clean     Clear existing data before seeding (WARNING: destructive!)

Environment:
    Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env file
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(project_root / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
    sys.exit(1)


def get_supabase_client():
    """Initialize Supabase client."""
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def now_utc():
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


def clean_database(supabase):
    """Remove all existing data (use with caution!)."""
    print("\n🗑️  Cleaning existing data...")

    tables = ["processed_events", "messages", "sessions", "tenants"]

    for table in tables:
        try:
            # Delete all rows
            supabase.table(table).delete().neq("id", -1).execute()
            print(f"   ✓ Cleared {table}")
        except Exception as e:
            print(f"   ✗ Failed to clear {table}: {e}")


def seed_tenants(supabase):
    """Seed tenant data."""
    print("\n📦 Seeding tenants...")

    tenants = [
        {
            "instance_name": "demo-instance",
            "evo_server_url": "https://evolution-api.example.com",
            "evo_api_key": "demo-api-key-12345",
            "system_prompt": """You are a friendly and professional WhatsApp assistant for Demo Company.

Your role:
- Answer customer questions about products and services
- Help with order status inquiries
- Provide business hours and contact information
- Escalate complex issues to human support

Guidelines:
- Be concise and helpful
- Use a friendly but professional tone
- If unsure, offer to connect with a human agent
- Never make up information about prices or availability""",
            "llm_provider": "anthropic",
        },
        {
            "instance_name": "support-bot",
            "evo_server_url": "https://evolution-api.example.com",
            "evo_api_key": "support-api-key-67890",
            "system_prompt": """You are a technical support assistant for TechCorp.

Your responsibilities:
- Help users troubleshoot common issues
- Provide step-by-step instructions
- Collect information for support tickets
- Direct users to relevant documentation

Always be patient and thorough in your explanations.""",
            "llm_provider": "anthropic",
        },
        {
            "instance_name": "sales-assistant",
            "evo_server_url": "https://evolution-api.example.com",
            "evo_api_key": "sales-api-key-11111",
            "system_prompt": """You are a sales assistant for Premium Services Inc.

Your goals:
- Answer questions about our service plans
- Help customers choose the right plan
- Explain pricing and features
- Schedule demos with the sales team

Be enthusiastic but not pushy. Focus on understanding customer needs.""",
            "llm_provider": "openai",
        },
    ]

    inserted_tenants = []
    for tenant in tenants:
        try:
            result = supabase.table("tenants").insert(tenant).execute()
            if result.data:
                inserted = result.data[0]
                inserted_tenants.append(inserted)
                print(f"   ✓ Created tenant: {inserted['instance_name']} (id: {inserted['id']})")
        except Exception as e:
            if "duplicate key" in str(e).lower():
                # Fetch existing tenant
                existing = supabase.table("tenants").select("*").eq(
                    "instance_name", tenant["instance_name"]
                ).limit(1).execute()
                if existing.data:
                    inserted_tenants.append(existing.data[0])
                    print(f"   ⚠ Tenant exists: {tenant['instance_name']} (id: {existing.data[0]['id']})")
            else:
                print(f"   ✗ Failed to create tenant {tenant['instance_name']}: {e}")

    return inserted_tenants


def seed_sessions(supabase, tenants):
    """Seed session data."""
    print("\n💬 Seeding sessions...")

    if not tenants:
        print("   ⚠ No tenants available, skipping sessions")
        return []

    # Sample phone numbers (fake)
    phone_numbers = [
        "5511999991111",
        "5511999992222",
        "5511999993333",
        "5511999994444",
        "5511999995555",
        "5521988881111",
        "5521988882222",
        "5531977771111",
    ]

    sessions = []

    for i, phone in enumerate(phone_numbers):
        # Distribute across tenants
        tenant = tenants[i % len(tenants)]
        chat_id = f"{phone}@s.whatsapp.net"

        # Vary session states
        is_paused = i % 3 == 0  # Every 3rd session is paused

        # Calculate timestamps
        hours_ago = i * 2
        last_message = now_utc() - timedelta(hours=hours_ago)
        last_human = last_message - timedelta(minutes=30) if is_paused else None

        session = {
            "tenant_id": tenant["id"],
            "chat_id": chat_id,
            "is_paused": is_paused,
            "pause_reason": "human_intervention" if is_paused else None,
            "last_message_at": last_message.isoformat(),
            "last_human_at": last_human.isoformat() if last_human else None,
        }
        sessions.append(session)

    inserted_sessions = []
    for session in sessions:
        try:
            result = supabase.table("sessions").insert(session).execute()
            if result.data:
                inserted = result.data[0]
                inserted_sessions.append(inserted)
                status = "PAUSED" if inserted["is_paused"] else "ACTIVE"
                print(f"   ✓ Created session: {inserted['chat_id'][:20]}... [{status}]")
        except Exception as e:
            if "duplicate key" in str(e).lower():
                print(f"   ⚠ Session exists: {session['chat_id'][:20]}...")
            else:
                print(f"   ✗ Failed to create session: {e}")

    return inserted_sessions


def seed_messages(supabase, tenants):
    """Seed message data."""
    print("\n📝 Seeding messages...")

    if not tenants:
        print("   ⚠ No tenants available, skipping messages")
        return []

    # Sample conversations
    conversations = [
        # Conversation 1: Product inquiry
        [
            {"from_me": False, "text": "Hi, I'm interested in your premium plan. What's included?"},
            {"from_me": True, "text": "Hello! Great to hear from you. Our premium plan includes unlimited messaging, priority support, and advanced analytics. Would you like me to explain each feature in detail?"},
            {"from_me": False, "text": "Yes please, especially the analytics part"},
            {"from_me": True, "text": "Our analytics dashboard provides real-time insights including: message response times, customer satisfaction scores, conversation trends, and peak hours analysis. You can also export reports in PDF or CSV format."},
            {"from_me": False, "text": "That sounds great! How much does it cost?"},
            {"from_me": True, "text": "The premium plan is $49/month when billed annually, or $59/month for monthly billing. We also offer a 14-day free trial so you can test all features. Would you like me to set that up for you?"},
        ],
        # Conversation 2: Support issue
        [
            {"from_me": False, "text": "My account isn't working, I can't log in"},
            {"from_me": True, "text": "I'm sorry to hear you're having trouble logging in. Let me help you with that. Can you tell me what error message you're seeing?"},
            {"from_me": False, "text": "It says 'invalid credentials' but I'm sure my password is correct"},
            {"from_me": True, "text": "I understand that's frustrating. Let's try a few things: 1) Make sure Caps Lock is off, 2) Try resetting your password using the 'Forgot Password' link. Would you like me to send a password reset link to your email?"},
            {"from_me": False, "text": "Yes please"},
            {"from_me": True, "text": "I've sent a password reset link to your registered email address. Please check your inbox (and spam folder) and follow the instructions. The link expires in 24 hours. Let me know if you need any further assistance!"},
        ],
        # Conversation 3: Quick question
        [
            {"from_me": False, "text": "What are your business hours?"},
            {"from_me": True, "text": "We're available Monday through Friday, 9 AM to 6 PM (EST). For urgent matters outside these hours, you can leave a message and we'll respond first thing the next business day. Is there anything specific I can help you with today?"},
        ],
        # Conversation 4: Human takeover scenario
        [
            {"from_me": False, "text": "I need to speak with a manager about my refund"},
            {"from_me": True, "text": "I understand you'd like to discuss your refund with a manager. Let me check on that for you. Can you provide your order number?"},
            {"from_me": False, "text": "Order #12345"},
            {"from_me": True, "text": "Thank you. I can see order #12345. Before I connect you with a manager, may I ask what specific issue you're experiencing with the refund?"},
            {"from_me": False, "text": "I was promised a refund 2 weeks ago and still haven't received it"},
            # Human takes over here
            {"from_me": True, "text": "Hi, this is Sarah from the support team. I sincerely apologize for the delay with your refund. I'm looking into this personally right now and will ensure it's processed today. You should see it in your account within 3-5 business days."},
        ],
    ]

    inserted_messages = []
    phone_numbers = ["5511999991111", "5511999992222", "5511999993333", "5511999994444"]

    for conv_idx, conversation in enumerate(conversations):
        tenant = tenants[conv_idx % len(tenants)]
        phone = phone_numbers[conv_idx % len(phone_numbers)]
        chat_id = f"{phone}@s.whatsapp.net"

        # Generate messages with realistic timestamps
        base_time = now_utc() - timedelta(hours=conv_idx * 4)

        for msg_idx, msg in enumerate(conversation):
            # Each message 1-3 minutes apart
            msg_time = base_time + timedelta(minutes=msg_idx * 2)

            message = {
                "tenant_id": tenant["id"],
                "chat_id": chat_id,
                "message_id": f"msg-{conv_idx}-{msg_idx}-{int(msg_time.timestamp())}",
                "from_me": msg["from_me"],
                "message_type": "conversation",
                "text": msg["text"],
                "raw": {
                    "event": "messages.upsert",
                    "data": {
                        "key": {
                            "remoteJid": chat_id,
                            "fromMe": msg["from_me"],
                            "id": f"msg-{conv_idx}-{msg_idx}"
                        },
                        "message": {
                            "conversation": msg["text"]
                        }
                    }
                },
                "created_at": msg_time.isoformat(),
            }

            try:
                result = supabase.table("messages").insert(message).execute()
                if result.data:
                    inserted_messages.append(result.data[0])
            except Exception as e:
                if "duplicate key" not in str(e).lower():
                    print(f"   ✗ Failed to create message: {e}")

    print(f"   ✓ Created {len(inserted_messages)} messages across {len(conversations)} conversations")
    return inserted_messages


def seed_processed_events(supabase, tenants):
    """Seed processed events for idempotency tracking."""
    print("\n🔄 Seeding processed events...")

    if not tenants:
        print("   ⚠ No tenants available, skipping processed events")
        return []

    events = []
    actions = ["ai_replied", "paused", "ignored_paused", "ai_replied", "ai_replied"]

    for i in range(10):
        tenant = tenants[i % len(tenants)]
        event_time = now_utc() - timedelta(hours=i)

        event = {
            "tenant_id": tenant["id"],
            "message_id": f"evt-msg-{i}-{int(event_time.timestamp())}",
            "event_type": "messages.upsert",
            "action_taken": actions[i % len(actions)],
            "processed_at": event_time.isoformat(),
        }
        events.append(event)

    inserted_events = []
    for event in events:
        try:
            result = supabase.table("processed_events").insert(event).execute()
            if result.data:
                inserted_events.append(result.data[0])
        except Exception as e:
            if "duplicate key" not in str(e).lower():
                print(f"   ✗ Failed to create processed event: {e}")

    print(f"   ✓ Created {len(inserted_events)} processed events")
    return inserted_events


def print_summary(supabase):
    """Print summary of seeded data."""
    print("\n" + "=" * 50)
    print("📊 SEED DATA SUMMARY")
    print("=" * 50)

    tables = ["tenants", "sessions", "messages", "processed_events"]

    for table in tables:
        try:
            result = supabase.table(table).select("*", count="exact").execute()
            count = len(result.data) if result.data else 0
            print(f"   {table}: {count} rows")
        except Exception as e:
            print(f"   {table}: ERROR - {e}")

    print("\n" + "=" * 50)
    print("✅ Seed data complete!")
    print("=" * 50)

    # Print useful info
    print("\n📌 Quick Start:")
    print("   1. Start server: uvicorn app.main:app --reload")
    print("   2. View API docs: http://localhost:8000/docs")
    print("   3. Health check: http://localhost:8000/health")
    print("   4. List tenants: http://localhost:8000/api/tenants")
    print("   5. List sessions: http://localhost:8000/api/sessions?tenant_id=1")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Seed database with sample data")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clear existing data before seeding (WARNING: destructive!)"
    )
    args = parser.parse_args()

    print("=" * 50)
    print("🌱 HybridFlow Seed Data Script")
    print("=" * 50)

    # Initialize Supabase client
    print("\n🔗 Connecting to Supabase...")
    try:
        supabase = get_supabase_client()
        print("   ✓ Connected successfully")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        sys.exit(1)

    # Clean if requested
    if args.clean:
        confirm = input("\n⚠️  WARNING: This will delete ALL existing data. Continue? (yes/no): ")
        if confirm.lower() == "yes":
            clean_database(supabase)
        else:
            print("   Skipping clean operation")

    # Seed data
    tenants = seed_tenants(supabase)
    sessions = seed_sessions(supabase, tenants)
    messages = seed_messages(supabase, tenants)
    events = seed_processed_events(supabase, tenants)

    # Print summary
    print_summary(supabase)


if __name__ == "__main__":
    main()
