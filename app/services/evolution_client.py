"""
Evolution API client for sending WhatsApp messages.
This client can be used directly by FastAPI or called via API endpoints by n8n.
"""
import httpx
from typing import Optional, Dict, Any
from ..db import supabase


class EvolutionAPIError(Exception):
    """Raised when Evolution API returns an error"""
    pass


class EvolutionClient:
    """Client for interacting with Evolution API"""

    def __init__(self, timeout: int = 60, global_server_url: str = None, global_api_key: str = None):
        self.timeout = timeout
        self.global_server_url = global_server_url
        self.global_api_key = global_api_key

    async def _get_tenant_config(self, tenant_id: int) -> Dict[str, Any]:
        """Fetch tenant Evolution API configuration from database"""
        result = supabase.table("tenants").select(
            "evo_server_url, evo_api_key, instance_name"
        ).eq("id", tenant_id).limit(1).execute()

        if not result.data:
            raise ValueError(f"Tenant {tenant_id} not found")

        return result.data[0]

    async def send_text_message(
        self,
        tenant_id: int,
        chat_id: str,
        text: str,
        instance_name: Optional[str] = None,
        quoted_message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a text message via Evolution API.

        Args:
            tenant_id: Tenant ID for configuration lookup
            chat_id: WhatsApp chat ID (e.g., "5511999999999@s.whatsapp.net")
            text: Message text to send
            instance_name: Override instance name (uses tenant's if not provided)
            quoted_message_id: Optional message ID to reply/quote (helps with @lid contacts)

        Returns:
            Evolution API response dict

        Raises:
            EvolutionAPIError: If Evolution API returns error
            httpx.HTTPError: If HTTP request fails
        """
        # Get tenant config
        tenant_config = await self._get_tenant_config(tenant_id)
        evo_url = tenant_config["evo_server_url"]
        evo_api_key = tenant_config.get("evo_api_key")
        instance = instance_name or tenant_config["instance_name"]

        if not evo_url:
            raise ValueError(f"Tenant {tenant_id} missing evo_server_url")

        # Prepare request
        endpoint = f"{evo_url}/message/sendText/{instance}"
        headers = {
            "Content-Type": "application/json",
        }

        if evo_api_key:
            headers["apikey"] = evo_api_key

        # Handle different chat_id formats
        # - Phone format: "5511999999999@s.whatsapp.net" -> use just the number
        # - LID format: "170166654656630@lid" -> use full ID with @lid suffix
        # - Plain number: "5511999999999" -> use as-is
        if chat_id.endswith("@lid"):
            # LID format - use the full ID including @lid
            number = chat_id
        elif "@" in chat_id:
            # Phone format - extract just the number
            number = chat_id.split("@")[0]
        else:
            number = chat_id

        # Evolution API v2 sendText payload format (flat structure)
        payload = {
            "number": number,
            "text": text
        }

        # Add quoted message for reply (helps with @lid contacts)
        if quoted_message_id:
            payload["quoted"] = {
                "key": {
                    "remoteJid": chat_id,
                    "fromMe": False,
                    "id": quoted_message_id
                }
            }

        # Send request - use short timeout since Evolution API may not respond
        # even when message sends successfully (known issue)
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()

                result = response.json()

                # Check if Evolution API returned an error in response body
                if isinstance(result, dict) and result.get("error"):
                    raise EvolutionAPIError(f"Evolution API error: {result.get('message', 'Unknown error')}")

                return result

            except httpx.HTTPStatusError as e:
                error_detail = "Unknown error"
                try:
                    error_body = e.response.json()
                    error_detail = error_body.get("message", str(error_body))
                except:
                    error_detail = e.response.text

                raise EvolutionAPIError(
                    f"Evolution API HTTP {e.response.status_code}: {error_detail}"
                ) from e

            except httpx.TimeoutException:
                # Evolution API often doesn't respond even when message sends successfully
                # Return success assuming message was sent (fire-and-forget)
                return {
                    "status": "sent_no_confirmation",
                    "message": "Message likely sent (Evolution API did not respond in time)",
                    "number": number,
                    "instance": instance
                }

            except httpx.RequestError as e:
                raise EvolutionAPIError(
                    f"Evolution API request failed: {str(e)}"
                ) from e

    async def get_instance_status(
        self,
        tenant_id: int,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get WhatsApp instance connection status.

        Args:
            tenant_id: Tenant ID for configuration lookup
            instance_name: Override instance name (uses tenant's if not provided)

        Returns:
            Instance status dict
        """
        tenant_config = await self._get_tenant_config(tenant_id)
        evo_url = tenant_config["evo_server_url"]
        evo_api_key = tenant_config.get("evo_api_key")
        instance = instance_name or tenant_config["instance_name"]

        endpoint = f"{evo_url}/instance/connectionState/{instance}"
        headers = {}

        if evo_api_key:
            headers["apikey"] = evo_api_key

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(endpoint, headers=headers)
                response.raise_for_status()
                return response.json()

            except httpx.HTTPError as e:
                raise EvolutionAPIError(
                    f"Failed to get instance status: {str(e)}"
                ) from e

    async def mark_as_read(
        self,
        tenant_id: int,
        chat_id: str,
        message_id: str,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mark a message as read (send read receipt / blue checkmarks).

        Args:
            tenant_id: Tenant ID for configuration lookup
            chat_id: WhatsApp chat ID (remoteJid)
            message_id: Message ID to mark as read
            instance_name: Override instance name (uses tenant's if not provided)

        Returns:
            Evolution API response dict
        """
        tenant_config = await self._get_tenant_config(tenant_id)
        evo_url = tenant_config["evo_server_url"]
        evo_api_key = tenant_config.get("evo_api_key")
        instance = instance_name or tenant_config["instance_name"]

        endpoint = f"{evo_url}/chat/markMessageAsRead/{instance}"
        headers = {
            "Content-Type": "application/json",
        }

        if evo_api_key:
            headers["apikey"] = evo_api_key

        payload = {
            "readMessages": [
                {
                    "remoteJid": chat_id,
                    "fromMe": False,
                    "id": message_id
                }
            ]
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                # Don't raise error for mark as read - it's not critical
                error_detail = "Unknown error"
                try:
                    error_body = e.response.json()
                    error_detail = error_body.get("message", str(error_body))
                except:
                    error_detail = e.response.text
                return {
                    "status": "failed",
                    "error": f"HTTP {e.response.status_code}: {error_detail}"
                }

            except httpx.TimeoutException:
                return {
                    "status": "timeout",
                    "message": "Mark as read request timed out"
                }

            except httpx.RequestError as e:
                return {
                    "status": "failed",
                    "error": str(e)
                }

    async def send_presence(
        self,
        tenant_id: int,
        chat_id: str,
        presence: str = "composing",
        delay: int = 1000,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send presence status (typing indicator).

        Args:
            tenant_id: Tenant ID for configuration lookup
            chat_id: WhatsApp chat ID (remoteJid)
            presence: Presence type - "composing", "recording", "available", "unavailable", "paused"
            delay: Delay in milliseconds for the presence
            instance_name: Override instance name (uses tenant's if not provided)

        Returns:
            Evolution API response dict
        """
        tenant_config = await self._get_tenant_config(tenant_id)
        evo_url = tenant_config["evo_server_url"]
        evo_api_key = tenant_config.get("evo_api_key")
        instance = instance_name or tenant_config["instance_name"]

        endpoint = f"{evo_url}/chat/sendPresence/{instance}"
        headers = {
            "Content-Type": "application/json",
        }

        if evo_api_key:
            headers["apikey"] = evo_api_key

        # Handle different chat_id formats (same as send_text_message)
        if chat_id.endswith("@lid"):
            number = chat_id
        elif "@" in chat_id:
            number = chat_id.split("@")[0]
        else:
            number = chat_id

        payload = {
            "number": number,
            "delay": delay,
            "presence": presence
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                # Don't raise error for presence - it's not critical
                error_detail = "Unknown error"
                try:
                    error_body = e.response.json()
                    error_detail = error_body.get("message", str(error_body))
                except:
                    error_detail = e.response.text
                return {
                    "status": "failed",
                    "error": f"HTTP {e.response.status_code}: {error_detail}"
                }

            except httpx.TimeoutException:
                return {
                    "status": "timeout",
                    "message": "Send presence request timed out"
                }

            except httpx.RequestError as e:
                return {
                    "status": "failed",
                    "error": str(e)
                }

    async def create_instance(
        self,
        instance_name: str,
        webhook_url: str = None
    ) -> Dict[str, Any]:
        """
        Create a new WhatsApp instance in Evolution API.

        Args:
            instance_name: Name for the new instance
            webhook_url: URL to receive webhook events

        Returns:
            Evolution API response with instance details
        """
        if not self.global_server_url:
            raise ValueError("Global Evolution server URL not configured")

        endpoint = f"{self.global_server_url}/instance/create"
        headers = {
            "Content-Type": "application/json",
        }

        if self.global_api_key:
            headers["apikey"] = self.global_api_key

        payload = {
            "instanceName": instance_name,
            "integration": "WHATSAPP-BAILEYS",
            "qrcode": True,
        }

        # Add webhook configuration if provided
        if webhook_url:
            payload["webhook"] = {
                "url": webhook_url,
                "byEvents": False,
                "base64": False,
                "events": [
                    "MESSAGES_UPSERT",
                    "CONNECTION_UPDATE",
                    "MESSAGES_UPDATE"
                ]
            }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                error_detail = "Unknown error"
                try:
                    error_body = e.response.json()
                    error_detail = error_body.get("message", str(error_body))
                except:
                    error_detail = e.response.text
                raise EvolutionAPIError(
                    f"Failed to create instance: HTTP {e.response.status_code}: {error_detail}"
                ) from e

            except httpx.RequestError as e:
                raise EvolutionAPIError(
                    f"Failed to create instance: {str(e)}"
                ) from e

    async def get_qr_code(
        self,
        instance_name: str
    ) -> Dict[str, Any]:
        """
        Get QR code for connecting WhatsApp.

        Args:
            instance_name: Instance name to get QR for

        Returns:
            Dict with base64 QR code image or pairingCode
        """
        if not self.global_server_url:
            raise ValueError("Global Evolution server URL not configured")

        endpoint = f"{self.global_server_url}/instance/connect/{instance_name}"
        headers = {}

        if self.global_api_key:
            headers["apikey"] = self.global_api_key

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(endpoint, headers=headers)
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                error_detail = "Unknown error"
                try:
                    error_body = e.response.json()
                    error_detail = error_body.get("message", str(error_body))
                except:
                    error_detail = e.response.text
                raise EvolutionAPIError(
                    f"Failed to get QR code: HTTP {e.response.status_code}: {error_detail}"
                ) from e

            except httpx.RequestError as e:
                raise EvolutionAPIError(
                    f"Failed to get QR code: {str(e)}"
                ) from e

    async def get_connection_state(
        self,
        instance_name: str
    ) -> Dict[str, Any]:
        """
        Get connection state for an instance.

        Args:
            instance_name: Instance name to check

        Returns:
            Dict with connection state (open, close, connecting)
        """
        if not self.global_server_url:
            raise ValueError("Global Evolution server URL not configured")

        endpoint = f"{self.global_server_url}/instance/connectionState/{instance_name}"
        headers = {}

        if self.global_api_key:
            headers["apikey"] = self.global_api_key

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(endpoint, headers=headers)
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                error_detail = "Unknown error"
                try:
                    error_body = e.response.json()
                    error_detail = error_body.get("message", str(error_body))
                except:
                    error_detail = e.response.text
                raise EvolutionAPIError(
                    f"Failed to get connection state: HTTP {e.response.status_code}: {error_detail}"
                ) from e

            except httpx.RequestError as e:
                raise EvolutionAPIError(
                    f"Failed to get connection state: {str(e)}"
                ) from e

    async def delete_instance(
        self,
        instance_name: str
    ) -> Dict[str, Any]:
        """
        Delete an instance from Evolution API.

        Args:
            instance_name: Instance name to delete

        Returns:
            Evolution API response
        """
        if not self.global_server_url:
            raise ValueError("Global Evolution server URL not configured")

        endpoint = f"{self.global_server_url}/instance/delete/{instance_name}"
        headers = {}

        if self.global_api_key:
            headers["apikey"] = self.global_api_key

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.delete(endpoint, headers=headers)
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                error_detail = "Unknown error"
                try:
                    error_body = e.response.json()
                    error_detail = error_body.get("message", str(error_body))
                except:
                    error_detail = e.response.text
                raise EvolutionAPIError(
                    f"Failed to delete instance: HTTP {e.response.status_code}: {error_detail}"
                ) from e

            except httpx.RequestError as e:
                raise EvolutionAPIError(
                    f"Failed to delete instance: {str(e)}"
                ) from e
