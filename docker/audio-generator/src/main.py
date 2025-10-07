"""
Agent Adventures Audio Generator - Main Application

Multi-channel AI audio generation service for interactive streaming.
Connects to Agent Adventures platform via WebSocket for story state updates.
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from websocket_client import AgentAdventuresClient
from channel_manager import ChannelManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global instances
ws_client: AgentAdventuresClient = None
channel_manager: ChannelManager = None
status_task: asyncio.Task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Handles startup and shutdown.
    """
    # Startup
    logger.info("🚀 Starting Agent Adventures Audio Generator...")
    await startup()

    yield

    # Shutdown
    logger.info("🛑 Shutting down Agent Adventures Audio Generator...")
    await shutdown()


# Create FastAPI app
app = FastAPI(
    title="Agent Adventures Audio Generator",
    description="Multi-channel AI audio generation for interactive streaming",
    version="1.0.0",
    lifespan=lifespan
)


async def startup():
    """Initialize application on startup"""
    global ws_client, channel_manager, status_task

    try:
        # Get configuration from environment
        ws_uri = os.getenv("AGENT_ADVENTURES_WS_URL", "ws://localhost:3001/ws/audio")
        reconnect_interval = int(os.getenv("RECONNECT_INTERVAL", "5"))
        status_interval = int(os.getenv("STATUS_REPORT_INTERVAL", "5"))

        # Initialize channel manager
        logger.info("Initializing channel manager...")
        channel_manager = ChannelManager(ws_client=None)  # Will be set after ws_client is created
        await channel_manager.initialize()

        # Initialize WebSocket client
        logger.info("Connecting to Agent Adventures...")
        ws_client = AgentAdventuresClient(
            uri=ws_uri,
            reconnect_interval=reconnect_interval,
            status_interval=status_interval
        )

        # Register message handlers
        ws_client.on("auth_response", handle_auth_response)
        ws_client.on("story_update", handle_story_update)
        ws_client.on("control", handle_control)

        # Connect to Agent Adventures
        await ws_client.connect()

        # Set ws_client in channel_manager for audio ready notifications
        channel_manager.ws_client = ws_client

        # Start status reporting loop
        status_task = asyncio.create_task(status_reporter(status_interval))

        logger.info("✅ Application startup complete")

    except Exception as e:
        logger.error(f"❌ Startup failed: {e}", exc_info=True)
        raise


async def shutdown():
    """Cleanup on shutdown"""
    global ws_client, channel_manager, status_task

    try:
        # Cancel status reporter
        if status_task:
            status_task.cancel()
            try:
                await status_task
            except asyncio.CancelledError:
                pass

        # Disconnect WebSocket
        if ws_client:
            await ws_client.disconnect()

        # Shutdown channel manager
        if channel_manager:
            await channel_manager.shutdown()

        logger.info("✅ Shutdown complete")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


# WebSocket Message Handlers

async def handle_auth_response(data: dict):
    """
    Handle authentication response from Agent Adventures.

    Args:
        data: Authentication response data
    """
    client_id = data.get("clientId")
    logger.info(f"✅ Authenticated with Agent Adventures (ID: {client_id})")


async def handle_story_update(data: dict):
    """
    Handle story state update from Agent Adventures.

    Args:
        data: Story update message
    """
    channel = data.get("channel")
    update_data = data.get("data", {})
    metadata = data.get("metadata", {})

    logger.info(f"📥 Story update received for channel: {channel}")

    try:
        # Route to appropriate channel
        if channel == "narration":
            request_id = await channel_manager.generate_narration(update_data, metadata)
            logger.debug(f"Narration queued: {request_id}")

        elif channel == "ambient":
            request_id = await channel_manager.update_ambient(update_data, metadata)
            logger.debug(f"Ambient update queued: {request_id}")

        elif channel == "music":
            request_id = await channel_manager.update_music(update_data, metadata)
            logger.debug(f"Music update queued: {request_id}")

        elif channel == "commentary":
            request_id = await channel_manager.generate_commentary(update_data, metadata)
            logger.debug(f"Commentary queued: {request_id}")

        else:
            logger.warning(f"Unknown channel: {channel}")

    except Exception as e:
        logger.error(f"Error processing story update for {channel}: {e}", exc_info=True)

        # Send error to Agent Adventures
        if ws_client:
            await ws_client.send_error(
                channel=channel,
                error={
                    "code": "PROCESSING_ERROR",
                    "message": str(e),
                    "details": {"data": update_data}
                },
                severity="error"
            )


