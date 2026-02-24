#!/usr/bin/env python3
"""
Auto-resume paused sessions after inactivity.

This script automatically resumes sessions that have been paused due to human takeover
after a configurable period of inactivity (default: 2 hours).

Usage:
    python scripts/auto_resume.py

Environment Variables:
    SUPABASE_URL: Supabase project URL
    SUPABASE_SERVICE_ROLE_KEY: Supabase service role key
    RESUME_AFTER_HOURS: Hours of inactivity before auto-resume (default: 2)

Run this script periodically via:
    - Cron job (every 15 minutes)
    - Railway cron service
    - Cloud Run scheduled task
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
RESUME_AFTER_HOURS = int(os.getenv("RESUME_AFTER_HOURS", "2"))


def auto_resume_sessions():
    """
    Resume sessions that have been paused for longer than RESUME_AFTER_HOURS.

    Returns:
        int: Number of sessions resumed
    """
    from supabase import create_client

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set", file=sys.stderr)
        sys.exit(1)

    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    # Calculate cutoff time
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=RESUME_AFTER_HOURS)
    cutoff_iso = cutoff_time.isoformat()

    print(f"Auto-resuming sessions paused before {cutoff_iso} ({RESUME_AFTER_HOURS} hours ago)")

    try:
        # Query sessions that should be resumed
        sessions_to_resume = supabase.table("sessions").select(
            "id, tenant_id, chat_id, last_human_at"
        ).eq("is_paused", True).lt("last_human_at", cutoff_iso).execute()

        if not sessions_to_resume.data:
            print("No sessions to resume")
            return 0

        # Log sessions that will be resumed
        print(f"Found {len(sessions_to_resume.data)} sessions to resume:")
        for session in sessions_to_resume.data:
            print(f"  - Session {session['id']}: tenant_id={session['tenant_id']}, "
                  f"chat_id={session['chat_id']}, last_human_at={session['last_human_at']}")

        # Update sessions to resume them
        result = supabase.table("sessions").update({
            "is_paused": False,
            "pause_reason": None,
        }).eq("is_paused", True).lt("last_human_at", cutoff_iso).execute()

        resumed_count = len(result.data) if result.data else 0
        print(f"✓ Successfully resumed {resumed_count} sessions")

        # Also clean up old processed_events (if table exists)
        try:
            cleanup_cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            cleanup_result = supabase.table("processed_events").delete().lt(
                "processed_at", cleanup_cutoff
            ).execute()
            deleted_count = len(cleanup_result.data) if cleanup_result.data else 0
            if deleted_count > 0:
                print(f"✓ Cleaned up {deleted_count} old processed events (>7 days)")
        except Exception as e:
            # Table might not exist yet, that's okay
            print(f"Note: Could not clean up processed_events: {e}")

        return resumed_count

    except Exception as e:
        print(f"ERROR: Failed to auto-resume sessions: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 60)
    print("Whaply Auto-Resume Script")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    resumed_count = auto_resume_sessions()

    print("=" * 60)
    print(f"Done. Resumed {resumed_count} sessions.")
    print("=" * 60)
