"""
HTTP request handler for Agent WorldRecorder API endpoints.
"""

import time
import logging
import shutil
from typing import Dict, Any, Optional
from pathlib import Path

# Note: Unified logging is initialized once in api_interface.py

# Import centralized version management
def _find_and_import_versions():
    """Find and import version management module using robust path resolution."""
    try:
        # Strategy 1: Search upward in directory tree for agentworld-extensions
        current = Path(__file__).resolve()
        for _ in range(10):  # Reasonable search limit
            if current.name == 'agentworld-extensions' or (current / 'agent_world_versions.py').exists():
                sys.path.insert(0, str(current))
                from agent_world_versions import get_version, get_service_name
                return get_version, get_service_name
            if current.parent == current:  # Reached filesystem root
                break
            current = current.parent
        
        # Strategy 2: Environment variable fallback
        env_path = os.getenv('AGENT_WORLD_VERSIONS_PATH')
        if env_path:
            sys.path.insert(0, env_path)
            from agent_world_versions import get_version, get_service_name
            return get_version, get_service_name
            
        return None, None
    except ImportError:
        return None, None

# Unified HTTP handler import with fallback
try:
    import sys as _sys
    from pathlib import Path as _P
    _cur = _P(__file__).resolve()
    for _ in range(10):
        if _cur.name == 'agentworld-extensions':
            _sys.path.insert(0, str(_cur))
            break
        _cur = _cur.parent
    from agent_world_http import WorldHTTPHandler
    UNIFIED = True
except Exception:
    from http.server import BaseHTTPRequestHandler as WorldHTTPHandler  # type: ignore
    UNIFIED = False

try:
    import sys
    import os
    get_version, get_service_name = _find_and_import_versions()
    VERSION_AVAILABLE = get_version is not None
except Exception:
    VERSION_AVAILABLE = False

logger = logging.getLogger(__name__)


