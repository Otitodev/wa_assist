"""
Evolution API WebSocket Client

Connects to Evolution API via Socket.IO for real-time event handling.
This is an alternative to webhooks that provides:
- Lower latency
- Works behind firewalls/NAT
- Automatic reconnection

Usage:
    from app.services.evolution_websocket import EvolutionWebSocket

    ws = EvolutionWebSocket(
        server_url="https://evolution-api.example.com",
        instance_name="test-02",  # or None for global mode
        on_message=handle_message_callback
    )
    await ws.connect()
"""

import asyncio
import socketio
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timezone

from ..logger import log_info, log_error, log_warning


class EvolutionWebSocket:
    """Socket.IO client for Evolution API real-time events."""

    def __init__(
        self,
        server_url: str,
        instance_name: Optional[str] = None,
        api_key: Optional[str] = None,
        on_message: Optional[Callable] = None,
        on_connection_update: Optional[Callable] = None,
        on_any_event: Optional[Callable] = None,
        reconnect: bool = True,
        reconnect_delay: int = 5,
    ):
        """
        Initialize Evolution WebSocket client.

        Args:
            server_url: Evolution API server URL (e.g., "https://evolution-api.example.com")
            instance_name: Instance name for traditional mode, None for global mode
            api_key: API key for authentication (if required)
            on_message: Callback for messages.upsert events
            on_connection_update: Callback for connection.update events
            on_any_event: Callback for any event (for debugging/logging)
            reconnect: Whether to auto-reconnect on disconnect
            reconnect_delay: Seconds to wait before reconnecting
        """
        self.server_url = server_url.rstrip('/')
        self.instance_name = instance_name
        self.api_key = api_key
        self.on_message = on_message
        self.on_connection_update = on_connection_update
        self.on_any_event = on_any_event
        self.reconnect = reconnect
        self.reconnect_delay = reconnect_delay

        self._connected = False
        self._should_reconnect = True

        # Create Socket.IO client with WebSocket transport
        self.sio = socketio.AsyncClient(
            reconnection=reconnect,
            reconnection_delay=reconnect_delay,
            reconnection_delay_max=30,
            logger=False,
            engineio_logger=False,
        )

        # Register event handlers
        self._register_handlers()

    def _get_connection_url(self) -> str:
        """Get the WebSocket connection URL."""
        if self.instance_name:
            # Traditional mode - connect to specific instance
            return f"{self.server_url}/{self.instance_name}"
        else:
            # Global mode - receive events from all instances
            return self.server_url

    def _register_handlers(self):
        """Register Socket.IO event handlers."""

        @self.sio.event
        async def connect():
            self._connected = True
            log_info(
                "WebSocket connected to Evolution API",
                server_url=self.server_url,
                instance=self.instance_name or "global",
                action="websocket_connected",
            )

        @self.sio.event
        async def disconnect():
            self._connected = False
            log_warning(
                "WebSocket disconnected from Evolution API",
                server_url=self.server_url,
                instance=self.instance_name or "global",
                action="websocket_disconnected",
            )

        @self.sio.event
        async def connect_error(data):
            log_error(
                "WebSocket connection error",
                server_url=self.server_url,
                instance=self.instance_name or "global",
                error=str(data),
                action="websocket_error",
            )

        # Message events
        @self.sio.on("messages.upsert")
        async def on_messages_upsert(data):
            await self._handle_event("messages.upsert", data)

        @self.sio.on("message")
        async def on_message(data):
            await self._handle_event("message", data)

        # Connection events
        @self.sio.on("connection.update")
        async def on_connection_update(data):
            await self._handle_event("connection.update", data)

        # Message status updates
        @self.sio.on("messages.update")
        async def on_messages_update(data):
            await self._handle_event("messages.update", data)

        # Send message confirmation
        @self.sio.on("send.message")
        async def on_send_message(data):
            await self._handle_event("send.message", data)

        # QR Code events
        @self.sio.on("qrcode.updated")
        async def on_qrcode_updated(data):
            await self._handle_event("qrcode.updated", data)

        # Catch-all for any other events
        @self.sio.on("*")
        async def on_any(event, data):
            await self._handle_event(event, data)

    async def _handle_event(self, event: str, data: Any):
        """Handle incoming events."""
        log_info(
            f"WebSocket event received: {event}",
            event=event,
            instance=self.instance_name or "global",
            action="websocket_event",
        )

        # Call the any-event callback if set
        if self.on_any_event:
            try:
                if asyncio.iscoroutinefunction(self.on_any_event):
                    await self.on_any_event(event, data)
                else:
                    self.on_any_event(event, data)
            except Exception as e:
                log_error(
                    f"Error in on_any_event callback: {e}",
                    event=event,
                    error_type=type(e).__name__,
                )

        # Route to specific callbacks
        if event in ("messages.upsert", "message") and self.on_message:
            try:
                if asyncio.iscoroutinefunction(self.on_message):
                    await self.on_message(data)
                else:
                    self.on_message(data)
            except Exception as e:
                log_error(
                    f"Error in on_message callback: {e}",
                    event=event,
                    error_type=type(e).__name__,
                )

        elif event == "connection.update" and self.on_connection_update:
            try:
                if asyncio.iscoroutinefunction(self.on_connection_update):
                    await self.on_connection_update(data)
                else:
                    self.on_connection_update(data)
            except Exception as e:
                log_error(
                    f"Error in on_connection_update callback: {e}",
                    event=event,
                    error_type=type(e).__name__,
                )

    async def connect(self):
        """Connect to Evolution API WebSocket."""
        url = self._get_connection_url()

        log_info(
            "Connecting to Evolution API WebSocket",
            url=url,
            instance=self.instance_name or "global",
            action="websocket_connecting",
        )

        try:
            # Connection options
            headers = {}
            if self.api_key:
                headers["apikey"] = self.api_key

            await self.sio.connect(
                url,
                transports=["websocket"],
                headers=headers if headers else None,
            )

        except Exception as e:
            log_error(
                f"Failed to connect to Evolution API WebSocket: {e}",
                url=url,
                error_type=type(e).__name__,
                action="websocket_connect_failed",
            )
            raise

    async def disconnect(self):
        """Disconnect from Evolution API WebSocket."""
        self._should_reconnect = False
        if self._connected:
            await self.sio.disconnect()
            log_info(
                "Disconnected from Evolution API WebSocket",
                action="websocket_manual_disconnect",
            )

    @property
    def connected(self) -> bool:
        """Check if connected."""
        return self._connected

    async def wait(self):
        """Wait for the connection to close."""
        await self.sio.wait()


