from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import httpx
import time
import asyncio
import random
import os
from .db import supabase
from .auth import auth_router, get_current_user, require_tenant_access, get_optional_user
from .evolve_parse import (
    extract_chat_id, extract_message_id, extract_from_me,
    extract_text, extract_message_type
)
from .services.collision import should_pause_on_event, now_utc
from .services.llm_client import get_llm_provider
from .services.evolution_client import EvolutionClient, EvolutionAPIError
from .config import (
    N8N_ENABLED, N8N_WEBHOOK_URL, N8N_API_KEY,
    DEFAULT_SYSTEM_PROMPT, LLM_PROVIDER, LOG_LEVEL, CRON_SECRET, CORS_ORIGINS,
    WEBSOCKET_ENABLED, WEBSOCKET_MODE, EVOLUTION_SERVER_URL, EVOLUTION_API_KEY,
    MESSAGE_DELAY_ENABLED, MESSAGE_DELAY_MIN_MS, MESSAGE_DELAY_MAX_MS,
    TYPING_INDICATOR_ENABLED
)
from .logger import logger, log_info, log_warning, log_error, configure_logger_from_config
from .services.evolution_websocket import EvolutionWebSocket, EvolutionWebSocketManager
from .services.websocket_handler import handle_websocket_message, handle_websocket_connection_update

# Configure logger with settings from config
configure_logger_from_config()

app = FastAPI(title="HybridFlow Control Plane", version="0.1.0")

# Configure CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register auth routes
app.include_router(auth_router)

# Log application startup
logger.info("HybridFlow Control Plane starting up")
logger.info(f"CORS enabled for origins: {', '.join(CORS_ORIGINS)}")

# Global WebSocket manager (initialized on startup if enabled)
websocket_manager: EvolutionWebSocketManager = None


@app.on_event("startup")
async def startup_event():
    """Initialize WebSocket connection on startup if enabled."""
    global websocket_manager

    if not WEBSOCKET_ENABLED:
        log_info("WebSocket mode disabled, using webhooks", action="websocket_disabled")
        return

    if not EVOLUTION_SERVER_URL:
        log_warning(
            "WEBSOCKET_ENABLED=true but EVOLUTION_SERVER_URL not set",
            action="websocket_config_error"
        )
        return

    log_info(
        "Initializing WebSocket connection to Evolution API",
        mode=WEBSOCKET_MODE,
        server_url=EVOLUTION_SERVER_URL,
        action="websocket_init_start",
    )

    websocket_manager = EvolutionWebSocketManager()
    websocket_manager.set_message_handler(handle_websocket_message)
    websocket_manager.set_connection_handler(handle_websocket_connection_update)

    try:
        if WEBSOCKET_MODE == "global":
            # Global mode - receive events from all instances
            await websocket_manager.connect_global(
                server_url=EVOLUTION_SERVER_URL,
                api_key=EVOLUTION_API_KEY or None,
            )
            log_info(
                "WebSocket connected in global mode",
                server_url=EVOLUTION_SERVER_URL,
                action="websocket_connected_global",
            )
        else:
            # Instance mode - would need to connect per tenant
            # For now, just log that this mode requires per-tenant setup
            log_info(
                "WebSocket instance mode enabled - connect instances via API",
                action="websocket_instance_mode",
            )
    except Exception as e:
        log_error(
            f"Failed to connect WebSocket: {e}",
            action="websocket_connect_failed",
            error_type=type(e).__name__,
        )


@app.on_event("shutdown")
async def shutdown_event():
    """Disconnect WebSocket connections on shutdown."""
    global websocket_manager

    if websocket_manager:
        log_info("Disconnecting WebSocket connections", action="websocket_shutdown_start")
        try:
            await websocket_manager.disconnect_all()
            log_info("WebSocket connections closed", action="websocket_shutdown_complete")
        except Exception as e:
            log_error(
                f"Error during WebSocket shutdown: {e}",
                action="websocket_shutdown_error",
                error_type=type(e).__name__,
            )


# Helper function to record processed events for idempotency
def record_processed_event(
    tenant_id: int,
    message_id: str,
    event_type: str,
    action_taken: str
):
    """
    Record a processed event to prevent duplicate processing.

    Args:
        tenant_id: Tenant ID
        message_id: Message ID
        event_type: Event type (e.g., "messages.upsert")
        action_taken: Action that was taken (e.g., "paused", "ai_replied")
    """
    try:
        supabase.table("processed_events").insert({
            "tenant_id": tenant_id,
            "message_id": message_id,
            "event_type": event_type,
            "action_taken": action_taken,
        }).execute()
    except Exception as e:
        # Table might not exist yet or insert failed - log but don't crash
        log_warning(
            "Failed to record processed event",
            tenant_id=tenant_id,
            message_id=message_id,
            event_type=event_type,
            action_taken=action_taken,
            error=str(e),
        )


