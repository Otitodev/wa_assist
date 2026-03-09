"""
Media processing pipeline: Cloudflare R2 storage + OpenAI Whisper transcription.

Responsibilities:
- Upload raw media bytes to R2 and return a permanent public URL
- Transcribe audio files via OpenAI Whisper
- Determine the right action for each media type (vision / transcribe / fallback)
"""

import asyncio
import base64
import io
import mimetypes
import uuid
from typing import Optional

import boto3
from botocore.config import Config

from ..config import (
    CF_R2_ACCOUNT_ID, CF_R2_ACCESS_KEY_ID, CF_R2_SECRET_ACCESS_KEY,
    CF_R2_BUCKET_NAME, CF_R2_PUBLIC_URL, OPENAI_API_KEY,
)
from ..logger import log_info, log_warning, log_error

# Message types handled by each processing path
IMAGE_TYPES = {"imageMessage"}
AUDIO_TYPES = {"audioMessage", "pttMessage"}  # ptt = push-to-talk (voice note)
FALLBACK_TYPES = {"videoMessage", "documentMessage", "stickerMessage"}

FALLBACK_MESSAGES = {
    "videoMessage": "I received your video, but I can only process text and images right now. Could you describe what you need?",
    "documentMessage": "I received your document, but I can only process text and images right now. Could you summarise what you'd like help with?",
    "stickerMessage": "Nice sticker! 😄 How can I help you today?",
}

DEFAULT_FALLBACK = "I received your message, but I can only process text and images right now. Please type your question and I'll be happy to help!"


def _get_r2_client():
    """Create a boto3 S3 client configured for Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=f"https://{CF_R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=CF_R2_ACCESS_KEY_ID,
        aws_secret_access_key=CF_R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


async def upload_to_r2(data: bytes, content_type: str, folder: str = "media") -> str:
    """
    Upload bytes to Cloudflare R2 and return the public URL.

    Args:
        data: Raw file bytes
        content_type: MIME type (e.g. 'image/jpeg', 'audio/ogg')
        folder: R2 key prefix (default 'media')

    Returns:
        Public URL string

    Raises:
        Exception if upload fails
    """
    ext = mimetypes.guess_extension(content_type) or ""
    key = f"{folder}/{uuid.uuid4().hex}{ext}"

    def _upload():
        client = _get_r2_client()
        client.put_object(
            Bucket=CF_R2_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    # Run blocking boto3 call in thread pool
    await asyncio.get_event_loop().run_in_executor(None, _upload)

    base_url = CF_R2_PUBLIC_URL.rstrip("/")
    public_url = f"{base_url}/{key}"
    log_info("Media uploaded to R2", key=key, url=public_url, action="r2_upload_success")
    return public_url


async def transcribe_audio(audio_bytes: bytes, mimetype: str) -> Optional[str]:
    """
    Transcribe audio bytes using OpenAI Whisper.

    Args:
        audio_bytes: Raw audio file bytes
        mimetype: MIME type of the audio (e.g. 'audio/ogg', 'audio/mpeg')

    Returns:
        Transcription text, or None if transcription fails
    """
    if not OPENAI_API_KEY:
        log_warning("OPENAI_API_KEY not set — cannot transcribe audio", action="whisper_no_key")
        return None

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        # Map mimetype to a filename extension Whisper accepts
        ext_map = {
            "audio/ogg": "audio.ogg",
            "audio/mpeg": "audio.mp3",
            "audio/mp4": "audio.mp4",
            "audio/wav": "audio.wav",
            "audio/webm": "audio.webm",
        }
        filename = ext_map.get(mimetype, "audio.ogg")

        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename

        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        text = transcript.text.strip()
        log_info("Audio transcribed", length=len(text), action="whisper_success")
        return text if text else None

    except Exception as e:
        log_error("Audio transcription failed", error=str(e), action="whisper_failed")
        return None


def decode_base64_media(base64_data: str) -> bytes:
    """Decode a base64 string (with or without data URL prefix) to bytes."""
    if "," in base64_data:
        base64_data = base64_data.split(",", 1)[1]
    return base64.b64decode(base64_data)


def get_fallback_message(msg_type: str) -> str:
    """Return a polite fallback reply for unsupported media types."""
    return FALLBACK_MESSAGES.get(msg_type, DEFAULT_FALLBACK)
