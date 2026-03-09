"""
Shared media message handler.

Called from both the webhook handler (app/main.py) and the WebSocket handler
(app/services/websocket_handler.py) when a non-text inbound message arrives.

Pipeline:
  imageMessage  → download → R2 → Claude Vision → text reply
  audioMessage / pttMessage → download → R2 → Whisper → LLM → text reply
  other media   → polite fallback reply
"""

import asyncio
import random
import time
from typing import Optional

from ..db import supabase
from ..logger import log_info, log_warning, log_error
from ..config import (
    MEDIA_PROCESSING_ENABLED, CF_R2_ACCOUNT_ID, CF_R2_PUBLIC_URL,
    DEFAULT_SYSTEM_PROMPT, LLM_PROVIDER,
    MESSAGE_DELAY_ENABLED, MESSAGE_DELAY_MIN_MS, MESSAGE_DELAY_MAX_MS,
    TYPING_INDICATOR_ENABLED, CONTEXT_MESSAGES,
)
from ..services.evolution_client import EvolutionClient, EvolutionAPIError
from ..services.llm_client import get_llm_provider
from ..services.media_processor import (
    IMAGE_TYPES, AUDIO_TYPES, FALLBACK_TYPES,
    upload_to_r2, transcribe_audio, get_fallback_message,
)
from ..evolve_parse import extract_media_mimetype, extract_media_caption


def _r2_configured() -> bool:
    return bool(CF_R2_ACCOUNT_ID and CF_R2_PUBLIC_URL)


async def process_media_message(
    *,
    tenant_id: int,
    chat_id: str,
    msg_id: str,
    msg_type: str,
    payload: dict,
    tenant: dict,
    is_lid_contact: bool,
    event: str,
    source: str = "webhook",  # "webhook" or "websocket"
) -> dict:
    """
    Process an inbound non-text WhatsApp message and send an AI reply.

    Returns a dict with 'action' key describing what was done.
    Never raises — all errors are caught and logged.
    """
    if not MEDIA_PROCESSING_ENABLED:
        return {"ok": True, "action": "media_disabled", "chat_id": chat_id}

    system_prompt = tenant.get("system_prompt") or DEFAULT_SYSTEM_PROMPT
    provider_name = tenant.get("llm_provider") or LLM_PROVIDER
    data = payload.get("data", {})

    # Fallback types: polite reply, no AI processing
    if msg_type in FALLBACK_TYPES:
        fallback_text = get_fallback_message(msg_type)
        await _send_reply(
            tenant_id=tenant_id,
            chat_id=chat_id,
            msg_id=msg_id,
            reply_text=fallback_text,
            is_lid_contact=is_lid_contact,
            tenant=tenant,
            source=source,
            action_tag="media_fallback",
            msg_type=msg_type,
        )
        _record_event(tenant_id, msg_id, event, "media_fallback")
        return {"ok": True, "action": "media_fallback", "chat_id": chat_id}

    if msg_type not in IMAGE_TYPES and msg_type not in AUDIO_TYPES:
        return {"ok": True, "action": "no_text_ignored", "chat_id": chat_id}

    start = time.time()

    try:
        evolution_client = EvolutionClient()

        # --- Download media from Evolution API ---
        log_info(
            "Downloading media from Evolution API",
            tenant_id=tenant_id, chat_id=chat_id, msg_type=msg_type,
            action=f"{source}_media_download_start",
        )
        media_bytes = await evolution_client.download_media(
            tenant_id=tenant_id,
            message_data=data,
        )

        if not media_bytes:
            log_warning(
                "Media download returned empty — sending fallback",
                tenant_id=tenant_id, chat_id=chat_id,
                action=f"{source}_media_download_empty",
            )
            fallback_text = get_fallback_message(msg_type)
            await _send_reply(
                tenant_id=tenant_id, chat_id=chat_id, msg_id=msg_id,
                reply_text=fallback_text, is_lid_contact=is_lid_contact,
                tenant=tenant, source=source, action_tag="media_download_fallback",
                msg_type=msg_type,
            )
            _record_event(tenant_id, msg_id, event, "media_download_failed")
            return {"ok": True, "action": "media_download_failed", "chat_id": chat_id}

        mimetype = extract_media_mimetype(payload) or (
            "image/jpeg" if msg_type in IMAGE_TYPES else "audio/ogg"
        )

        # --- Upload to R2 ---
        r2_url: Optional[str] = None
        if _r2_configured():
            try:
                folder = "images" if msg_type in IMAGE_TYPES else "audio"
                r2_url = await upload_to_r2(media_bytes, mimetype, folder)
                log_info(
                    "Media stored in R2",
                    tenant_id=tenant_id, url=r2_url,
                    action=f"{source}_r2_upload_success",
                )
            except Exception as e:
                log_warning(
                    "R2 upload failed — will use base64 fallback for vision",
                    tenant_id=tenant_id, error=str(e),
                    action=f"{source}_r2_upload_failed",
                )
        else:
            log_warning(
                "R2 not configured (CF_R2_ACCOUNT_ID/CF_R2_PUBLIC_URL missing) — skipping R2 upload",
                action=f"{source}_r2_not_configured",
            )

        # --- Generate AI reply ---
        llm_provider = get_llm_provider(provider_name)
        reply_text: Optional[str] = None

        # Fetch conversation history for context
        _history = supabase.table("messages").select(
            "from_me, text"
        ).eq("tenant_id", tenant_id).eq("chat_id", chat_id).not_.is_(
            "text", "null"
        ).order("created_at", desc=True).limit(CONTEXT_MESSAGES).execute()
        context = [
            {"role": "assistant" if m["from_me"] else "user", "content": m["text"]}
            for m in reversed(_history.data or [])
            if m.get("text")
        ]

        if msg_type in IMAGE_TYPES:
            caption = extract_media_caption(payload) or ""
            prompt_text = caption if caption else "Please respond to this image the customer sent."

            # Use base64 if R2 upload failed
            import base64 as _base64
            image_b64 = _base64.b64encode(media_bytes).decode() if not r2_url else None

            log_info(
                "Calling LLM with image (vision)",
                tenant_id=tenant_id, chat_id=chat_id,
                has_url=bool(r2_url), has_b64=bool(image_b64),
                action=f"{source}_vision_start",
            )
            reply_text = await llm_provider.generate_reply(
                message=prompt_text,
                system_prompt=system_prompt,
                context=context,
                image_url=r2_url,
                image_base64=image_b64,
                image_mimetype=mimetype,
            )

        elif msg_type in AUDIO_TYPES:
            log_info(
                "Transcribing audio with Whisper",
                tenant_id=tenant_id, chat_id=chat_id,
                action=f"{source}_whisper_start",
            )
            transcript = await transcribe_audio(media_bytes, mimetype)
            if transcript:
                log_info(
                    "Audio transcribed — generating LLM reply",
                    tenant_id=tenant_id, chat_id=chat_id,
                    transcript_length=len(transcript),
                    action=f"{source}_whisper_success",
                )
                reply_text = await llm_provider.generate_reply(
                    message=transcript,
                    system_prompt=system_prompt,
                    context=context,
                )
            else:
                reply_text = "I received your voice message but had trouble understanding it. Could you type your message instead?"

        if not reply_text:
            reply_text = get_fallback_message(msg_type)

        duration_ms = int((time.time() - start) * 1000)
        log_info(
            "Media reply generated",
            tenant_id=tenant_id, chat_id=chat_id, msg_type=msg_type,
            duration_ms=duration_ms, action=f"{source}_media_reply_generated",
        )

        # --- Send reply ---
        await _send_reply(
            tenant_id=tenant_id, chat_id=chat_id, msg_id=msg_id,
            reply_text=reply_text, is_lid_contact=is_lid_contact,
            tenant=tenant, source=source, action_tag="media_replied",
            msg_type=msg_type,
        )
        _record_event(tenant_id, msg_id, event, "media_replied")
        return {"ok": True, "action": "media_replied", "chat_id": chat_id}

    except Exception as e:
        log_error(
            "Media processing pipeline failed",
            tenant_id=tenant_id, chat_id=chat_id, msg_type=msg_type,
            error=str(e), action=f"{source}_media_failed",
        )
        # Graceful degradation: still send a fallback so customer isn't ghosted
        try:
            fallback_text = get_fallback_message(msg_type)
            await _send_reply(
                tenant_id=tenant_id, chat_id=chat_id, msg_id=msg_id,
                reply_text=fallback_text, is_lid_contact=is_lid_contact,
                tenant=tenant, source=source, action_tag="media_error_fallback",
                msg_type=msg_type,
            )
        except Exception:
            pass
        _record_event(tenant_id, msg_id, event, "media_failed")
        return {"ok": True, "action": "media_failed", "chat_id": chat_id}


