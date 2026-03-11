"""
Billing service — plan lookups, conversation metering, and usage gating.

Plans are stored in the `plans` table; tenant subscriptions in `subscriptions`;
monthly usage in `usage_records`.  A Postgres trigger auto-creates a free
subscription for each new tenant (see database/schema.sql).
"""
from datetime import datetime, timezone
from ..db import supabase


def _current_month() -> str:
    """Returns the first day of the current UTC month as ISO date (YYYY-MM-01)."""
    now = datetime.now(timezone.utc)
    return f"{now.year}-{now.month:02d}-01"


async def get_active_plan(tenant_id: int) -> dict:
    """
    Returns the active plan dict for a tenant.
    Falls back to the 'free' plan if no subscription exists.
    """
    result = (
        supabase.table("subscriptions")
        .select("status, plan_id, plans(id, name, display_name, max_instances, max_conversations_per_month, features)")
        .eq("tenant_id", tenant_id)
        .maybe_single()
        .execute()
    )
    if result.data and result.data.get("plans"):
        plan = result.data["plans"]
        plan["subscription_status"] = result.data["status"]
        return plan

    # Fallback: fetch free plan directly
    free = (
        supabase.table("plans")
        .select("*")
        .eq("name", "free")
        .single()
        .execute()
    )
    plan = free.data or {}
    plan["subscription_status"] = "active"
    return plan


async def get_conversation_count(tenant_id: int) -> int:
    """Returns AI conversations used this month for the tenant."""
    month = _current_month()
    result = (
        supabase.table("usage_records")
        .select("ai_conversations")
        .eq("tenant_id", tenant_id)
        .eq("month", month)
        .maybe_single()
        .execute()
    )
    if result.data:
        return result.data.get("ai_conversations", 0)
    return 0


async def is_within_conversation_limit(tenant_id: int) -> bool:
    """
    Returns True if the tenant can send another AI reply this month.
    max_conversations_per_month == -1 means unlimited.
    """
    plan = await get_active_plan(tenant_id)
    if plan.get("subscription_status") not in ("active",):
        return False  # past_due or cancelled tenants cannot use AI

    max_convos = plan.get("max_conversations_per_month", 100)
    if max_convos == -1:
        return True  # unlimited (agency/enterprise)

    used = await get_conversation_count(tenant_id)
    return used < max_convos


async def increment_conversation_count(tenant_id: int) -> int:
    """
    Upserts usage_records for the current month, increments ai_conversations.
    Returns the new count.
    """
    month = _current_month()
    # Upsert: insert row if not exists, else increment
    result = (
        supabase.rpc(
            "increment_conversation_usage",
            {"p_tenant_id": tenant_id, "p_month": month},
        )
        .execute()
    )
    # Fallback if RPC not deployed yet: fetch and update manually
    if result.data is None:
        existing = (
            supabase.table("usage_records")
            .select("id, ai_conversations")
            .eq("tenant_id", tenant_id)
            .eq("month", month)
            .maybe_single()
            .execute()
        )
        if existing.data:
            new_count = existing.data["ai_conversations"] + 1
            supabase.table("usage_records").update(
                {"ai_conversations": new_count}
            ).eq("id", existing.data["id"]).execute()
        else:
            new_count = 1
            supabase.table("usage_records").insert(
                {"tenant_id": tenant_id, "month": month, "ai_conversations": new_count}
            ).execute()
        return new_count

    return result.data or 1


async def get_subscription_summary(tenant_id: int) -> dict:
    """
    Returns a full summary for the billing API endpoint and dashboard widget.
    """
    plan = await get_active_plan(tenant_id)
    used = await get_conversation_count(tenant_id)
    max_convos = plan.get("max_conversations_per_month", 100)

    sub_result = (
        supabase.table("subscriptions")
        .select("status, billing_cycle, currency, current_period_end, cancel_at_period_end, processor")
        .eq("tenant_id", tenant_id)
        .maybe_single()
        .execute()
    )
    sub = sub_result.data or {}

    return {
        "plan_name": plan.get("name", "free"),
        "plan_display_name": plan.get("display_name", "Free"),
        "status": sub.get("status", "active"),
        "billing_cycle": sub.get("billing_cycle", "monthly"),
        "currency": sub.get("currency", "USD"),
        "processor": sub.get("processor", "free"),
        "max_instances": plan.get("max_instances", 1),
        "max_conversations_per_month": max_convos,
        "conversations_used": used,
        "conversations_remaining": max(0, max_convos - used) if max_convos != -1 else -1,
        "current_period_end": sub.get("current_period_end"),
        "cancel_at_period_end": sub.get("cancel_at_period_end", False),
        "features": plan.get("features", {}),
    }


async def handle_paystack_webhook(event_type: str, data: dict) -> str:
    """
    Handles Paystack webhook events and updates subscription records.
    Returns the action taken.
    """
    if event_type == "subscription.create":
        sub_code = data.get("subscription_code")
        customer = data.get("customer", {})
        plan_code = data.get("plan", {}).get("plan_code")

        # Find tenant by customer email
        user_result = (
            supabase.table("user")
            .select("id")
            .eq("email", customer.get("email", ""))
            .maybe_single()
            .execute()
        )
        if not user_result.data:
            return "user_not_found"

        # Update subscription
        supabase.table("subscriptions").update({
            "processor": "paystack",
            "processor_subscription_id": sub_code,
            "processor_customer_id": customer.get("customer_code"),
            "status": "active",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("processor_subscription_id", sub_code).execute()

        return "subscription_activated"

    elif event_type == "subscription.disable":
        sub_code = data.get("subscription_code")
        supabase.table("subscriptions").update({
            "status": "cancelled",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("processor_subscription_id", sub_code).execute()
        return "subscription_cancelled"

    elif event_type == "invoice.payment_failed":
        sub_code = data.get("subscription", {}).get("subscription_code")
        if sub_code:
            supabase.table("subscriptions").update({
                "status": "past_due",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("processor_subscription_id", sub_code).execute()
        return "payment_failed"

    elif event_type == "charge.success":
        sub_code = data.get("metadata", {}).get("subscription_code")
        if sub_code:
            supabase.table("subscriptions").update({
                "status": "active",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("processor_subscription_id", sub_code).execute()
        return "payment_succeeded"

    return "unhandled_event"


async def handle_lemonsqueezy_webhook(event_type: str, data: dict) -> str:
    """
    Handles Lemonsqueezy webhook events and updates subscription records.
    Returns the action taken.
    """
    attributes = data.get("attributes", {})
    sub_id = str(data.get("id", ""))
    customer_email = attributes.get("user_email", "")

    if event_type == "subscription_created":
        supabase.table("subscriptions").update({
            "processor": "lemonsqueezy",
            "processor_subscription_id": sub_id,
            "processor_customer_id": str(attributes.get("customer_id", "")),
            "status": "active",
            "billing_cycle": "monthly" if attributes.get("billing_anchor") else "monthly",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("processor_subscription_id", sub_id).execute()
        return "subscription_created"

    elif event_type == "subscription_cancelled":
        supabase.table("subscriptions").update({
            "status": "cancelled",
            "cancel_at_period_end": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("processor_subscription_id", sub_id).execute()
        return "subscription_cancelled"

    elif event_type == "subscription_payment_success":
        supabase.table("subscriptions").update({
            "status": "active",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("processor_subscription_id", sub_id).execute()
        return "payment_succeeded"

    elif event_type == "subscription_payment_failed":
        supabase.table("subscriptions").update({
            "status": "past_due",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("processor_subscription_id", sub_id).execute()
        return "payment_failed"

    return "unhandled_event"