async def handle_control(data: dict):
    """
    Handle control command from Agent Adventures.

    Args:
        data: Control command message
    """
    command = data.get("command")
    channel = data.get("channel")
    params = data.get("params", {})

    logger.info(f"🎛️ Control command received: {command} for {channel}")

    try:
        if command == "pause":
            await channel_manager.pause_channel(channel, params)

        elif command == "resume":
            await channel_manager.resume_channel(channel, params)

        elif command == "clear_queue":
            await channel_manager.clear_queue(channel)

        elif command == "register_sync":
            sync_id = params.get("syncId") or params.get("sync_id") or data.get("syncId") or data.get("sync_id")
            channels = params.get("channels") or params.get("channelIds") or params.get("channel_ids") or data.get("channels")
            metadata = params.get("metadata") or data.get("metadata") or {}

            if not sync_id:
                logger.warning("register_sync command missing syncId")
                return

            if not channels:
                logger.warning("register_sync command missing channels")
                return

            channel_list = [str(ch).lower() for ch in channels if ch]
            if not channel_list:
                logger.warning("register_sync provided channels but none were valid")
                return

            channel_manager.register_sync_group(sync_id, channel_list, metadata)
            logger.info(
                "Registered sync group %s with channels %s",
                sync_id,
                ", ".join(channel_list)
            )

        else:
            logger.warning(f"Unknown control command: {command}")

    except Exception as e:
        logger.error(f"Error executing control command {command}: {e}", exc_info=True)


async def status_reporter(interval: int):
    """
    Periodic status reporting to Agent Adventures.

    Args:
        interval: Seconds between status updates
    """
    while True:
        try:
            await asyncio.sleep(interval)

            if ws_client and ws_client.is_connected():
                status = await channel_manager.get_status()
                await ws_client.send_status(status)
                logger.debug("Status update sent to Agent Adventures")

        except asyncio.CancelledError:
            logger.info("Status reporter cancelled")
            break
        except Exception as e:
            logger.error(f"Error in status reporter: {e}", exc_info=True)


# REST API Endpoints

@app.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "service": "audio-generator",
        "ws_connected": ws_client.is_connected() if ws_client else False,
        "channels_initialized": channel_manager._initialized if channel_manager else False
    }


@app.get("/status")
async def get_status():
    """
    Get detailed status of all audio channels.

    Returns:
        dict: Channel status information
    """
    if not channel_manager:
        raise HTTPException(status_code=503, detail="Channel manager not initialized")

    channels = await channel_manager.get_status()

    return {
        "success": True,
        "ws_connected": ws_client.is_connected() if ws_client else False,
        "client_id": ws_client.client_id if ws_client else None,
        "channels": channels
    }


@app.post("/api/narration")
async def trigger_narration(request: dict):
    """
    Manually trigger narration (for testing).

    Args:
        request: Narration request data

    Returns:
        dict: Request status
    """
    if not channel_manager:
        raise HTTPException(status_code=503, detail="Channel manager not initialized")

    try:
        request_id = await channel_manager.generate_narration(
            data=request.get("data", {}),
            metadata=request.get("metadata", {})
        )

        return {
            "success": True,
            "request_id": request_id,
            "message": "Narration queued"
        }
    except Exception as e:
        logger.error(f"Error triggering narration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ambient")
async def update_ambient_audio(request: dict):
    """
    Manually update ambient audio (for testing).

    Args:
        request: Ambient update request data

    Returns:
        dict: Request status
    """
    if not channel_manager:
        raise HTTPException(status_code=503, detail="Channel manager not initialized")

    try:
        request_id = await channel_manager.update_ambient(
            data=request.get("data", {}),
            metadata=request.get("metadata", {})
        )

        return {
            "success": True,
            "request_id": request_id,
            "message": "Ambient update queued"
        }
    except Exception as e:
        logger.error(f"Error updating ambient: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/music")
