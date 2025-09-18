"""Controller functions for WorldBuilder HTTP routes."""

from __future__ import annotations

from typing import Any, Dict

from .schemas import (
    AddElementPayload,
    CreateBatchPayload,
    PlaceAssetPayload,
    TransformAssetPayload,
    ClearPathPayload,
    validate_payload,
)
from ..services.worldbuilder_service import WorldBuilderService


class WorldBuilderController:
    """Coordinate request validation and service execution."""

    def __init__(self, service: WorldBuilderService):
        self._service = service

    # Basic endpoints -----------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        return self._service.get_stats()

    def get_health(self) -> Dict[str, Any]:
        return self._service.get_health()

    def get_metrics(self) -> Dict[str, Any]:
        return self._service.get_metrics()

    def get_prometheus_metrics(self) -> str:
        return self._service.get_prometheus_metrics()

    # Mutation endpoints --------------------------------------------------
    def add_element(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = validate_payload(AddElementPayload, payload)
        return self._service.add_element(data)

    def create_batch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = validate_payload(CreateBatchPayload, payload)
        return self._service.create_batch(data)

    def place_asset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = validate_payload(PlaceAssetPayload, payload)
        return self._service.place_asset(data)

    def transform_asset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = validate_payload(TransformAssetPayload, payload)
        return self._service.transform_asset(data)

    def remove_element(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._service.remove_element(payload)

    def clear_path(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = validate_payload(ClearPathPayload, payload)
        return self._service.clear_path(data)

    # Query endpoints -----------------------------------------------------
    def get_scene(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._service.get_scene(payload)

    def scene_status(self) -> Dict[str, Any]:
        return self._service.get_scene_status()

    def list_elements(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._service.list_elements(payload)

    def batch_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._service.get_batch_info(payload)

    def list_batches(self) -> Dict[str, Any]:
        return self._service.list_batches()

    def request_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._service.get_request_status(payload)

    def query_objects_by_type(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._service.query_objects_by_type(payload)

    def query_objects_in_bounds(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self._service.query_objects_in_bounds(payload)
        except ValueError as exc:
            return {'success': False, 'error': str(exc)}

    def query_objects_near_point(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self._service.query_objects_near_point(payload)
        except ValueError as exc:
            return {'success': False, 'error': str(exc)}

    def calculate_bounds(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self._service.calculate_bounds(payload)
        except ValueError as exc:
            return {'success': False, 'error': str(exc)}

    def find_ground_level(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self._service.find_ground_level(payload)
        except ValueError as exc:
            return {'success': False, 'error': str(exc)}

    def align_objects(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._service.align_objects(payload)


__all__ = ["WorldBuilderController"]
