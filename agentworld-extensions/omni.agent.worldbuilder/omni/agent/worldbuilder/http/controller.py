"""Controller functions for WorldBuilder HTTP routes."""

from __future__ import annotations

from typing import Any, Callable, Dict

from agent_world_logging import module_logger

from .schemas import (
    AddElementPayload,
    CreateBatchPayload,
    PlaceAssetPayload,
    TransformAssetPayload,
    ClearPathPayload,
    validate_payload,
)
from ..services.worldbuilder_service import WorldBuilderService
from ..errors import (
    WorldBuilderError,
    WorldBuilderValidationError,
    error_response,
)
from ..transport import normalize_transport_response


logger = module_logger(service='worldbuilder', component='controller')


class WorldBuilderController:
    """Coordinate request validation and service execution."""

    def __init__(self, service: WorldBuilderService):
        self._service = service

    # Basic endpoints -----------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        return self._safe_call('get_stats', self._service.get_stats, default_error_code='STATS_FAILED')

    def get_health(self) -> Dict[str, Any]:
        return self._safe_call('get_health', self._service.get_health, default_error_code='HEALTH_FAILED')

    def get_metrics(self) -> Dict[str, Any]:
        return self._safe_call('get_metrics', self._service.get_metrics, default_error_code='METRICS_FAILED')

    def get_prometheus_metrics(self) -> str:
        try:
            return self._service.get_prometheus_metrics()
        except Exception as exc:
            logger.exception('prometheus_metrics_error', extra={'operation': 'prometheus_metrics', 'error': str(exc)})
            return '# Error generating metrics\n'

    # Mutation endpoints --------------------------------------------------
    def add_element(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'add_element',
            lambda: self._service.add_element(validate_payload(AddElementPayload, payload)),
            default_error_code='ADD_ELEMENT_FAILED'
        )

    def create_batch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'create_batch',
            lambda: self._service.create_batch(validate_payload(CreateBatchPayload, payload)),
            default_error_code='CREATE_BATCH_FAILED'
        )

    def place_asset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'place_asset',
            lambda: self._service.place_asset(validate_payload(PlaceAssetPayload, payload)),
            default_error_code='PLACE_ASSET_FAILED'
        )

    def transform_asset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'transform_asset',
            lambda: self._service.transform_asset(validate_payload(TransformAssetPayload, payload)),
            default_error_code='TRANSFORM_ASSET_FAILED'
        )

    def remove_element(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'remove_element',
            lambda: self._service.remove_element(payload),
            default_error_code='REMOVE_ELEMENT_FAILED'
        )

    def clear_path(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'clear_path',
            lambda: self._service.clear_path(validate_payload(ClearPathPayload, payload)),
            default_error_code='CLEAR_PATH_FAILED'
        )

    # Query endpoints -----------------------------------------------------
    def get_scene(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'get_scene',
            lambda: self._service.get_scene(payload),
            default_error_code='GET_SCENE_FAILED'
        )

    def scene_status(self) -> Dict[str, Any]:
        return self._safe_call('scene_status', self._service.get_scene_status, default_error_code='SCENE_STATUS_FAILED')

    def list_elements(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'list_elements',
            lambda: self._service.list_elements(payload),
            default_error_code='LIST_ELEMENTS_FAILED'
        )

    def batch_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'batch_info',
            lambda: self._service.get_batch_info(payload),
            default_error_code='BATCH_INFO_FAILED'
        )

    def list_batches(self) -> Dict[str, Any]:
        return self._safe_call('list_batches', self._service.list_batches, default_error_code='LIST_BATCHES_FAILED')

    def request_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'request_status',
            lambda: self._service.get_request_status(payload),
            default_error_code='REQUEST_STATUS_FAILED'
        )

    def query_objects_by_type(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'query_objects_by_type',
            lambda: self._service.query_objects_by_type(payload),
            default_error_code='QUERY_OBJECTS_BY_TYPE_FAILED'
        )

    def query_objects_in_bounds(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'query_objects_in_bounds',
            lambda: self._service.query_objects_in_bounds(payload),
            default_error_code='QUERY_OBJECTS_IN_BOUNDS_FAILED'
        )

    def query_objects_near_point(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'query_objects_near_point',
            lambda: self._service.query_objects_near_point(payload),
            default_error_code='QUERY_OBJECTS_NEAR_POINT_FAILED'
        )

    def calculate_bounds(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'calculate_bounds',
            lambda: self._service.calculate_bounds(payload),
            default_error_code='CALCULATE_BOUNDS_FAILED'
        )

    def find_ground_level(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'find_ground_level',
            lambda: self._service.find_ground_level(payload),
            default_error_code='FIND_GROUND_LEVEL_FAILED'
        )

    def align_objects(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call(
            'align_objects',
            lambda: self._service.align_objects(payload),
            default_error_code='ALIGN_OBJECTS_FAILED'
        )

    # ------------------------------------------------------------------
    # Internal helpers
    def _safe_call(
        self,
        operation: str,
        func: Callable[[], Dict[str, Any]],
        *,
        default_error_code: str,
    ) -> Dict[str, Any]:
        try:
            response = func()
            return self._normalize_response(operation, response, default_error_code)
        except WorldBuilderValidationError as exc:
            logger.warning(
                'validation_error',
                extra={'operation': operation, 'error': exc.message, 'error_code': exc.code},
            )
            return exc.to_payload()
        except WorldBuilderError as exc:
            logger.error(
                'domain_error',
                extra={'operation': operation, 'error': exc.message, 'error_code': exc.code},
            )
            return exc.to_payload()
        except ValueError as exc:
            logger.warning(
                'validation_error',
                extra={'operation': operation, 'error': str(exc), 'error_code': 'VALIDATION_ERROR'},
            )
            return error_response('VALIDATION_ERROR', str(exc))
        except Exception as exc:
            logger.exception('unhandled_exception', extra={'operation': operation})
            return error_response(
                'INTERNAL_ERROR',
                'Unexpected error processing request',
                details={'operation': operation, 'error': str(exc)}
            )

    def _normalize_response(
        self,
        operation: str,
        response: Any,
        default_error_code: str,
    ) -> Dict[str, Any]:
        normalized = normalize_transport_response(
            operation,
            response,
            default_error_code=default_error_code,
        )
        if not normalized.get('success', True):
            logger.error(
                'normalized_error',
                extra={
                    'operation': operation,
                    'error': normalized.get('error'),
                    'error_code': normalized.get('error_code'),
                },
            )
        return normalized


__all__ = ["WorldBuilderController"]
