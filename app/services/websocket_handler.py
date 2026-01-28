"""
WebSocket Event Handler for Evolution API

This module handles incoming WebSocket events from Evolution API
and processes them using the same logic as the webhook handler.
"""

import asyncio
import time
import random
from typing import Optional, Dict, Any

from ..db import supabase
from ..evolve_parse import (
    extract_chat_id, extract_message_id, extract_from_me,
    extract_text, extract_message_type
)
from ..services.collision import should_pause_on_event, now_utc
from ..services.llm_client import get_llm_provider
from ..services.evolution_client import EvolutionClient, EvolutionAPIError
from ..config import (
    DEFAULT_SYSTEM_PROMPT, LLM_PROVIDER,
    MESSAGE_DELAY_ENABLED, MESSAGE_DELAY_MIN_MS, MESSAGE_DELAY_MAX_MS,
    TYPING_INDICATOR_ENABLED
)
from ..logger import log_info, log_warning, log_error


async def handle_websocket_message(data: Dict[str, Any]):
    """
    Handle incoming message from WebSocket.

    This function processes the message using the same logic as the webhook handler.

    Args:
        data: The event data from Evolution API WebSocket
    """
    start_time = time.time()

    # WebSocket data structure might be slightly different from webhook
    # Extract the event type and instance
    event = data.get("event", "messages.upsert")
    instance = data.get("instance")

    # If data is nested, extract it
    if "data" in data:
        payload = data
    else:
        # Assume data IS the payload
        payload = {"event": event, "instance": instance, "data": data}

    log_info(
        "WebSocket message received",
        event=event,
        instance=instance,
        action="ws_message_received",
    )

    if not instance:
        log_warning("WebSocket message missing instance", action="ws_missing_instance")
        return {"ok": False, "error": "Missing instance"}

    # 1) Resolve tenant by instance_name
    try:
        tenant_resp = (
            supabase.table("tenants")
            .select("id, instance_name, evo_server_url, system_prompt, llm_provider")
            .eq("instance_name", instance)
            .limit(1)
            .execute()
        )
    except Exception as e:
        log_error(
            "Database error resolving tenant",
            instance=instance,
            error=str(e),
            action="ws_tenant_error",
        )
        return {"ok": False, "error": f"Database error: {e}"}

    if not tenant_resp.data:
        log_warning("Unknown instance from WebSocket", instance=instance, action="ws_unknown_instance")
        return {"ok": False, "error": f"Unknown instance: {instance}"}

    tenant = tenant_resp.data[0]
    tenant_id = tenant["id"]

    log_info("Tenant resolved via WebSocket", tenant_id=tenant_id, instance=instance, action="ws_tenant_resolved")

    # Only handle message events
    if event not in ("messages.upsert", "message"):
        log_info(f"Ignoring event type: {event}", action="ws_event_ignored")
        return {"ok": True, "ignored": event}

    # Extract message data
    chat_id = extract_chat_id(payload)
    msg_id = extract_message_id(payload)
    from_me = extract_from_me(payload)
    text = extract_text(payload)
    msg_type = extract_message_type(payload)

    if not chat_id or not msg_id:
        return {"ok": True, "note": "No chat_id or message_id"}

    # For replies, use chat_id (remoteJid) which is the customer
    reply_to = chat_id

    # 2) Idempotency check
    try:
        existing = supabase.table("processed_events").select("*").eq(
            "tenant_id", tenant_id
        ).eq("message_id", msg_id).eq("event_type", event).execute()

        if existing.data and len(existing.data) > 0:
            log_info(
                "Duplicate message ignored - already processed",
                tenant_id=tenant_id,
                chat_id=chat_id,
                message_id=msg_id,
                action="ws_duplicate_ignored",
            )
            return {"ok": True, "action": "duplicate_ignored", "message_id": msg_id}
    except Exception as e:
        log_warning(
            "Idempotency check skipped",
            error=str(e),
            action="ws_idempotency_skipped",
        )

    # 3) Store inbound message
    try:
        supabase.table("messages").insert({
            "tenant_id": tenant_id,
            "chat_id": chat_id,
            "message_id": msg_id,
            "from_me": from_me,
            "message_type": msg_type or "conversation",
            "text": text,
            "raw": payload,
        }).execute()
    except Exception as e:
        if "duplicate key" not in str(e).lower():
            log_warning(
                "Failed to store message",
                tenant_id=tenant_id,
                message_id=msg_id,
                error=str(e),
                action="ws_store_message_failed",
            )

    # 4) Upsert session
    now = now_utc()
    session_data = {
        "tenant_id": tenant_id,
        "chat_id": chat_id,
        "last_message_at": now.isoformat(),
    }

    # 5) Check for collision (human intervention)
    if should_pause_on_event(event, from_me):
        session_data["is_paused"] = True
        session_data["pause_reason"] = "human_intervention"
        session_data["last_human_at"] = now.isoformat()

        log_info(
            "Session paused due to human intervention (WebSocket)",
            tenant_id=tenant_id,
            chat_id=chat_id,
            action="ws_session_paused",
        )

        # Record event and return
        _record_processed_event(tenant_id, msg_id, event, "paused")

        try:
            supabase.table("sessions").upsert(
                session_data,
                on_conflict="tenant_id,chat_id"
            ).execute()
        except Exception as e:
            log_error("Failed to upsert session", error=str(e))

        return {"ok": True, "action": "paused", "chat_id": chat_id}

    # Upsert session (not paused)
    try:
        supabase.table("sessions").upsert(
            session_data,
            on_conflict="tenant_id,chat_id"
        ).execute()
    except Exception as e:
        log_warning("Failed to upsert session", error=str(e))

    # 6) Check if session is paused
    try:
        session_resp = supabase.table("sessions").select("is_paused").eq(
            "tenant_id", tenant_id
        ).eq("chat_id", chat_id).limit(1).execute()

        if session_resp.data and session_resp.data[0].get("is_paused"):
            log_info(
                "Session is paused, skipping AI reply (WebSocket)",
                tenant_id=tenant_id,
                chat_id=chat_id,
                action="ws_ignored_paused",
            )
            _record_processed_event(tenant_id, msg_id, event, "ignored_paused")
            return {"ok": True, "action": "ignored_paused", "chat_id": chat_id}
    except Exception as e:
        log_warning("Failed to check session pause status", error=str(e))

    # 7) Generate AI reply for inbound messages
    if from_me is False:
        try:
            evolution_client = EvolutionClient()

            # Skip mark_as_read and typing for @lid contacts (Evolution API doesn't support them)
            is_lid_contact = chat_id.endswith("@lid")

            # Mark message as read before processing (show blue checkmarks)
            # Skip for @lid contacts as Evolution API can't validate them
            if not is_lid_contact:
                try:
                    await evolution_client.mark_as_read(
                        tenant_id=tenant_id,
                        chat_id=chat_id,
                        message_id=msg_id
                    )
                    log_info(
                        "Message marked as read (WebSocket)",
                        tenant_id=tenant_id,
                        chat_id=chat_id,
                        message_id=msg_id,
                        action="ws_mark_read_success",
                    )
                except Exception as e:
                    log_warning(
                        "Failed to mark message as read",
                        tenant_id=tenant_id,
                        chat_id=chat_id,
                        message_id=msg_id,
                        error=str(e),
                        action="ws_mark_read_failed",
                    )

            # Send typing indicator (composing) before generating reply
            # Skip for @lid contacts as Evolution API can't validate them
            if TYPING_INDICATOR_ENABLED and not is_lid_contact:
                try:
                    await evolution_client.send_presence(
                        tenant_id=tenant_id,
                        chat_id=chat_id,
                        presence="composing",
                        delay=5000  # Keep typing for 5 seconds initially
                    )
                    log_info(
                        "Typing indicator sent (WebSocket)",
                        tenant_id=tenant_id,
                        chat_id=chat_id,
                        action="ws_typing_start",
                    )
                except Exception as e:
                    log_warning(
                        "Failed to send typing indicator",
                        tenant_id=tenant_id,
                        chat_id=chat_id,
                        error=str(e),
                        action="ws_typing_failed",
                    )

            system_prompt = tenant.get("system_prompt") or DEFAULT_SYSTEM_PROMPT
            provider_name = tenant.get("llm_provider") or LLM_PROVIDER

            log_info(
                "Generating AI reply (WebSocket)",
                tenant_id=tenant_id,
                chat_id=chat_id,
                provider=provider_name,
                action="ws_ai_generate_start",
            )

            # Generate AI reply
            llm_provider = get_llm_provider(provider_name)
            reply_text = await llm_provider.generate_reply(
                message=text,
                system_prompt=system_prompt,
            )

            log_info(
                "AI reply generated (WebSocket)",
                tenant_id=tenant_id,
                chat_id=chat_id,
                reply_length=len(reply_text),
                action="ws_ai_generate_success",
            )

            # Add human-like delay before sending (to avoid WhatsApp bans)
            if MESSAGE_DELAY_ENABLED:
                delay_ms = random.randint(MESSAGE_DELAY_MIN_MS, MESSAGE_DELAY_MAX_MS)
                delay_seconds = delay_ms / 1000.0

                # Refresh typing indicator during delay (skip for @lid contacts)
                if TYPING_INDICATOR_ENABLED and not is_lid_contact:
                    try:
                        await evolution_client.send_presence(
                            tenant_id=tenant_id,
                            chat_id=chat_id,
                            presence="composing",
                            delay=delay_ms
                        )
                    except Exception:
                        pass  # Non-critical

                log_info(
                    "Adding human-like delay before sending (WebSocket)",
                    tenant_id=tenant_id,
                    chat_id=chat_id,
                    delay_ms=delay_ms,
                    action="ws_delay_start",
                )
                await asyncio.sleep(delay_seconds)

            # Send reply via Evolution API
            await evolution_client.send_text_message(
                tenant_id=tenant_id,
                chat_id=reply_to,
                text=reply_text
            )

            # Stop typing indicator after sending (skip for @lid contacts)
            if TYPING_INDICATOR_ENABLED and not is_lid_contact:
                try:
                    await evolution_client.send_presence(
                        tenant_id=tenant_id,
                        chat_id=chat_id,
                        presence="paused"
                    )
                except Exception:
                    pass  # Non-critical

            log_info(
                "Reply sent via Evolution API (WebSocket)",
                tenant_id=tenant_id,
                chat_id=chat_id,
                action="ws_evolution_send_success",
            )

            # Store outbound message
            try:
                supabase.table("messages").insert({
                    "tenant_id": tenant_id,
                    "chat_id": chat_id,
                    "message_id": f"out-{msg_id}",
                    "from_me": True,
                    "message_type": "conversation",
                    "text": reply_text,
                    "raw": {"generated": True, "model": llm_provider.get_model_name(), "source": "websocket"}
                }).execute()
            except Exception as e:
                log_warning("Failed to store outbound message", error=str(e))

            total_duration = int((time.time() - start_time) * 1000)

            log_info(
                "AI reply pipeline completed (WebSocket)",
                tenant_id=tenant_id,
                chat_id=chat_id,
                duration_ms=total_duration,
                action="ws_ai_replied",
            )

            _record_processed_event(tenant_id, msg_id, event, "ai_replied")

            return {
                "ok": True,
                "action": "ai_replied",
                "chat_id": chat_id,
                "reply_preview": reply_text[:100] + "..." if len(reply_text) > 100 else reply_text
            }

        except EvolutionAPIError as e:
            log_error(
                "Evolution API send failed (WebSocket)",
                tenant_id=tenant_id,
                chat_id=chat_id,
                error=str(e),
                action="ws_evolution_send_failed",
            )
            _record_processed_event(tenant_id, msg_id, event, "evolution_send_failed")
            return {"ok": True, "action": "evolution_send_failed", "error": str(e)}

        except Exception as e:
            log_error(
                "AI reply pipeline failed (WebSocket)",
                tenant_id=tenant_id,
                chat_id=chat_id,
                error=str(e),
                action="ws_ai_failed",
            )
            _record_processed_event(tenant_id, msg_id, event, "ai_failed")
            return {"ok": True, "action": "ai_failed", "error": str(e)}

    return {"ok": True}


async def handle_websocket_connection_update(data: Dict[str, Any]):
    """Handle connection update events from WebSocket."""
    instance = data.get("instance")
    state = data.get("data", {}).get("state") if isinstance(data.get("data"), dict) else data.get("state")

    log_info(
        "Connection update received (WebSocket)",
        instance=instance,
        state=state,
        action="ws_connection_update",
    )

    return {"ok": True, "instance": instance, "state": state}


def _record_processed_event(tenant_id: int, message_id: str, event_type: str, action_taken: str):
    """Record a processed event for idempotency."""
    try:
        supabase.table("processed_events").insert({
            "tenant_id": tenant_id,
            "message_id": message_id,
            "event_type": event_type,
            "action_taken": action_taken,
        }).execute()
    except Exception as e:
        log_warning(
            "Failed to record processed event",
            tenant_id=tenant_id,
            message_id=message_id,
            error=str(e),
        )
