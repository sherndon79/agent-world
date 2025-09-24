"""
Screenshot Manager

Cross-platform screenshot capture with automatic platform detection
and fallback strategies. Supports window-specific, desktop, and area screenshots.
"""

import platform
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except (ImportError, NotImplementedError):
    PYGETWINDOW_AVAILABLE = False

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

logger = logging.getLogger(__name__)


class ScreenshotManager:
    """
    Cross-platform screenshot manager with automatic platform detection.
    
    Provides unified interface for screenshot operations across Windows, macOS, and Linux.
    Uses platform-specific implementations with intelligent fallback strategies.
    """
    
    def __init__(self):
        """Initialize screenshot manager with platform detection."""
        self.platform = platform.system().lower()
        self.session_type = self._detect_session_type()
        
        logger.info(f"Screenshot manager initialized for {self.platform}")
        if self.platform == "linux":
            logger.info(f"Linux session type: {self.session_type}")
        
        # Check available libraries
        self._check_dependencies()
    
    def _detect_session_type(self) -> Optional[str]:
        """Detect Linux session type (X11 vs Wayland)."""
        if self.platform != "linux":
            return None
        
        try:
            session_type = subprocess.check_output(
                ["bash", "-c", "echo $XDG_SESSION_TYPE"],
                universal_newlines=True
            ).strip()
            return session_type if session_type else "unknown"
        except Exception:
            return "unknown"
    
    def _check_dependencies(self) -> None:
        """Check availability of required dependencies."""
        missing_deps = []
        
        if not MSS_AVAILABLE:
            missing_deps.append("mss")
        if not PYGETWINDOW_AVAILABLE:
            missing_deps.append("pygetwindow")
        if not PILLOW_AVAILABLE:
            missing_deps.append("pillow")
        
        if missing_deps:
            logger.warning(f"Missing optional dependencies: {', '.join(missing_deps)}")
    
    def screenshot_window(self, window_title: str, output_path: str) -> str:
        """
        Capture screenshot of specific window by title.
        
        Args:
            window_title: Title/name of window to capture
            output_path: Path where screenshot should be saved
            
        Returns:
            Path to saved screenshot file
            
        Raises:
            Exception: If window not found or screenshot fails
        """
        logger.info(f"Capturing window screenshot: {window_title}")
        
        if self.platform == "linux":
            return self._screenshot_window_linux(window_title, output_path)
        elif self.platform == "darwin":
            return self._screenshot_window_macos(window_title, output_path)
        elif self.platform == "windows":
            return self._screenshot_window_windows(window_title, output_path)
        else:
            # Fallback to cross-platform library
            return self._screenshot_window_crossplatform(window_title, output_path)
    
    def screenshot_desktop(self, output_path: str) -> str:
        """
        Capture full desktop screenshot.
        
        Args:
            output_path: Path where screenshot should be saved
            
        Returns:
            Path to saved screenshot file
        """
        logger.info("Capturing desktop screenshot")
        
        if MSS_AVAILABLE:
            return self._screenshot_desktop_mss(output_path)
        else:
            return self._screenshot_desktop_platform_specific(output_path)
    
    def screenshot_area(self, x: int, y: int, width: int, height: int, output_path: str) -> str:
        """
        Capture specific rectangular area of screen.
        
        Args:
            x, y: Top-left coordinates
            width, height: Area dimensions  
            output_path: Path where screenshot should be saved
            
        Returns:
            Path to saved screenshot file
        """
        logger.info(f"Capturing area screenshot: {x},{y} {width}x{height}")
        
        if MSS_AVAILABLE:
            return self._screenshot_area_mss(x, y, width, height, output_path)
        else:
            return self._screenshot_area_platform_specific(x, y, width, height, output_path)
    
    # Linux implementations
    def _screenshot_window_linux(self, window_title: str, output_path: str) -> str:
        """Linux window screenshot implementation."""
        if self.session_type == "wayland":
            return self._screenshot_window_linux_wayland(window_title, output_path)
        else:
            return self._screenshot_window_linux_x11(window_title, output_path)
    
    def _screenshot_window_linux_x11(self, window_title: str, output_path: str) -> str:
        """Linux X11 window screenshot using ImageMagick + xdotool."""
        try:
            # Try to find window ID using xdotool
            cmd_find = ["xdotool", "search", "--name", window_title]
            result = subprocess.run(cmd_find, capture_output=True, text=True, check=True)
            
            window_ids = result.stdout.strip().split('\\n')
            if not window_ids or not window_ids[0]:
                raise Exception(f"Window not found: {window_title}")
            
            window_id = window_ids[0]  # Use first match
            
            # Capture screenshot using ImageMagick import
            cmd_screenshot = ["import", "-window", window_id, output_path]
            subprocess.run(cmd_screenshot, check=True)
            
            logger.info(f"X11 window screenshot saved: {output_path}")
            return output_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"X11 screenshot command failed: {e}")
            # Fallback to cross-platform method
            return self._screenshot_window_crossplatform(window_title, output_path)
        except FileNotFoundError:
            logger.warning("xdotool or import not found, falling back to cross-platform method")
            return self._screenshot_window_crossplatform(window_title, output_path)
    
    def _screenshot_window_linux_wayland(self, window_title: str, output_path: str) -> str:
        """Linux Wayland window screenshot using GNOME Screenshot."""
        try:
            # GNOME Screenshot doesn't support window by name directly
            # Fall back to interactive window selection or cross-platform method
            logger.warning("Wayland window-specific screenshot limited, using cross-platform fallback")
            return self._screenshot_window_crossplatform(window_title, output_path)
            
        except Exception as e:
            logger.error(f"Wayland screenshot failed: {e}")
            return self._screenshot_window_crossplatform(window_title, output_path)
    
    # macOS implementations
    def _screenshot_window_macos(self, window_title: str, output_path: str) -> str:
        """macOS window screenshot using screencapture."""
        try:
            # Try to get window ID for specific application
            # This is a simplified approach - could be enhanced with pyobjc
            cmd = ["screencapture", "-w", output_path]
            
            # Note: This opens interactive window selection
            # Could be enhanced to find specific window programmatically
            logger.warning("macOS window screenshot using interactive selection")
            subprocess.run(cmd, check=True)
            
            logger.info(f"macOS window screenshot saved: {output_path}")
            return output_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"macOS screenshot command failed: {e}")
            return self._screenshot_window_crossplatform(window_title, output_path)
    
    # Windows implementations  
    def _screenshot_window_windows(self, window_title: str, output_path: str) -> str:
        """Windows window screenshot using Win32 API."""
        try:
            # Use cross-platform method as primary approach for Windows
            return self._screenshot_window_crossplatform(window_title, output_path)
            
        except Exception as e:
            logger.error(f"Windows screenshot failed: {e}")
            raise
    
    # Cross-platform implementations
    def _screenshot_window_crossplatform(self, window_title: str, output_path: str) -> str:
        """Cross-platform window screenshot using pygetwindow + mss."""
        if not PYGETWINDOW_AVAILABLE or not MSS_AVAILABLE:
            raise Exception("pygetwindow and mss required for cross-platform window screenshots")
        
        try:
            # Find windows with matching title
            windows = gw.getWindowsWithTitle(window_title)
            if not windows:
                # Try partial match
                all_windows = gw.getAllWindows()
                windows = [w for w in all_windows if window_title.lower() in w.title.lower()]
            
            if not windows:
                raise Exception(f"Window not found: {window_title}")
            
            window = windows[0]  # Use first match
            
            # Get window bounds
            bbox = (window.left, window.top, window.right, window.bottom)
            
            # Capture screenshot
            with mss.mss() as sct:
                screenshot = sct.grab(bbox)
                mss.tools.to_png(screenshot.rgb, screenshot.size, output=output_path)
            
            logger.info(f"Cross-platform window screenshot saved: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Cross-platform window screenshot failed: {e}")
            raise
    
    def _screenshot_desktop_mss(self, output_path: str) -> str:
        """Desktop screenshot using mss library."""
        try:
            with mss.mss() as sct:
                # Capture all monitors
                screenshot = sct.grab(sct.monitors[0])  # Monitor 0 is all monitors combined
                mss.tools.to_png(screenshot.rgb, screenshot.size, output=output_path)
            
            logger.info(f"MSS desktop screenshot saved: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"MSS desktop screenshot failed: {e}")
            raise
    
    def _screenshot_desktop_platform_specific(self, output_path: str) -> str:
        """Platform-specific desktop screenshot fallback."""
        if self.platform == "linux":
            if self.session_type == "wayland":
                cmd = ["gnome-screenshot", "-f", output_path]
            else:
                cmd = ["import", "-window", "root", output_path]
        elif self.platform == "darwin":
            cmd = ["screencapture", output_path]
        elif self.platform == "windows":
            # PowerShell approach for Windows
            raise Exception("Platform-specific Windows desktop screenshot not implemented")
        else:
            raise Exception(f"Unsupported platform: {self.platform}")
        
        try:
            subprocess.run(cmd, check=True)
            logger.info(f"Platform-specific desktop screenshot saved: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Platform-specific desktop screenshot failed: {e}")
            raise
    
    def _screenshot_area_mss(self, x: int, y: int, width: int, height: int, output_path: str) -> str:
        """Area screenshot using mss library."""
        try:
            bbox = (x, y, x + width, y + height)
            
            with mss.mss() as sct:
                screenshot = sct.grab(bbox)
                mss.tools.to_png(screenshot.rgb, screenshot.size, output=output_path)
            
            logger.info(f"MSS area screenshot saved: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"MSS area screenshot failed: {e}")
            raise
    
    def _screenshot_area_platform_specific(self, x: int, y: int, width: int, height: int, output_path: str) -> str:
        """Platform-specific area screenshot fallback."""
        if self.platform == "linux":
            if self.session_type == "wayland":
                # GNOME Screenshot area selection
                cmd = ["gnome-screenshot", "-a", "-f", output_path]
            else:
                # ImageMagick with geometry
                geometry = f"{width}x{height}+{x}+{y}"
                cmd = ["import", "-window", "root", "-crop", geometry, output_path]
        elif self.platform == "darwin":
            # screencapture with region
            cmd = ["screencapture", "-R", f"{x},{y},{width},{height}", output_path]
        else:
            raise Exception(f"Platform-specific area screenshot not supported: {self.platform}")
        
        try:
            subprocess.run(cmd, check=True)
            logger.info(f"Platform-specific area screenshot saved: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Platform-specific area screenshot failed: {e}")
            raise