class WorldRecorderHTTPHandler(WorldHTTPHandler):
    """HTTP handler for world recording via omni.kit.capture.viewport (Kit-native).
    
    Provides endpoints for:
    - Single frame capture using proper viewport utilities
    - Frame sequence capture with timestamped sessions
    - Continuous video recording
    - Status monitoring and metrics
    """

    api_interface = None

    def get_routes(self):  # type: ignore[override]
        """Return route mappings for unified HTTP handler."""
        return {
            'video/status': self._handle_status,
            'video/start': self._handle_start,
            'video/cancel': self._handle_cancel,
            # Parity aliases with worldrecorder
            'recording/status': self._handle_status,
            'recording/start': self._handle_start,
            'recording/cancel': self._handle_cancel,
            # Single-frame capture
            'viewport/capture_frame': self._handle_capture_frame,
            # Cleanup utilities
            'cleanup/frames': self._handle_cleanup_frames,
        }

    # Route handlers
    def _handle_status(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import omni.kit.capture.viewport as vcap
            inst = vcap.CaptureExtension.get_instance()
            # Hide default progress popup unless explicitly requested
            try:
                inst.show_default_progress_window = bool(data.get('show_progress', False))
            except Exception:
                pass
            done = bool(getattr(inst, 'done', False))
            outputs: list = []
            try:
                outs = inst.get_outputs() or []
                outputs = [str(x) for x in outs]
            except Exception:
                pass
            try:
                sid = getattr(self.api_interface, 'current_session_id', None)
                if sid:
                    sess = self.api_interface.sessions.setdefault(sid, {})
                    was_done = sess.get('done', False)
                    sess['outputs'] = outputs
                    sess['done'] = done
                    
                    # Note: Automatic cleanup now handled by background cleanup monitor thread
            except Exception:
                pass
            return {
                'success': True,
                'done': done,
                'outputs': outputs,
                'session_id': getattr(self.api_interface, 'current_session_id', None),
                'last_session_id': getattr(self.api_interface, 'last_session_id', None),
                'timestamp': time.time(),
            }
        except Exception as e:
            return {'success': False, 'error': f'status error: {e}'}

    def _handle_start(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import omni.kit.capture.viewport as vcap
            from omni.kit.capture.viewport import CaptureOptions, CaptureRangeType
            import uuid
            
            inst = vcap.CaptureExtension.get_instance()
            opts = CaptureOptions()

            out_path = data.get('output_path')
            if not out_path:
                return {'success': False, 'error': 'output_path required'}
            
            # File type resolution: path extension wins, file_type as fallback
            out = Path(out_path)
            if out.suffix:
                file_type = out.suffix
                opts.output_folder = str(out.parent)
                opts.file_name = out.stem
            else:
                file_type = data.get('file_type') or '.mp4'
                opts.output_folder = str(out.parent)
                opts.file_name = out.name
                # Add extension for proper file creation
                out = out.with_suffix(file_type)
            opts.file_type = file_type

            # Basic video parameters (continuous recording only)
            fps = data.get('fps', 30)
            try:
                opts.fps = float(fps)
            except Exception:
                opts.fps = 30.0

            w = data.get('width'); h = data.get('height')
            if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
                opts.res_width = int(w)
                opts.res_height = int(h)

            # Duration handling
            duration_sec = data.get('duration_sec')
            if not duration_sec:
                return {'success': False, 'error': 'duration_sec is required'}

            # Standard continuous recording
            opts.range_type = CaptureRangeType.SECONDS
            opts.start_time = 0
            opts.end_time = float(duration_sec)

            # Generate session ID
            session_id = data.get('session_id') or f"vc_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
            
            def _start():
                inst.options = opts
                ok = bool(inst.start())
                try:
                    full = inst.options.get_full_path()
                except Exception:
                    full = str(out)
                return {'success': ok, 'output': full, 'started': ok}

            # Execute on main thread to avoid UI thread violations
            if hasattr(self.api_interface, 'run_on_main'):
                res = self.api_interface.run_on_main(_start)
            else:
                res = _start()
                
            if not res.get('started'):
                return {'success': False, 'error': 'failed to start video recording'}
            
            # Store session info
            try:
                cleanup_frames = data.get('cleanup_frames', True)  # Default to True
                self.api_interface.current_session_id = session_id
                self.api_interface.sessions[session_id] = {
                    'output_hint': str(out), 
                    'started_at': time.time(),
                    'capture_mode': 'continuous',
                    'cleanup_frames': cleanup_frames
                }
            except Exception:
                pass
            
            # Start background cleanup monitor if cleanup is enabled
            if cleanup_frames:
                import threading
                cleanup_thread = threading.Thread(
                    target=self._background_cleanup_monitor,
                    args=(session_id, str(out)),
                    daemon=True
                )
                cleanup_thread.start()
            
            # Build response
            response = {
                'success': True,
                'session_id': session_id,
                'output_path': str(out),
                'file_type': file_type,
                'fps': fps,
                'duration_sec': duration_sec,
                'timestamp': time.time()
            }
            
            return response
            
        except Exception as e:
            return {'success': False, 'error': f'start error: {e}'}

    def _handle_cancel(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import omni.kit.capture.viewport as vcap
            inst = vcap.CaptureExtension.get_instance()
            def _stop():
                try:
                    inst.cancel()
                except Exception:
                    pass
                
                # Wait for cancellation to complete safely before cleanup
                import time
                max_wait_time = 5.0  # 5 seconds max
                poll_interval = 0.1  # Check every 100ms
                
                for _ in range(int(max_wait_time / poll_interval)):
                    if getattr(inst, 'done', False):
                        break
                    time.sleep(poll_interval)
                
                done = bool(getattr(inst, 'done', False))
                outs = []
                try:
                    outs = inst.get_outputs() or []
                except Exception:
                    pass
                try:
                    sid = getattr(self.api_interface, 'current_session_id', None)
                    self.api_interface.last_session_id = sid
                    if sid:
                        sess = self.api_interface.sessions.setdefault(sid, {})
                        sess['outputs'] = [str(x) for x in outs]
                        sess['done'] = done
                        
                        # Perform cleanup if recording is done and cleanup was requested
                        if done and sess.get('cleanup_frames', True) and not sess.get('cleaned_up', False):
                            output_hint = sess.get('output_hint', '')
                            if output_hint:
                                self._cleanup_frame_directories(output_hint)
                                sess['cleaned_up'] = True
                except Exception:
                    pass
                return {'success': True, 'done': done, 'outputs': outs, 'session_id': getattr(self.api_interface, 'current_session_id', None)}

            if hasattr(self.api_interface, 'run_on_main'):
                return self.api_interface.run_on_main(_stop)
            else:
                return _stop()
        except Exception as e:
            return {'success': False, 'error': f'stop error: {e}'}

    def _handle_capture_frame(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Capture a single frame or frame sequence to image files using proper viewport utilities."""
        try:
            from datetime import datetime
            import uuid
            import threading
            
            out_path = data.get('output_path')
            if not out_path:
                return {'success': False, 'error': 'output_path required'}
            
            # Check if this is a sequence capture
            duration_sec = data.get('duration_sec')
            interval_sec = data.get('interval_sec')
            frame_count = data.get('frame_count')
            
            is_sequence = duration_sec and (interval_sec or frame_count)
            
            # File type resolution: path extension wins, file_type as fallback
            out = Path(out_path)
            if out.suffix:
                file_type = out.suffix
            else:
                file_type = data.get('file_type') or '.png'
                # Add extension to path for single file
                if not is_sequence:
                    out = out.with_suffix(file_type)
            
            # Get optional resolution parameters
            width = data.get('width')
            height = data.get('height')
            
            if is_sequence:
                # Frame sequence capture
                if interval_sec and frame_count:
                    return {'success': False, 'error': 'Cannot specify both interval_sec and frame_count'}
                
                # Calculate missing parameter
                if interval_sec:
                    estimated_frame_count = int(duration_sec / interval_sec)
                else:  # frame_count provided
                    interval_sec = duration_sec / frame_count
                    estimated_frame_count = frame_count
                
                # Create timestamped session directory
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                session_dir = out / f"session_{timestamp}"
                session_dir.mkdir(parents=True, exist_ok=True)
                
                session_id = f"fs_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
                
                # Start frame sequence capture in background
                def _capture_frame_sequence():
                    """Capture frame sequence using individual frame captures with timing."""
                    try:
                        captured_frames = []
                        start_time = time.time()
                        
                        frame_index = 1
                        next_capture_time = start_time
                        
                        while time.time() - start_time < duration_sec:
                            current_time = time.time()
                            
                            # Wait until it's time for next capture
                            if current_time >= next_capture_time:
                                # Generate frame path
                                frame_filename = f"frame_{frame_index:03d}{file_type}"
                                frame_path = session_dir / frame_filename
                                
                                # Capture single frame using proper viewport utilities
                                frame_result = self._capture_single_frame_impl(str(frame_path), width, height)
                                
                                if frame_result.get('success'):
                                    captured_frames.append(str(frame_path))
                                    
                                frame_index += 1
                                next_capture_time += interval_sec
                            else:
                                # Sleep briefly to avoid busy waiting
                                time.sleep(0.1)
                        
                        # Store results in session info
                        try:
                            if hasattr(self.api_interface, 'sessions'):
                                session_info = self.api_interface.sessions.get(session_id, {})
                                session_info.update({
                                    'captured_frames': captured_frames,
                                    'completed': True,
                                    'actual_frame_count': len(captured_frames)
                                })
                                self.api_interface.sessions[session_id] = session_info
                        except Exception:
                            pass
                            
                    except Exception as e:
                        # Store error in session info
                        try:
                            if hasattr(self.api_interface, 'sessions'):
                                session_info = self.api_interface.sessions.get(session_id, {})
                                session_info.update({
                                    'error': str(e),
                                    'completed': True
                                })
                                self.api_interface.sessions[session_id] = session_info
                        except Exception:
                            pass
                
                # Start background capture thread
                capture_thread = threading.Thread(target=_capture_frame_sequence, daemon=True)
                capture_thread.start()
                
                # Store session info
                try:
                    if hasattr(self.api_interface, 'sessions'):
                        self.api_interface.current_session_id = session_id
                        self.api_interface.sessions[session_id] = {
                            'output_hint': str(out),
                            'session_directory': str(session_dir),
                            'started_at': time.time(),
                            'capture_mode': 'sequence',
                            'completed': False
                        }
                except Exception:
                    pass
                
                return {
                    'success': True,
                    'session_id': session_id,
                    'output_path': str(out),
                    'session_directory': str(session_dir),
                    'file_type': file_type,
                    'capture_mode': 'sequence',
                    'duration_sec': duration_sec,
                    'interval_sec': interval_sec,
                    'estimated_frame_count': estimated_frame_count,
                    'frame_pattern': 'frame_{:03d}' + file_type,
                    'timestamp': time.time()
                }
            
            else:
                # Single frame capture using proper viewport utilities
                result = self._capture_single_frame_impl(str(out), width, height)
                
                if result.get('success'):
                    return {
                        'success': True,
                        'outputs': [result.get('frame_path', str(out))],
                        'output_path': str(out),
                        'file_type': file_type,
                        'capture_mode': 'single',
                        'method': result.get('method', 'unknown'),
                        'timestamp': time.time()
                    }
                else:
                    return result
                
        except Exception as e:
            return {'success': False, 'error': f'capture_frame error: {e}'}
    
    def _capture_single_frame_impl(self, out_path: str, width: Optional[int], height: Optional[int]) -> Dict[str, Any]:
        """Capture a single frame using proper viewport utilities (adapted from original)."""
        
        def _do_capture():
            # Ensure parent directory exists
            try:
                import os
                parent = os.path.dirname(out_path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
            except Exception:
                pass
                
            # Initialize diagnostics
            utility_err: Optional[str] = None
            vcap_err: Optional[str] = None
            fallback_err: Optional[str] = None

            # 1) Try utility helper (used by replicator)
            try:
                from omni.kit.viewport.utility import (
                    get_active_viewport,
                    capture_viewport_to_file,
                )
                vp = get_active_viewport()
                if vp is not None and callable(capture_viewport_to_file):
                    capture_viewport_to_file(vp, file_path=out_path)
                    if self.api_interface:
                        self.api_interface._last_frame_path = out_path
                    return {
                        'success': True,
                        'frame_path': out_path,
                        'method': 'viewport.utility.capture_viewport_to_file',
                    }
            except Exception as e:
                utility_err = str(e)

            # 2) Try omni.kit.capture.viewport APIs (names vary across versions)
            try:
                import omni.kit.capture.viewport as vcap
                # Heuristic: try common function names
                vp = None
                try:
                    from omni.kit.viewport.utility import get_active_viewport
                    vp = get_active_viewport()
                except Exception:
                    pass

                candidates = [
                    getattr(vcap, 'capture_viewport_to_file', None),
                    getattr(vcap, 'capture_to_file', None),
                    getattr(vcap, 'capture_single_frame_to_file', None),
                ]
                for fn in candidates:
                    if callable(fn) and vp is not None:
                        fn(vp, out_path)
                        if self.api_interface:
                            self.api_interface._last_frame_path = out_path
                        return {
                            'success': True,
                            'frame_path': out_path,
                            'method': f'kit.capture.viewport.{fn.__name__}',
                        }
            except Exception as e:
                vcap_err = str(e)

            # 3) Fallback to schedule_capture with FileCapture delegate
            try:
                from omni.kit.viewport.utility import get_active_viewport_window
                try:
                    # Different versions place this differently; try both
                    try:
                        from omni.kit.widget.viewport.capture import FileCapture  # type: ignore
                    except Exception:
                        from omni.kit.capture.viewport import FileCapture  # type: ignore

                except Exception as e:
                    return {'success': False, 'error': f'missing capture helpers: {e} (ensure omni.kit.capture.viewport is enabled)'}

                vpw = get_active_viewport_window()
                if not vpw or not hasattr(vpw, 'viewport_api') or vpw.viewport_api is None:
                    return {'success': False, 'error': 'No active viewport window'}

                api = vpw.viewport_api
                if not hasattr(api, 'schedule_capture'):
                    return {'success': False, 'error': 'Viewport API lacks schedule_capture'}

                try:
                    delegate = FileCapture(out_path, aov_name="")
                    api.schedule_capture(delegate)
                    if self.api_interface:
                        self.api_interface._last_frame_path = out_path
                    return {
                        'success': True,
                        'frame_path': out_path,
                        'method': 'viewport_api.schedule_capture(FileCapture)',
                        'note': 'capture scheduled asynchronously',
                    }
                except Exception as e:
                    return {'success': False, 'error': f'schedule_capture failed: {e}'}
            except Exception as e:
                fallback_err = str(e)

            # If we get here, all strategies failed; include diagnostics
            return {
                'success': False,
                'error': 'All capture strategies failed',
                'diagnostics': {
                    'utility_error': utility_err,
                    'vcap_error': vcap_err,
                    'fallback_error': fallback_err,
                }
            }
        
        # Execute on main thread via queue if available
        if hasattr(self.api_interface, 'run_on_main'):
            return self.api_interface.run_on_main(_do_capture)
        else:
            return _do_capture()
    
    def _cleanup_frame_directories(self, output_path: str) -> None:
        """Clean up temporary frame directories created during recording"""
        logger.debug(f"_cleanup_frame_directories called with output_path: {output_path}")
        try:
            if not output_path:
                logger.debug("No output_path provided, returning")
                return
                
            output_file = Path(output_path)
            parent_dir = output_file.parent
            base_name = output_file.stem
            
            logger.debug(f"Looking for frame directories with pattern: {base_name}_frames in {parent_dir}")
            
            # Look for frame directories with pattern: {base_name}_frames
            frame_dir_pattern = f"{base_name}_frames"
            
            cleaned_dirs = []
            for item in parent_dir.glob(f"{frame_dir_pattern}*"):
                logger.debug(f"Found potential frame directory: {item}")
                if item.is_dir() and frame_dir_pattern in item.name:
                    try:
                        logger.debug(f"Removing directory: {item}")
                        shutil.rmtree(item)
                        cleaned_dirs.append(str(item))
                        logger.debug(f"Successfully removed: {item}")
                    except Exception as e:
                        logger.warning(f"Failed to remove {item}: {e}")
                        pass  # Continue with other directories
            
            if cleaned_dirs:
                logger.info(f"Cleaned up {len(cleaned_dirs)} frame directories: {cleaned_dirs}")
            else:
                logger.debug("No frame directories found to clean up")
                    
        except Exception as e:
            logger.error(f"Exception in _cleanup_frame_directories: {e}")
            pass  # Fail silently - cleanup is best effort

    def _background_cleanup_monitor(self, session_id: str, output_path: str):
        """Background thread to monitor completion and trigger automatic cleanup."""
        logger = logging.getLogger('worldrecorder')
        
        try:
            import omni.kit.capture.viewport as vcap
            inst = vcap.CaptureExtension.get_instance()
            
            logger.debug(f"Starting background cleanup monitor for session {session_id}")
            
            # Poll until recording/encoding is complete
            while not getattr(inst, 'done', False):
                time.sleep(1.5)  # Poll every 1.5 seconds
            
            # Check if session still exists and cleanup is enabled
            if session_id in self.api_interface.sessions:
                sess = self.api_interface.sessions[session_id]
                if sess.get('cleanup_frames', True) and not sess.get('cleaned_up', False):
                    logger.info(f"Background cleanup triggered for completed session {session_id}")
                    self._cleanup_frame_directories(output_path)
                    sess['cleaned_up'] = True
                else:
                    logger.debug(f"Skipping cleanup for session {session_id} (cleanup_frames={sess.get('cleanup_frames', True)}, cleaned_up={sess.get('cleaned_up', False)})")
            else:
                logger.debug(f"Session {session_id} no longer exists, skipping cleanup")
                
        except Exception as e:
            logger.error(f"Background cleanup monitor error for session {session_id}: {e}")
    
    def _handle_cleanup_frames(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Manual cleanup of frame directories for a specific session or output path"""
        try:
            session_id = data.get('session_id')
            output_path = data.get('output_path')
            
            # If session_id provided, use session's output_hint
            if session_id:
                if hasattr(self.api_interface, 'sessions') and session_id in self.api_interface.sessions:
                    session = self.api_interface.sessions[session_id]
                    output_path = session.get('output_hint', '')
                else:
                    return {'success': False, 'error': f'Session {session_id} not found'}
            
            # Must have output_path to proceed
            if not output_path:
                return {'success': False, 'error': 'Either session_id or output_path is required'}
            
            # Perform cleanup
            try:
                output_file = Path(output_path)
                parent_dir = output_file.parent
                base_name = output_file.stem
                frame_dir_pattern = f"{base_name}_frames"
                
                cleaned_dirs = []
                for item in parent_dir.glob(f"{frame_dir_pattern}*"):
                    if item.is_dir() and frame_dir_pattern in item.name:
                        try:
                            shutil.rmtree(item)
                            cleaned_dirs.append(str(item))
                        except Exception:
                            continue  # Skip directories that can't be removed
                
                return {
                    'success': True,
                    'cleaned_directories': cleaned_dirs,
                    'count': len(cleaned_dirs),
                    'output_path': output_path
                }
                
            except Exception as e:
                return {'success': False, 'error': f'Cleanup failed: {e}'}
                
        except Exception as e:
            return {'success': False, 'error': f'cleanup error: {e}'}
