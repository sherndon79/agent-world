"""Request schema definitions for WorldViewer HTTP endpoints."""

from __future__ import annotations

from typing import Any, Dict, Optional

try:  # Optional Pydantic validation support
    from pydantic import BaseModel, Field, ValidationError, conlist
    try:
        from pydantic import ConfigDict  # Pydantic v2
    except ImportError:  # pragma: no cover - v1 compatibility
        ConfigDict = None  # type: ignore
except ImportError:  # pragma: no cover - validation becomes a no-op
    BaseModel = None  # type: ignore
    Field = None  # type: ignore
    ValidationError = Exception  # type: ignore
    conlist = list  # type: ignore
    ConfigDict = None  # type: ignore


schemas_available = BaseModel is not None


if schemas_available:  # pragma: no branch

    class WorldViewerModel(BaseModel):
        """Base model configuration with permissive extra handling."""

        if ConfigDict is not None:  # Pydantic v2
            model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        else:  # pragma: no cover - Pydantic v1 fallback
            class Config:
                extra = 'allow'
                arbitrary_types_allowed = True

    class SetCameraPositionPayload(WorldViewerModel):
        position: conlist(float, min_length=3, max_length=3)
        target: Optional[conlist(float, min_length=3, max_length=3)] = None
        up_vector: Optional[conlist(float, min_length=3, max_length=3)] = None

    class FrameObjectPayload(WorldViewerModel):
        object_path: str
        distance: Optional[float] = None

    class OrbitCameraPayload(WorldViewerModel):
        center: conlist(float, min_length=3, max_length=3)
        distance: float
        elevation: float
        azimuth: float

    class SmoothMovePayload(WorldViewerModel):
        start_position: conlist(float, min_length=3, max_length=3)
        end_position: conlist(float, min_length=3, max_length=3)
        duration: Optional[float] = None
        easing_type: Optional[str] = Field(default=None, alias='easing')

    class OrbitShotPayload(WorldViewerModel):
        start_position: Optional[conlist(float, min_length=3, max_length=3)] = None
        target_position: Optional[conlist(float, min_length=3, max_length=3)] = None
        target_object: Optional[str] = None
        duration: Optional[float] = None
        movement_style: Optional[str] = None

    class ArcShotPayload(WorldViewerModel):
        start_position: conlist(float, min_length=3, max_length=3)
        end_position: Optional[conlist(float, min_length=3, max_length=3)] = None
        control_points: Optional[list] = None
        duration: Optional[float] = None
        movement_style: Optional[str] = None

    class MovementStatusPayload(WorldViewerModel):
        movement_id: str

    class RequestStatusPayload(WorldViewerModel):
        request_id: str

    class AssetTransformQuery(WorldViewerModel):
        usd_path: str
        calculation_mode: Optional[str] = Field(default='auto')

else:  # pragma: no cover - fallback definitions when Pydantic unavailable

    class WorldViewerModel:  # type: ignore
        def __init__(self, **data: Any) -> None:
            self.__dict__ = data

        def model_dump(self) -> Dict[str, Any]:
            return self.__dict__

    SetCameraPositionPayload = WorldViewerModel  # type: ignore
    FrameObjectPayload = WorldViewerModel  # type: ignore
    OrbitCameraPayload = WorldViewerModel  # type: ignore
    SmoothMovePayload = WorldViewerModel  # type: ignore
    OrbitShotPayload = WorldViewerModel  # type: ignore
    ArcShotPayload = WorldViewerModel  # type: ignore
    MovementStatusPayload = WorldViewerModel  # type: ignore
    RequestStatusPayload = WorldViewerModel  # type: ignore
    AssetTransformQuery = WorldViewerModel  # type: ignore
    ValidationError = Exception  # type: ignore


MODEL_MAP = {
    'set_camera_position': SetCameraPositionPayload,
    'frame_object': FrameObjectPayload,
    'orbit_camera': OrbitCameraPayload,
    'smooth_move': SmoothMovePayload,
    'orbit_shot': OrbitShotPayload,
    'arc_shot': ArcShotPayload,
    'movement_status': MovementStatusPayload,
    'request_status': RequestStatusPayload,
    'asset_transform': AssetTransformQuery,
}


def validate_payload(model_cls, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate payload with provided model when Pydantic is available."""
    if not schemas_available:
        return data
    try:
        return model_cls(**data).model_dump()
    except ValidationError as exc:  # pragma: no cover - re-raise for controller handling
        raise ValueError(str(exc)) from exc


__all__ = [
    'MODEL_MAP',
    'SetCameraPositionPayload',
    'FrameObjectPayload',
    'OrbitCameraPayload',
    'SmoothMovePayload',
    'OrbitShotPayload',
    'ArcShotPayload',
    'MovementStatusPayload',
    'RequestStatusPayload',
    'AssetTransformQuery',
    'validate_payload',
]
