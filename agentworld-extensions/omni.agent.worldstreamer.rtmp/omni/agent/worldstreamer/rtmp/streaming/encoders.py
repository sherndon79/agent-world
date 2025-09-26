"""
External encoding pipeline for WorldStreamer.

Provides hardware-accelerated video encoding with multiple fallback options:
- NVENC (NVIDIA hardware encoding)
- VA-API (Intel hardware encoding)
- GStreamer software encoding
- OpenCV fallback

Designed for 24fps RTMP streaming from Isaac Sim viewport capture.
Includes secure command injection prevention.
"""

import logging
import subprocess
import threading
import time
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
import queue

# Import secure subprocess utilities
from agentworld_core.subprocess_security import (
    create_secure_rtmp_pipeline,
    validate_gstreamer_element_availability,
    safe_subprocess_run,
    CommandInjectionError
)

logger = logging.getLogger(__name__)


class BaseEncoder(ABC):
    """Base class for video encoders."""
    
    def __init__(self, resolution: Tuple[int, int], fps: int, rtmp_url: str, bitrate_kbps: int = 2000):
        self.resolution = resolution
        self.fps = fps
        self.rtmp_url = rtmp_url
        self.bitrate_kbps = bitrate_kbps
        self._active = False
        
    @abstractmethod
    def initialize(self) -> Dict[str, Any]:
        """Initialize the encoder."""
        pass
    
    @abstractmethod
    def encode_frame(self, frame_data: bytes) -> bool:
        """Encode a single frame."""
        pass
    
    @abstractmethod
    def stop(self):
        """Stop encoding and cleanup."""
        pass
    
    @abstractmethod
    def get_info(self) -> str:
        """Get encoder information string."""
        pass

    
    def is_active(self) -> bool:
        """Check if encoder is active."""
        return self._active