async def _send_reply(
    *,
    tenant_id: int,
    chat_id: str,
    msg_id: str,
    reply_text: str,
    is_lid_contact: bool,
    tenant: dict,
    source: str,
    action_tag: str,
    msg_type: str,
) -> None:
    """Send text reply via Evolution API with delay + typing indicator, then store in DB."""
    evolution_client = EvolutionClient()

    # Typing indicator
    if TYPING_INDICATOR_ENABLED and not is_lid_contact:
        try:
            await evolution_client.send_presence(
                tenant_id=tenant_id, chat_id=chat_id,
                presence="composing", delay=3000,
            )
        except Exception:
            pass

    # Human-like delay
    if MESSAGE_DELAY_ENABLED:
        delay_ms = random.randint(MESSAGE_DELAY_MIN_MS, MESSAGE_DELAY_MAX_MS)
        if TYPING_INDICATOR_ENABLED and not is_lid_contact:
            try:
                await evolution_client.send_presence(
                    tenant_id=tenant_id, chat_id=chat_id,
                    presence="composing", delay=delay_ms,
                )
            except Exception:
                pass
        await asyncio.sleep(delay_ms / 1000.0)

    await evolution_client.send_text_message(
        tenant_id=tenant_id,
        chat_id=chat_id,
        text=reply_text,
        quoted_message_id=msg_id if is_lid_contact else None,
    )

    if TYPING_INDICATOR_ENABLED and not is_lid_contact:
        try:
            await evolution_client.send_presence(
                tenant_id=tenant_id, chat_id=chat_id, presence="paused",
            )
        except Exception:
            pass

    # Store outbound message
    try:
        supabase.table("messages").insert({
            "tenant_id": tenant_id,
            "chat_id": chat_id,
            "message_id": f"media-out-{msg_id}",
            "from_me": True,
            "message_type": "conversation",
            "text": reply_text,
            "raw": {"generated": True, "source": source, "in_response_to": msg_type},
        }).execute()
    except Exception:
        pass  # Non-critical

    log_info(
        "Media reply sent",
        tenant_id=tenant_id, chat_id=chat_id,
        action=f"{source}_{action_tag}",
    )


def _record_event(tenant_id: int, msg_id: str, event: str, action: str) -> None:
    try:
        supabase.table("processed_events").insert({
            "tenant_id": tenant_id,
            "message_id": msg_id,
            "event_type": event,
            "action_taken": action,
        }).execute()
    except Exception:
        pass
