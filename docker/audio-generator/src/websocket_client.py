"""
WebSocket client for Agent Adventures platform integration.

Handles bidirectional communication between the audio generator
and the Agent Adventures Node.js platform.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Dict, Any, Optional
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

logger = logging.getLogger(__name__)


class AgentAdventuresClient:
    """WebSocket client for Agent Adventures platform"""

    def __init__(
        self,
        uri: str = "ws://localhost:3001/ws/audio",
        reconnect_interval: int = 5,
        status_interval: int = 5
    ):
        """
        Initialize WebSocket client.

        Args:
            uri: WebSocket URI for Agent Adventures
            reconnect_interval: Seconds between reconnection attempts
            status_interval: Seconds between status updates
        """
        self.uri = uri
        self.reconnect_interval = reconnect_interval
        self.status_interval = status_interval
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.message_handlers: Dict[str, Callable] = {}
        self.connected = False
        self.client_id: Optional[str] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """
        Connect to Agent Adventures WebSocket server.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to Agent Adventures at {self.uri}")
            self.websocket = await websockets.connect(
                self.uri,
                ping_interval=20,
                ping_timeout=10
            )
            self.connected = True
            logger.info(f"✅ Connected to Agent Adventures")

            # Send authentication
            await self._authenticate()

            # Start listening for messages
            self._listen_task = asyncio.create_task(self._listen())

            return True

        except WebSocketException as e:
            logger.error(f"WebSocket connection error: {e}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self.connected = False
            return False

    async def _authenticate(self):
        """Send authentication message to server"""
        auth_message = {
            "type": "auth",
            "service": "audio-generator",
            "version": "1.0.0",
            "capabilities": ["narration", "ambient", "music", "commentary"]
        }
        await self.send(auth_message)
        logger.info("Authentication message sent")

    async def _listen(self):
        """Listen for incoming messages"""
        try:
            async for message in self.websocket:
                await self._handle_message(message)
        except ConnectionClosed:
            logger.warning("Connection closed by server")
            self.connected = False
            await self._handle_disconnect()
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
            self.connected = False
            await self._handle_disconnect()

    async def _handle_message(self, message: str):
        """
        Handle incoming message from server.

        Args:
            message: Raw JSON message string
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            logger.debug(f"Received message type: {msg_type}")

            # Handle auth response specially
            if msg_type == "auth_response":
                self.client_id = data.get("clientId")
                logger.info(f"Authenticated with client ID: {self.client_id}")

            # Call registered handler if exists
            if msg_type in self.message_handlers:
                await self.message_handlers[msg_type](data)
            else:
                logger.warning(f"No handler registered for message type: {msg_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)

    async def _handle_disconnect(self):
        """Handle disconnection and attempt reconnection"""
        self.connected = False
        self.client_id = None

        logger.warning(f"Disconnected from Agent Adventures, will retry in {self.reconnect_interval}s")

        # Start reconnection task if not already running
        if not self._reconnect_task or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self):
        """Continuously attempt to reconnect"""
        while not self.connected:
            try:
                logger.info(f"Attempting to reconnect...")
                await asyncio.sleep(self.reconnect_interval)
                await self.connect()
            except Exception as e:
                logger.error(f"Reconnection attempt failed: {e}")

    def on(self, message_type: str, handler: Callable):
        """
        Register message handler for specific message type.

        Args:
            message_type: Type of message to handle (e.g., 'story_update', 'control')
            handler: Async function to call when message received
        """
        self.message_handlers[message_type] = handler
        logger.debug(f"Registered handler for message type: {message_type}")

    async def send(self, data: Dict[str, Any]) -> bool:
        """
        Send message to Agent Adventures server.

        Args:
            data: Dictionary to send as JSON

        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.connected or not self.websocket:
            logger.warning("Not connected, cannot send message")
            return False

        try:
            message = json.dumps(data)
            await self.websocket.send(message)
            logger.debug(f"Sent message type: {data.get('type')}")
            return True
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    async def send_status(self, channels: list) -> bool:
        """
        Send audio status update to server.

        Args:
            channels: List of channel status dictionaries

        Returns:
            bool: True if sent successfully
        """
        return await self.send({
            "type": "audio_status",
            "status": "active",
            "channels": channels,
            "timestamp": datetime.now().isoformat()
        })

    async def send_error(
        self,
        channel: str,
        error: Dict[str, Any],
        severity: str = "error"
    ) -> bool:
        """
        Send error message to server.

        Args:
            channel: Audio channel name
            error: Error details dictionary
            severity: Error severity (info, warning, error, critical)

        Returns:
            bool: True if sent successfully
        """
        return await self.send({
            "type": "audio_error",
            "severity": severity,
            "channel": channel,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })

    async def send_complete(
        self,
        channel: str,
        request_id: str,
        result: Dict[str, Any]
    ) -> bool:
        """
        Send audio generation complete message.

        Args:
            channel: Audio channel name
            request_id: Unique request identifier
            result: Generation result details

        Returns:
            bool: True if sent successfully
        """
        return await self.send({
            "type": "audio_complete",
            "channel": channel,
            "request_id": request_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })

    async def disconnect(self):
        """Disconnect from server gracefully"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            self.client_id = None
            logger.info("Disconnected from Agent Adventures")

    def is_connected(self) -> bool:
        """Check if currently connected to server"""
        return self.connected and self.websocket is not None
