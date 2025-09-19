"""Request schema definitions for WorldBuilder HTTP endpoints."""

from __future__ import annotations

from typing import Any, Dict

try:  # Optional Pydantic validation
    from pydantic import BaseModel, Field, ValidationError
    from pydantic import conlist
except ImportError:  # pragma: no cover - validation becomes a no-op
    BaseModel = None  # type: ignore
    Field = None  # type: ignore
    ValidationError = Exception  # type: ignore
    conlist = list  # type: ignore


def _coerce_int(value: Any, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    """Best-effort coercion for pagination values."""
    if value is None:
        return default
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return default
    if coerced < minimum:
        coerced = minimum
    if maximum is not None and coerced > maximum:
        coerced = maximum
    return coerced


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
        elements: list[BatchElement]
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

    class PaginationParams(BaseModel):
        page: int = Field(default=1, ge=1)
        page_size: int = Field(default=50, ge=1, le=500)

else:  # Fallback definitions when Pydantic is unavailable

    class _BaseSchema:  # type: ignore
        def __init__(self, **data: Any) -> None:
            self.__dict__ = data

        def model_dump(self) -> Dict[str, Any]:
            return self.__dict__

    class AddElementPayload(_BaseSchema):
        pass

    BatchElement = AddElementPayload  # type: ignore

    class CreateBatchPayload(_BaseSchema):
        pass

    class PlaceAssetPayload(_BaseSchema):
        pass

    class TransformAssetPayload(_BaseSchema):
        pass

    class ClearPathPayload(_BaseSchema):
        pass

    class PaginationParams:
        def __init__(self, page: int = 1, page_size: int = 50) -> None:
            self.page = page
            self.page_size = page_size

        @classmethod
        def from_payload(cls, payload: Dict[str, Any]) -> 'PaginationParams':
            return cls(
                page=_coerce_int(payload.get('page'), 1, minimum=1),
                page_size=_coerce_int(payload.get('page_size'), 50, minimum=1, maximum=500),
            )

        def model_dump(self) -> Dict[str, Any]:  # pragma: no cover - parity helper
            return {'page': self.page, 'page_size': self.page_size}


def validate_payload(model_cls, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate data with the provided model if Pydantic is available."""
    if not schemas_available:
        return data
    try:
        return model_cls(**data).model_dump()
    except ValidationError as exc:  # pragma: no cover
        raise ValueError(str(exc)) from exc


def parse_pagination(payload: Dict[str, Any]) -> PaginationParams:
    """Return a PaginationParams instance regardless of Pydantic availability."""
    if schemas_available:
        return PaginationParams(**{k: payload.get(k) for k in ('page', 'page_size') if k in payload})
    return PaginationParams.from_payload(payload)


__all__ = [
    "AddElementPayload",
    "CreateBatchPayload",
    "PlaceAssetPayload",
    "TransformAssetPayload",
    "ClearPathPayload",
    "PaginationParams",
    "validate_payload",
    "parse_pagination",
]