# Helper function to trigger n8n workflows (for migration path)
async def trigger_n8n_workflow(workflow_name: str, data: dict) -> dict:
    """
    Trigger an n8n workflow via webhook.

    Args:
        workflow_name: Name of the workflow to trigger (e.g., "ai-reply")
        data: Payload to send to the workflow

    Returns:
        n8n response dict
    """
    if not N8N_ENABLED:
        raise ValueError("n8n integration is not enabled")

    if not N8N_WEBHOOK_URL:
        raise ValueError("N8N_WEBHOOK_URL not configured")

    url = f"{N8N_WEBHOOK_URL}/{workflow_name}"
    headers = {}

    if N8N_API_KEY:
        headers["Authorization"] = f"Bearer {N8N_API_KEY}"

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            return {"ok": True, "n8n_response": response.json()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

@app.get("/health")
async def health():
    """
    Health check endpoint for monitoring and load balancers.

    Returns:
        - ok: Overall health status (true/false)
        - checks: Individual component health statuses
        - version: API version
        - timestamp: Current server time
    """
    from datetime import datetime, timezone

    health_status = {
        "ok": True,
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {}
    }

    # Check database connectivity
    try:
        result = supabase.table("tenants").select("id").limit(1).execute()
        health_status["checks"]["database"] = {
            "status": "ok",
            "message": "Connected to Supabase"
        }
    except Exception as e:
        health_status["ok"] = False
        health_status["checks"]["database"] = {
            "status": "error",
            "message": f"Database connection failed: {str(e)}"
        }

    # Check LLM provider configuration
    try:
        from .config import ANTHROPIC_API_KEY, OPENAI_API_KEY

        if ANTHROPIC_API_KEY or OPENAI_API_KEY:
            health_status["checks"]["llm"] = {
                "status": "ok",
                "message": "LLM provider configured"
            }
        else:
            health_status["ok"] = False
            health_status["checks"]["llm"] = {
                "status": "warning",
                "message": "No LLM API keys configured"
            }
    except Exception as e:
        health_status["checks"]["llm"] = {
            "status": "warning",
            "message": f"LLM check failed: {str(e)}"
        }

    # Check n8n configuration (optional)
    if N8N_ENABLED:
        if N8N_WEBHOOK_URL:
            health_status["checks"]["n8n"] = {
                "status": "ok",
                "message": "n8n integration enabled"
            }
        else:
            health_status["checks"]["n8n"] = {
                "status": "warning",
                "message": "n8n enabled but webhook URL not configured"
            }
    else:
        health_status["checks"]["n8n"] = {
            "status": "ok",
            "message": "n8n integration disabled (direct mode)"
        }

    # Check WebSocket status
    if WEBSOCKET_ENABLED:
        if websocket_manager:
            connected_count = sum(1 for ws in websocket_manager.connections.values() if ws.connected)
            total_count = len(websocket_manager.connections)
            health_status["checks"]["websocket"] = {
                "status": "ok" if connected_count > 0 else "warning",
                "message": f"WebSocket enabled ({connected_count}/{total_count} connections active)",
                "mode": WEBSOCKET_MODE,
                "connections": list(websocket_manager.connections.keys())
            }
        else:
            health_status["checks"]["websocket"] = {
                "status": "warning",
                "message": "WebSocket enabled but manager not initialized"
            }
    else:
        health_status["checks"]["websocket"] = {
            "status": "ok",
            "message": "WebSocket disabled (using webhooks)"
        }

    return health_status

@app.post("/webhooks/evolution")
async def evolution_webhook(req: Request):
    start_time = time.time()
    import hmac
    import hashlib
    from .config import EVOLUTION_WEBHOOK_SHARED_SECRET

    # Parse JSON body with error handling
    try:
        body = await req.body()
        if not body:
            log_warning("Webhook received empty body")
            raise HTTPException(status_code=400, detail="Empty request body")

        # Verify webhook signature if secret is configured (not default)
        if EVOLUTION_WEBHOOK_SHARED_SECRET and EVOLUTION_WEBHOOK_SHARED_SECRET != "change-me":
            signature = req.headers.get("X-Evolution-Signature") or req.headers.get("x-webhook-signature")
            if signature:
                # Compute expected signature
                expected_signature = hmac.new(
                    EVOLUTION_WEBHOOK_SHARED_SECRET.encode(),
                    body,
                    hashlib.sha256
                ).hexdigest()

                # Compare signatures securely
                if not hmac.compare_digest(signature.lower(), expected_signature.lower()):
                    log_warning(
                        "Webhook signature verification failed",
                        action="webhook_signature_invalid",
                    )
                    raise HTTPException(status_code=401, detail="Invalid webhook signature")

                log_info("Webhook signature verified", action="webhook_signature_valid")

        import json
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        log_error(
            "Webhook received invalid JSON",
            error=str(e),
            # Don't log body content for security - may contain sensitive data
        )
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    event = payload.get("event")
    instance = payload.get("instance")

    # Log webhook received (minimal info for security)
    log_info(
        "Webhook received",
        event=event,
        instance=instance,
    )

    if not event or not instance:
        log_warning("Webhook missing required fields", event=event, instance=instance)
        raise HTTPException(status_code=400, detail="Missing event or instance")

    # 1) Resolve tenant by instance_name
    tenant_resp = (
        supabase.table("tenants")
        .select("id, instance_name, evo_server_url, system_prompt, llm_provider")
        .eq("instance_name", instance)
        .limit(1)
        .execute()
    )
    if not tenant_resp.data:
        log_error("Unknown instance", instance=instance)
        raise HTTPException(status_code=404, detail=f"Unknown instance: {instance}")

    tenant = tenant_resp.data[0]
    tenant_id = tenant["id"]

    log_info("Tenant resolved", tenant_id=tenant_id, instance=instance)

    # Only handle message events for now
    if event not in ("messages.upsert", "messages.update", "connection.update"):
        return {"ok": True, "ignored": event}

    chat_id = extract_chat_id(payload)
    msg_id = extract_message_id(payload)
    from_me = extract_from_me(payload)
    text = extract_text(payload)
    msg_type = extract_message_type(payload)

    # For replies, always use chat_id (remoteJid) which is the customer
    # The "sender" field is actually the instance owner (business account), not the customer
    # LID format (e.g., "170166654656630@lid") should work with Evolution API
    reply_to = chat_id

    # Check if this is a @lid contact (Evolution API v2.2.x has issues with @lid)
    is_lid_contact = chat_id.endswith("@lid") if chat_id else False

    # connection.update doesn't have key/remoteJid in the same way
    if event == "connection.update":
        return {"ok": True}

    if not chat_id or not msg_id:
        return {"ok": True, "note": "No chat_id or message_id"}

    # 2) Idempotency check - prevent duplicate processing
    try:
        existing = supabase.table("processed_events").select("*").eq(
            "tenant_id", tenant_id
        ).eq("message_id", msg_id).eq("event_type", event).execute()

        if existing.data and len(existing.data) > 0:
            log_info(
                "Duplicate webhook ignored - already processed",
                tenant_id=tenant_id,
                chat_id=chat_id,
                message_id=msg_id,
                event=event,
                action="duplicate_ignored",
            )
            return {"ok": True, "action": "duplicate_ignored", "message_id": msg_id}
    except Exception as e:
        # Table might not exist yet - log but continue processing
        log_warning(
            "Idempotency check skipped - processed_events table may not exist",
            tenant_id=tenant_id,
            message_id=msg_id,
            error=str(e),
        )

    # 3) Upsert session
    session_row = {
        "tenant_id": tenant_id,
        "chat_id": chat_id,
        "last_message_at": now_utc().isoformat()
    }
    supabase.table("sessions").upsert(session_row, on_conflict="tenant_id,chat_id").execute()

    # 3) Store message (optional but recommended)
    supabase.table("messages").upsert({
        "tenant_id": tenant_id,
        "chat_id": chat_id,
        "message_id": msg_id,
        "from_me": bool(from_me),
        "message_type": msg_type,
        "text": text,
        "raw": payload
    }, on_conflict="tenant_id,message_id").execute()

    # 4) Collision rule: pause on owner action
    if should_pause_on_event(event, from_me):
        supabase.table("sessions").update({
            "is_paused": True,
            "pause_reason": "human_takeover",
            "last_human_at": now_utc().isoformat()
        }).eq("tenant_id", tenant_id).eq("chat_id", chat_id).execute()

        log_warning(
            "Session paused - human takeover",
            tenant_id=tenant_id,
            chat_id=chat_id,
            message_id=msg_id,
            action="paused",
        )

        # Record this event as processed
        record_processed_event(tenant_id, msg_id, event, "paused")

        return {"ok": True, "action": "paused", "chat_id": chat_id}

    # 5) Gate AI if paused
    sess = (
        supabase.table("sessions")
        .select("is_paused, last_human_at")
        .eq("tenant_id", tenant_id)
        .eq("chat_id", chat_id)
        .limit(1)
        .execute()
    )
    if sess.data and sess.data[0].get("is_paused") is True:
        log_info(
            "Message ignored - session paused",
            tenant_id=tenant_id,
            chat_id=chat_id,
            message_id=msg_id,
            action="ignored_paused",
        )

        # Record this event as processed
        record_processed_event(tenant_id, msg_id, event, "ignored_paused")

        return {"ok": True, "action": "ignored_paused", "chat_id": chat_id}

    # 6) If inbound message and not paused → generate AI reply
    if from_me is False and event == "messages.upsert":
        # Skip if no message text
        if not text or text.strip() == "":
            return {"ok": True, "action": "no_text", "chat_id": chat_id}

        # Migration path: Check if n8n orchestration is enabled
        if N8N_ENABLED:
            # Delegate to n8n workflow
            try:
                log_info(
                    "Triggering n8n workflow",
                    tenant_id=tenant_id,
                    chat_id=chat_id,
                    message_id=msg_id,
                    action="n8n_trigger",
                )
                n8n_result = await trigger_n8n_workflow("ai-reply", {
                    "tenant_id": tenant_id,
                    "instance": instance,
                    "chat_id": chat_id,
                    "message": text,
                    "message_id": msg_id,
                })
                log_info(
                    "n8n workflow triggered successfully",
                    tenant_id=tenant_id,
                    chat_id=chat_id,
                    message_id=msg_id,
                    action="n8n_triggered",
                )

                # Record this event as processed
                record_processed_event(tenant_id, msg_id, event, "n8n_triggered")

                return {
                    "ok": True,
                    "action": "n8n_triggered",
                    "chat_id": chat_id,
                    "n8n_result": n8n_result
                }
            except Exception as e:
                # Log error but don't crash webhook
                log_error(
                    "n8n workflow trigger failed",
                    tenant_id=tenant_id,
                    chat_id=chat_id,
                    message_id=msg_id,
                    action="n8n_failed",
                    error_type=type(e).__name__,
                    exc_info=True,
                )

                # Record this event as processed (even though it failed)
                record_processed_event(tenant_id, msg_id, event, "n8n_failed")

                return {
                    "ok": True,
                    "action": "n8n_failed",
                    "error": str(e),
                    "chat_id": chat_id
                }
        else:
            # Direct LLM call (MVP mode)
            llm_start_time = time.time()
            try:
                evolution_client = EvolutionClient()

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
                            "Message marked as read",
                            tenant_id=tenant_id,
                            chat_id=chat_id,
                            message_id=msg_id,
                            action="mark_read_success",
                        )
                    except Exception as e:
                        log_warning(
                            "Failed to mark message as read",
                            tenant_id=tenant_id,
                            chat_id=chat_id,
                            message_id=msg_id,
                            error=str(e),
                            action="mark_read_failed",
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
                            "Typing indicator sent",
                            tenant_id=tenant_id,
                            chat_id=chat_id,
                            action="typing_start",
                        )
                    except Exception as e:
                        log_warning(
                            "Failed to send typing indicator",
                            tenant_id=tenant_id,
                            chat_id=chat_id,
                            error=str(e),
                            action="typing_failed",
                        )

                # Get tenant's system prompt and LLM provider
                system_prompt = tenant.get("system_prompt") or DEFAULT_SYSTEM_PROMPT
                provider_name = tenant.get("llm_provider") or LLM_PROVIDER

                log_info(
                    "Generating AI reply",
                    tenant_id=tenant_id,
                    chat_id=chat_id,
                    message_id=msg_id,
                    provider=provider_name,
                    action="ai_generate_start",
                )

                # Generate AI reply
                llm_provider = get_llm_provider(provider_name)
                reply_text = await llm_provider.generate_reply(
                    message=text,
                    system_prompt=system_prompt,
                )

                llm_duration = int((time.time() - llm_start_time) * 1000)

                log_info(
                    "AI reply generated successfully",
                    tenant_id=tenant_id,
                    chat_id=chat_id,
                    message_id=msg_id,
                    provider=provider_name,
                    model=llm_provider.get_model_name(),
                    duration_ms=llm_duration,
                    reply_length=len(reply_text),
                    action="ai_generate_success",
                )

                # Send reply via Evolution API
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
                        "Adding human-like delay before sending",
                        tenant_id=tenant_id,
                        chat_id=chat_id,
                        message_id=msg_id,
                        delay_ms=delay_ms,
                        action="delay_start",
                    )
                    await asyncio.sleep(delay_seconds)

                log_info(
                    "Sending reply via Evolution API",
                    tenant_id=tenant_id,
                    chat_id=chat_id,
                    message_id=msg_id,
                    action="evolution_send_start",
                )

                # For @lid contacts, use quoted message to reply (helps bypass number validation)
                await evolution_client.send_text_message(
                    tenant_id=tenant_id,
                    chat_id=reply_to,  # Use reply_to (sender) for LID format
                    text=reply_text,
                    quoted_message_id=msg_id if is_lid_contact else None
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
                    "Reply sent successfully via Evolution API",
                    tenant_id=tenant_id,
                    chat_id=chat_id,
                    message_id=msg_id,
                    action="evolution_send_success",
                )

                # Store outbound message in database
                supabase.table("messages").insert({
                    "tenant_id": tenant_id,
                    "chat_id": chat_id,
                    "message_id": f"out-{msg_id}",
                    "from_me": True,
                    "message_type": "conversation",
                    "text": reply_text,
                    "raw": {"generated": True, "model": llm_provider.get_model_name()}
                }).execute()

                total_duration = int((time.time() - start_time) * 1000)

                log_info(
                    "AI reply pipeline completed successfully",
                    tenant_id=tenant_id,
                    chat_id=chat_id,
                    message_id=msg_id,
                    duration_ms=total_duration,
                    action="ai_replied",
                )

                # Record this event as processed
                record_processed_event(tenant_id, msg_id, event, "ai_replied")

                return {
                    "ok": True,
                    "action": "ai_replied",
                    "chat_id": chat_id,
                    "reply_preview": reply_text[:100] + "..." if len(reply_text) > 100 else reply_text
                }

            except EvolutionAPIError as e:
                # Evolution API failed - log but don't crash webhook
                log_error(
                    "Evolution API send failed",
                    tenant_id=tenant_id,
                    chat_id=chat_id,
                    message_id=msg_id,
                    action="evolution_send_failed",
                    error_type=type(e).__name__,
                    exc_info=True,
                )

                # Record this event as processed (even though send failed)
                record_processed_event(tenant_id, msg_id, event, "evolution_send_failed")

                return {
                    "ok": True,
                    "action": "evolution_send_failed",
                    "error": str(e),
                    "chat_id": chat_id
                }
            except Exception as e:
                # LLM or other error - log but don't crash webhook
                log_error(
                    "AI reply pipeline failed",
                    tenant_id=tenant_id,
                    chat_id=chat_id,
                    message_id=msg_id,
                    action="ai_failed",
                    error_type=type(e).__name__,
                    exc_info=True,
                )

                # Record this event as processed (even though AI failed)
                record_processed_event(tenant_id, msg_id, event, "ai_failed")

                return {
                    "ok": True,
                    "action": "ai_failed",
                    "error": str(e),
                    "chat_id": chat_id
                }

    return {"ok": True}
    

