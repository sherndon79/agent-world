"""
WorldStreamer Extension

Isaac Sim RTMP streaming control extension.
Provides API for starting, stopping, and managing RTMP streaming sessions.
"""

import omni.ext
import omni.ui as ui
import carb
import logging
import threading
from pathlib import Path

from .config import get_config
from .security import WorldStreamerAuth
from .api_interface import WorldStreamerAPI
from .streaming import StreamingInterface

logger = logging.getLogger(__name__)


class WorldStreamerExtension(omni.ext.IExt):
    """
    WorldStreamer Extension for Isaac Sim RTMP streaming control.
    
    Provides unified streaming management through modular architecture
    with API endpoints for external control and MCP integration.
    """

    def __init__(self):
        super().__init__()
        # Initialize UI components
        self._window = None
        self._status_label = None
        self._api_status_label = None
        self._api_url_label = None
        self._streaming_status_label = None
        self._streaming_urls_label = None
        self._start_button = None
        self._stop_button = None
        self._ui_update_timer = None
        
        # Thread safety
        self._main_thread_id = threading.get_ident()

    def on_startup(self, ext_id: str):
        """Extension startup initialization."""
        try:
            logger.info("WorldStreamer Extension starting up...")
            
            # Initialize configuration
            self._config = get_config()
            logger.info(f"WorldStreamer configuration loaded successfully")
            
            # Initialize authentication using unified config
            self._auth = WorldStreamerAuth(config=self._config)
            logger.info(f"Authentication {'enabled' if self._auth.is_enabled() else 'disabled'}")
            
            # Initialize streaming interface using unified config
            rtmp_port = self._config.get('rtmp_port', 1935)
            stream_key = "live"  # Default stream key
            try:
                enc_cfg = self._config.get_encoder_config()
                fps = int(enc_cfg.get('encoding_fps', 24))
            except Exception:
                fps = 24
            self._streaming = StreamingInterface(rtmp_port=rtmp_port, stream_key=stream_key, fps=fps)
            
            # Initialize API interface using unified config
            server_port = self._config.get('server_port')
            self._api = WorldStreamerAPI(
                config=self._config,
                auth=self._auth,
                streaming=self._streaming,
                port=server_port
            )
            
            # Start HTTP server
            server_result = self._api.start_server()
            if server_result['success']:
                logger.info(f"WorldStreamer API server started on port {server_port}")
            else:
                logger.error(f"Failed to start API server: {server_result.get('error')}")
                return
            
            # Validate streaming environment
            env_validation = self._streaming.validate_environment()
            if env_validation['valid']:
                logger.info("Streaming environment validation passed")
            else:
                logger.warning(f"Streaming environment issues: {env_validation.get('warnings', [])}")
                if env_validation.get('errors'):
                    logger.error(f"Streaming environment errors: {env_validation['errors']}")
            
            # Create UI window
            self._create_window()
            
            # Start UI update timer
            self._start_ui_update_timer()
            
            # Extension startup complete
            self._ext_id = ext_id
            logger.info(f"WorldStreamer Extension '{ext_id}' started successfully")
            
            # Log startup summary
            self._log_startup_summary()
            
        except Exception as e:
            logger.error(f"WorldStreamer Extension startup failed: {e}")
            raise

    def on_shutdown(self):
        """Extension shutdown cleanup."""
        try:
            logger.info("WorldStreamer Extension shutting down...")
            
            # Stop UI update timer
            if self._ui_update_timer:
                self._ui_update_timer.unsubscribe()
                self._ui_update_timer = None
            
            # Close UI window
            if self._window:
                self._window = None
            
            # Stop streaming if active
            if hasattr(self, '_streaming') and self._streaming:
                try:
                    status = self._streaming.get_streaming_status()
                    if status.get('success') and status['status'].get('is_active'):
                        logger.info("Stopping active streaming session...")
                        stop_result = self._streaming.stop_streaming()
                        if stop_result['success']:
                            logger.info("Streaming stopped successfully")
                        else:
                            logger.warning(f"Failed to stop streaming: {stop_result.get('error')}")
                except Exception as e:
                    logger.warning(f"Error stopping streaming during shutdown: {e}")
            
            # Stop API server
            if hasattr(self, '_api') and self._api:
                try:
                    stop_result = self._api.stop_server()
                    if stop_result['success']:
                        logger.info("API server stopped successfully")
                    else:
                        logger.warning(f"Failed to stop API server: {stop_result.get('error')}")
                except Exception as e:
                    logger.warning(f"Error stopping API server during shutdown: {e}")
            
            # Clean up resources
            self._cleanup_resources()
            
            logger.info("WorldStreamer Extension shutdown complete")
            
        except Exception as e:
            logger.error(f"WorldStreamer Extension shutdown error: {e}")

    def _log_startup_summary(self):
        """Log extension startup summary information."""
        try:
            summary_lines = [
                "=== WorldStreamer Extension Startup Summary ===",
                f"Extension ID: {getattr(self, '_ext_id', 'unknown')}",
                f"API Server Port: {self._config.get('server_port')}",
                f"RTMP Streaming Port: {self._config.get('rtmp_port')}",
                f"Authentication: {'Enabled' if self._auth.is_enabled() else 'Disabled'}",
            ]
            
            # Add streaming environment status
            try:
                env_status = self._streaming.validate_environment()
                summary_lines.append(f"Environment Valid: {env_status.get('valid', 'unknown')}")
            except Exception:
                summary_lines.append("Environment Valid: unknown")
            
            # Add connection info
            try:
                urls = self._streaming.get_streaming_urls()
                if urls.get('success'):
                    rtmp_url = urls['urls'].get('rtmp_stream_url', 'not available')
                    summary_lines.append(f"RTMP Streaming URL: {rtmp_url}")
            except Exception:
                summary_lines.append("RTMP Streaming URL: not available")
            
            summary_lines.append("=" * 50)
            
            for line in summary_lines:
                logger.info(line)
                
        except Exception as e:
            logger.warning(f"Failed to generate startup summary: {e}")

    def _cleanup_resources(self):
        """Clean up extension resources."""
        try:
            # Reset streaming interface
            if hasattr(self, '_streaming') and self._streaming:
                self._streaming.reset()
            
            # Clear references
            self._streaming = None
            self._api = None
            self._auth = None
            self._config = None
            # Cleanup performed by individual components
            
        except Exception as e:
            logger.warning(f"Resource cleanup error: {e}")

    def get_streaming_interface(self) -> 'StreamingInterface':
        """
        Get the streaming interface for programmatic access.
        
        Returns:
            StreamingInterface instance
        """
        return getattr(self, '_streaming', None)

    def get_api_interface(self) -> 'WorldStreamerAPI':
        """
        Get the API interface for programmatic access.
        
        Returns:
            WorldStreamerAPI instance
        """
        return getattr(self, '_api', None)

    def get_extension_info(self) -> dict:
        """
        Get extension information and status.
        
        Returns:
            Dict with extension information
        """
        try:
            info = {
                'extension_id': getattr(self, '_ext_id', 'unknown'),
                'name': 'WorldStreamer',
                'version': '1.0.0',
                'status': 'active',
                'config_available': self._config is not None,
                'authentication_enabled': self._auth.is_enabled() if hasattr(self, '_auth') else False
            }
            
            # Add streaming status if available
            if hasattr(self, '_streaming') and self._streaming:
                try:
                    streaming_status = self._streaming.get_streaming_status()
                    if streaming_status.get('success'):
                        info['streaming_status'] = streaming_status['status']
                except Exception:
                    info['streaming_status'] = 'unavailable'
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get extension info: {e}")
            return {
                'extension_id': 'unknown',
                'name': 'WorldStreamer',
                'status': 'error',
                'error': str(e)
            }

    def _is_main_thread(self) -> bool:
        """Check if we're running on the main thread."""
        return threading.get_ident() == self._main_thread_id

    def _create_window(self):
        """Create the extension's UI window."""
        if not self._is_main_thread():
            logger.warning("UI creation called from non-main thread, skipping")
            return
            
        try:
            self._window = ui.Window("Agent WorldStreamer (RTMP)", width=320, height=300)
            
            with self._window.frame:
                with ui.VStack(spacing=2):
                    # Title section
                    with ui.HStack(height=0):
                        ui.Label("Agent WorldStreamer (RTMP) Extension", style={"font_size": 14})
                    ui.Separator(height=2)
                    
                    # Status section
                    with ui.CollapsableFrame("Status", collapsed=False, height=0):
                        with ui.VStack(spacing=1):
                            self._status_label = ui.Label("Extension: Active")
                            
                            ui.Spacer(height=2)
                            ui.Label("HTTP API:", style={"font_size": 12})
                            self._api_status_label = ui.Label("Server: Starting...")
                            self._api_url_label = ui.Label("URL: Starting...")
                            
                            ui.Spacer(height=2)
                            ui.Label("RTMP Streaming:", style={"font_size": 12})
                            self._streaming_status_label = ui.Label("Status: Not active")
                            self._streaming_urls_label = ui.Label("URLs: Not available")
                    
                    # Controls section
                    with ui.CollapsableFrame("Streaming Controls", collapsed=False, height=0):
                        with ui.VStack(spacing=2):
                            with ui.HStack(height=0):
                                self._start_button = ui.Button("Start Streaming", clicked_fn=self._on_start_streaming)
                                self._stop_button = ui.Button("Stop Streaming", clicked_fn=self._on_stop_streaming)
                            
                            # Initially disable stop button
                            self._stop_button.enabled = False
                            
        except Exception as e:
            logger.error(f"Failed to create UI window: {e}")

    def _start_ui_update_timer(self):
        """Start the timer for updating UI periodically."""
        try:
            import omni.kit.app
            
            def update_ui(dt):
                """Update UI with current status - called from main thread."""
                if self._is_main_thread():
                    # Update UI
                    self._update_ui()
                    
                    # Capture viewport frames for streaming (main thread only)
                    if self._streaming:
                        try:
                            self._streaming.capture_frame_on_main_thread()
                        except Exception as e:
                            # Don't spam logs with capture errors
                            if hasattr(self, '_last_capture_error'):
                                if str(e) != self._last_capture_error:
                                    logger.warning(f"Main thread viewport capture failed: {e}")
                                    self._last_capture_error = str(e)
                            else:
                                logger.warning(f"Main thread viewport capture failed: {e}")
                                self._last_capture_error = str(e)
                
            # Create timer to update UI every 1 second
            update_stream = omni.kit.app.get_app().get_update_event_stream()
            self._ui_update_timer = update_stream.create_subscription_to_pop(
                update_ui, name="worldstreamer_ui_update_timer"
            )
            
        except Exception as e:
            logger.error(f"Failed to start UI update timer: {e}")

    def _update_ui(self):
        """Update UI with current status - must be called from main thread."""
        if not self._is_main_thread() or not self._window:
            return
            
        try:
            # Update API status
            if hasattr(self, '_api') and self._api:
                api_status = self._api.get_server_status()
                if api_status.get('running', False):
                    self._api_status_label.text = "Server: Running"
                    port = api_status.get('port', 'unknown')
                    self._api_url_label.text = f"URL: http://localhost:{port}"
                else:
                    self._api_status_label.text = "Server: Stopped"
                    self._api_url_label.text = "URL: Not available"
            
            # Update streaming status
            if hasattr(self, '_streaming') and self._streaming:
                try:
                    streaming_status = self._streaming.get_streaming_status()
                    if streaming_status.get('success'):
                        status = streaming_status['status']
                        is_active = status.get('is_active', False)
                        
                        if is_active:
                            self._streaming_status_label.text = "Status: Active"
                            self._start_button.enabled = False
                            self._stop_button.enabled = True
                        else:
                            self._streaming_status_label.text = "Status: Not active"
                            self._start_button.enabled = True
                            self._stop_button.enabled = False
                        
                        # Update RTMP URLs
                        try:
                            urls_result = self._streaming.get_streaming_urls()
                            if urls_result.get('success'):
                                urls = urls_result['urls']
                                rtmp_url = urls.get('rtmp_stream_url', 'Not available')
                                self._streaming_urls_label.text = f"RTMP: {rtmp_url[:30]}..."
                            else:
                                self._streaming_urls_label.text = "URLs: Not available"
                        except Exception:
                            self._streaming_urls_label.text = "URLs: Error"
                    else:
                        self._streaming_status_label.text = "Status: Error"
                        self._streaming_urls_label.text = "URLs: Not available"
                        self._start_button.enabled = True
                        self._stop_button.enabled = False
                        
                except Exception as e:
                    self._streaming_status_label.text = f"Status: Error - {str(e)[:20]}..."
                    self._streaming_urls_label.text = "URLs: Not available"
                    self._start_button.enabled = True
                    self._stop_button.enabled = False
            
        except Exception as e:
            logger.debug(f"UI update error: {e}")

    def _on_start_streaming(self):
        """Handle start streaming button click."""
        if not self._is_main_thread():
            logger.warning("Start streaming called from non-main thread")
            return
            
        try:
            if hasattr(self, '_streaming') and self._streaming:
                logger.info("Starting streaming from UI...")
                result = self._streaming.start_streaming()
                if result.get('success'):
                    logger.info("Streaming started successfully from UI")
                    # UI will update automatically via timer
                else:
                    logger.warning(f"Failed to start streaming from UI: {result.get('error')}")
            else:
                logger.warning("No streaming interface available")
        except Exception as e:
            logger.error(f"Error starting streaming from UI: {e}")

    def _on_stop_streaming(self):
        """Handle stop streaming button click."""
        if not self._is_main_thread():
            logger.warning("Stop streaming called from non-main thread")
            return
            
        try:
            if hasattr(self, '_streaming') and self._streaming:
                logger.info("Stopping streaming from UI...")
                result = self._streaming.stop_streaming()
                if result.get('success'):
                    logger.info("Streaming stopped successfully from UI")
                    # UI will update automatically via timer
                else:
                    logger.warning(f"Failed to stop streaming from UI: {result.get('error')}")
            else:
                logger.warning("No streaming interface available")
        except Exception as e:
            logger.error(f"Error stopping streaming from UI: {e}")
