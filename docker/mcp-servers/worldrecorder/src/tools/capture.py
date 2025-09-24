#!/usr/bin/env python3
"""
WorldRecorder Frame Capture Tools

Tools for capturing individual frames and managing frame cleanup.
"""

from typing import Any, Dict, Optional
from mcp.server.fastmcp import FastMCP

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)
mcp: FastMCP = None


async def worldrecorder_capture_frame(
    output_path: str,
    duration_sec: Optional[float] = None,
    interval_sec: Optional[float] = None,
    frame_count: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    file_type: str = ".png"
) -> Dict[str, Any]:
    """Capture a single frame or frame sequence from Isaac Sim viewport

    Args:
        output_path: File path for image output (single frame) or base directory for frame sequences
        duration_sec: Total capture duration for sequences (optional - if provided with interval_sec or frame_count, captures frame sequence)
        interval_sec: Time between frames for sequences (optional - mutually exclusive with frame_count)
        frame_count: Total number of frames to capture over duration (optional - mutually exclusive with interval_sec)
        width: Image width in pixels (optional, uses viewport width if not specified)
        height: Image height in pixels (optional, uses viewport height if not specified)
        file_type: Image file format (.png, .jpg, .jpeg, .bmp, .tiff)
    """
    client = get_client()

    args = {
        "output_path": output_path,
        "file_type": file_type
    }
    if duration_sec is not None:
        args["duration_sec"] = duration_sec
    if interval_sec is not None:
        args["interval_sec"] = interval_sec
    if frame_count is not None:
        args["frame_count"] = frame_count
    if width is not None:
        args["width"] = width
    if height is not None:
        args["height"] = height

    result = await client.request('viewport/capture_frame', payload=args)
    return result


async def worldrecorder_cleanup_frames(
    session_id: str = "",
    output_path: str = ""
) -> Dict[str, Any]:
    """Manually clean up temporary frame directories for a session or output path

    Args:
        session_id: Session ID to clean up (will use session's output path)
        output_path: Direct output path to clean up frame directories for
    """
    client = get_client()

    args = {}
    if session_id:
        args["session_id"] = session_id
    if output_path:
        args["output_path"] = output_path

    result = await client.request('cleanup/frames', payload=args)
    return result