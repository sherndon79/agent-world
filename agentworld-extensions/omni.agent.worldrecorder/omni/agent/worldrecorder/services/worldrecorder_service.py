"""Service layer implementing WorldRecorder operations."""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..errors import ValidationFailure, WorldRecorderError, error_response

LOGGER = logging.getLogger('worldrecorder.service')


def _validate_output_path(path_str: str | None) -> Optional[Path]:
    """Validate and normalise filesystem paths for capture outputs."""
    if not path_str or not isinstance(path_str, str):
        return None

    try:
        cleaned = path_str.replace('\x00', '')
        path = Path(cleaned).resolve()

        allowed_bases: List[Path] = [
            Path('/tmp').resolve(),
            Path(os.path.expanduser('~/Downloads')).resolve(),
            Path(os.path.expanduser('~/Desktop')).resolve(),
            Path.cwd().resolve(),
        ]

        for base in allowed_bases:
            try:
                path.relative_to(base)
                return path
            except ValueError:
                continue

        LOGGER.warning('Path validation failed for %s', path)
        return None
    except (OSError, ValueError) as exc:
        LOGGER.warning('Path validation error for %s: %s', path_str, exc)
        return None


class WorldRecorderService:
    """Encapsulates WorldRecorder business logic for HTTP/MCP callers."""

    def __init__(self, api_interface) -> None:
        self._api = api_interface
        self._logger = logging.getLogger('worldrecorder.service')

    # ------------------------------------------------------------------
    # Status helpers
    def get_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import omni.kit.capture.viewport as vcap
        except Exception as exc:  # pragma: no cover - requires Isaac runtime
            raise WorldRecorderError('Viewport capture module unavailable', details={'error': str(exc)}) from exc

        inst = vcap.CaptureExtension.get_instance()
        show_progress = bool(payload.get('show_progress', False))
        try:
            inst.show_default_progress_window = show_progress
        except Exception:
            pass

        done = bool(getattr(inst, 'done', False))
        outputs: List[str] = []
        try:
            outputs = [str(path) for path in inst.get_outputs() or []]
        except Exception:
            pass

        try:
            session_id = getattr(self._api, 'current_session_id', None)
            if session_id:
                session = self._api.sessions.setdefault(session_id, {})
                session['outputs'] = outputs
                session['done'] = done
        except Exception:
            pass

        return {
            'success': True,
            'done': done,
            'outputs': outputs,
            'session_id': getattr(self._api, 'current_session_id', None),
            'last_session_id': getattr(self._api, 'last_session_id', None),
            'timestamp': time.time(),
        }

    # ------------------------------------------------------------------
    # Video recording operations
    def start_video(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        output_path = payload.get('output_path')
        if not output_path:
            raise ValidationFailure('output_path is required', details={'parameter': 'output_path'})

        duration = payload.get('duration_sec')
        if duration is None:
            raise ValidationFailure('duration_sec is required', details={'parameter': 'duration_sec'})

        validated_path = _validate_output_path(output_path)
        if not validated_path:
            raise ValidationFailure('output_path is not within an allowed directory', details={'parameter': 'output_path'})

        try:
            import omni.kit.capture.viewport as vcap
            from omni.kit.capture.viewport import CaptureOptions, CaptureRangeType
        except Exception as exc:  # pragma: no cover - requires Isaac runtime
            raise WorldRecorderError('Viewport capture module unavailable', details={'error': str(exc)}) from exc

        opts = CaptureOptions()

        if validated_path.suffix:
            file_type = validated_path.suffix
            opts.output_folder = str(validated_path.parent)
            opts.file_name = validated_path.stem
        else:
            file_type = payload.get('file_type') or '.mp4'
            opts.output_folder = str(validated_path.parent)
            opts.file_name = validated_path.name
            validated_path = validated_path.with_suffix(file_type)
        opts.file_type = file_type

        fps_value = payload.get('fps', 30)
        try:
            opts.fps = float(fps_value)
        except Exception:
            opts.fps = 30.0

        width = payload.get('width')
        height = payload.get('height')
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            opts.res_width = int(width)
            opts.res_height = int(height)

        opts.range_type = CaptureRangeType.SECONDS
        opts.start_time = 0
        try:
            opts.end_time = float(duration)
        except Exception as exc:
            raise ValidationFailure('duration_sec must be numeric', details={'parameter': 'duration_sec'}) from exc

        session_id = payload.get('session_id') or f"vc_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"

        inst = vcap.CaptureExtension.get_instance()

        def _start_capture():
            inst.options = opts
            started = bool(inst.start())
            try:
                full_path = inst.options.get_full_path()
            except Exception:
                full_path = str(validated_path)
            return {'success': started, 'output': full_path, 'started': started}

        result = self._run_on_main(_start_capture)
        if not result.get('started'):
            raise WorldRecorderError('Failed to start video recording', details={'session_id': session_id})

        cleanup_frames = bool(payload.get('cleanup_frames', True))
        try:
            self._api.current_session_id = session_id
            session = self._api.sessions.setdefault(session_id, {})
            session.update({
                'output_hint': str(validated_path),
                'started_at': time.time(),
                'capture_mode': 'continuous',
                'cleanup_frames': cleanup_frames,
            })
        except Exception:
            pass

        if cleanup_frames:
            thread = threading.Thread(
                target=self._background_cleanup_monitor,
                args=(session_id, str(validated_path)),
                daemon=True,
            )
            thread.start()

        return {
            'success': True,
            'session_id': session_id,
            'output_path': str(validated_path),
            'file_type': file_type,
            'fps': fps_value,
            'duration_sec': duration,
            'timestamp': time.time(),
        }

    def cancel_video(self) -> Dict[str, Any]:
        try:
            import omni.kit.capture.viewport as vcap
        except Exception as exc:  # pragma: no cover - requires Isaac runtime
            raise WorldRecorderError('Viewport capture module unavailable', details={'error': str(exc)}) from exc

        inst = vcap.CaptureExtension.get_instance()

        def _cancel():
            try:
                inst.cancel()
            except Exception:
                pass

            deadline = time.time() + 5.0
            while time.time() < deadline:
                if getattr(inst, 'done', False):
                    break
                time.sleep(0.1)

            done = bool(getattr(inst, 'done', False))
            outputs: List[str] = []
            try:
                outputs = [str(path) for path in inst.get_outputs() or []]
            except Exception:
                pass

            try:
                session_id = getattr(self._api, 'current_session_id', None)
                self._api.last_session_id = session_id
                if session_id:
                    session = self._api.sessions.setdefault(session_id, {})
                    session['outputs'] = outputs
                    session['done'] = done
                    if done and session.get('cleanup_frames', True) and not session.get('cleaned_up', False):
                        hint = session.get('output_hint')
                        if hint:
                            self._cleanup_frame_directories(hint)
                            session['cleaned_up'] = True
            except Exception:
                pass

            return {'success': True, 'done': done, 'outputs': outputs, 'session_id': getattr(self._api, 'current_session_id', None)}

        return self._run_on_main(_cancel)

    # ------------------------------------------------------------------
    # Frame capture operations
    def capture_frame(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        output_path = payload.get('output_path')
        if not output_path:
            raise ValidationFailure('output_path is required', details={'parameter': 'output_path'})

        validated_path = _validate_output_path(output_path)
        if not validated_path:
            raise ValidationFailure('output_path is not within an allowed directory', details={'parameter': 'output_path'})

        duration = payload.get('duration_sec')
        interval = payload.get('interval_sec')
        frame_count = payload.get('frame_count')
        is_sequence = bool(duration and (interval or frame_count))

        file_type = validated_path.suffix or payload.get('file_type') or '.png'
        width = payload.get('width')
        height = payload.get('height')

        if is_sequence:
            if interval and frame_count:
                raise ValidationFailure('interval_sec and frame_count cannot both be provided', details={'parameters': ['interval_sec', 'frame_count']})

            if not interval and not frame_count:
                raise ValidationFailure('interval_sec or frame_count required for sequence capture', details={'parameters': ['interval_sec', 'frame_count']})

            if interval:
                estimated_frames = int(duration / interval)
            else:
                estimated_frames = int(frame_count)
                interval = duration / estimated_frames if estimated_frames else duration

            session_dir = validated_path / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            session_dir.mkdir(parents=True, exist_ok=True)

            session_id = f"fs_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"

            def _capture_sequence():  # pragma: no cover - requires Isaac runtime
                captured: List[str] = []
                start = time.time()
                next_capture = start
                frame_index = 1

                while time.time() - start < duration:
                    current = time.time()
                    if current >= next_capture:
                        frame_name = session_dir / f"frame_{frame_index:03d}{file_type}"
                        result = self._capture_single_frame_impl(str(frame_name), width, height)
                        if result.get('success'):
                            captured.append(str(frame_name))
                        frame_index += 1
                        next_capture += interval
                    else:
                        time.sleep(0.1)

                try:
                    session = self._api.sessions.setdefault(session_id, {})
                    session.update({
                        'captured_frames': captured,
                        'completed': True,
                        'actual_frame_count': len(captured),
                    })
                except Exception:
                    pass

            threading.Thread(target=_capture_sequence, daemon=True).start()

            try:
                self._api.current_session_id = session_id
                session = self._api.sessions.setdefault(session_id, {})
                session.update({
                    'output_hint': str(validated_path),
                    'session_directory': str(session_dir),
                    'started_at': time.time(),
                    'capture_mode': 'sequence',
                    'completed': False,
                })
            except Exception:
                pass

            return {
                'success': True,
                'session_id': session_id,
                'output_path': str(validated_path),
                'session_directory': str(session_dir),
                'file_type': file_type,
                'capture_mode': 'sequence',
                'duration_sec': duration,
                'interval_sec': interval,
                'estimated_frame_count': estimated_frames,
                'frame_pattern': 'frame_{:03d}' + file_type,
                'timestamp': time.time(),
            }

        result = self._capture_single_frame_impl(str(validated_path if validated_path.suffix else validated_path.with_suffix(file_type)), width, height)
        if not result.get('success'):
            raise WorldRecorderError('Frame capture failed', details={'output_path': output_path})

        return {
            'success': True,
            'outputs': [result.get('frame_path', str(validated_path))],
            'output_path': result.get('frame_path', str(validated_path)),
            'file_type': file_type,
            'capture_mode': 'single',
            'method': result.get('method', 'unknown'),
            'timestamp': time.time(),
        }

    # ------------------------------------------------------------------
    # Cleanup
    def cleanup_frames(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        session_id = payload.get('session_id')
        output_path = payload.get('output_path')

        if session_id:
            if hasattr(self._api, 'sessions') and session_id in self._api.sessions:
                output_path = self._api.sessions[session_id].get('output_hint', '')
            else:
                return error_response('NOT_FOUND', f'Session {session_id} not found', details={'session_id': session_id})

        if not output_path:
            raise ValidationFailure('Either session_id or output_path is required', details={'parameters': ['session_id', 'output_path']})

        validated_path = _validate_output_path(output_path)
        if not validated_path:
            raise ValidationFailure('output_path is not within an allowed directory', details={'parameter': 'output_path'})

        parent_dir = validated_path.parent
        base_name = validated_path.stem
        pattern = f"{base_name}_frames"

        cleaned: List[str] = []
        try:
            for item in parent_dir.glob(f"{pattern}*"):
                if item.is_dir() and pattern in item.name:
                    try:
                        import shutil
                        shutil.rmtree(item)
                        cleaned.append(str(item))
                    except Exception as exc:
                        self._logger.warning('Failed to remove %s: %s', item, exc)
                        continue
        except Exception as exc:
            raise WorldRecorderError('Cleanup failed', details={'error': str(exc)}) from exc

        return {
            'success': True,
            'cleaned_directories': cleaned,
            'count': len(cleaned),
            'output_path': output_path,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    def _run_on_main(self, fn):
        if hasattr(self._api, 'run_on_main'):
            return self._api.run_on_main(fn)
        return fn()

    def _capture_single_frame_impl(self, output_path: str, width: Optional[int], height: Optional[int]) -> Dict[str, Any]:
        """Capture a single viewport frame using Kit utilities."""
        try:
            import omni.kit.capture.viewport as vcap
        except Exception as exc:  # pragma: no cover - requires Isaac runtime
            raise WorldRecorderError('Viewport capture module unavailable', details={'error': str(exc)}) from exc

        inst = vcap.CaptureExtension.get_instance()

        def _capture():  # pragma: no cover - requires Isaac runtime
            options = inst.get_screenshot_options()
            if width and height:
                options.res_width = int(width)
                options.res_height = int(height)
            options.file_path = output_path
            ok = bool(inst.capture_screenshot_with_options(options))
            return {'success': ok, 'frame_path': output_path, 'method': 'viewport_capture'}

        return self._run_on_main(_capture)

    def _cleanup_frame_directories(self, output_path: str) -> None:
        validated = _validate_output_path(output_path)
        if not validated:
            return

        parent_dir = validated.parent
        base_name = validated.stem
        pattern = f"{base_name}_frames"

        for item in parent_dir.glob(f"{pattern}*"):
            if item.is_dir() and pattern in item.name:
                try:
                    import shutil
                    shutil.rmtree(item)
                except Exception as exc:
                    self._logger.warning('Failed to remove %s: %s', item, exc)

    def _background_cleanup_monitor(self, session_id: str, output_path: str) -> None:  # pragma: no cover - requires Isaac runtime
        try:
            import omni.kit.capture.viewport as vcap
        except Exception as exc:
            self._logger.warning('Background cleanup unavailable: %s', exc)
            return

        inst = vcap.CaptureExtension.get_instance()
        self._logger.debug('Starting cleanup monitor for %s', session_id)

        try:
            while not getattr(inst, 'done', False):
                time.sleep(1.5)

            if session_id in getattr(self._api, 'sessions', {}):
                session = self._api.sessions[session_id]
                if session.get('cleanup_frames', True) and not session.get('cleaned_up', False):
                    self._logger.info('Cleanup triggered for session %s', session_id)
                    self._cleanup_frame_directories(output_path)
                    session['cleaned_up'] = True
        except Exception as exc:
            self._logger.error('Background cleanup error for %s: %s', session_id, exc)


__all__ = ["WorldRecorderService"]