async def update_music(request: dict):
    """
    Manually update music (for testing).

    Args:
        request: Music update request data

    Returns:
        dict: Request status
    """
    if not channel_manager:
        raise HTTPException(status_code=503, detail="Channel manager not initialized")

    try:
        request_id = await channel_manager.update_music(
            data=request.get("data", {}),
            metadata=request.get("metadata", {})
        )

        return {
            "success": True,
            "request_id": request_id,
            "message": "Music update queued"
        }
    except Exception as e:
        logger.error(f"Error updating music: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/commentary")
async def trigger_commentary(request: dict):
    """
    Manually trigger commentary (for testing).

    Args:
        request: Commentary request data

    Returns:
        dict: Request status
    """
    if not channel_manager:
        raise HTTPException(status_code=503, detail="Channel manager not initialized")

    try:
        request_id = await channel_manager.generate_commentary(
            data=request.get("data", {}),
            metadata=request.get("metadata", {})
        )

        return {
            "success": True,
            "request_id": request_id,
            "message": "Commentary queued"
        }
    except Exception as e:
        logger.error(f"Error triggering commentary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync")
async def trigger_synchronized(request: dict):
    """
    Trigger multiple channels synchronously.

    Example request:
    {
        "sync_id": "scene_123",
        "channels": {
            "narration": {
                "text": "The battle begins!",
                "voice": "af_heart:60,af_bella:40",
                "emotion": "intense"
            },
            "music": {
                "tension_level": "high",
                "intensity": 0.8,
                "genre": "orchestral"
            }
        }
    }

    Args:
        request: Synchronized request data

    Returns:
        dict: Request status
    """
    if not channel_manager:
        raise HTTPException(status_code=503, detail="Channel manager not initialized")

    try:
        sync_id = request.get("sync_id")
        channels = request.get("channels", {})

        if not sync_id:
            raise HTTPException(status_code=400, detail="sync_id is required")

        if not channels:
            raise HTTPException(status_code=400, detail="At least one channel is required")

        # Register sync group
        sync_metadata = request.get("metadata") or request.get("syncMetadata") or {}
        if not isinstance(sync_metadata, dict):
            sync_metadata = {}

        channel_manager.register_sync_group(sync_id, list(channels.keys()), sync_metadata)

        # Queue all channels with sync_id in metadata
        request_ids = {}
        for channel_id, channel_data in channels.items():
            metadata = {"sync_id": sync_id}

            if channel_id == "narration":
                request_ids[channel_id] = await channel_manager.generate_narration(
                    data=channel_data,
                    metadata=metadata
                )
            elif channel_id == "ambient":
                request_ids[channel_id] = await channel_manager.update_ambient(
                    data=channel_data,
                    metadata=metadata
                )
            elif channel_id == "music":
                request_ids[channel_id] = await channel_manager.update_music(
                    data=channel_data,
                    metadata=metadata
                )
            elif channel_id == "commentary":
                request_ids[channel_id] = await channel_manager.generate_commentary(
                    data=channel_data,
                    metadata=metadata
                )

        return {
            "success": True,
            "sync_id": sync_id,
            "request_ids": request_ids,
            "message": f"Synchronized request queued for {len(channels)} channels"
        }

    except Exception as e:
        logger.error(f"Error triggering synchronized request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/clear")
async def clear_queues(request: dict):
    """
    Clear queues for specified channels or all channels.

    Example request:
    {
        "channels": ["narration", "music"]  // optional, clears all if omitted
    }

    Args:
        request: Clear request data

    Returns:
        dict: Clear operation status
    """
    if not channel_manager:
        raise HTTPException(status_code=503, detail="Channel manager not available")

    try:
        channels_to_clear = request.get("channels", ["narration", "ambient", "music", "commentary"])

        if not isinstance(channels_to_clear, list):
            raise HTTPException(status_code=400, detail="channels must be a list")

        cleared = {}
        for channel_id in channels_to_clear:
            result = await channel_manager.clear_queue(channel_id)
            cleared[channel_id] = result

        return {
            "success": True,
            "cleared": cleared,
            "message": f"Cleared {len(cleared)} channel(s)"
        }

    except Exception as e:
        logger.error(f"Error clearing queues: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


if __name__ == "__main__":
    # Get port from environment
    port = int(os.getenv("PORT", "8080"))

    # Run the application
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
