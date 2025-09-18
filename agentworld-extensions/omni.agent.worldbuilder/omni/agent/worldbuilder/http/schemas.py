"""Request schema definitions for WorldBuilder HTTP endpoints."""

from typing import Any, Dict, List

try:  # Optional Pydantic validation
    from pydantic import BaseModel, Field, ValidationError
    from pydantic import conlist
except ImportError:  # pragma: no cover - validation becomes a no-op
    BaseModel = None  # type: ignore
    Field = None  # type: ignore
    ValidationError = Exception  # type: ignore
    conlist = list  # type: ignore


schemas_available = BaseModel is not None


if schemas_available:  # pragma: no branch

    class AddElementPayload(BaseModel):
        name: str | None = None
        element_type: str = Field(default="cube")
        position: conlist(float, min_length=3, max_length=3) = Field(default=[0.0, 0.0, 0.0])
        rotation: conlist(float, min_length=3, max_length=3) = Field(default=[0.0, 0.0, 0.0])
        scale: conlist(float, min_length=3, max_length=3) = Field(default=[1.0, 1.0, 1.0])
        color: conlist(float, min_length=3, max_length=3) = Field(default=[0.5, 0.5, 0.5])
        parent_path: str = Field(default="/World")
        metadata: Dict[str, Any] = Field(default_factory=dict)

    class BatchElement(BaseModel):
        name: str | None = None
        element_type: str = Field(default="cube")
        position: conlist(float, min_length=3, max_length=3) = Field(default=[0.0, 0.0, 0.0])
        rotation: conlist(float, min_length=3, max_length=3) = Field(default=[0.0, 0.0, 0.0])
        scale: conlist(float, min_length=3, max_length=3) = Field(default=[1.0, 1.0, 1.0])
        color: conlist(float, min_length=3, max_length=3) = Field(default=[0.5, 0.5, 0.5])
        metadata: Dict[str, Any] = Field(default_factory=dict)

    class CreateBatchPayload(BaseModel):
        batch_name: str
        elements: List[BatchElement]
        parent_path: str | None = Field(default="/World")

    class PlaceAssetPayload(BaseModel):
        name: str
        asset_path: str
        position: conlist(float, min_length=3, max_length=3) = Field(default=[0.0, 0.0, 0.0])
        rotation: conlist(float, min_length=3, max_length=3) = Field(default=[0.0, 0.0, 0.0])
        scale: conlist(float, min_length=3, max_length=3) = Field(default=[1.0, 1.0, 1.0])
        parent_path: str | None = Field(default="/World")
        prim_path: str | None = None
        metadata: Dict[str, Any] = Field(default_factory=dict)

    class TransformAssetPayload(BaseModel):
        prim_path: str
        position: conlist(float, min_length=3, max_length=3) | None = None
        rotation: conlist(float, min_length=3, max_length=3) | None = None
        scale: conlist(float, min_length=3, max_length=3) | None = None

    class ClearPathPayload(BaseModel):
        path: str

else:  # Fallback definitions when Pydantic is unavailable

    class AddElementPayload:  # type: ignore
        def __init__(self, **data: Any) -> None:
            self.__dict__ = data

        def model_dump(self) -> Dict[str, Any]:  # pragma: no cover
            return self.__dict__

    BatchElement = AddElementPayload  # type: ignore

    class CreateBatchPayload:  # type: ignore
        def __init__(self, **data: Any) -> None:
            self.__dict__ = data

        def model_dump(self) -> Dict[str, Any]:
            return self.__dict__

    class PlaceAssetPayload(AddElementPayload):
        pass

    class TransformAssetPayload(AddElementPayload):
        pass

    class ClearPathPayload(AddElementPayload):
        pass

    ValidationError = Exception  # type: ignore


def validate_payload(model_cls, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate data with the provided model if Pydantic is available."""
    if not schemas_available:
        return data
    try:
        return model_cls(**data).model_dump()
    except ValidationError as exc:  # pragma: no cover
        raise ValueError(str(exc)) from exc
