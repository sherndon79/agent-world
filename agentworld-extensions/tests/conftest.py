"""Pytest configuration ensuring extension modules import without Isaac Sim."""

from __future__ import annotations

import sys
import types
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

_WORLD_BUILDER_ROOT = _PROJECT_ROOT / "omni.agent.worldbuilder" / "omni"
_WORLD_VIEWER_ROOT = _PROJECT_ROOT / "omni.agent.worldviewer" / "omni"
_WORLD_SURVEYOR_ROOT = _PROJECT_ROOT / "omni.agent.worldsurveyor" / "omni"
_WORLD_RECORDER_ROOT = _PROJECT_ROOT / "omni.agent.worldrecorder" / "omni"
_WORLD_STREAMER_RTMP_ROOT = _PROJECT_ROOT / "omni.agent.worldstreamer.rtmp" / "omni"
_WORLD_STREAMER_SRT_ROOT = _PROJECT_ROOT / "omni.agent.worldstreamer.srt" / "omni"

_PACKAGE_PATHS = {
    "omni": [
        _WORLD_BUILDER_ROOT,
        _WORLD_VIEWER_ROOT,
        _WORLD_SURVEYOR_ROOT,
        _WORLD_RECORDER_ROOT,
        _WORLD_STREAMER_RTMP_ROOT,
        _WORLD_STREAMER_SRT_ROOT,
    ],
    "omni.agent": [
        _WORLD_BUILDER_ROOT / "agent",
        _WORLD_VIEWER_ROOT / "agent",
        _WORLD_SURVEYOR_ROOT / "agent",
        _WORLD_RECORDER_ROOT / "agent",
        _WORLD_STREAMER_RTMP_ROOT / "agent",
        _WORLD_STREAMER_SRT_ROOT / "agent",
    ],
    "omni.agent.worldbuilder": [
        _WORLD_BUILDER_ROOT / "agent" / "worldbuilder",
    ],
    "omni.agent.worldviewer": [
        _WORLD_VIEWER_ROOT / "agent" / "worldviewer",
    ],
    "omni.agent.worldsurveyor": [
        _WORLD_SURVEYOR_ROOT / "agent" / "worldsurveyor",
    ],
    "omni.agent.worldrecorder": [
        _WORLD_RECORDER_ROOT / "agent" / "worldrecorder",
    ],
    "omni.agent.worldstreamer": [
        _WORLD_STREAMER_RTMP_ROOT / "agent" / "worldstreamer",
        _WORLD_STREAMER_SRT_ROOT / "agent" / "worldstreamer",
    ],
    "omni.agent.worldstreamer.rtmp": [
        _WORLD_STREAMER_RTMP_ROOT / "agent" / "worldstreamer" / "rtmp",
    ],
    "omni.agent.worldstreamer.srt": [
        _WORLD_STREAMER_SRT_ROOT / "agent" / "worldstreamer" / "srt",
    ],
}


def _ensure_namespace(pkg_name: str, paths: list[Path]) -> None:
    existing_paths = [str(path) for path in paths if path.is_dir()]
    if not existing_paths:
        return

    module = sys.modules.get(pkg_name)
    if module is None:
        module = types.ModuleType(pkg_name)
        module.__path__ = []  # type: ignore[attr-defined]
        sys.modules[pkg_name] = module

    pkg_path = getattr(module, "__path__", [])
    for path_str in existing_paths:
        if path_str not in pkg_path:
            pkg_path.append(path_str)
    module.__path__ = pkg_path  # type: ignore[attr-defined]


def _ensure_stub_module(name: str, factory) -> None:
    if name not in sys.modules:
        sys.modules[name] = factory()


def _create_omni_usd_stub():
    module = types.ModuleType('omni.usd')

    class _UsdContextStub:
        def get_stage(self):
            return None

    def get_context():
        return _UsdContextStub()

    module.get_context = get_context  # type: ignore[attr-defined]
    return module


def _create_omni_kit_app_stub():
    module = types.ModuleType('omni.kit.app')

    class _Subscription:
        def unsubscribe(self):
            return None

    class _UpdateStream:
        def create_subscription_to_pop(self, *_args, **_kwargs):
            return _Subscription()

    class _AppStub:
        def get_update_event_stream(self):
            return _UpdateStream()

    def get_app():
        return _AppStub()

    module.get_app = get_app  # type: ignore[attr-defined]
    return module


def _create_pxr_stub():
    module = types.ModuleType('pxr')

    class _PxrStub:
        def __call__(self, *args, **kwargs):
            return self

        def __getattr__(self, _name):
            return _PxrStub()

    stub_instance = _PxrStub()
    module.Usd = stub_instance  # type: ignore[attr-defined]
    module.UsdGeom = stub_instance  # type: ignore[attr-defined]
    module.Gf = stub_instance  # type: ignore[attr-defined]
    module.Sdf = stub_instance  # type: ignore[attr-defined]
    return module


for package, paths in _PACKAGE_PATHS.items():
    _ensure_namespace(package, paths)

_ensure_stub_module('omni.usd', _create_omni_usd_stub)
_ensure_stub_module('omni.kit.app', _create_omni_kit_app_stub)
_ensure_stub_module('pxr', _create_pxr_stub)


def _create_omni_kit_viewport_utility_stub():
    module = types.ModuleType('omni.kit.viewport.utility')

    class _ViewportStub:
        viewport_api = types.SimpleNamespace()

    def get_active_viewport_window():
        return _ViewportStub()

    module.get_active_viewport_window = get_active_viewport_window  # type: ignore[attr-defined]
    return module


_ensure_stub_module('omni.kit.viewport.utility', _create_omni_kit_viewport_utility_stub)
