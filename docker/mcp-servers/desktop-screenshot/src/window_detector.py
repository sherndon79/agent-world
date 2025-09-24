"""
Window Detector

Cross-platform window enumeration and search functionality.
Finds windows by title, process name, and other criteria.
"""

import platform
import subprocess
import logging
from typing import List, Dict, Any, Optional

try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except (ImportError, NotImplementedError):
    PYGETWINDOW_AVAILABLE = False

logger = logging.getLogger(__name__)


class WindowDetector:
    """
    Cross-platform window detection and enumeration.
    
    Provides unified interface for finding and listing windows across
    Windows, macOS, and Linux platforms.
    """
    
    def __init__(self):
        """Initialize window detector with platform detection."""
        self.platform = platform.system().lower()
        self.session_type = self._detect_session_type()
        
        logger.info(f"Window detector initialized for {self.platform}")
        
        # Check available libraries
        if not PYGETWINDOW_AVAILABLE:
            logger.warning("pygetwindow not available, using platform-specific methods")
    
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
    
    def list_windows(self) -> List[Dict[str, Any]]:
        """
        List all open windows with their properties.
        
        Returns:
            List of dictionaries containing window information:
            - title: Window title/name
            - pid: Process ID (if available)
            - process: Process name (if available)
            - geometry: Window bounds (if available)
        """
        logger.info("Listing all open windows")
        
        if PYGETWINDOW_AVAILABLE:
            try:
                return self._list_windows_crossplatform()
            except Exception as e:
                logger.warning(f"Cross-platform window listing failed: {e}")
        
        # Fallback to platform-specific methods
        if self.platform == "linux":
            return self._list_windows_linux()
        elif self.platform == "darwin":
            return self._list_windows_macos()
        elif self.platform == "windows":
            return self._list_windows_windows()
        else:
            logger.error(f"Unsupported platform: {self.platform}")
            return []
    
    def find_windows_by_title(self, title: str, exact_match: bool = False) -> List[Dict[str, Any]]:
        """
        Find windows by title.
        
        Args:
            title: Window title to search for
            exact_match: If True, require exact title match; if False, allow partial matches
            
        Returns:
            List of matching window dictionaries
        """
        logger.info(f"Searching for windows with title: {title} (exact={exact_match})")
        
        all_windows = self.list_windows()
        matching_windows = []
        
        for window in all_windows:
            window_title = window.get('title', '')
            if not window_title:
                continue
                
            if exact_match:
                if window_title == title:
                    matching_windows.append(window)
            else:
                if title.lower() in window_title.lower():
                    matching_windows.append(window)
        
        logger.info(f"Found {len(matching_windows)} matching windows")
        return matching_windows
    
    def find_windows_by_process(self, process_name: str) -> List[Dict[str, Any]]:
        """
        Find windows by process name.
        
        Args:
            process_name: Process name to search for
            
        Returns:
            List of matching window dictionaries
        """
        logger.info(f"Searching for windows with process: {process_name}")
        
        all_windows = self.list_windows()
        matching_windows = []
        
        for window in all_windows:
            window_process = window.get('process', '')
            if process_name.lower() in window_process.lower():
                matching_windows.append(window)
        
        logger.info(f"Found {len(matching_windows)} windows for process {process_name}")
        return matching_windows
    
    def get_active_window(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the currently active window.
        
        Returns:
            Dictionary with active window information, or None if not available
        """
        logger.info("Getting active window")
        
        if PYGETWINDOW_AVAILABLE:
            try:
                active_window = gw.getActiveWindow()
                if active_window:
                    return {
                        'title': active_window.title,
                        'geometry': {
                            'x': active_window.left,
                            'y': active_window.top,
                            'width': active_window.width,
                            'height': active_window.height
                        }
                    }
            except Exception as e:
                logger.warning(f"Cross-platform active window detection failed: {e}")
        
        # Platform-specific fallbacks
        if self.platform == "linux":
            return self._get_active_window_linux()
        elif self.platform == "darwin":
            return self._get_active_window_macos()
        elif self.platform == "windows":
            return self._get_active_window_windows()
        
        return None
    
    # Cross-platform implementation
    def _list_windows_crossplatform(self) -> List[Dict[str, Any]]:
        """List windows using pygetwindow (cross-platform)."""
        windows = []
        
        for window in gw.getAllWindows():
            if window.title:  # Only include windows with titles
                window_info = {
                    'title': window.title,
                    'geometry': {
                        'x': window.left,
                        'y': window.top,
                        'width': window.width,
                        'height': window.height
                    }
                }
                windows.append(window_info)
        
        logger.info(f"Found {len(windows)} windows using cross-platform method")
        return windows
    
    # Linux implementations
    def _list_windows_linux(self) -> List[Dict[str, Any]]:
        """List windows on Linux using wmctrl or xdotool."""
        if self.session_type == "wayland":
            return self._list_windows_linux_wayland()
        else:
            return self._list_windows_linux_x11()
    
    def _list_windows_linux_x11(self) -> List[Dict[str, Any]]:
        """List windows on Linux X11 using wmctrl."""
        windows = []
        
        try:
            # Try wmctrl first
            result = subprocess.run(
                ["wmctrl", "-l", "-p"],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.strip().split('\\n'):
                if line:
                    parts = line.split(None, 4)
                    if len(parts) >= 5:
                        window_id, desktop, pid, hostname, title = parts
                        windows.append({
                            'title': title,
                            'pid': int(pid),
                            'window_id': window_id
                        })
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to xdotool
            try:
                result = subprocess.run(
                    ["xdotool", "search", "--name", ".*"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                for window_id in result.stdout.strip().split('\\n'):
                    if window_id:
                        try:
                            title_result = subprocess.run(
                                ["xdotool", "getwindowname", window_id],
                                capture_output=True,
                                text=True,
                                check=True
                            )
                            title = title_result.stdout.strip()
                            if title:
                                windows.append({
                                    'title': title,
                                    'window_id': window_id
                                })
                        except subprocess.CalledProcessError:
                            continue
                            
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning("Neither wmctrl nor xdotool available for window listing")
        
        logger.info(f"Found {len(windows)} windows using Linux X11 method")
        return windows
    
    def _list_windows_linux_wayland(self) -> List[Dict[str, Any]]:
        """List windows on Linux Wayland (limited functionality)."""
        logger.warning("Wayland window listing has limited functionality")
        # Wayland doesn't provide easy window enumeration for security reasons
        # This would require specific compositor support (GNOME Shell extensions, etc.)
        return []
    
    def _get_active_window_linux(self) -> Optional[Dict[str, Any]]:
        """Get active window on Linux."""
        if self.session_type != "wayland":
            try:
                # Get active window ID using xdotool
                result = subprocess.run(
                    ["xdotool", "getactivewindow"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                window_id = result.stdout.strip()
                
                # Get window title
                title_result = subprocess.run(
                    ["xdotool", "getwindowname", window_id],
                    capture_output=True,
                    text=True,
                    check=True
                )
                title = title_result.stdout.strip()
                
                return {
                    'title': title,
                    'window_id': window_id
                }
                
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning("xdotool not available for active window detection")
        
        return None
    
    # macOS implementations
    def _list_windows_macos(self) -> List[Dict[str, Any]]:
        """List windows on macOS using osascript."""
        windows = []
        
        try:
            # AppleScript to get window information
            script = '''
            tell application "System Events"
                set windowList to {}
                repeat with proc in (every application process whose background only is false)
                    try
                        repeat with win in (every window of proc)
                            set windowTitle to name of win
                            if windowTitle is not "" then
                                set end of windowList to {windowTitle, name of proc}
                            end if
                        end repeat
                    end try
                end repeat
                return windowList
            end tell
            '''
            
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse AppleScript output (simplified)
            # This would need more sophisticated parsing in practice
            logger.info("macOS window listing completed (basic implementation)")
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("osascript not available for window listing")
        
        return windows
    
    def _get_active_window_macos(self) -> Optional[Dict[str, Any]]:
        """Get active window on macOS."""
        try:
            script = '''
            tell application "System Events"
                set frontApp to first application process whose frontmost is true
                set appName to name of frontApp
                try
                    set windowTitle to name of front window of frontApp
                    return appName & "|" & windowTitle
                on error
                    return appName & "|"
                end try
            end tell
            '''
            
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                check=True
            )
            
            output = result.stdout.strip()
            if "|" in output:
                app_name, window_title = output.split("|", 1)
                return {
                    'title': window_title,
                    'process': app_name
                }
                
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("osascript not available for active window detection")
        
        return None
    
    # Windows implementations
    def _list_windows_windows(self) -> List[Dict[str, Any]]:
        """List windows on Windows using PowerShell."""
        windows = []
        
        try:
            # PowerShell script to get window information
            script = '''
            Add-Type @"
                using System;
                using System.Runtime.InteropServices;
                using System.Text;
                public class Win32 {
                    [DllImport("user32.dll")]
                    public static extern IntPtr GetForegroundWindow();
                    [DllImport("user32.dll")]
                    public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
                    [DllImport("user32.dll")]
                    public static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);
                    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
                }
            "@
            Get-Process | Where-Object {$_.MainWindowTitle} | Select-Object ProcessName, MainWindowTitle, Id
            '''
            
            result = subprocess.run(
                ["powershell", "-Command", script],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse PowerShell output (simplified)
            logger.info("Windows window listing completed (basic implementation)")
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("PowerShell not available for window listing")
        
        return windows
    
    def _get_active_window_windows(self) -> Optional[Dict[str, Any]]:
        """Get active window on Windows."""
        # This would require Win32 API calls or PowerShell
        # Implementation depends on pywin32 or similar libraries
        logger.info("Windows active window detection not implemented")
        return None