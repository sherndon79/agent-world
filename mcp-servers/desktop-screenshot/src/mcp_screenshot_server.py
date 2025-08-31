#!/usr/bin/env python3
"""
MCP Screenshot Server

Cross-platform Model Context Protocol server for desktop screenshot capture.
Enables AI agents to capture screenshots of desktop applications programmatically.

Usage:
    python mcp_screenshot_server.py

Integration:
    Configure as MCP server in Claude Code or other MCP clients.
"""

import asyncio
import json
import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel import NotificationOptions
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    TextContent,
)

from screenshot_manager import ScreenshotManager
from window_detector import WindowDetector

class ScreenshotMetadata:
    """Manages screenshot metadata using JSON sidecar files."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
    
    def save_metadata(self, screenshot_path: Path, metadata: dict):
        """Save metadata as JSON sidecar file."""
        metadata_path = screenshot_path.with_suffix('.json')
        
        # Auto-populate standard fields
        try:
            file_size = screenshot_path.stat().st_size if screenshot_path.exists() else 0
        except Exception:
            file_size = 0
            
        full_metadata = {
            "screenshot_file": screenshot_path.name,
            "timestamp": datetime.now().isoformat(),
            "file_size_bytes": file_size,
            **metadata  # User-provided metadata
        }
        
        try:
            with open(metadata_path, 'w') as f:
                json.dump(full_metadata, f, indent=2)
            logger.info(f"Saved metadata to {metadata_path}")
        except Exception as e:
            logger.warning(f"Failed to save metadata to {metadata_path}: {e}")
    
    def load_metadata(self, screenshot_path: Path) -> dict:
        """Load metadata for a screenshot."""
        metadata_path = screenshot_path.with_suffix('.json')
        if metadata_path.exists():
            try:
                with open(metadata_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load metadata from {metadata_path}: {e}")
        return {}
    
    def has_metadata(self, screenshot_path: Path) -> bool:
        """Check if screenshot has metadata file."""
        metadata_path = screenshot_path.with_suffix('.json')
        return metadata_path.exists()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mcp_screenshot_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MCPScreenshotServer:
    """
    MCP Screenshot Server
    
    Provides screenshot capture capabilities through the Model Context Protocol.
    Supports cross-platform window-specific and desktop screenshots.
    """
    
    def __init__(self):
        """Initialize the MCP Screenshot Server."""
        self.screenshot_manager = ScreenshotManager()
        self.window_detector = WindowDetector()
        self.server = Server("desktop-screenshot")
        
        # Output directory for screenshots
        self.output_dir = Path("screenshots")
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize metadata manager with output directory
        self.metadata_manager = ScreenshotMetadata(self.output_dir)
        
        logger.info("MCP Screenshot Server initialized")
        
        # Register tools
        self._register_tools()
    
    def _register_tools(self) -> None:
        """Register all available screenshot tools."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List all available screenshot tools."""
            return [
                Tool(
                    name="screenshot_window",
                    description="Capture screenshot of specific window by title",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "window_title": {
                                "type": "string",
                                "description": "Title/name of window to capture"
                            },
                            "output_path": {
                                "type": "string",
                                "description": "Optional custom output path (auto-generated if not provided)"
                            },
                            "purpose": {
                                "type": "string",
                                "description": "Why this screenshot is being taken (e.g., 'confirming element placement', 'visual validation')"
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Categorization tags for organizing screenshots"
                            },
                            "notes": {
                                "type": "string",
                                "description": "Additional context or observations"
                            }
                        },
                        "required": ["window_title"]
                    }
                ),
                Tool(
                    name="screenshot_isaac_sim",
                    description="Specialized tool for capturing Isaac Sim window",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_path": {
                                "type": "string",
                                "description": "Optional custom output path (auto-generated if not provided)"
                            },
                            "purpose": {
                                "type": "string",
                                "description": "Why this screenshot is being taken (e.g., 'confirming element placement', 'visual validation')"
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Categorization tags for organizing screenshots"
                            },
                            "notes": {
                                "type": "string",
                                "description": "Additional context or observations"
                            }
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="list_windows",
                    description="List all open windows with their titles and process information",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="screenshot_desktop",
                    description="Capture full desktop screenshot",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_path": {
                                "type": "string",
                                "description": "Optional custom output path (auto-generated if not provided)"
                            },
                            "purpose": {
                                "type": "string",
                                "description": "Why this screenshot is being taken (e.g., 'confirming element placement', 'visual validation')"
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Categorization tags for organizing screenshots"
                            },
                            "notes": {
                                "type": "string",
                                "description": "Additional context or observations"
                            }
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="screenshot_area",
                    description="Capture specific rectangular area of screen",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "integer",
                                "description": "X coordinate of top-left corner"
                            },
                            "y": {
                                "type": "integer",
                                "description": "Y coordinate of top-left corner"
                            },
                            "width": {
                                "type": "integer",
                                "description": "Width of area to capture"
                            },
                            "height": {
                                "type": "integer",
                                "description": "Height of area to capture"
                            },
                            "output_path": {
                                "type": "string",
                                "description": "Optional custom output path (auto-generated if not provided)"
                            },
                            "purpose": {
                                "type": "string",
                                "description": "Why this screenshot is being taken (e.g., 'confirming element placement', 'visual validation')"
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Categorization tags for organizing screenshots"
                            },
                            "notes": {
                                "type": "string",
                                "description": "Additional context or observations"
                            }
                        },
                        "required": ["x", "y", "width", "height"]
                    }
                ),
                Tool(
                    name="screenshot_purge",
                    description="Clean up old screenshots based on age criteria",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "age": {
                                "type": "string",
                                "description": "Maximum age to keep (e.g., '1h', '2d', '1w', '30d')",
                                "pattern": "^\\d+[hmtdwMy]$"
                            },
                            "dry_run": {
                                "type": "boolean", 
                                "description": "Preview mode - show what would be deleted without deleting",
                                "default": True
                            },
                            "pattern": {
                                "type": "string",
                                "description": "Optional file pattern filter (e.g., 'isaac_sim_*')"
                            }
                        },
                        "required": ["age"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> List[TextContent]:
            """Handle tool calls for screenshot operations."""
            try:
                if name == "screenshot_window":
                    return await self._screenshot_window(arguments)
                elif name == "screenshot_isaac_sim":
                    return await self._screenshot_isaac_sim(arguments)
                elif name == "list_windows":
                    return await self._list_windows(arguments)
                elif name == "screenshot_desktop":
                    return await self._screenshot_desktop(arguments)
                elif name == "screenshot_area":
                    return await self._screenshot_area(arguments)
                elif name == "screenshot_purge":
                    return await self._screenshot_purge(arguments)
                else:
                    return [TextContent(
                        type="text",
                        text=f"Unknown tool: {name}"
                    )]
                    
            except Exception as e:
                logger.error(f"Error handling tool call {name}: {e}")
                return [TextContent(
                    type="text",
                    text=f"Error: {str(e)}"
                )]
    
    async def _screenshot_window(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Capture screenshot of specific window by title."""
        window_title = arguments["window_title"]
        output_path = arguments.get("output_path")
        
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = "".join(c for c in window_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title.replace(' ', '_')
            output_path = self.output_dir / f"{safe_title}_{timestamp}.png"
        else:
            output_path = Path(output_path)
        
        try:
            result_path = await asyncio.to_thread(
                self.screenshot_manager.screenshot_window,
                window_title, 
                str(output_path)
            )
            
            logger.info(f"Window screenshot captured: {result_path}")
            
            # Save metadata if provided
            self._extract_and_save_metadata(Path(result_path), arguments, "screenshot_window")
            
            return [TextContent(
                type="text",
                text=f"Screenshot captured successfully: {result_path}"
            )]
            
        except Exception as e:
            logger.error(f"Failed to capture window screenshot: {e}")
            return [TextContent(
                type="text",
                text=f"Failed to capture window screenshot: {str(e)}"
            )]
    
    async def _screenshot_isaac_sim(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Specialized tool for capturing Isaac Sim window."""
        output_path = arguments.get("output_path")
        
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"isaac_sim_{timestamp}.png"
        else:
            output_path = Path(output_path)
        
        try:
            # Try common Isaac Sim window titles
            isaac_titles = [
                "Isaac Sim",
                "IsaacSim",
                "Isaac-Sim",
                "Omniverse Isaac Sim",
                "Kit"
            ]
            
            result_path = None
            for title in isaac_titles:
                try:
                    result_path = await asyncio.to_thread(
                        self.screenshot_manager.screenshot_window,
                        title,
                        str(output_path)
                    )
                    break
                except Exception:
                    continue
            
            if result_path:
                logger.info(f"Isaac Sim screenshot captured: {result_path}")
                
                # Save metadata if provided
                self._extract_and_save_metadata(Path(result_path), arguments, "screenshot_isaac_sim")
                
                return [TextContent(
                    type="text",
                    text=f"Isaac Sim screenshot captured successfully: {result_path}"
                )]
            else:
                # List available windows to help debug
                windows = await asyncio.to_thread(self.window_detector.list_windows)
                window_list = "\\n".join([f"- {w['title']}" for w in windows if w['title']])
                
                return [TextContent(
                    type="text",
                    text=f"Isaac Sim window not found. Available windows:\\n{window_list}"
                )]
                
        except Exception as e:
            logger.error(f"Failed to capture Isaac Sim screenshot: {e}")
            return [TextContent(
                type="text",
                text=f"Failed to capture Isaac Sim screenshot: {str(e)}"
            )]
    
    async def _list_windows(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """List all open windows with their titles and process information."""
        try:
            windows = await asyncio.to_thread(self.window_detector.list_windows)
            
            # Format window information
            window_info = []
            for window in windows:
                if window['title']:  # Only include windows with titles
                    info = f"Title: {window['title']}"
                    if 'process' in window:
                        info += f" | Process: {window['process']}"
                    if 'pid' in window:
                        info += f" | PID: {window['pid']}"
                    window_info.append(info)
            
            if window_info:
                result = "Open Windows:\\n" + "\\n".join(window_info)
            else:
                result = "No windows with titles found"
            
            logger.info(f"Listed {len(window_info)} windows")
            return [TextContent(
                type="text",
                text=result
            )]
            
        except Exception as e:
            logger.error(f"Failed to list windows: {e}")
            return [TextContent(
                type="text",
                text=f"Failed to list windows: {str(e)}"
            )]
    
    async def _screenshot_desktop(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Capture full desktop screenshot."""
        output_path = arguments.get("output_path")
        
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"desktop_{timestamp}.png"
        else:
            output_path = Path(output_path)
        
        try:
            result_path = await asyncio.to_thread(
                self.screenshot_manager.screenshot_desktop,
                str(output_path)
            )
            
            logger.info(f"Desktop screenshot captured: {result_path}")
            
            # Save metadata if provided
            self._extract_and_save_metadata(Path(result_path), arguments, "screenshot_desktop")
            
            return [TextContent(
                type="text",
                text=f"Desktop screenshot captured successfully: {result_path}"
            )]
            
        except Exception as e:
            logger.error(f"Failed to capture desktop screenshot: {e}")
            return [TextContent(
                type="text",
                text=f"Failed to capture desktop screenshot: {str(e)}"
            )]
    
    async def _screenshot_area(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Capture specific rectangular area of screen."""
        x = arguments["x"]
        y = arguments["y"]
        width = arguments["width"]
        height = arguments["height"]
        output_path = arguments.get("output_path")
        
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"area_{x}_{y}_{width}x{height}_{timestamp}.png"
        else:
            output_path = Path(output_path)
        
        try:
            result_path = await asyncio.to_thread(
                self.screenshot_manager.screenshot_area,
                x, y, width, height,
                str(output_path)
            )
            
            logger.info(f"Area screenshot captured: {result_path}")
            
            # Save metadata if provided
            self._extract_and_save_metadata(Path(result_path), arguments, "screenshot_area")
            
            return [TextContent(
                type="text",
                text=f"Area screenshot captured successfully: {result_path}"
            )]
            
        except Exception as e:
            logger.error(f"Failed to capture area screenshot: {e}")
            return [TextContent(
                type="text",
                text=f"Failed to capture area screenshot: {str(e)}"
            )]
    
    def _extract_and_save_metadata(self, screenshot_path: Path, arguments: Dict[str, Any], tool_name: str):
        """Extract metadata from arguments and save as JSON sidecar file."""
        purpose = arguments.get("purpose")
        tags = arguments.get("tags", [])
        notes = arguments.get("notes")
        
        # Only save metadata if at least one field is provided
        if purpose or tags or notes:
            metadata = {
                "purpose": purpose,
                "tags": tags,
                "notes": notes,
                "tool_used": tool_name,
            }
            
            # Add tool-specific metadata
            if tool_name == "screenshot_window":
                metadata["window_title"] = arguments.get("window_title")
            elif tool_name == "screenshot_area":
                metadata["capture_area"] = {
                    "x": arguments.get("x"),
                    "y": arguments.get("y"), 
                    "width": arguments.get("width"),
                    "height": arguments.get("height")
                }
            
            self.metadata_manager.save_metadata(screenshot_path, metadata)
    
    def _parse_age_string(self, age_str: str) -> timedelta:
        """Parse age strings like '1h', '2d', '1w' into timedelta objects."""
        pattern = r'^(\d+)([hmtdwMy])$'
        match = re.match(pattern, age_str)
        if not match:
            raise ValueError(f"Invalid age format: {age_str}. Use format like '1h', '2d', '1w'")
        
        amount, unit = match.groups()
        amount = int(amount)
        
        unit_map = {
            'm': timedelta(minutes=amount),
            'h': timedelta(hours=amount),
            'd': timedelta(days=amount),
            'w': timedelta(weeks=amount),
            'M': timedelta(days=amount * 30),  # Approximate month
            'y': timedelta(days=amount * 365)  # Approximate year
        }
        
        return unit_map[unit]
    
    def _purge_screenshots(self, max_age: timedelta, dry_run: bool = True, pattern: str = None) -> Dict[str, Any]:
        """
        Delete screenshots older than max_age from the output directory.
        
        Args:
            max_age: Maximum age threshold for keeping screenshots
            dry_run: If True, only report what would be deleted
            pattern: Optional glob pattern to filter files
            
        Returns:
            dict: Summary of operation (files_found, size_freed, files_deleted)
        """
        cutoff_time = datetime.now() - max_age
        screenshot_dir = self.output_dir
        
        # Default patterns for screenshot files
        if pattern is None:
            patterns = ["*.png", "*.jpg", "*.jpeg"]
        else:
            patterns = [pattern]
        
        files_to_delete = []  # Will contain tuples of (screenshot_path, metadata_path)
        total_size = 0
        
        for file_pattern in patterns:
            for file_path in screenshot_dir.glob(file_pattern):
                if file_path.is_file():
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        # Find corresponding metadata file
                        metadata_path = file_path.with_suffix('.json')
                        
                        # Add screenshot size
                        total_size += file_path.stat().st_size
                        
                        # Add metadata size if it exists
                        if metadata_path.exists():
                            total_size += metadata_path.stat().st_size
                        
                        files_to_delete.append((file_path, metadata_path))
        
        if dry_run:
            file_list = []
            for screenshot_path, metadata_path in files_to_delete:
                file_list.append(str(screenshot_path.name))
                if metadata_path.exists():
                    file_list.append(str(metadata_path.name))
            
            return {
                "dry_run": True,
                "files_found": len(files_to_delete),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "files": file_list
            }
        else:
            deleted_count = 0
            for screenshot_path, metadata_path in files_to_delete:
                # Try to delete the screenshot file
                try:
                    screenshot_path.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted screenshot: {screenshot_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete screenshot {screenshot_path}: {e}")
                
                # Try to delete the metadata sidecar (if it exists)
                try:
                    if metadata_path.exists():
                        metadata_path.unlink()
                        logger.info(f"Deleted metadata: {metadata_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete metadata {metadata_path}: {e}")
            
            return {
                "dry_run": False,
                "files_deleted": deleted_count,
                "size_freed_mb": round(total_size / (1024 * 1024), 2),
                "total_files_attempted": len(files_to_delete)
            }
    
    async def _screenshot_purge(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Clean up old screenshots based on age criteria."""
        age_str = arguments["age"]
        dry_run = arguments.get("dry_run", True)
        pattern = arguments.get("pattern")
        
        try:
            # Parse age string into timedelta
            max_age = self._parse_age_string(age_str)
            
            # Perform purge operation
            result = await asyncio.to_thread(
                self._purge_screenshots,
                max_age,
                dry_run,
                pattern
            )
            
            # Format response message
            if result["dry_run"]:
                if result["files_found"] == 0:
                    message = f"No screenshots found older than {age_str}"
                else:
                    file_list = "\\n".join([f"  - {name}" for name in result["files"][:10]])
                    if len(result["files"]) > 10:
                        file_list += f"\\n  ... and {len(result['files']) - 10} more"
                    
                    message = (f"📋 Found {result['files_found']} screenshots older than {age_str} "
                             f"({result['total_size_mb']} MB)\\n"
                             f"Files that would be deleted:\\n{file_list}\\n\\n"
                             f"💡 Use dry_run=false to actually delete these files")
            else:
                if result["files_deleted"] == 0:
                    message = f"No screenshots were deleted (none found older than {age_str})"
                else:
                    message = (f"🗑️ Deleted {result['files_deleted']} screenshots older than {age_str}\\n"
                             f"💾 Freed {result['size_freed_mb']} MB of storage")
                    
                    if result["files_deleted"] < result["total_files_attempted"]:
                        failed = result["total_files_attempted"] - result["files_deleted"]
                        message += f"\\n⚠️ Failed to delete {failed} files (check permissions)"
            
            return [TextContent(
                type="text",
                text=message
            )]
            
        except ValueError as e:
            return [TextContent(
                type="text",
                text=f"❌ Invalid age format: {str(e)}"
            )]
        except Exception as e:
            logger.error(f"Failed to purge screenshots: {e}")
            return [TextContent(
                type="text",
                text=f"❌ Failed to purge screenshots: {str(e)}"
            )]
    
    async def run(self) -> None:
        """Run the MCP screenshot server."""
        logger.info("Starting MCP Screenshot Server...")
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, 
                write_stream,
                InitializationOptions(
                    server_name="desktop-screenshot",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                )
            )


async def main():
    """Main entry point for the MCP Screenshot Server."""
    server = MCPScreenshotServer()
    await server.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MCP Screenshot Server stopped by user")
    except Exception as e:
        logger.error(f"MCP Screenshot Server error: {e}")
        sys.exit(1)