"""
Streaming Interface for WorldStreamer

Core RTMP streaming control interface for Isaac Sim viewport capture.
Provides 24fps continuous viewport streaming with external encoding pipeline.
"""

import logging
import threading
import time
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from collections import deque
import queue

# Import viewport capture utilities from Isaac Sim
try:
    from omni.kit.viewport.utility import get_active_viewport, get_active_viewport_window
    VIEWPORT_AVAILABLE = True
except ImportError:
    VIEWPORT_AVAILABLE = False

from .status_tracker import StatusTracker, StreamingState
from .environment_detector import EnvironmentDetector
from .connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


class StreamingInterface:
    """
    Core RTMP streaming interface for Isaac Sim viewport capture.
    
    Provides unified streaming control with 24fps viewport capture
    and external encoding pipeline (GStreamer/NVENC/fallbacks).
    """
    
    def __init__(self, rtmp_port: int = 1935, stream_key: str = "live", fps: int = 24):
        """
        Initialize streaming interface.
        
        Args:
            rtmp_port: RTMP server port (default 1935)
            stream_key: RTMP stream key/path (default "live")
        """
        self._rtmp_port = rtmp_port
        self._stream_key = stream_key
        self._fps = int(fps) if fps and fps > 0 else 24  # Default 24fps
        
        # Streaming state
        self._is_streaming = False
        self._stream_start_time = None
        self._last_error = None
        self._frame_count = 0
        self._stream_thread = None
        self._stop_event = threading.Event()
        
        # Main thread viewport capture system
        self._frame_queue = queue.Queue(maxsize=5)  # Small queue to prevent memory buildup
        self._viewport_capture_active = False
        
        # Viewport capture state
        self._viewport = None
        self._resolution = (640, 480)  # Smaller default for testing
        
        # Initialize specialized modules
        self._environment_detector = EnvironmentDetector()
        self._connection_manager = ConnectionManager()
        self._status_tracker = StatusTracker()
        
        # Encoding pipeline (to be initialized on start)
        self._encoder = None
        
        logger.info(f"StreamingInterface initialized - RTMP port: {rtmp_port}, Stream key: {stream_key}")
    
    def capture_frame_on_main_thread(self) -> bool:
        """
        Capture viewport frame on main thread and queue it for streaming.
        Called from extension's main thread update subscription.
        
        Returns:
            True if capture successful, False otherwise
        """
        # Keep this lightweight; runs on Isaac main thread every tick
        logger.debug(f"capture_frame_on_main_thread active={self._viewport_capture_active}")
        
        if not self._viewport_capture_active:
            logger.debug("Early return: viewport_capture_active is False")
            return False
            
        try:
            # Drop oldest frame if queue is full (avoid blocking main thread)
            if self._frame_queue.full():
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    pass

            # Capture frame using main thread context
            import numpy as np
            import omni.kit.viewport.utility as vp_util

            viewport_api = vp_util.get_active_viewport()
            if not viewport_api:
                logger.warning("No viewport API found, returning False")
                return False

            captured_buffer = None

            def buffer_callback(buffer, buffer_size, width, height, format):
                nonlocal captured_buffer
                try:
                    if not (buffer and buffer_size > 0 and width > 0 and height > 0):
                        return
                    # Prefer buffer protocol; fall back to PyCapsule pointer extraction
                    try:
                        buffer_array = np.frombuffer(buffer, dtype=np.uint8)
                    except Exception:
                        try:
                            import ctypes
                            content = ctypes.pythonapi.PyCapsule_GetPointer(buffer, None)
                            pointer = ctypes.cast(content, ctypes.POINTER(ctypes.c_ubyte * buffer_size))
                            buffer_array = np.frombuffer(pointer.contents, dtype=np.uint8)
                        except Exception as e:
                            logger.error(f"Viewport buffer conversion failed: {e}")
                            return
                    # Convert to RGB layout (no channel swapping)
                    if format == "RGBA" or buffer_size == width * height * 4:
                        frame_rgba = buffer_array.reshape((height, width, 4))
                        # Drop alpha, preserve channel order as RGB
                        captured_buffer = frame_rgba[:, :, :3].copy()
                    elif format == "RGB" or buffer_size == width * height * 3:
                        # Already RGB; reshape and use as-is
                        captured_buffer = buffer_array.reshape((height, width, 3))
                except Exception as e:
                    logger.error(f"Main thread buffer callback failed: {e}")

                # Enqueue immediately if possible (non-blocking)
                try:
                    if captured_buffer is not None:
                        buffer_height, buffer_width = captured_buffer.shape[:2]
                        if (buffer_width, buffer_height) != self._resolution:
                            self._resolution = (buffer_width, buffer_height)
                        self._frame_queue.put_nowait(captured_buffer.tobytes())
                except Exception:
                    pass

            # Kick off capture; do NOT block the main thread.
            vp_util.capture_viewport_to_buffer(viewport_api, buffer_callback)

            # Return immediately; callback will enqueue when ready
            return True

        except Exception as e:
            logger.error(f"Main thread viewport capture failed: {e}")
            return False
    
    def start_streaming(self, server_ip: Optional[str] = None) -> Dict[str, Any]:
        """
        Start RTMP streaming of Isaac Sim viewport.
        
        Args:
            server_ip: Optional server IP override for RTMP URLs
            
        Returns:
            Dict with streaming start results
        """
        try:
            # Check if already streaming
            if self._is_streaming:
                logger.warning("Streaming already active")
                return {
                    'success': False,
                    'error': 'Streaming is already active',
                    'status': self._status_tracker.get_streaming_status()
                }
            
            # Set starting state
            self._status_tracker.set_streaming_state(StreamingState.STARTING)
            
            # Validate environment for viewport capture and encoding
            env_validation = self.validate_environment()
            if not env_validation['valid']:
                error_msg = f"Environment validation failed: {'; '.join(env_validation['errors'])}"
                self._status_tracker.set_error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'validation': env_validation
                }
            
            # Initialize viewport capture
            viewport_result = self._initialize_viewport_capture()
            if not viewport_result['success']:
                self._status_tracker.set_error(viewport_result['error'])
                return viewport_result
            
            # Initialize encoding pipeline
            encoder_result = self._initialize_encoder()
            if not encoder_result['success']:
                self._status_tracker.set_error(encoder_result['error'])
                return encoder_result
            
            # Start streaming thread
            self._stop_event.clear()
            self._stream_thread = threading.Thread(
                target=self._streaming_loop,
                name="WorldStreamer-Viewport-Capture",
                daemon=True
            )
            self._stream_thread.start()
            
            # Generate streaming URLs
            url_result = self._connection_manager.generate_streaming_urls(
                self._rtmp_port, server_ip, stream_key=self._stream_key
            )
            
            if url_result['success']:
                # Update stream info and set active state
                self._status_tracker.update_stream_info(self._rtmp_port, url_result['urls'])
                self._status_tracker.set_streaming_state(StreamingState.ACTIVE, {
                    'fps': self._fps,
                    'resolution': f"{self._resolution[0]}x{self._resolution[1]}",
                    'encoder': self._encoder.get_info() if self._encoder else 'none',
                    'start_method': 'api',
                    'server_ip_override': server_ip
                })
                
                self._is_streaming = True
                self._stream_start_time = datetime.utcnow()
                self._frame_count = 0
                
                # Enable main thread viewport capture
                self._viewport_capture_active = True
                logger.info("Main thread viewport capture enabled")
                
                logger.info(f"RTMP streaming started successfully on port {self._rtmp_port}")
                
                return {
                    'success': True,
                    'message': 'Streaming started successfully',
                    'streaming_info': {
                        'rtmp_port': self._rtmp_port,
                        'fps': self._fps,
                        'resolution': self._resolution,
                        'urls': url_result['urls'],
                        'start_time': self._stream_start_time.isoformat()
                    },
                    'status': self._status_tracker.get_streaming_status()
                }
            else:
                error_msg = f"URL generation failed: {url_result.get('error', 'Unknown error')}"
                self._status_tracker.set_error(error_msg)
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            error_msg = f"Failed to start streaming: {e}"
            logger.error(error_msg)
            self._status_tracker.set_error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def stop_streaming(self) -> Dict[str, Any]:
        """
        Stop RTMP streaming.
        
        Returns:
            Dict with streaming stop results
        """
        try:
            # Check if streaming is active
            if not self._is_streaming:
                logger.warning("No active streaming to stop")
                return {
                    'success': False,
                    'error': 'No active streaming session',
                    'status': self._status_tracker.get_streaming_status()
                }
            
            # Set stopping state
            self._status_tracker.set_streaming_state(StreamingState.STOPPING)
            
            # Signal streaming thread to stop
            self._stop_event.set()
            
            # Wait for streaming thread to finish
            if self._stream_thread and self._stream_thread.is_alive():
                self._stream_thread.join(timeout=5.0)
                if self._stream_thread.is_alive():
                    logger.warning("Streaming thread did not stop cleanly")
            
            # Cleanup encoder
            if self._encoder:
                try:
                    self._encoder.stop()
                    self._encoder = None
                except Exception as e:
                    logger.warning(f"Error stopping encoder: {e}")
            
            # Update state
            self._status_tracker.set_streaming_state(StreamingState.INACTIVE, {
                'stop_method': 'api',
                'stop_time': datetime.utcnow().isoformat(),
                'total_frames': self._frame_count
            })
            
            self._is_streaming = False
            self._viewport_capture_active = False  # Disable main thread capture
            logger.info("Main thread viewport capture disabled")
            
            duration = None
            if self._stream_start_time:
                duration = (datetime.utcnow() - self._stream_start_time).total_seconds()
            
            logger.info("RTMP streaming stopped successfully")
            
            return {
                'success': True,
                'message': 'Streaming stopped successfully',
                'session_info': {
                    'duration_seconds': duration,
                    'total_frames': self._frame_count,
                    'average_fps': self._frame_count / duration if duration and duration > 0 else 0,
                    'stop_time': datetime.utcnow().isoformat()
                },
                'status': self._status_tracker.get_streaming_status()
            }
            
        except Exception as e:
            error_msg = f"Failed to stop streaming: {e}"
            logger.error(error_msg)
            self._status_tracker.set_error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_streaming_status(self) -> Dict[str, Any]:
        """
        Get comprehensive streaming status.
        
        Returns:
            Dict with complete streaming status
        """
        try:
            # Get base status from tracker
            status = self._status_tracker.get_streaming_status()
            
            # Add interface-level information
            status.update({
                'interface_active': self._is_streaming,
                'rtmp_port': self._rtmp_port,
                'fps': self._fps,
                'frame_count': self._frame_count,
                'resolution': self._resolution,
                'viewport_available': VIEWPORT_AVAILABLE and self._viewport is not None,
                'encoder_active': self._encoder is not None and self._encoder.is_active() if self._encoder else False
            })
            
            # Add uptime if streaming
            if self._is_streaming and self._stream_start_time:
                uptime = (datetime.utcnow() - self._stream_start_time).total_seconds()
                status['uptime_seconds'] = uptime
                status['average_fps'] = self._frame_count / uptime if uptime > 0 else 0
            
            # Add connection information
            connection_status = self._connection_manager.get_connection_status()
            status['connection_info'] = connection_status
            
            return {
                'success': True,
                'status': status
            }
            
        except Exception as e:
            logger.error(f"Failed to get streaming status: {e}")
            return {
                'success': False,
                'error': f"Status retrieval failed: {e}"
            }
    
    def get_streaming_urls(self, server_ip: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current streaming URLs.
        
        Args:
            server_ip: Optional server IP override
            
        Returns:
            Dict with streaming URLs
        """
        try:
            return self._connection_manager.generate_streaming_urls(
                self._rtmp_port, server_ip, stream_key=self._stream_key
            )
        except Exception as e:
            logger.error(f"Failed to get streaming URLs: {e}")
            return {
                'success': False,
                'error': f"URL generation failed: {e}"
            }
    
    def validate_environment(self) -> Dict[str, Any]:
        """
        Validate streaming environment.
        
        Returns:
            Dict with validation results
        """
        try:
            # Check viewport availability
            if not VIEWPORT_AVAILABLE:
                return {
                    'valid': False,
                    'errors': ['Isaac Sim viewport utilities not available'],
                    'warnings': [],
                    'recommendations': ['Ensure Isaac Sim is properly initialized']
                }
            
            # Use environment detector for encoding capabilities
            env_result = self._environment_detector.validate_isaac_environment()
            
            # Add viewport-specific checks
            try:
                viewport = get_active_viewport()
                if viewport is None:
                    env_result['warnings'].append('No active viewport detected')
                else:
                    env_result['recommendations'].append('Viewport capture ready')
            except Exception as e:
                env_result['warnings'].append(f'Viewport check failed: {e}')
            
            return env_result
            
        except Exception as e:
            logger.error(f"Environment validation failed: {e}")
            return {
                'valid': False,
                'errors': [f"Validation error: {e}"],
                'warnings': [],
                'recommendations': []
            }
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get streaming interface health status.
        
        Returns:
            Dict with health information
        """
        try:
            return {
                'streaming_interface_functional': True,
                'is_streaming': self._is_streaming,
                'rtmp_port': self._rtmp_port,
                'fps': self._fps,
                'viewport_available': VIEWPORT_AVAILABLE,
                'encoder_available': self._encoder is not None,
                'frame_count': self._frame_count,
                'status_tracker': self._status_tracker.get_health_status(),
                'connection_manager': self._connection_manager.get_connection_status(),
                'environment_detector': {
                    'functional': True,
                    'environment_valid': self._environment_detector.is_environment_valid()
                }
            }
        except Exception as e:
            logger.error(f"Health status check failed: {e}")
            return {
                'streaming_interface_functional': False,
                'error': str(e)
            }
    
    def _initialize_viewport_capture(self) -> Dict[str, Any]:
        """
        Initialize Isaac Sim viewport capture.
        
        Returns:
            Dict with initialization result
        """
        try:
            if not VIEWPORT_AVAILABLE:
                return {
                    'success': False,
                    'error': 'Viewport utilities not available'
                }
            
            # Get active viewport
            self._viewport = get_active_viewport()
            if self._viewport is None:
                return {
                    'success': False,
                    'error': 'No active viewport found'
                }
            
            # Detect viewport resolution
            try:
                # Try to get resolution from viewport
                if hasattr(self._viewport, 'resolution'):
                    self._resolution = tuple(self._viewport.resolution)
                elif hasattr(self._viewport, 'get_resolution'):
                    self._resolution = tuple(self._viewport.get_resolution())
                else:
                    # Fallback to viewport window
                    vp_window = get_active_viewport_window()
                    if vp_window and hasattr(vp_window, 'get_resolution'):
                        self._resolution = tuple(vp_window.get_resolution())
                    else:
                        logger.warning("Could not detect viewport resolution, using default 640x480")
                        self._resolution = (640, 480)
            except Exception as e:
                logger.warning(f"Resolution detection failed: {e}, using default")
                self._resolution = (640, 480)
            
            logger.info(f"Viewport capture initialized - Resolution: {self._resolution[0]}x{self._resolution[1]}")
            
            return {
                'success': True,
                'resolution': self._resolution,
                'viewport': str(type(self._viewport).__name__)
            }
            
        except Exception as e:
            error_msg = f"Viewport initialization failed: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def _initialize_encoder(self) -> Dict[str, Any]:
        """
        Initialize external encoding pipeline.
        
        Returns:
            Dict with encoder initialization result
        """
        try:
            # TODO: Initialize actual encoder (GStreamer/NVENC/fallback)
            # For now, create a placeholder encoder
            from .encoders import get_best_encoder
            # Pull encoder preferences from unified config if available
            try:
                from ..config import get_config
                enc_cfg = get_config().get_encoder_config()
                bitrate_kbps = int(enc_cfg.get('encoding_bitrate', 2000))
                preferred = enc_cfg.get('encoder_type', 'auto')
            except Exception:
                bitrate_kbps = 2000
                preferred = 'auto'

            self._encoder = get_best_encoder(
                resolution=self._resolution,
                fps=self._fps,
                rtmp_url=f"rtmp://localhost:{self._rtmp_port}/{self._stream_key}",
                bitrate_kbps=bitrate_kbps,
                preferred_type=preferred
            )
            
            if not self._encoder:
                return {
                    'success': False,
                    'error': 'No suitable encoder found'
                }
            
            # Initialize encoder
            init_result = self._encoder.initialize()
            if not init_result['success']:
                return init_result
            
            logger.info(f"Encoder initialized: {self._encoder.get_info()}")
            
            return {
                'success': True,
                'encoder': self._encoder.get_info()
            }
            
        except Exception as e:
            error_msg = f"Encoder initialization failed: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def _streaming_loop(self):
        """
        Main streaming loop - captures viewport at 24fps and feeds to encoder.
        """
        logger.info("Starting viewport capture streaming loop")
        frame_interval = 1.0 / self._fps  # 24fps = ~0.042 seconds per frame
        
        try:
            while not self._stop_event.is_set():
                frame_start = time.time()
                
                try:
                    # Capture viewport frame
                    frame_data = self._capture_viewport_frame()
                    if frame_data:
                        # Send frame to encoder
                        if self._encoder:
                            self._encoder.encode_frame(frame_data)
                        
                        self._frame_count += 1
                        
                        # Log progress periodically
                        if self._frame_count % (self._fps * 10) == 0:  # Every 10 seconds
                            logger.debug(f"Streaming progress: {self._frame_count} frames captured")
                
                except Exception as e:
                    logger.error(f"Frame capture error: {e}")
                    # Continue streaming despite frame errors
                
                # Maintain target framerate
                frame_time = time.time() - frame_start
                sleep_time = max(0, frame_interval - frame_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                elif frame_time > frame_interval * 1.5:
                    logger.warning(f"Frame processing too slow: {frame_time:.3f}s (target: {frame_interval:.3f}s)")
        
        except Exception as e:
            logger.error(f"Streaming loop error: {e}")
            self._status_tracker.set_error(f"Streaming loop failed: {e}")
        
        finally:
            logger.info("Viewport capture streaming loop ended")
    
    def _capture_viewport_frame(self) -> Optional[bytes]:
        """
        Capture a single frame from Isaac Sim viewport using ByteCapture buffer method.
        
        Returns:
            Frame data as bytes, or None if capture failed
        """
        try:
            # Try to get frame from queue (non-blocking)
            try:
                frame_data = self._frame_queue.get_nowait()
                logger.debug(f"Frame dequeued (n={self._frame_count}, q={self._frame_queue.qsize()})")
                return frame_data
            except queue.Empty:
                # No frame available, generate synthetic fallback (debug-only log)
                if self._frame_count % 120 == 0:
                    logger.debug(f"No frame in queue, generating synthetic frame (n={self._frame_count})")
            
                # Generate synthetic fallback frame
                import numpy as np
                height, width = self._resolution[1], self._resolution[0]
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                time_offset = (self._frame_count * 5) % 255
                frame[:, :, 0] = time_offset
                frame[:, :, 1] = (time_offset + 85) % 255
                frame[:, :, 2] = (time_offset + 170) % 255
                return frame.tobytes()
            
            # Debug: Log viewport API found
            if self._frame_count % 120 == 0:
                logger.info(f"Viewport API found: {type(viewport_api).__name__}")
            
            # Use ByteCapture with callback for buffer access
            captured_buffer = None
            capture_complete = threading.Event()
            
            def buffer_callback(buffer, buffer_size, width, height, format):
                """Callback that receives viewport buffer data."""
                nonlocal captured_buffer
                logger.debug(f"Buffer callback: size={buffer_size}, dims={width}x{height}, fmt={format}")
                try:
                    if buffer and buffer_size > 0 and width > 0 and height > 0:
                        # Convert buffer to numpy array
                        # Buffer format is typically RGBA (4 channels)
                        if format == "RGBA" or buffer_size == width * height * 4:
                            # RGBA format: reshape and drop alpha; keep RGB order
                            buffer_array = np.frombuffer(buffer, dtype=np.uint8)
                            frame_rgba = buffer_array.reshape((height, width, 4))
                            captured_buffer = frame_rgba[:, :, :3].copy()
                        elif format == "RGB" or buffer_size == width * height * 3:
                            # RGB format: reshape as-is
                            buffer_array = np.frombuffer(buffer, dtype=np.uint8)
                            captured_buffer = buffer_array.reshape((height, width, 3))
                        else:
                            logger.warning(f"Unknown buffer format: {format}, size: {buffer_size}, dimensions: {width}x{height}")
                            
                        logger.debug(f"Captured buffer: {width}x{height}, format: {format}, size: {buffer_size}")
                        
                    else:
                        logger.warning(f"Invalid buffer data: buffer={bool(buffer)}, size={buffer_size}, dimensions={width}x{height}")
                        
                except Exception as e:
                    logger.error(f"Buffer callback failed: {e}")
                finally:
                    capture_complete.set()
            
            # Use WorldRecorder's proven main thread pattern
            def main_thread_capture_task():
                """Task to execute on main thread"""
                nonlocal captured_buffer
                try:
                    import omni.kit.viewport.utility as vp_util
                    
                    logger.info("Executing capture on Isaac Sim main thread...")
                    
                    # This MUST run on main thread for event loop
                    cap_obj = vp_util.capture_viewport_to_buffer(viewport_api, buffer_callback)
                    logger.info(f"Main thread capture object created: {cap_obj}")
                    
                    return True
                except Exception as e:
                    logger.error(f"Main thread capture task failed: {e}")
                    capture_complete.set()  # Signal completion even on failure
                    return False
            
            try:
                # Execute capture task on main thread and wait for result
                if hasattr(self, '_api_interface') and hasattr(self._api_interface, 'run_on_main'):
                    # Use API interface's main thread runner if available
                    logger.debug("Using API interface main thread runner")
                    result = self._api_interface.run_on_main(main_thread_capture_task, timeout=8.0)
                    if result:
                        # Wait for buffer callback to complete
                        if capture_complete.wait(timeout=5.0):
                            if captured_buffer is not None:
                                logger.debug(f"API interface capture successful, shape={captured_buffer.shape}")
                                buffer_height, buffer_width = captured_buffer.shape[:2]
                                if (buffer_width, buffer_height) != self._resolution:
                                    logger.info(f"Updating resolution from {self._resolution} to {(buffer_width, buffer_height)}")
                                    self._resolution = (buffer_width, buffer_height)
                                return captured_buffer.tobytes()
                            else:
                                logger.warning("API interface capture completed but buffer is None")
                                return None
                        else:
                            logger.debug("API interface capture callback timed out")
                            return None
                    else:
                        logger.debug("API interface main thread execution failed")
                        return None
                else:
                    logger.debug("No API interface main thread runner, using direct approach")
                    # Direct approach will fail but we'll catch it below
                    import omni.kit.viewport.utility as vp_util
                    cap_obj = vp_util.capture_viewport_to_buffer(viewport_api, buffer_callback)
                    logger.info(f"Direct capture object created: {cap_obj}")
                    if capture_complete.wait(timeout=5.0):
                        if captured_buffer is not None:
                            logger.debug(f"Direct capture successful, shape={captured_buffer.shape}")
                            buffer_height, buffer_width = captured_buffer.shape[:2]
                            if (buffer_width, buffer_height) != self._resolution:
                                self._resolution = (buffer_width, buffer_height)
                            return captured_buffer.tobytes()
                        else:
                            return None
                    else:
                        return None
                        
            except RuntimeError as e:
                logger.debug(f"No event loop for async capture: {e}")
                # Fallback to synthetic data
                height, width = self._resolution[1], self._resolution[0]
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                time_offset = (self._frame_count * 5) % 255
                frame[:, :, 0] = time_offset
                frame[:, :, 1] = (time_offset + 85) % 255
                frame[:, :, 2] = (time_offset + 170) % 255
                return frame.tobytes()
                    
            except Exception as e:
                logger.error(f"Viewport capture approach failed: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Viewport frame capture failed: {e}")
            return None
    
    def reset(self):
        """Reset streaming interface to initial state."""
        try:
            # Stop streaming if active
            if self._is_streaming:
                self.stop_streaming()
            
            # Reset modules
            self._status_tracker.reset()
            self._connection_manager.clear_cache()
            
            # Reset interface state
            self._is_streaming = False
            self._stream_start_time = None
            self._last_error = None
            self._frame_count = 0
            self._viewport = None
            self._encoder = None
            
            logger.info("StreamingInterface reset completed")
            
        except Exception as e:
            logger.error(f"Failed to reset StreamingInterface: {e}")