class EvolutionWebSocketManager:
    """
    Manages WebSocket connections for multiple Evolution API instances.

    Use this for global mode or managing multiple instance connections.
    """

    def __init__(self):
        self.connections: Dict[str, EvolutionWebSocket] = {}
        self._message_handler: Optional[Callable] = None
        self._connection_handler: Optional[Callable] = None

    def set_message_handler(self, handler: Callable):
        """Set the handler for message events."""
        self._message_handler = handler

    def set_connection_handler(self, handler: Callable):
        """Set the handler for connection events."""
        self._connection_handler = handler

    async def connect_instance(
        self,
        server_url: str,
        instance_name: str,
        api_key: Optional[str] = None,
    ) -> EvolutionWebSocket:
        """Connect to a specific instance."""
        if instance_name in self.connections:
            if self.connections[instance_name].connected:
                return self.connections[instance_name]
            # Disconnect old connection
            await self.connections[instance_name].disconnect()

        ws = EvolutionWebSocket(
            server_url=server_url,
            instance_name=instance_name,
            api_key=api_key,
            on_message=self._message_handler,
            on_connection_update=self._connection_handler,
        )

        await ws.connect()
        self.connections[instance_name] = ws
        return ws

    async def connect_global(
        self,
        server_url: str,
        api_key: Optional[str] = None,
    ) -> EvolutionWebSocket:
        """Connect in global mode (all instances)."""
        if "global" in self.connections:
            if self.connections["global"].connected:
                return self.connections["global"]
            await self.connections["global"].disconnect()

        ws = EvolutionWebSocket(
            server_url=server_url,
            instance_name=None,  # Global mode
            api_key=api_key,
            on_message=self._message_handler,
            on_connection_update=self._connection_handler,
        )

        await ws.connect()
        self.connections["global"] = ws
        return ws

    async def disconnect_all(self):
        """Disconnect all connections."""
        for name, ws in self.connections.items():
            try:
                await ws.disconnect()
            except Exception as e:
                log_error(f"Error disconnecting {name}: {e}")
        self.connections.clear()

    async def disconnect_instance(self, instance_name: str):
        """Disconnect a specific instance."""
        if instance_name in self.connections:
            await self.connections[instance_name].disconnect()
            del self.connections[instance_name]
