#!/usr/bin/env python3
"""
WorldRecorder Video Recording Tools

Tools for continuous video recording and recording session management.
"""

from typing import Any, Dict, Optional

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)


async def worldrecorder_start_video(
    output_path: str,
    duration_sec: float,
    fps: float = 30,
    width: Optional[int] = None,
    height: Optional[int] = None,
    file_type: str = ".mp4",
    session_id: str = "",
    show_progress: bool = False,
    cleanup_frames: bool = True
) -> Dict[str, Any]:
    """Start continuous video recording in Isaac Sim viewport

    Args:
        output_path: File path for video output (e.g., '/tmp/my_video.mp4')
        duration_sec: Recording duration in seconds (0.1-86400)
        fps: Frames per second for recording (1-120)
        width: Video width in pixels (optional, uses viewport width if not specified)
        height: Video height in pixels (optional, uses viewport height if not specified)
        file_type: Video file format (.mp4, .avi, .mov)
        session_id: Optional unique session identifier for tracking
        show_progress: Show progress UI during recording
        cleanup_frames: Automatically clean up temporary frame directories after recording
    """
    client = get_client()

    args = {
        "output_path": output_path,
        "duration_sec": duration_sec,
        "fps": fps,
        "file_type": file_type,
        "show_progress": show_progress,
        "cleanup_frames": cleanup_frames
    }
    if width is not None:
        args["width"] = width
    if height is not None:
        args["height"] = height
    if session_id:
        args["session_id"] = session_id

    result = await client.request('video/start', payload=args)
    return result


async def worldrecorder_start_recording(
    output_path: str,
    duration_sec: float,
    fps: float = 30,
    width: Optional[int] = None,
    height: Optional[int] = None,
    file_type: str = ".mp4",
    session_id: str = "",
    show_progress: bool = False,
    cleanup_frames: bool = True
) -> Dict[str, Any]:
    """Start recording via recording/* API (alias of video/start)

    Args:
        output_path: Output file path
        duration_sec: Recording duration in seconds (0.1-86400)
        fps: Frames per second (1-120)
        width: Video width in pixels (optional)
        height: Video height in pixels (optional)
        file_type: Video file format (.mp4, .avi, .mov)
        session_id: Optional session identifier
        show_progress: Show progress UI during recording
        cleanup_frames: Automatically clean up temporary frame directories after recording
    """
    client = get_client()

    args = {
        "output_path": output_path,
        "duration_sec": duration_sec,
        "fps": fps,
        "file_type": file_type,
        "show_progress": show_progress,
        "cleanup_frames": cleanup_frames
    }
    if width is not None:
        args["width"] = width
    if height is not None:
        args["height"] = height
    if session_id:
        args["session_id"] = session_id

    result = await client.request('recording/start', payload=args)
    return result


async def worldrecorder_cancel_recording(session_id: str = "") -> Dict[str, Any]:
    """Cancel recording via recording/* API - stops capture without encoding

    Args:
        session_id: Optional session id
    """
    client = get_client()

    args = {}
    if session_id:
        args["session_id"] = session_id

    result = await client.request('recording/cancel', payload=args)
    return result


async def worldrecorder_recording_status() -> Dict[str, Any]:
    """Get recording status via recording/* API"""
    client = get_client()

    result = await client.request('recording/status', method="GET")
    return result


async def worldrecorder_cancel_video() -> Dict[str, Any]:
    """Cancel current video recording - stops capture without encoding"""
    client = get_client()

    result = await client.request('video/cancel', payload={})
    return result


async def worldrecorder_get_status() -> Dict[str, Any]:
    """Get current video recording status and session information"""
    client = get_client()

    result = await client.request('video/status', method="GET")
    return result