# ============================================================================
# LEGACY SESSION ENDPOINTS (Now secured with authentication)
# ============================================================================

@app.get("/sessions/{instance}/{chat_id:path}")
def get_session_legacy(
    instance: str,
    chat_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get session by instance name and chat_id (legacy endpoint).
    Now requires authentication.
    """
    # Verify user has access to this instance
    tenant_resp = supabase.table("tenants").select("id").eq("instance_name", instance).limit(1).execute()
    if not tenant_resp.data:
        raise HTTPException(status_code=404, detail="Unknown instance")

    tenant_id = tenant_resp.data[0]["id"]

    # Check user has access to this tenant
    user_tenants = user.get("user_tenants", [])
    if not any(ut["tenant_id"] == tenant_id for ut in user_tenants):
        raise HTTPException(status_code=403, detail="Access denied to this instance")

    sess = (
        supabase.table("sessions")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("chat_id", chat_id)
        .limit(1)
        .execute()
    )
    if not sess.data:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess.data[0]


@app.post("/sessions/{instance}/{chat_id:path}/resume")
def resume_session_legacy(
    instance: str,
    chat_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Resume a paused session (legacy endpoint).
    Now requires authentication.
    """
    tenant_resp = supabase.table("tenants").select("id").eq("instance_name", instance).limit(1).execute()
    if not tenant_resp.data:
        raise HTTPException(status_code=404, detail="Unknown instance")

    tenant_id = tenant_resp.data[0]["id"]

    # Check user has access to this tenant
    user_tenants = user.get("user_tenants", [])
    if not any(ut["tenant_id"] == tenant_id for ut in user_tenants):
        raise HTTPException(status_code=403, detail="Access denied to this instance")

    supabase.table("sessions").update({
        "is_paused": False,
        "pause_reason": None
    }).eq("tenant_id", tenant_id).eq("chat_id", chat_id).execute()

    log_info(
        "Session resumed via legacy endpoint",
        action="legacy_resume",
        tenant_id=tenant_id,
        chat_id=chat_id,
        user_id=user["id"],
    )

    return {"ok": True, "resumed": True}


@app.post("/api/evolution/send-message")
async def send_evolution_message(
    data: dict,
    user: dict = Depends(get_current_user)
):
    """
    Send a WhatsApp message via Evolution API.
    Now requires authentication and tenant access verification.

    Expected payload:
    {
        "tenant_id": 1,
        "chat_id": "5511999999999@s.whatsapp.net",
        "text": "Message text"
    }
    """
    tenant_id = data.get("tenant_id")
    chat_id = data.get("chat_id")
    text = data.get("text")

    if not tenant_id or not chat_id or not text:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: tenant_id, chat_id, text"
        )

    # Verify user has access to this tenant
    user_tenants = user.get("user_tenants", [])
    if not any(ut["tenant_id"] == tenant_id for ut in user_tenants):
        raise HTTPException(status_code=403, detail="Access denied to this tenant")

    try:
        client = EvolutionClient()
        result = await client.send_text_message(tenant_id, chat_id, text)

        log_info(
            "Message sent via API",
            action="api_send_message",
            tenant_id=tenant_id,
            chat_id=chat_id,
            user_id=user["id"],
        )

        return {"ok": True, "result": result}
    except EvolutionAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


