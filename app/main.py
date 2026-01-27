from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import time
from .db import supabase
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
    WEBSOCKET_ENABLED, WEBSOCKET_MODE, EVOLUTION_SERVER_URL, EVOLUTION_API_KEY
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

    # Parse JSON body with error handling
    try:
        body = await req.body()
        if not body:
            log_warning("Webhook received empty body")
            raise HTTPException(status_code=400, detail="Empty request body")

        import json
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        log_error(
            "Webhook received invalid JSON",
            error=str(e),
            body_preview=body[:200].decode('utf-8', errors='replace') if body else "empty"
        )
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    event = payload.get("event")
    instance = payload.get("instance")

    # Log webhook received
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
                # Mark message as read before processing (show blue checkmarks)
                try:
                    evolution_client = EvolutionClient()
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
                log_info(
                    "Sending reply via Evolution API",
                    tenant_id=tenant_id,
                    chat_id=chat_id,
                    message_id=msg_id,
                    action="evolution_send_start",
                )

                evolution_client = EvolutionClient()
                await evolution_client.send_text_message(
                    tenant_id=tenant_id,
                    chat_id=reply_to,  # Use reply_to (sender) for LID format
                    text=reply_text
                )

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
    

@app.get("/sessions/{instance}/{chat_id:path}")
def get_session(instance: str, chat_id: str):
    tenant_resp = supabase.table("tenants").select("id").eq("instance_name", instance).limit(1).execute()
    if not tenant_resp.data:
        raise HTTPException(status_code=404, detail="Unknown instance")

    tenant_id = tenant_resp.data[0]["id"]
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
def resume_session(instance: str, chat_id: str):
    tenant_resp = supabase.table("tenants").select("id").eq("instance_name", instance).limit(1).execute()
    if not tenant_resp.data:
        raise HTTPException(status_code=404, detail="Unknown instance")

    tenant_id = tenant_resp.data[0]["id"]

    supabase.table("sessions").update({
        "is_paused": False,
        "pause_reason": None
    }).eq("tenant_id", tenant_id).eq("chat_id", chat_id).execute()

    return {"ok": True, "resumed": True}


@app.post("/api/evolution/send-message")
async def send_evolution_message(data: dict):
    """
    Send a WhatsApp message via Evolution API.
    This endpoint can be called by n8n workflows or directly by FastAPI.

    Expected payload:
    {
        "tenant_id": 1,
        "chat_id": "5511999999999@s.whatsapp.net",
        "text": "Message text"
    }
    """
    from .services.evolution_client import EvolutionClient, EvolutionAPIError

    tenant_id = data.get("tenant_id")
    chat_id = data.get("chat_id")
    text = data.get("text")

    if not tenant_id or not chat_id or not text:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: tenant_id, chat_id, text"
        )

    try:
        client = EvolutionClient()
        result = await client.send_text_message(tenant_id, chat_id, text)
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

@app.get("/api/tenants")
def list_tenants():
    """
    List all tenants.

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

    Note: In production, add authentication and filter by user_id.
    """
    try:
        result = supabase.table("tenants").select(
            "id, instance_name, evo_server_url, llm_provider, created_at, updated_at"
        ).execute()

        log_info(
            "Listed tenants",
            action="list_tenants",
            tenant_count=len(result.data) if result.data else 0,
        )

        return {"tenants": result.data or []}

    except Exception as e:
        log_error(
            "Failed to list tenants",
            action="list_tenants_failed",
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to list tenants: {str(e)}")


@app.get("/api/tenants/{tenant_id}")
def get_tenant(tenant_id: int):
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
    """
    try:
        result = supabase.table("tenants").select(
            "id, instance_name, evo_server_url, system_prompt, llm_provider, created_at, updated_at"
        ).eq("id", tenant_id).limit(1).execute()

        if not result.data:
            log_warning("Tenant not found", action="get_tenant_not_found", tenant_id=tenant_id)
            raise HTTPException(status_code=404, detail=f"Tenant with id {tenant_id} not found")

        log_info("Retrieved tenant details", action="get_tenant", tenant_id=tenant_id)

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


# ============================================================================
# INSTANCE MANAGEMENT APIs
# ============================================================================

@app.get("/api/instances")
def list_instances(tenant_id: int):
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
def get_instance(instance_name: str, tenant_id: int):
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
async def test_instance_webhook(instance_name: str, tenant_id: int):
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
    limit: int = 50
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
def get_session_by_id(session_id: int, tenant_id: int):
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


@app.post("/api/sessions/{session_id}/pause")
def pause_session(session_id: int, tenant_id: int):
    """
    Manually pause a session.

    Args:
        session_id: Session ID
        tenant_id: Tenant ID (query parameter for authorization)

    Returns:
        {
            "ok": true,
            "paused": true,
            "session_id": 1
        }
    """
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
def resume_session_by_id(session_id: int, tenant_id: int):
    """
    Manually resume a paused session.

    Args:
        session_id: Session ID
        tenant_id: Tenant ID (query parameter for authorization)

    Returns:
        {
            "ok": true,
            "resumed": true,
            "session_id": 1
        }
    """
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
    limit: int = 100
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