class GStreamerEncoder(BaseEncoder):
    """GStreamer-based encoder with hardware acceleration support."""
    
    def __init__(self, resolution: Tuple[int, int], fps: int, rtmp_url: str, encoder_type: str = "auto", bitrate_kbps: int = 2000):
        super().__init__(resolution, fps, rtmp_url, bitrate_kbps)
        self.encoder_type = encoder_type  # "nvenc", "vaapi", "x264"
        self._process = None
        self._frame_queue = queue.Queue(maxsize=5)  # Smaller buffer to detect issues faster
        self._encoder_thread = None
        self._stop_event = threading.Event()
        
    def initialize(self) -> Dict[str, Any]:
        """Initialize GStreamer encoder pipeline."""
        try:
            # Check GStreamer availability
            if not self._check_gstreamer():
                return {
                    'success': False,
                    'error': 'GStreamer not available'
                }
            
            # Detect best encoder if auto
            if self.encoder_type == "auto":
                self.encoder_type = self._detect_best_encoder()
            
            # Build GStreamer pipeline
            pipeline = self._build_pipeline()
            if not pipeline:
                return {
                    'success': False,
                    'error': f'Failed to build {self.encoder_type} pipeline'
                }
            
            # Start GStreamer process
            try:
                logger.info(f"Starting GStreamer pipeline: {' '.join(pipeline)}")
                # Avoid backpressure on stdio; gst verbose output can block if not drained
                self._process = subprocess.Popen(
                    pipeline,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    bufsize=0
                )
                
                # Start encoder thread
                self._stop_event.clear()
                self._encoder_thread = threading.Thread(
                    target=self._encoder_loop,
                    name="GStreamer-Encoder",
                    daemon=True
                )
                self._encoder_thread.start()
                
                self._active = True
                
                logger.info(f"GStreamer encoder initialized: {self.encoder_type}")
                return {
                    'success': True,
                    'encoder_type': self.encoder_type,
                    'pipeline': ' '.join(pipeline)
                }
                
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Failed to start GStreamer process: {e}'
                }
                
        except Exception as e:
            logger.error(f"GStreamer initialization failed: {e}")
            return {
                'success': False,
                'error': f'GStreamer initialization error: {e}'
            }
    
    def encode_frame(self, frame_data: bytes) -> bool:
        """Queue frame for encoding."""
        try:
            if not self._active:
                return False
            
            # Validate frame size
            expected_size = self.resolution[0] * self.resolution[1] * 3  # RGB
            if len(frame_data) != expected_size:
                logger.error(f"Frame size mismatch: got {len(frame_data)}, expected {expected_size} bytes for {self.resolution[0]}x{self.resolution[1]} RGB")
                return False
            else:
                logger.debug(f"Frame size OK: {len(frame_data)} bytes for {self.resolution[0]}x{self.resolution[1]} RGB")
            
            # Add frame to queue (non-blocking)
            try:
                self._frame_queue.put_nowait(frame_data)
                return True
            except queue.Full:
                # Drop frame if queue is full (maintain real-time performance)
                logger.debug("Encoder queue full, dropping frame")
                return False
                
        except Exception as e:
            logger.error(f"Frame encoding failed: {e}")
            return False
    
    def stop(self):
        """Stop GStreamer encoder."""
        try:
            self._active = False
            self._stop_event.set()
            
            # Stop encoder thread
            if self._encoder_thread and self._encoder_thread.is_alive():
                self._encoder_thread.join(timeout=3.0)
            
            # Stop GStreamer process
            if self._process:
                try:
                    self._process.stdin.close()
                    self._process.terminate()
                    self._process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait()
                except Exception as e:
                    logger.warning(f"Error stopping GStreamer process: {e}")
                finally:
                    self._process = None
            
            # Clear frame queue
            while not self._frame_queue.empty():
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    break
                    
            logger.info("GStreamer encoder stopped")
            
        except Exception as e:
            logger.error(f"Error stopping GStreamer encoder: {e}")
    
    def get_info(self) -> str:
        """Get encoder information."""
        return f"GStreamer-{self.encoder_type} ({self.resolution[0]}x{self.resolution[1]}@{self.fps}fps)"

    
    
    def _check_gstreamer(self) -> bool:
        """Check if GStreamer is available."""
        try:
            result = subprocess.run(['gst-launch-1.0', '--version'], 
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False
    
    def _detect_best_encoder(self) -> str:
        """Detect best available hardware encoder."""
        # Test NVENC (NVIDIA) - highest priority for RTX 4090
        if self._test_encoder_availability('nvh264enc'):
            logger.info("NVENC hardware encoder detected and selected")
            return "nvenc"
        
        # Test VA-API (Intel)  
        if self._test_encoder_availability('vaapih264enc'):
            logger.info("VA-API hardware encoder detected and selected")
            return "vaapi"
        
        # Fallback to software x264
        logger.warning("No hardware encoders available, falling back to x264 software encoding")
        return "x264"
    
    def _test_encoder_availability(self, encoder_element: str) -> bool:
        """Test if a GStreamer encoder element is available using secure validation."""
        try:
            return validate_gstreamer_element_availability(encoder_element)
        except Exception as e:
            logger.debug(f"Error testing encoder availability for {encoder_element}: {e}")
            return False
    
    def _build_pipeline(self) -> Optional[list]:
        """Build secure GStreamer pipeline command with input validation."""
        try:
            width, height = self.resolution

            # Use secure pipeline builder to prevent command injection
            pipeline = create_secure_rtmp_pipeline(
                width=width,
                height=height,
                fps=self.fps,
                bitrate_kbps=self.bitrate_kbps,
                rtmp_url=self.rtmp_url,
                encoder_type=self.encoder_type
            )

            logger.debug(f"Built secure RTMP pipeline with {len(pipeline)} arguments")
            return pipeline

        except CommandInjectionError as e:
            logger.error(f"Security violation in pipeline parameters: {e}")
            return None
        except Exception as e:
            logger.error(f"Pipeline build failed: {e}")
            return None
    
    def _encoder_loop(self):
        """Encoder thread loop - sends frames to GStreamer."""
        logger.info("GStreamer encoder loop started")
        
        try:
            while not self._stop_event.is_set() and self._process:
                try:
                    # Get frame from queue with timeout
                    frame_data = self._frame_queue.get(timeout=1.0)
                    
                    # Send frame to GStreamer
                    if self._process and self._process.stdin and not self._process.stdin.closed:
                        try:
                            self._process.stdin.write(frame_data)
                            self._process.stdin.flush()
                        except ValueError as e:
                            if "closed file" in str(e):
                                logger.debug("Stream stdin closed during write, stopping encoder loop")
                                break
                            else:
                                raise
                    
                except queue.Empty:
                    continue  # Timeout, check stop event
                except BrokenPipeError:
                    logger.error("Broken pipe: RTMP server disconnected or pipeline failed")
                    # Log GStreamer stderr for debugging
                    if self._process and self._process.stderr:
                        try:
                            stderr_output = self._process.stderr.read().decode('utf-8')
                            if stderr_output.strip():
                                logger.error(f"GStreamer stderr: {stderr_output}")
                        except Exception as e:
                            logger.warning(f"Could not read GStreamer stderr: {e}")
                    self._active = False
                    break
                except Exception as e:
                    logger.error(f"Frame processing error: {e}")
                    # Don't immediately stop on other errors - retry a few times
                    continue
                    
        except Exception as e:
            logger.error(f"Encoder loop error: {e}")
        finally:
            logger.info("GStreamer encoder loop ended")


class OpenCVEncoder(BaseEncoder):
    """OpenCV-based fallback encoder."""
    
    def __init__(self, resolution: Tuple[int, int], fps: int, rtmp_url: str):
        super().__init__(resolution, fps, rtmp_url)
        self._writer = None
        
    def initialize(self) -> Dict[str, Any]:
        """Initialize OpenCV encoder."""
        try:
            import cv2
            
            # Use OpenCV VideoWriter with FFMPEG backend
            fourcc = cv2.VideoWriter_fourcc(*'H264')
            
            self._writer = cv2.VideoWriter(
                self.rtmp_url,
                fourcc,
                self.fps,
                self.resolution
            )
            
            if not self._writer.isOpened():
                return {
                    'success': False,
                    'error': 'Failed to open OpenCV VideoWriter'
                }
            
            self._active = True
            logger.info("OpenCV encoder initialized")
            
            return {
                'success': True,
                'encoder_type': 'opencv-h264'
            }
            
        except ImportError:
            return {
                'success': False,
                'error': 'OpenCV not available'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'OpenCV encoder initialization failed: {e}'
            }
    
    def encode_frame(self, frame_data: bytes) -> bool:
        """Encode frame with OpenCV."""
        try:
            if not self._active or not self._writer:
                return False
            
            # Convert frame_data to OpenCV format
            # TODO: Implement proper frame conversion
            # This is a placeholder - need to convert bytes to cv2 image format
            
            # For now, skip actual encoding
            return True
            
        except Exception as e:
            logger.error(f"OpenCV frame encoding failed: {e}")
            return False
    
    def stop(self):
        """Stop OpenCV encoder."""
        try:
            self._active = False
            if self._writer:
                self._writer.release()
                self._writer = None
            logger.info("OpenCV encoder stopped")
        except Exception as e:
            logger.error(f"Error stopping OpenCV encoder: {e}")
    
    def get_info(self) -> str:
        """Get encoder information."""
        return f"OpenCV-H264 ({self.resolution[0]}x{self.resolution[1]}@{self.fps}fps)"


def get_available_encoders() -> Dict[str, bool]:
    """Check which encoders are available on the system."""
    available = {}
    
    # Check GStreamer
    try:
        result = subprocess.run(['gst-launch-1.0', '--version'], 
                              capture_output=True, timeout=5)
        available['gstreamer'] = result.returncode == 0
    except Exception:
        available['gstreamer'] = False
    
    # Check NVENC
    if available['gstreamer']:
        try:
            result = subprocess.run(['gst-inspect-1.0', 'nvh264enc'], 
                                  capture_output=True, timeout=3)
            available['nvenc'] = result.returncode == 0
        except Exception:
            available['nvenc'] = False
    else:
        available['nvenc'] = False
    
    # Check VA-API
    if available['gstreamer']:
        try:
            result = subprocess.run(['gst-inspect-1.0', 'vaapih264enc'], 
                                  capture_output=True, timeout=3)
            available['vaapi'] = result.returncode == 0
        except Exception:
            available['vaapi'] = False
    else:
        available['vaapi'] = False
    
    # Check OpenCV
    try:
        import cv2
        available['opencv'] = True
    except ImportError:
        available['opencv'] = False
    
    return available


def get_best_encoder(resolution: Tuple[int, int], fps: int, rtmp_url: str, bitrate_kbps: int = 2000, preferred_type: str = "auto") -> Optional[BaseEncoder]:
    """
    Get the best available encoder for the system.
    
    Priority:
    1. GStreamer with hardware acceleration (NVENC/VA-API)
    2. GStreamer with software encoding (x264)
    3. OpenCV fallback
    
    Args:
        resolution: Video resolution (width, height)
        fps: Frame rate
        rtmp_url: RTMP output URL
        
    Returns:
        Best available encoder instance, or None if none available
    """
    try:
        available = get_available_encoders()
        
        logger.info(f"Available encoders: {available}")
        
        # Try GStreamer first (best option)
        if available['gstreamer']:
            # Honor preferred encoder type when possible
            enc_type = "auto" if preferred_type not in ("nvenc", "vaapi", "x264") else preferred_type
            encoder = GStreamerEncoder(resolution, fps, rtmp_url, enc_type, bitrate_kbps)
            logger.info("Selected GStreamer encoder (with auto hardware detection)")
            return encoder
        
        # Fallback to OpenCV
        if available['opencv']:
            encoder = OpenCVEncoder(resolution, fps, rtmp_url)
            logger.info("Selected OpenCV encoder (fallback)")
            return encoder
        
        # No encoders available
        logger.error("No suitable encoders available")
        return None
        
    except Exception as e:
        logger.error(f"Encoder selection failed: {e}")
        return None


def test_encoding_capabilities() -> Dict[str, Any]:
    """
    Test system encoding capabilities.
    
    Returns:
        Dict with capability test results
    """
    try:
        available = get_available_encoders()
        
        # Test basic encoder creation
        test_resolution = (1280, 720)
        test_fps = 24
        test_url = "rtmp://test/stream"
        
        results = {
            'available_encoders': available,
            'test_results': {}
        }
        
        # Test GStreamer
        if available['gstreamer']:
            try:
                encoder = GStreamerEncoder(test_resolution, test_fps, test_url, "auto")
                detected_type = encoder._detect_best_encoder()
                results['test_results']['gstreamer'] = {
                    'available': True,
                    'best_hardware_encoder': detected_type,
                    'nvenc_available': available['nvenc'],
                    'vaapi_available': available['vaapi']
                }
            except Exception as e:
                results['test_results']['gstreamer'] = {
                    'available': False,
                    'error': str(e)
                }
        
        # Test OpenCV
        if available['opencv']:
            try:
                encoder = OpenCVEncoder(test_resolution, test_fps, test_url)
                results['test_results']['opencv'] = {
                    'available': True,
                    'backend': 'ffmpeg'
                }
            except Exception as e:
                results['test_results']['opencv'] = {
                    'available': False,
                    'error': str(e)
                }
        
        return results
        
    except Exception as e:
        return {
            'error': f'Capability test failed: {e}',
            'available_encoders': {},
            'test_results': {}
        }


# Note: Removed duplicate get_best_encoder definition for clarity and maintainability.
