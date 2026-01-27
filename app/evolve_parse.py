from typing import Any, Optional

def extract_chat_id(payload: dict) -> Optional[str]:
    data = payload.get("data") or {}
    key = data.get("key") or {}
    return key.get("remoteJid")

def extract_message_id(payload: dict) -> Optional[str]:
    data = payload.get("data") or {}
    key = data.get("key") or {}
    return key.get("id")

def extract_from_me(payload: dict) -> Optional[bool]:
    data = payload.get("data") or {}
    key = data.get("key") or {}
    return key.get("fromMe")

def extract_text(payload: dict) -> Optional[str]:
    data = payload.get("data") or {}
    msg = data.get("message") or {}

    # common types (you can expand later)
    if "conversation" in msg:
        return msg.get("conversation")
    if "extendedTextMessage" in msg and isinstance(msg["extendedTextMessage"], dict):
        return msg["extendedTextMessage"].get("text")
    return None

def extract_message_type(payload: dict) -> Optional[str]:
    data = payload.get("data") or {}
    return data.get("messageType")


def extract_push_name(payload: dict) -> Optional[str]:
    """Extract sender's display name."""
    data = payload.get("data") or {}
    return data.get("pushName")


def extract_timestamp(payload: dict) -> Optional[int]:
    """Extract message timestamp (Unix epoch)."""
    data = payload.get("data") or {}
    return data.get("messageTimestamp")


def extract_sender(payload: dict) -> Optional[str]:
    """Extract sender WhatsApp ID from top-level field."""
    return payload.get("sender")