@app.post("/cron/auto-resume")
async def cron_auto_resume(request: Request):
    """
    Auto-resume paused sessions after inactivity.
    This endpoint is designed to be called by cron schedulers (Cloud Run, Railway, etc.)

    Security: Requires CRON_SECRET header for authentication.

    Expected headers:
        X-Cron-Secret: Value matching CRON_SECRET env var
        OR
        X-Cloudscheduler-Token: Value matching CRON_SECRET env var (Google Cloud Scheduler)

    Returns:
        {
            "ok": true,
            "resumed_count": <number>,
            "cleaned_up_events": <number>
        }
    """
    from datetime import timedelta

    # Verify cron secret for security
    cron_secret = request.headers.get("X-Cron-Secret") or request.headers.get("X-Cloudscheduler-Token")

    if not cron_secret or cron_secret != CRON_SECRET:
        log_warning("Unauthorized cron request", action="cron_unauthorized")
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid or missing cron secret")

    log_info("Auto-resume cron job started", action="cron_auto_resume_start")

    try:
        from .config import RESUME_AFTER_HOURS
    except ImportError:
        RESUME_AFTER_HOURS = 2

    # Calculate cutoff time
    cutoff_time = now_utc() - timedelta(hours=RESUME_AFTER_HOURS)
    cutoff_iso = cutoff_time.isoformat()

    log_info(
        f"Resuming sessions paused before {cutoff_iso}",
        action="cron_resume_query",
        resume_after_hours=RESUME_AFTER_HOURS,
    )

    try:
        # Query sessions that should be resumed (for logging)
        sessions_to_resume = supabase.table("sessions").select(
            "id, tenant_id, chat_id, last_human_at"
        ).eq("is_paused", True).lt("last_human_at", cutoff_iso).execute()

        sessions_count = len(sessions_to_resume.data) if sessions_to_resume.data else 0

        if sessions_count > 0:
            log_info(
                f"Found {sessions_count} sessions to resume",
                action="cron_sessions_found",
                sessions_count=sessions_count,
            )

        # Update sessions to resume them
        result = supabase.table("sessions").update({
            "is_paused": False,
            "pause_reason": None,
        }).eq("is_paused", True).lt("last_human_at", cutoff_iso).execute()

        resumed_count = len(result.data) if result.data else 0

        log_info(
            f"Auto-resumed {resumed_count} sessions",
            action="cron_resume_success",
            resumed_count=resumed_count,
        )

        # Clean up old processed_events (>7 days)
        cleaned_up_events = 0
        try:
            cleanup_cutoff = (now_utc() - timedelta(days=7)).isoformat()
            cleanup_result = supabase.table("processed_events").delete().lt(
                "processed_at", cleanup_cutoff
            ).execute()
            cleaned_up_events = len(cleanup_result.data) if cleanup_result.data else 0

            if cleaned_up_events > 0:
                log_info(
                    f"Cleaned up {cleaned_up_events} old processed events",
                    action="cron_cleanup_success",
                    cleaned_up_count=cleaned_up_events,
                )
        except Exception as e:
            # Table might not exist yet, that's okay
            log_info(
                "Processed events cleanup skipped (table may not exist yet)",
                action="cron_cleanup_skipped",
            )

        return {
            "ok": True,
            "resumed_count": resumed_count,
            "cleaned_up_events": cleaned_up_events,
            "cutoff_time": cutoff_iso,
        }

    except Exception as e:
        log_error(
            "Auto-resume cron job failed",
            action="cron_auto_resume_failed",
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Auto-resume failed: {str(e)}")


# ============================================================================
# TENANT MANAGEMENT APIs
# ============================================================================

# Pydantic model for tenant creation
class TenantCreate(BaseModel):
    """Request model for creating a new tenant."""
    instance_name: str
    evo_server_url: str
    evo_api_key: Optional[str] = None
    system_prompt: Optional[str] = None
    # llm_provider is set by backend, not user-configurable


# Pydantic model for tenant updates
class TenantUpdate(BaseModel):
    """Request model for updating a tenant."""
    evo_server_url: Optional[str] = None
    evo_api_key: Optional[str] = None
    system_prompt: Optional[str] = None
    # llm_provider is not user-configurable


@app.post("/api/tenants")
async def create_tenant(
    data: TenantCreate,
    user: dict = Depends(get_current_user)
):
    """
    Create a new tenant (WhatsApp instance) for the current user.

    The authenticated user becomes the owner of the new tenant.

    Request body:
        {
            "instance_name": "my-business",
            "evo_server_url": "https://evolution-api.example.com",
            "evo_api_key": "optional-api-key",
            "system_prompt": "Optional custom AI prompt",
            "llm_provider": "openai"  // or "anthropic"
        }

    Returns:
        The created tenant object
    """
    try:
        # Check if instance_name already exists
        existing = supabase.table("tenants").select("id").eq(
            "instance_name", data.instance_name
        ).limit(1).execute()

        if existing.data:
            raise HTTPException(
                status_code=400,
                detail=f"Instance name '{data.instance_name}' already exists"
            )

        # Create tenant
        tenant_data = {
            "instance_name": data.instance_name,
            "evo_server_url": data.evo_server_url,
            "evo_api_key": data.evo_api_key,
            "system_prompt": data.system_prompt or DEFAULT_SYSTEM_PROMPT,
            "llm_provider": LLM_PROVIDER,  # Set by backend, not user-configurable
            "owner_user_id": user["id"],
        }

        tenant_result = supabase.table("tenants").insert(tenant_data).execute()

        if not tenant_result.data:
            raise HTTPException(status_code=500, detail="Failed to create tenant")

        tenant = tenant_result.data[0]

        # Create user_tenants relationship (owner role)
        supabase.table("user_tenants").insert({
            "user_id": user["id"],
            "tenant_id": tenant["id"],
            "role": "owner",
        }).execute()

        log_info(
            "Tenant created",
            action="create_tenant",
            tenant_id=tenant["id"],
            instance_name=data.instance_name,
            user_id=user["id"],
        )

        return tenant

    except HTTPException:
        raise
    except Exception as e:
        log_error(
            "Failed to create tenant",
            action="create_tenant_failed",
            instance_name=data.instance_name,
            user_id=user["id"],
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to create tenant: {str(e)}")


@app.get("/api/tenants")
def list_tenants(user: dict = Depends(get_current_user)):
    """
    List tenants the authenticated user has access to.

    Returns:
        {
            "tenants": [
                {
                    "id": 1,
                    "instance_name": "demo-instance",
                    "evo_server_url": "https://evolution-api.com",
                    "created_at": "2026-01-23T...",
                    "updated_at": "2026-01-23T..."
                },
                ...
            ]
        }

    Requires: Valid access token in Authorization header
    """
    try:
        # Get tenant IDs user has access to
        user_tenants = user.get("user_tenants", [])
        tenant_ids = [ut["tenant_id"] for ut in user_tenants]

        if not tenant_ids:
            log_info(
                "Listed tenants (user has no tenants)",
                action="list_tenants",
                user_id=user["id"],
                tenant_count=0,
            )
            return {"tenants": []}

        result = supabase.table("tenants").select(
            "id, instance_name, evo_server_url, llm_provider, created_at, updated_at"
        ).in_("id", tenant_ids).execute()

        log_info(
            "Listed tenants",
            action="list_tenants",
            user_id=user["id"],
            tenant_count=len(result.data) if result.data else 0,
        )

        return {"tenants": result.data or []}

    except Exception as e:
        log_error(
            "Failed to list tenants",
            action="list_tenants_failed",
            user_id=user.get("id"),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to list tenants: {str(e)}")


@app.get("/api/tenants/{tenant_id}")
def get_tenant(
    tenant_id: int,
    user: dict = Depends(get_current_user),
    _: None = Depends(require_tenant_access("member"))
):
    """
    Get detailed information about a specific tenant.

    Args:
        tenant_id: Tenant ID

    Returns:
        {
            "id": 1,
            "instance_name": "demo-instance",
            "evo_server_url": "https://evolution-api.com",
            "system_prompt": "You are a helpful assistant...",
            "llm_provider": "anthropic",
            "created_at": "2026-01-23T...",
            "updated_at": "2026-01-23T..."
        }

    Requires: Valid access token with member access to the tenant
    """
    try:
        result = supabase.table("tenants").select(
            "id, instance_name, evo_server_url, system_prompt, llm_provider, created_at, updated_at"
        ).eq("id", tenant_id).limit(1).execute()

        if not result.data:
            log_warning("Tenant not found", action="get_tenant_not_found", tenant_id=tenant_id)
            raise HTTPException(status_code=404, detail=f"Tenant with id {tenant_id} not found")

        log_info("Retrieved tenant details", action="get_tenant", tenant_id=tenant_id, user_id=user["id"])

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        log_error(
            "Failed to get tenant",
            action="get_tenant_failed",
            tenant_id=tenant_id,
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to get tenant: {str(e)}")


@app.put("/api/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: int,
    data: TenantUpdate,
    user: dict = Depends(get_current_user),
    _: None = Depends(require_tenant_access("owner"))
):
    """
    Update tenant configuration.

    Only owners can update tenant settings.
    llm_provider is managed by backend and not exposed to users.

    Args:
        tenant_id: Tenant ID

    Request body (all fields optional):
        {
            "evo_server_url": "https://new-evolution-api.com",
            "evo_api_key": "new-api-key",
            "system_prompt": "Updated AI prompt..."
        }

    Returns:
        The updated tenant object
    """
    try:
        # Build update dict with only provided fields
        update_data = {}
        if data.evo_server_url is not None:
            update_data["evo_server_url"] = data.evo_server_url
        if data.evo_api_key is not None:
            update_data["evo_api_key"] = data.evo_api_key
        if data.system_prompt is not None:
            update_data["system_prompt"] = data.system_prompt

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        update_data["updated_at"] = now_utc().isoformat()

        result = supabase.table("tenants").update(update_data).eq("id", tenant_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Tenant not found")

        log_info(
            "Tenant updated",
            action="update_tenant",
            tenant_id=tenant_id,
            user_id=user["id"],
            updated_fields=list(update_data.keys()),
        )

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        log_error(
            "Failed to update tenant",
            action="update_tenant_failed",
            tenant_id=tenant_id,
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to update tenant: {str(e)}")


# ============================================================================
# INSTANCE MANAGEMENT APIs
# ============================================================================

@app.get("/api/instances")
def list_instances(
    tenant_id: int,
    user: dict = Depends(get_current_user),
    _: None = Depends(require_tenant_access("member"))
):
    """
    List WhatsApp instances for a tenant.

    Query parameters:
        tenant_id: Filter by tenant ID (required)

    Returns:
        {
            "instances": [
                {
                    "id": 1,
                    "instance_name": "demo-instance",
                    "evo_server_url": "https://evolution-api.com",
                    "llm_provider": "anthropic",
                    "created_at": "2026-01-23T...",
                    "updated_at": "2026-01-23T..."
                },
                ...
            ]
        }

    Note: For MVP, each tenant has one instance_name.
    In the future, a separate instances table may be created for multi-instance support.
    """
    try:
        result = supabase.table("tenants").select(
            "id, instance_name, evo_server_url, llm_provider, created_at, updated_at"
        ).eq("id", tenant_id).execute()

        log_info(
            "Listed instances for tenant",
            action="list_instances",
            tenant_id=tenant_id,
            instance_count=len(result.data) if result.data else 0,
        )

        return {"instances": result.data or []}

    except Exception as e:
        log_error(
            "Failed to list instances",
            action="list_instances_failed",
            tenant_id=tenant_id,
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to list instances: {str(e)}")


@app.get("/api/instances/{instance_name}")
def get_instance(
    instance_name: str,
    tenant_id: int,
    user: dict = Depends(get_current_user),
    _: None = Depends(require_tenant_access("member"))
):
    """
    Get details about a specific WhatsApp instance.

    Args:
        instance_name: Instance name from Evolution API
        tenant_id: Tenant ID (query parameter)

    Returns:
        {
            "id": 1,
            "instance_name": "demo-instance",
            "evo_server_url": "https://evolution-api.com",
            "system_prompt": "You are a helpful assistant...",
            "llm_provider": "anthropic",
            "created_at": "2026-01-23T...",
            "updated_at": "2026-01-23T..."
        }
    """
    try:
        result = supabase.table("tenants").select(
            "id, instance_name, evo_server_url, system_prompt, llm_provider, created_at, updated_at"
        ).eq("instance_name", instance_name).eq("id", tenant_id).limit(1).execute()

        if not result.data:
            log_warning(
                "Instance not found",
                action="get_instance_not_found",
                instance=instance_name,
                tenant_id=tenant_id,
            )
            raise HTTPException(
                status_code=404,
                detail=f"Instance '{instance_name}' not found for tenant {tenant_id}"
            )

        log_info(
            "Retrieved instance details",
            action="get_instance",
            instance=instance_name,
            tenant_id=tenant_id,
        )

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        log_error(
            "Failed to get instance",
            action="get_instance_failed",
            instance=instance_name,
            tenant_id=tenant_id,
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to get instance: {str(e)}")


@app.post("/api/instances/{instance_name}/test-webhook")
async def test_instance_webhook(
    instance_name: str,
    tenant_id: int,
    user: dict = Depends(get_current_user),
    _: None = Depends(require_tenant_access("member"))
):
    """
    Test webhook connectivity by checking Evolution API connection status.

    Args:
        instance_name: Instance name from Evolution API
        tenant_id: Tenant ID (query parameter)

    Returns:
        Success:
            {
                "ok": true,
                "status": {
                    "state": "open",
                    "statusReason": 200,
                    ...
                }
            }

        Failure:
            {
                "ok": false,
                "error": "Error message"
            }
    """
    try:
        # Verify instance exists
        tenant_resp = supabase.table("tenants").select(
            "id, instance_name, evo_server_url, evo_api_key"
        ).eq("instance_name", instance_name).eq("id", tenant_id).limit(1).execute()

        if not tenant_resp.data:
            log_warning(
                "Instance not found for webhook test",
                action="test_webhook_not_found",
                instance=instance_name,
                tenant_id=tenant_id,
            )
            raise HTTPException(
                status_code=404,
                detail=f"Instance '{instance_name}' not found for tenant {tenant_id}"
            )

        tenant = tenant_resp.data[0]
        evo_url = tenant["evo_server_url"]
        evo_api_key = tenant.get("evo_api_key")

        log_info(
            "Testing webhook connectivity",
            action="test_webhook_start",
            instance=instance_name,
            tenant_id=tenant_id,
        )

        # Try to hit Evolution API connection status endpoint
        headers = {}
        if evo_api_key:
            headers["apikey"] = evo_api_key

        url = f"{evo_url}/instance/connectionState/{instance_name}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            status_data = response.json()

            log_info(
                "Webhook test successful",
                action="test_webhook_success",
                instance=instance_name,
                tenant_id=tenant_id,
                connection_state=status_data.get("state"),
            )

            return {
                "ok": True,
                "status": status_data,
                "message": "Successfully connected to Evolution API"
            }

    except httpx.HTTPStatusError as e:
        log_error(
            "Evolution API returned error status",
            action="test_webhook_http_error",
            instance=instance_name,
            tenant_id=tenant_id,
            status_code=e.response.status_code,
            exc_info=True,
        )
        return {
            "ok": False,
            "error": f"Evolution API returned status {e.response.status_code}: {str(e)}"
        }

    except httpx.TimeoutException:
        log_error(
            "Evolution API request timed out",
            action="test_webhook_timeout",
            instance=instance_name,
            tenant_id=tenant_id,
        )
        return {
            "ok": False,
            "error": "Connection to Evolution API timed out (10s)"
        }

    except HTTPException:
        raise

    except Exception as e:
        log_error(
            "Webhook test failed",
            action="test_webhook_failed",
            instance=instance_name,
            tenant_id=tenant_id,
            error_type=type(e).__name__,
            exc_info=True,
        )
        return {
            "ok": False,
            "error": f"Failed to connect to Evolution API: {str(e)}"
        }


# ============================================================================
# SESSION MANAGEMENT APIs
# ============================================================================

@app.get("/api/sessions")
def list_sessions(
    tenant_id: int,
    instance: str = None,
    state: str = None,  # "active", "paused"
    q: str = None,  # search chat_id
    page: int = 1,
    limit: int = 50,
    user: dict = Depends(get_current_user),
    _: None = Depends(require_tenant_access("member"))
):
    """
    List sessions with filters and pagination.

    Query parameters:
        tenant_id: Filter by tenant ID (required)
        instance: Filter by instance name (optional)
        state: Filter by state - "active" (not paused) or "paused" (optional)
        q: Search chat_id (case-insensitive substring match, optional)
        page: Page number (default: 1)
        limit: Results per page (default: 50, max: 100)

    Returns:
        {
            "sessions": [
                {
                    "id": 1,
                    "tenant_id": 1,
                    "chat_id": "5511999999999@s.whatsapp.net",
                    "is_paused": false,
                    "pause_reason": null,
                    "last_message_at": "2026-01-23T...",
                    "last_human_at": "2026-01-23T...",
                    "created_at": "2026-01-23T...",
                    "updated_at": "2026-01-23T...",
                    "tenants": {
                        "instance_name": "demo-instance"
                    }
                },
                ...
            ],
            "page": 1,
            "limit": 50,
            "total": 123
        }
    """
    try:
        # Validate limit
        if limit > 100:
            limit = 100

        # Build query
        query = supabase.table("sessions").select(
            "*, tenants!inner(instance_name)",
            count="exact"
        ).eq("tenant_id", tenant_id)

        # Filter by instance name
        if instance:
            query = query.eq("tenants.instance_name", instance)

        # Filter by state
        if state == "active":
            query = query.eq("is_paused", False)
        elif state == "paused":
            query = query.eq("is_paused", True)

        # Search chat_id
        if q:
            query = query.ilike("chat_id", f"%{q}%")

        # Pagination
        offset = (page - 1) * limit
        query = query.order("last_message_at", desc=True).range(offset, offset + limit - 1)

        result = query.execute()

        total_count = result.count if hasattr(result, 'count') else len(result.data)

        log_info(
            "Listed sessions",
            action="list_sessions",
            tenant_id=tenant_id,
            session_count=len(result.data) if result.data else 0,
            page=page,
            limit=limit,
        )

        return {
            "sessions": result.data or [],
            "page": page,
            "limit": limit,
            "total": total_count
        }

    except Exception as e:
        log_error(
            "Failed to list sessions",
            action="list_sessions_failed",
            tenant_id=tenant_id,
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@app.get("/api/sessions/{session_id}")
def get_session_by_id(
    session_id: int,
    tenant_id: int,
    user: dict = Depends(get_current_user),
    _: None = Depends(require_tenant_access("member"))
):
    """
    Get detailed information about a specific session.

    Args:
        session_id: Session ID
        tenant_id: Tenant ID (query parameter for authorization)

    Returns:
        {
            "id": 1,
            "tenant_id": 1,
            "chat_id": "5511999999999@s.whatsapp.net",
            "is_paused": false,
            "pause_reason": null,
            "last_message_at": "2026-01-23T...",
            "last_human_at": "2026-01-23T...",
            "created_at": "2026-01-23T...",
            "updated_at": "2026-01-23T..."
        }
    """
    try:
        result = supabase.table("sessions").select("*").eq(
            "id", session_id
        ).eq("tenant_id", tenant_id).limit(1).execute()

        if not result.data:
            log_warning(
                "Session not found",
                action="get_session_not_found",
                session_id=session_id,
                tenant_id=tenant_id,
            )
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found for tenant {tenant_id}"
            )

        log_info(
            "Retrieved session details",
            action="get_session",
            session_id=session_id,
            tenant_id=tenant_id,
        )

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        log_error(
            "Failed to get session",
            action="get_session_failed",
            session_id=session_id,
            tenant_id=tenant_id,
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to get session: {str(e)}")


class SessionActionRequest(BaseModel):
    """Request body for session pause/resume actions."""
    tenant_id: int


@app.post("/api/sessions/{session_id}/pause")
def pause_session(
    session_id: int,
    data: SessionActionRequest,
    user: dict = Depends(get_current_user),
):
    """
    Manually pause a session.

    Args:
        session_id: Session ID
        data.tenant_id: Tenant ID (in request body)

    Returns:
        {
            "ok": true,
            "paused": true,
            "session_id": 1
        }
    """
    tenant_id = data.tenant_id

    # Verify user has access to this tenant
    user_tenants = user.get("user_tenants", [])
    if not any(ut["tenant_id"] == tenant_id for ut in user_tenants):
        raise HTTPException(status_code=403, detail="Access denied to this tenant")

    try:
        # Verify session exists and belongs to tenant
        session_check = supabase.table("sessions").select("id, chat_id").eq(
            "id", session_id
        ).eq("tenant_id", tenant_id).limit(1).execute()

        if not session_check.data:
            log_warning(
                "Session not found for pause",
                action="pause_session_not_found",
                session_id=session_id,
                tenant_id=tenant_id,
            )
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found for tenant {tenant_id}"
            )

        chat_id = session_check.data[0]["chat_id"]

        # Update session to paused
        result = supabase.table("sessions").update({
            "is_paused": True,
            "pause_reason": "manual_pause",
            "updated_at": now_utc().isoformat(),
        }).eq("id", session_id).eq("tenant_id", tenant_id).execute()

        log_info(
            "Session manually paused",
            action="pause_session",
            session_id=session_id,
            tenant_id=tenant_id,
            chat_id=chat_id,
        )

        return {
            "ok": True,
            "paused": True,
            "session_id": session_id
        }

    except HTTPException:
        raise
    except Exception as e:
        log_error(
            "Failed to pause session",
            action="pause_session_failed",
            session_id=session_id,
            tenant_id=tenant_id,
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to pause session: {str(e)}")


@app.post("/api/sessions/{session_id}/resume")
def resume_session_by_id(
    session_id: int,
    data: SessionActionRequest,
    user: dict = Depends(get_current_user),
):
    """
    Manually resume a paused session.

    Args:
        session_id: Session ID
        data.tenant_id: Tenant ID (in request body)

    Returns:
        {
            "ok": true,
            "resumed": true,
            "session_id": 1
        }
    """
    tenant_id = data.tenant_id

    # Verify user has access to this tenant
    user_tenants = user.get("user_tenants", [])
    if not any(ut["tenant_id"] == tenant_id for ut in user_tenants):
        raise HTTPException(status_code=403, detail="Access denied to this tenant")

    try:
        # Verify session exists and belongs to tenant
        session_check = supabase.table("sessions").select("id, chat_id").eq(
            "id", session_id
        ).eq("tenant_id", tenant_id).limit(1).execute()

        if not session_check.data:
            log_warning(
                "Session not found for resume",
                action="resume_session_not_found",
                session_id=session_id,
                tenant_id=tenant_id,
            )
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found for tenant {tenant_id}"
            )

        chat_id = session_check.data[0]["chat_id"]

        # Update session to resumed
        result = supabase.table("sessions").update({
            "is_paused": False,
            "pause_reason": None,
            "updated_at": now_utc().isoformat(),
        }).eq("id", session_id).eq("tenant_id", tenant_id).execute()

        log_info(
            "Session manually resumed",
            action="resume_session",
            session_id=session_id,
            tenant_id=tenant_id,
            chat_id=chat_id,
        )

        return {
            "ok": True,
            "resumed": True,
            "session_id": session_id
        }

    except HTTPException:
        raise
    except Exception as e:
        log_error(
            "Failed to resume session",
            action="resume_session_failed",
            session_id=session_id,
            tenant_id=tenant_id,
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to resume session: {str(e)}")


# ============================================================================
# EVENT/MESSAGE QUERY APIs
# ============================================================================

@app.get("/api/events")
def list_events(
    tenant_id: int,
    instance: str = None,
    session_id: int = None,
    chat_id: str = None,
    limit: int = 100,
    user: dict = Depends(get_current_user),
    _: None = Depends(require_tenant_access("member"))
):
    """
    Get event timeline (messages).

    Query parameters:
        tenant_id: Filter by tenant ID (required)
        instance: Filter by instance name (optional)
        session_id: Filter by session ID (optional)
        chat_id: Filter by chat_id directly (optional)
        limit: Maximum number of events to return (default: 100, max: 500)

    Returns:
        {
            "events": [
                {
                    "id": 1,
                    "tenant_id": 1,
                    "chat_id": "5511999999999@s.whatsapp.net",
                    "message_id": "ABC123",
                    "from_me": false,
                    "message_type": "conversation",
                    "text": "Hello",
                    "created_at": "2026-01-23T..."
                },
                ...
            ],
            "limit": 100
        }
    """
    try:
        # Validate limit
        if limit > 500:
            limit = 500

        # Build query
        query = supabase.table("messages").select(
            "id, tenant_id, chat_id, message_id, from_me, message_type, text, created_at"
        ).eq("tenant_id", tenant_id)

        # If session_id provided, get chat_id from session
        if session_id:
            session = supabase.table("sessions").select("chat_id").eq(
                "id", session_id
            ).eq("tenant_id", tenant_id).limit(1).execute()

            if session.data:
                chat_id = session.data[0]["chat_id"]
                query = query.eq("chat_id", chat_id)
            else:
                # Session not found, return empty
                return {"events": [], "limit": limit}

        # Filter by chat_id directly
        elif chat_id:
            query = query.eq("chat_id", chat_id)

        # Order by created_at descending (most recent first)
        query = query.order("created_at", desc=True).limit(limit)

        result = query.execute()

        log_info(
            "Listed events",
            action="list_events",
            tenant_id=tenant_id,
            event_count=len(result.data) if result.data else 0,
            session_id=session_id,
            chat_id=chat_id,
        )

        return {
            "events": result.data or [],
            "limit": limit
        }

    except Exception as e:
        log_error(
            "Failed to list events",
            action="list_events_failed",
            tenant_id=tenant_id,
            session_id=session_id,
            chat_id=chat_id,
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to list events: {str(e)}")


# ============================================================================
# WEBSOCKET MANAGEMENT APIs
# ============================================================================

@app.get("/api/websocket/status")
async def get_websocket_status():
    """
    Get WebSocket connection status.

    Returns:
        {
            "enabled": true,
            "mode": "global",
            "connections": {
                "global": {"connected": true, "server_url": "https://..."},
                ...
            }
        }
    """
    if not WEBSOCKET_ENABLED:
        return {
            "enabled": False,
            "mode": None,
            "message": "WebSocket mode is disabled. Set WEBSOCKET_ENABLED=true to enable.",
            "connections": {}
        }

    if not websocket_manager:
        return {
            "enabled": True,
            "mode": WEBSOCKET_MODE,
            "message": "WebSocket manager not initialized",
            "connections": {}
        }

    connections_status = {}
    for name, ws in websocket_manager.connections.items():
        connections_status[name] = {
            "connected": ws.connected,
            "server_url": ws.server_url,
            "instance_name": ws.instance_name,
        }

    return {
        "enabled": True,
        "mode": WEBSOCKET_MODE,
        "server_url": EVOLUTION_SERVER_URL,
        "connections": connections_status
    }


@app.post("/api/websocket/connect")
async def connect_websocket(data: dict):
    """
    Connect to Evolution API via WebSocket.

    For global mode (receives all instances):
        {
            "mode": "global"
        }

    For instance mode (specific instance):
        {
            "mode": "instance",
            "instance_name": "test-02",
            "server_url": "https://evolution-api.example.com",  # optional, uses tenant config
            "api_key": "xxx"  # optional
        }

    Returns:
        {
            "ok": true,
            "connected": true,
            "mode": "global"
        }
    """
    global websocket_manager

    if not WEBSOCKET_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="WebSocket mode is disabled. Set WEBSOCKET_ENABLED=true to enable."
        )

    mode = data.get("mode", "global")

    if websocket_manager is None:
        websocket_manager = EvolutionWebSocketManager()
        websocket_manager.set_message_handler(handle_websocket_message)
        websocket_manager.set_connection_handler(handle_websocket_connection_update)

    try:
        if mode == "global":
            server_url = data.get("server_url") or EVOLUTION_SERVER_URL
            api_key = data.get("api_key") or EVOLUTION_API_KEY

            if not server_url:
                raise HTTPException(
                    status_code=400,
                    detail="server_url required for global mode (or set EVOLUTION_SERVER_URL)"
                )

            await websocket_manager.connect_global(
                server_url=server_url,
                api_key=api_key or None,
            )

            log_info(
                "WebSocket connected via API",
                mode="global",
                server_url=server_url,
                action="websocket_api_connect",
            )

            return {
                "ok": True,
                "connected": True,
                "mode": "global",
                "server_url": server_url
            }

        elif mode == "instance":
            instance_name = data.get("instance_name")
            if not instance_name:
                raise HTTPException(
                    status_code=400,
                    detail="instance_name required for instance mode"
                )

            # Get server URL from tenant config if not provided
            server_url = data.get("server_url")
            api_key = data.get("api_key")

            if not server_url:
                # Look up tenant config
                tenant_resp = supabase.table("tenants").select(
                    "evo_server_url, evo_api_key"
                ).eq("instance_name", instance_name).limit(1).execute()

                if tenant_resp.data:
                    server_url = tenant_resp.data[0].get("evo_server_url")
                    api_key = api_key or tenant_resp.data[0].get("evo_api_key")

            if not server_url:
                raise HTTPException(
                    status_code=400,
                    detail=f"server_url required (not found in tenant config for {instance_name})"
                )

            await websocket_manager.connect_instance(
                server_url=server_url,
                instance_name=instance_name,
                api_key=api_key or None,
            )

            log_info(
                "WebSocket connected via API",
                mode="instance",
                instance=instance_name,
                server_url=server_url,
                action="websocket_api_connect",
            )

            return {
                "ok": True,
                "connected": True,
                "mode": "instance",
                "instance_name": instance_name,
                "server_url": server_url
            }

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode: {mode}. Use 'global' or 'instance'."
            )

    except HTTPException:
        raise
    except Exception as e:
        log_error(
            f"WebSocket connect failed: {e}",
            mode=mode,
            action="websocket_api_connect_failed",
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect WebSocket: {str(e)}"
        )


# ============================================================================
# WHATSAPP CONNECTION APIs (QR Code Flow)
# ============================================================================

def extract_qr_code(qr_result: dict) -> Optional[str]:
    """
    Extract QR code from Evolution API response.

    Evolution API may return QR code data in different formats:
    - "base64": raw base64 or with data URL prefix
    - "qrcode": alternative property name
    - "code": another alternative

    This function handles all cases and strips any data URL prefix
    since the frontend adds it.
    """
    # Try different property names Evolution API might use
    qr_data = (
        qr_result.get("base64") or
        qr_result.get("qrcode") or
        qr_result.get("code") or
        qr_result.get("qr")
    )

    if not qr_data:
        # Log for debugging
        log_warning(
            "QR code not found in Evolution API response",
            action="qr_extract_missing",
            available_keys=list(qr_result.keys()) if qr_result else [],
        )
        return None

    # Strip data URL prefix if present (Evolution API may include it)
    # Frontend adds "data:image/png;base64," so we need raw base64 only
    if isinstance(qr_data, str) and qr_data.startswith("data:"):
        # Split at comma to get just the base64 part
        if "," in qr_data:
            qr_data = qr_data.split(",", 1)[1]

    return qr_data


class WhatsAppConnectRequest(BaseModel):
    """Request model for connecting a new WhatsApp."""
    instance_name: str
    system_prompt: Optional[str] = None


@app.post("/api/whatsapp/connect")
async def whatsapp_connect(
    data: WhatsAppConnectRequest,
    user: dict = Depends(get_current_user)
):
    """
    Create a new WhatsApp connection via QR code.

    This creates an instance in Evolution API and returns the QR code for scanning.
    After scanning, the instance will be linked to the user's phone.

    Request body:
        {
            "instance_name": "my-business",
            "system_prompt": "Optional custom AI prompt"
        }

    Returns:
        {
            "ok": true,
            "instance_name": "my-business",
            "qr_code": "base64_encoded_qr_image",
            "pairing_code": "ABC-DEF-GHI" (alternative to QR)
        }
    """
    if not EVOLUTION_SERVER_URL:
        raise HTTPException(
            status_code=503,
            detail="WhatsApp connection service not configured. Contact administrator."
        )

    try:
        # Check if instance_name already exists
        existing = supabase.table("tenants").select("id").eq(
            "instance_name", data.instance_name
        ).limit(1).execute()

        if existing.data:
            raise HTTPException(
                status_code=400,
                detail=f"Connection name '{data.instance_name}' already exists. Choose a different name."
            )

        # Create Evolution client with global config
        evolution_client = EvolutionClient(
            global_server_url=EVOLUTION_SERVER_URL,
            global_api_key=EVOLUTION_API_KEY
        )

        # Build webhook URL for this instance
        webhook_base = os.getenv("WEBHOOK_BASE_URL", "")
        webhook_url = f"{webhook_base}/webhooks/evolution" if webhook_base else None

        log_info(
            "Creating WhatsApp instance",
            action="whatsapp_connect_start",
            instance_name=data.instance_name,
            user_id=user["id"],
            webhook_url=webhook_url,
        )

        # Create instance in Evolution API
        create_result = await evolution_client.create_instance(
            instance_name=data.instance_name,
            webhook_url=webhook_url
        )

        log_info(
            "WhatsApp instance created, fetching QR code",
            action="whatsapp_instance_created",
            instance_name=data.instance_name,
        )

        # Get QR code
        qr_result = await evolution_client.get_qr_code(data.instance_name)

        # Create tenant record
        tenant_data = {
            "instance_name": data.instance_name,
            "evo_server_url": EVOLUTION_SERVER_URL,
            "evo_api_key": EVOLUTION_API_KEY,
            "system_prompt": data.system_prompt or DEFAULT_SYSTEM_PROMPT,
            "llm_provider": LLM_PROVIDER,
            "owner_user_id": user["id"],
        }

        tenant_result = supabase.table("tenants").insert(tenant_data).execute()

        if not tenant_result.data:
            # Rollback: delete instance from Evolution API
            try:
                await evolution_client.delete_instance(data.instance_name)
            except:
                pass
            raise HTTPException(status_code=500, detail="Failed to create connection record")

        tenant = tenant_result.data[0]

        # Create user_tenants relationship (owner role)
        supabase.table("user_tenants").insert({
            "user_id": user["id"],
            "tenant_id": tenant["id"],
            "role": "owner",
        }).execute()

        log_info(
            "WhatsApp connection created successfully",
            action="whatsapp_connect_success",
            instance_name=data.instance_name,
            tenant_id=tenant["id"],
            user_id=user["id"],
        )

        return {
            "ok": True,
            "instance_name": data.instance_name,
            "tenant_id": tenant["id"],
            "qr_code": extract_qr_code(qr_result),
            "pairing_code": qr_result.get("pairingCode"),
            "message": "Scan the QR code with WhatsApp to connect"
        }

    except HTTPException:
        raise
    except EvolutionAPIError as e:
        log_error(
            "Evolution API error during WhatsApp connect",
            action="whatsapp_connect_evolution_error",
            instance_name=data.instance_name,
            error=str(e),
        )
        raise HTTPException(status_code=502, detail=f"WhatsApp service error: {str(e)}")
    except Exception as e:
        log_error(
            "Failed to create WhatsApp connection",
            action="whatsapp_connect_failed",
            instance_name=data.instance_name,
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to create connection: {str(e)}")


@app.get("/api/whatsapp/qr-code/{instance_name}")
async def get_whatsapp_qr_code(
    instance_name: str,
    user: dict = Depends(get_current_user)
):
    """
    Get or refresh QR code for a WhatsApp instance.

    Use this endpoint to refresh the QR code if it expires before scanning.

    Returns:
        {
            "ok": true,
            "instance_name": "my-business",
            "qr_code": "base64_encoded_qr_image",
            "pairing_code": "ABC-DEF-GHI"
        }
    """
    if not EVOLUTION_SERVER_URL:
        raise HTTPException(
            status_code=503,
            detail="WhatsApp connection service not configured"
        )

    try:
        # Verify user has access to this instance
        tenant_resp = supabase.table("tenants").select("id").eq(
            "instance_name", instance_name
        ).limit(1).execute()

        if not tenant_resp.data:
            raise HTTPException(status_code=404, detail="Connection not found")

        tenant_id = tenant_resp.data[0]["id"]

        # Check user has access
        access_check = supabase.table("user_tenants").select("id").eq(
            "user_id", user["id"]
        ).eq("tenant_id", tenant_id).limit(1).execute()

        if not access_check.data:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get QR code from Evolution API
        evolution_client = EvolutionClient(
            global_server_url=EVOLUTION_SERVER_URL,
            global_api_key=EVOLUTION_API_KEY
        )

        qr_result = await evolution_client.get_qr_code(instance_name)

        return {
            "ok": True,
            "instance_name": instance_name,
            "qr_code": extract_qr_code(qr_result),
            "pairing_code": qr_result.get("pairingCode"),
        }

    except HTTPException:
        raise
    except EvolutionAPIError as e:
        raise HTTPException(status_code=502, detail=f"WhatsApp service error: {str(e)}")
    except Exception as e:
        log_error(
            "Failed to get QR code",
            action="get_qr_code_failed",
            instance_name=instance_name,
            error_type=type(e).__name__,
        )
        raise HTTPException(status_code=500, detail=f"Failed to get QR code: {str(e)}")


@app.get("/api/whatsapp/connection-status/{instance_name}")
async def get_whatsapp_connection_status(
    instance_name: str,
    user: dict = Depends(get_current_user)
):
    """
    Check WhatsApp connection status for an instance.

    Use this endpoint to poll for connection status after QR code scan.

    Returns:
        {
            "ok": true,
            "instance_name": "my-business",
            "connected": true,
            "state": "open"
        }

    States:
        - "open": Connected and ready
        - "connecting": Waiting for connection
        - "close": Disconnected
    """
    if not EVOLUTION_SERVER_URL:
        raise HTTPException(
            status_code=503,
            detail="WhatsApp connection service not configured"
        )

    try:
        # Verify user has access to this instance
        tenant_resp = supabase.table("tenants").select("id").eq(
            "instance_name", instance_name
        ).limit(1).execute()

        if not tenant_resp.data:
            raise HTTPException(status_code=404, detail="Connection not found")

        tenant_id = tenant_resp.data[0]["id"]

        # Check user has access
        access_check = supabase.table("user_tenants").select("id").eq(
            "user_id", user["id"]
        ).eq("tenant_id", tenant_id).limit(1).execute()

        if not access_check.data:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get connection state from Evolution API
        evolution_client = EvolutionClient(
            global_server_url=EVOLUTION_SERVER_URL,
            global_api_key=EVOLUTION_API_KEY
        )

        status_result = await evolution_client.get_connection_state(instance_name)

        state = status_result.get("state", status_result.get("instance", {}).get("state", "unknown"))
        connected = state == "open"

        return {
            "ok": True,
            "instance_name": instance_name,
            "connected": connected,
            "state": state,
        }

    except HTTPException:
        raise
    except EvolutionAPIError as e:
        raise HTTPException(status_code=502, detail=f"WhatsApp service error: {str(e)}")
    except Exception as e:
        log_error(
            "Failed to get connection status",
            action="get_connection_status_failed",
            instance_name=instance_name,
            error_type=type(e).__name__,
        )
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@app.delete("/api/whatsapp/instance/{instance_name}")
async def delete_whatsapp_instance(
    instance_name: str,
    user: dict = Depends(get_current_user)
):
    """
    Delete a WhatsApp connection.

    This removes the instance from Evolution API and deletes the local record.
    Only the owner can delete a connection.

    Returns:
        {
            "ok": true,
            "deleted": true
        }
    """
    if not EVOLUTION_SERVER_URL:
        raise HTTPException(
            status_code=503,
            detail="WhatsApp connection service not configured"
        )

    try:
        # Verify user is owner of this instance
        tenant_resp = supabase.table("tenants").select("id, owner_user_id").eq(
            "instance_name", instance_name
        ).limit(1).execute()

        if not tenant_resp.data:
            raise HTTPException(status_code=404, detail="Connection not found")

        tenant = tenant_resp.data[0]

        if tenant.get("owner_user_id") != user["id"]:
            # Check if user has owner role
            access_check = supabase.table("user_tenants").select("role").eq(
                "user_id", user["id"]
            ).eq("tenant_id", tenant["id"]).limit(1).execute()

            if not access_check.data or access_check.data[0].get("role") != "owner":
                raise HTTPException(status_code=403, detail="Only owners can delete connections")

        # Delete from Evolution API
        evolution_client = EvolutionClient(
            global_server_url=EVOLUTION_SERVER_URL,
            global_api_key=EVOLUTION_API_KEY
        )

        try:
            await evolution_client.delete_instance(instance_name)
        except EvolutionAPIError as e:
            log_warning(
                "Evolution API delete failed (continuing with local delete)",
                action="delete_instance_evolution_warning",
                instance_name=instance_name,
                error=str(e),
            )

        # Delete user_tenants associations
        supabase.table("user_tenants").delete().eq("tenant_id", tenant["id"]).execute()

        # Delete tenant record
        supabase.table("tenants").delete().eq("id", tenant["id"]).execute()

        log_info(
            "WhatsApp connection deleted",
            action="whatsapp_delete_success",
            instance_name=instance_name,
            tenant_id=tenant["id"],
            user_id=user["id"],
        )

        return {
            "ok": True,
            "deleted": True,
            "instance_name": instance_name
        }

    except HTTPException:
        raise
    except Exception as e:
        log_error(
            "Failed to delete WhatsApp connection",
            action="delete_instance_failed",
            instance_name=instance_name,
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to delete connection: {str(e)}")


@app.post("/api/websocket/disconnect")
async def disconnect_websocket(data: dict = None):
    """
    Disconnect WebSocket connections.

    To disconnect all:
        {}

    To disconnect specific instance:
        {
            "instance_name": "test-02"
        }

    Returns:
        {
            "ok": true,
            "disconnected": ["global"] or ["test-02"]
        }
    """
    global websocket_manager

    if not websocket_manager:
        return {
            "ok": True,
            "disconnected": [],
            "message": "No active WebSocket connections"
        }

    data = data or {}
    instance_name = data.get("instance_name")

    try:
        if instance_name:
            # Disconnect specific instance
            if instance_name in websocket_manager.connections:
                await websocket_manager.disconnect_instance(instance_name)
                log_info(
                    "WebSocket disconnected via API",
                    instance=instance_name,
                    action="websocket_api_disconnect",
                )
                return {
                    "ok": True,
                    "disconnected": [instance_name]
                }
            else:
                return {
                    "ok": True,
                    "disconnected": [],
                    "message": f"No connection found for instance: {instance_name}"
                }
        else:
            # Disconnect all
            disconnected = list(websocket_manager.connections.keys())
            await websocket_manager.disconnect_all()
            log_info(
                "All WebSocket connections disconnected via API",
                disconnected=disconnected,
                action="websocket_api_disconnect_all",
            )
            return {
                "ok": True,
                "disconnected": disconnected
            }

    except Exception as e:
        log_error(
            f"WebSocket disconnect failed: {e}",
            instance=instance_name,
            action="websocket_api_disconnect_failed",
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disconnect WebSocket: {str(e)}"
        )


# ============================================================================
# GDPR & DATA PRIVACY ENDPOINTS
# ============================================================================

@app.get("/api/privacy/export")
async def export_user_data(
    user: dict = Depends(get_current_user)
):
    """
    GDPR Data Subject Access Request (DSAR) - Export all user data.

    Returns all personal data associated with the authenticated user:
    - User profile
    - Tenant memberships
    - All messages from user's tenants (anonymized phone numbers)
    - Session data

    This complies with GDPR Article 15 (Right of Access).

    Returns:
        JSON file containing all user data
    """
    from datetime import datetime

    try:
        user_id = user["id"]

        # Get user tenants
        user_tenants = user.get("user_tenants", [])
        tenant_ids = [ut["tenant_id"] for ut in user_tenants]

        export_data = {
            "export_date": datetime.utcnow().isoformat(),
            "data_controller": "HybridFlow",
            "user_profile": {
                "id": user.get("id"),
                "email": user.get("email"),
                "display_name": user.get("display_name"),
                "created_at": user.get("created_at"),
            },
            "tenant_memberships": user_tenants,
            "tenants": [],
            "sessions": [],
            "messages": [],
        }

        if tenant_ids:
            # Get tenant details
            tenants_result = supabase.table("tenants").select(
                "id, instance_name, created_at, updated_at"
            ).in_("id", tenant_ids).execute()
            export_data["tenants"] = tenants_result.data or []

            # Get sessions (limited to last 90 days for performance)
            from datetime import timedelta
            cutoff_date = (datetime.utcnow() - timedelta(days=90)).isoformat()

            sessions_result = supabase.table("sessions").select(
                "id, chat_id, is_paused, pause_reason, last_message_at, created_at"
            ).in_("tenant_id", tenant_ids).gte("created_at", cutoff_date).execute()

            # Anonymize chat_id (phone numbers) in sessions
            sessions = sessions_result.data or []
            for session in sessions:
                if session.get("chat_id"):
                    # Hash the phone number for privacy
                    import hashlib
                    chat_id = session["chat_id"]
                    session["chat_id_hash"] = hashlib.sha256(chat_id.encode()).hexdigest()[:16]
                    # Show only last 4 digits
                    phone_part = chat_id.split("@")[0] if "@" in chat_id else chat_id
                    session["chat_id_masked"] = f"***{phone_part[-4:]}" if len(phone_part) > 4 else "****"
                    del session["chat_id"]
            export_data["sessions"] = sessions

            # Get messages (limited to last 30 days, exclude raw payloads)
            cutoff_messages = (datetime.utcnow() - timedelta(days=30)).isoformat()

            messages_result = supabase.table("messages").select(
                "id, chat_id, from_me, message_type, text, created_at"
            ).in_("tenant_id", tenant_ids).gte("created_at", cutoff_messages).limit(1000).execute()

            # Anonymize chat_id in messages
            messages = messages_result.data or []
            for message in messages:
                if message.get("chat_id"):
                    import hashlib
                    chat_id = message["chat_id"]
                    message["chat_id_hash"] = hashlib.sha256(chat_id.encode()).hexdigest()[:16]
                    phone_part = chat_id.split("@")[0] if "@" in chat_id else chat_id
                    message["chat_id_masked"] = f"***{phone_part[-4:]}" if len(phone_part) > 4 else "****"
                    del message["chat_id"]
            export_data["messages"] = messages

        log_info(
            "GDPR data export completed",
            action="gdpr_export",
            user_id=user_id,
            tenant_count=len(tenant_ids),
            session_count=len(export_data["sessions"]),
            message_count=len(export_data["messages"]),
        )

        return export_data

    except Exception as e:
        log_error(
            "GDPR data export failed",
            action="gdpr_export_failed",
            user_id=user.get("id"),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@app.delete("/api/privacy/data")
async def delete_user_data(
    confirm: bool = False,
    user: dict = Depends(get_current_user)
):
    """
    GDPR Right to Erasure - Delete all user data.

    This permanently deletes:
    - All messages from tenants owned by this user
    - All sessions from tenants owned by this user
    - Tenant records owned by this user
    - User's tenant memberships

    This complies with GDPR Article 17 (Right to Erasure / "Right to be Forgotten").

    Query Parameters:
        confirm: Must be true to proceed with deletion

    Returns:
        Summary of deleted data

    WARNING: This action is irreversible!
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must pass confirm=true to delete data. This action is irreversible."
        )

    try:
        user_id = user["id"]
        deleted_summary = {
            "messages_deleted": 0,
            "sessions_deleted": 0,
            "tenants_deleted": 0,
            "memberships_deleted": 0,
        }

        # Get tenants owned by this user
        owned_tenants = supabase.table("tenants").select("id").eq(
            "owner_user_id", user_id
        ).execute()

        owned_tenant_ids = [t["id"] for t in (owned_tenants.data or [])]

        if owned_tenant_ids:
            # Delete messages from owned tenants
            messages_result = supabase.table("messages").delete().in_(
                "tenant_id", owned_tenant_ids
            ).execute()
            deleted_summary["messages_deleted"] = len(messages_result.data or [])

            # Delete sessions from owned tenants
            sessions_result = supabase.table("sessions").delete().in_(
                "tenant_id", owned_tenant_ids
            ).execute()
            deleted_summary["sessions_deleted"] = len(sessions_result.data or [])

            # Delete processed_events from owned tenants
            try:
                supabase.table("processed_events").delete().in_(
                    "tenant_id", owned_tenant_ids
                ).execute()
            except:
                pass  # Table may not exist

            # Delete tenant memberships for owned tenants
            supabase.table("user_tenants").delete().in_(
                "tenant_id", owned_tenant_ids
            ).execute()

            # Delete owned tenants
            tenants_result = supabase.table("tenants").delete().in_(
                "id", owned_tenant_ids
            ).execute()
            deleted_summary["tenants_deleted"] = len(tenants_result.data or [])

        # Delete user's own memberships (for tenants they don't own)
        memberships_result = supabase.table("user_tenants").delete().eq(
            "user_id", user_id
        ).execute()
        deleted_summary["memberships_deleted"] = len(memberships_result.data or [])

        log_info(
            "GDPR data deletion completed",
            action="gdpr_delete",
            user_id=user_id,
            **deleted_summary,
        )

        return {
            "ok": True,
            "message": "All your data has been permanently deleted",
            "deleted": deleted_summary,
        }

    except Exception as e:
        log_error(
            "GDPR data deletion failed",
            action="gdpr_delete_failed",
            user_id=user.get("id"),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@app.delete("/api/privacy/messages/{chat_id:path}")
async def delete_chat_messages(
    chat_id: str,
    tenant_id: int,
    confirm: bool = False,
    user: dict = Depends(get_current_user),
    _: None = Depends(require_tenant_access("owner"))
):
    """
    Delete all messages for a specific chat/contact.

    This allows deletion of a specific contact's conversation data
    without affecting other data.

    Useful for:
    - Honoring deletion requests from WhatsApp contacts
    - Removing sensitive conversations

    Query Parameters:
        tenant_id: Tenant ID
        confirm: Must be true to proceed

    Returns:
        Count of deleted messages
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must pass confirm=true to delete messages"
        )

    try:
        # Delete messages for this chat
        messages_result = supabase.table("messages").delete().eq(
            "tenant_id", tenant_id
        ).eq("chat_id", chat_id).execute()

        deleted_count = len(messages_result.data or [])

        # Delete session for this chat
        supabase.table("sessions").delete().eq(
            "tenant_id", tenant_id
        ).eq("chat_id", chat_id).execute()

        log_info(
            "Chat messages deleted",
            action="delete_chat_messages",
            tenant_id=tenant_id,
            user_id=user["id"],
            messages_deleted=deleted_count,
        )

        return {
            "ok": True,
            "messages_deleted": deleted_count,
            "session_deleted": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        log_error(
            "Chat messages deletion failed",
            action="delete_chat_messages_failed",
            tenant_id=tenant_id,
            error_type=type(e).__name__,
        )
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@app.post("/api/privacy/cleanup-old-data")
async def cleanup_old_data(
    request: Request,
    days_to_keep: int = 90
):
    """
    Clean up old messages and processed events.

    This endpoint is designed to be called by cron jobs for automatic
    data retention compliance.

    Security: Requires CRON_SECRET header.

    Query Parameters:
        days_to_keep: Number of days of data to retain (default: 90)

    Returns:
        Count of deleted records
    """
    from datetime import timedelta

    # Verify cron secret
    cron_secret = request.headers.get("X-Cron-Secret") or request.headers.get("X-Cloudscheduler-Token")

    if not cron_secret or cron_secret != CRON_SECRET:
        log_warning("Unauthorized cleanup request", action="cleanup_unauthorized")
        raise HTTPException(status_code=403, detail="Unauthorized")

    if days_to_keep < 7:
        raise HTTPException(status_code=400, detail="days_to_keep must be at least 7")

    try:
        cutoff_date = (now_utc() - timedelta(days=days_to_keep)).isoformat()

        deleted_summary = {
            "messages_deleted": 0,
            "processed_events_deleted": 0,
        }

        # Delete old messages
        messages_result = supabase.table("messages").delete().lt(
            "created_at", cutoff_date
        ).execute()
        deleted_summary["messages_deleted"] = len(messages_result.data or [])

        # Delete old processed events
        try:
            events_result = supabase.table("processed_events").delete().lt(
                "processed_at", cutoff_date
            ).execute()
            deleted_summary["processed_events_deleted"] = len(events_result.data or [])
        except:
            pass  # Table may not exist

        log_info(
            "Data cleanup completed",
            action="data_cleanup",
            days_to_keep=days_to_keep,
            cutoff_date=cutoff_date,
            **deleted_summary,
        )

        return {
            "ok": True,
            "cutoff_date": cutoff_date,
            "deleted": deleted_summary,
        }

    except HTTPException:
        raise
    except Exception as e:
        log_error(
            "Data cleanup failed",
            action="data_cleanup_failed",
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")
