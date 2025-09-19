"""Business logic for WorldBuilder HTTP routes."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Dict, Optional, TYPE_CHECKING
import time

from ..scene_builder import SceneElement, AssetPlacement, PrimitiveType
from ..utils import collect_metrics, count_world_children, ensure_vector3
from ..errors import error_response

if TYPE_CHECKING:  # pragma: no cover - only used for typing
    from ..config import WorldBuilderConfig

try:
    from agent_world_versions import get_version, get_service_name
    VERSION_AVAILABLE = True
except ImportError:
    get_version = get_service_name = None
    VERSION_AVAILABLE = False


class WorldBuilderService:
    """Wrap USD operations exposed through the HTTP API."""

    def __init__(self, api_interface, config: Optional['WorldBuilderConfig'] = None):
        self._api = api_interface
        if config is None and hasattr(api_interface, '_config'):
            config = getattr(api_interface, '_config')
        if config is None:
            try:
                from ..config import get_config  # Local import to avoid cycles
                config = get_config()
            except ImportError:
                config = None
        self._config = config

    # ------------------------------------------------------------------
    # Helper properties
    @property
    def _scene_builder(self):
        return self._api._scene_builder

    @property
    def _stats(self) -> Dict[str, Any]:
        stats_provider = getattr(self._api, 'get_stats', None)
        if callable(stats_provider):
            return stats_provider()
        return dict(getattr(self._api, '_api_stats', {}))

    def _execute_on_main_thread(self, func, *, error_code: str) -> Dict[str, Any]:
        queue_manager = getattr(self._scene_builder, '_queue_manager', None)
        if queue_manager and hasattr(queue_manager, 'run_sync_operation'):
            return queue_manager.run_sync_operation(func, error_code=error_code)

        runner = getattr(self._api, 'run_on_main_thread', None)
        if callable(runner):
            try:
                return runner(func)
            except Exception as exc:  # pragma: no cover
                return error_response(error_code, str(exc))

        try:
            return func()
        except Exception as exc:  # pragma: no cover
            return error_response(error_code, str(exc))

    # ------------------------------------------------------------------
    # Basic endpoints
    def get_stats(self) -> Dict[str, Any]:
        stats = self._stats.copy()
        startup_error = getattr(self._api, '_startup_error', None)
        response = {
            'success': startup_error is None,
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        }
        if startup_error is not None:
            response['error'] = str(startup_error)
        return response

    def get_health(self) -> Dict[str, Any]:
        startup_error = getattr(self._api, '_startup_error', None)
        if startup_error is not None:
            return {
                'success': False,
                'error': str(startup_error),
                'timestamp': time.time(),
            }
        port = self._api.get_port() if self._api else 8899
        scene_object_count = self._scene_object_count()

        if VERSION_AVAILABLE and get_service_name and get_version:
            service_name = get_service_name('worldbuilder')
            version = get_version('worldbuilder', 'api_version')
        else:
            service_name = 'Agent WorldBuilder API'
            version = '0.1.0'

        return {
            'success': True,
            'service': service_name,
            'version': version,
            'url': f'http://localhost:{port}',
            'timestamp': time.time(),
            'scene_object_count': scene_object_count
        }

    def get_metrics(self) -> Dict[str, Any]:
        startup_error = getattr(self._api, '_startup_error', None)
        if startup_error is not None:
            return {
                'success': False,
                'error': str(startup_error),
                'metrics': collect_metrics(self._stats, scene_counter=self._scene_object_count),
            }
        metrics = collect_metrics(self._stats, scene_counter=self._scene_object_count)
        return {'success': True, 'metrics': metrics}

    def get_prometheus_metrics(self) -> str:
        startup_error = getattr(self._api, '_startup_error', None)
        metrics = collect_metrics(self._stats, scene_counter=self._scene_object_count)
        if startup_error is not None:
            reason = json.dumps(str(startup_error))
            return '\n'.join([
                '# ERROR worldbuilder_startup_failed WorldBuilder HTTP server failed to start',
                f"worldbuilder_startup_failed{{reason={reason}}} 1",
            ])
        lines = [
            '# HELP worldbuilder_requests_total Total HTTP requests received',
            '# TYPE worldbuilder_requests_total counter',
            f"worldbuilder_requests_total {metrics['requests_received']}",
            '# HELP worldbuilder_request_errors_total Failed HTTP requests',
            '# TYPE worldbuilder_request_errors_total counter',
            f"worldbuilder_request_errors_total {metrics['errors']}",
            '# HELP worldbuilder_scene_objects Scene objects present in /World',
            '# TYPE worldbuilder_scene_objects gauge',
            f"worldbuilder_scene_objects {metrics['scene_object_count']}",
            '# HELP worldbuilder_objects_queried Total objects inspected by query endpoints',
            '# TYPE worldbuilder_objects_queried counter',
            f"worldbuilder_objects_queried {metrics.get('objects_queried', 0)}",
        ]
        return '\n'.join(lines)

    # ------------------------------------------------------------------
    # Mutations
    def add_element(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        element = SceneElement(
            name=payload.get('name', f"element_{int(time.time())}"),  # type: ignore[name-defined]
            primitive_type=PrimitiveType(payload.get('element_type', 'cube')),
            position=tuple(payload.get('position', [0.0, 0.0, 0.0])),
            rotation=tuple(payload.get('rotation', [0.0, 0.0, 0.0])),
            scale=tuple(payload.get('scale', [1.0, 1.0, 1.0])),
            color=tuple(payload.get('color', [0.5, 0.5, 0.5])),
            parent_path=payload.get('parent_path', '/World'),
            metadata=payload.get('metadata', {})
        )
        response = self._scene_builder.add_element_to_stage(element)
        if response.get('success'):
            increment_elements = getattr(self._api, 'increment_elements_created', None)
            if callable(increment_elements):
                increment_elements(1)
            increment_success = getattr(self._api, 'increment_successful_requests', None)
            if callable(increment_success):
                increment_success()
        return response

    def create_batch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        batch_name = payload['batch_name']
        elements = payload.get('elements', [])
        batch_transform = None
        if 'batch_transform' in payload:
            batch_transform = payload['batch_transform']
        return self._scene_builder.create_batch_in_scene(batch_name, elements, batch_transform)

    def place_asset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        asset = AssetPlacement(
            name=payload['name'],
            asset_path=payload['asset_path'],
            prim_path=payload.get('prim_path') or payload.get('parent_path', payload['name']),
            position=tuple(payload.get('position', [0.0, 0.0, 0.0])),
            rotation=tuple(payload.get('rotation', [0.0, 0.0, 0.0])),
            scale=tuple(payload.get('scale', [1.0, 1.0, 1.0])),
            metadata=payload.get('metadata', {})
        )
        return self._scene_builder.place_asset_in_stage(asset)

    def transform_asset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._scene_builder.transform_asset_in_stage(
            payload['prim_path'],
            tuple(payload['position']) if payload.get('position') else None,
            tuple(payload['rotation']) if payload.get('rotation') else None,
            tuple(payload['scale']) if payload.get('scale') else None,
        )

    def remove_element(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        element_path = payload.get('element_path') or payload.get('usd_path')
        if not element_path:
            return error_response(
                'MISSING_PARAMETER',
                'element_path is required',
                details={'parameter': 'element_path'}
            )
        return self._scene_builder.remove_element_from_stage(element_path)

    def clear_path(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = payload.get('path')
        if not path:
            return error_response(
                'MISSING_PARAMETER',
                'path is required',
                details={'parameter': 'path'}
            )
        return self._scene_builder.clear_stage_path(path)

    # ------------------------------------------------------------------
    # Queries
    def get_scene(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = payload.get('path', '/World')
        include_metadata = payload.get('include_metadata', True)
        return self._execute_on_main_thread(
            lambda: self._scene_builder.get_scene_contents(path, include_metadata),
            error_code='GET_SCENE_FAILED'
        )

    def get_scene_status(self) -> Dict[str, Any]:
        def _compute_status():
            stage = None
            try:
                stage = self._scene_builder._usd_context.get_stage()
            except Exception:
                stage = None

            if not stage:
                return error_response('STAGE_UNAVAILABLE', 'No USD stage available')

            world_prim = stage.GetPrimAtPath('/World')
            if not world_prim or not world_prim.IsValid():
                return error_response('STAGE_UNAVAILABLE', "'/World' prim not found")

            stats = self._scene_builder.get_statistics()
            scene_info = {
                'has_stage': True,
                'prim_count': stats.get('total_prims', 0),
                'asset_count': stats.get('geometric_prims', 0),
                'queue_status': stats.get('queue_status', {}),
                'batch_statistics': stats.get('batch_statistics', {}),
            }
            return {'success': True, 'scene': scene_info}

        return self._execute_on_main_thread(_compute_status, error_code='SCENE_STATUS_FAILED')

    def list_elements(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        filter_type = payload.get('filter_type', '') if payload else ''
        page = max(1, int(payload.get('page', 1)))
        page_size = max(1, min(int(payload.get('page_size', 50)), 500))

        def _list_elements():
            result = self._scene_builder.list_elements_in_scene(filter_type)
            if not isinstance(result, dict) or not result.get('success', False):
                return result

            elements = result.get('elements', [])
            total = len(elements)
            start = (page - 1) * page_size
            end = start + page_size
            paged = elements[start:end]

            return {
                **result,
                'elements': paged,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_items': total,
                    'total_pages': max(1, (total + page_size - 1) // page_size),
                },
            }

        return self._execute_on_main_thread(
            _list_elements,
            error_code='LIST_ELEMENTS_FAILED'
        )

    def get_batch_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        batch_name = payload.get('batch_name')
        if not batch_name:
            return error_response(
                'MISSING_PARAMETER',
                'batch_name is required',
                details={'parameter': 'batch_name'}
            )
        return self._execute_on_main_thread(
            lambda: self._scene_builder.get_batch_info(batch_name),
            error_code='BATCH_INFO_FAILED'
        )

    def list_batches(self) -> Dict[str, Any]:
        return self._execute_on_main_thread(
            self._scene_builder.list_batches,
            error_code='LIST_BATCHES_FAILED'
        )

    def get_request_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request_id = payload.get('request_id')
        if not request_id:
            return error_response(
                'MISSING_PARAMETER',
                'request_id is required',
                details={'parameter': 'request_id'}
            )
        return self._scene_builder.get_request_status(request_id)

    def query_objects_by_type(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        object_type = payload.get('type') or payload.get('object_type')
        if isinstance(object_type, (list, tuple)):
            object_type = object_type[0] if object_type else None
        if object_type is not None and not isinstance(object_type, str):
            object_type = str(object_type)
        if not object_type:
            return error_response(
                'MISSING_PARAMETER',
                'type parameter is required',
                details={'parameter': 'type'}
            )
        if hasattr(self._api, '_query_objects_by_type'):
            normalized = self._execute_on_main_thread(
                lambda: self._api._query_objects_by_type(object_type),
                error_code='QUERY_OBJECTS_FAILED'
            )
            if isinstance(normalized, dict) and normalized.get('success', True) and 'query_type' not in normalized:
                normalized['query_type'] = object_type
            return normalized
        return error_response('HELPER_UNAVAILABLE', 'Query helper unavailable')

    def query_objects_in_bounds(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        min_bounds = payload.get('min') or payload.get('min_bounds')
        max_bounds = payload.get('max') or payload.get('max_bounds')
        if not min_bounds or not max_bounds:
            return error_response(
                'VALIDATION_ERROR',
                'Bounds must include both min and max values',
                details={'received': {'min': min_bounds, 'max': max_bounds}}
            )
        min_bounds = ensure_vector3(min_bounds)
        max_bounds = ensure_vector3(max_bounds)
        if hasattr(self._api, '_query_objects_in_bounds'):
            return self._execute_on_main_thread(
                lambda: self._api._query_objects_in_bounds(min_bounds, max_bounds),
                error_code='QUERY_OBJECTS_IN_BOUNDS_FAILED'
            )
        return error_response('HELPER_UNAVAILABLE', 'Bounds query helper unavailable')

    def query_objects_near_point(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        point = payload.get('point')
        if not point:
            return error_response(
                'MISSING_PARAMETER',
                'point parameter is required',
                details={'parameter': 'point'}
            )
        point = ensure_vector3(point)
        radius = payload.get('radius', 5.0)
        if hasattr(self._api, '_query_objects_near_point'):
            return self._execute_on_main_thread(
                lambda: self._api._query_objects_near_point(point, radius),
                error_code='QUERY_OBJECTS_NEAR_POINT_FAILED'
            )
        return error_response('HELPER_UNAVAILABLE', 'Near-point query helper unavailable')

    def calculate_bounds(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        objects = payload.get('objects', [])
        if not objects:
            return error_response(
                'MISSING_PARAMETER',
                'objects list is required',
                details={'parameter': 'objects'}
            )
        if hasattr(self._api, '_calculate_bounds'):
            return self._execute_on_main_thread(
                lambda: self._api._calculate_bounds(objects),
                error_code='CALCULATE_BOUNDS_FAILED'
            )
        return error_response('HELPER_UNAVAILABLE', 'Bounds helper unavailable')

    def find_ground_level(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        position = payload.get('position')
        if not position:
            return error_response(
                'MISSING_PARAMETER',
                'position parameter is required',
                details={'parameter': 'position'}
            )
        position = ensure_vector3(position)
        radius = payload.get('search_radius', 10.0)
        if hasattr(self._api, '_find_ground_level'):
            return self._execute_on_main_thread(
                lambda: self._api._find_ground_level(position, radius),
                error_code='FIND_GROUND_LEVEL_FAILED'
            )
        return error_response(
            'HELPER_UNAVAILABLE',
            'Ground level helper unavailable'
        )

    def align_objects(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        objects = payload.get('objects', [])
        axis = payload.get('axis')
        alignment = payload.get('alignment', 'center')
        spacing = payload.get('spacing')
        if not objects or not axis:
            return error_response(
                'MISSING_PARAMETER',
                'objects and axis are required',
                details={'parameters': ['objects', 'axis']}
            )
        if hasattr(self._api, '_align_objects'):
            return self._execute_on_main_thread(
                lambda: self._api._align_objects(objects, axis, alignment, spacing),
                error_code='ALIGN_OBJECTS_FAILED'
            )
        return error_response('HELPER_UNAVAILABLE', 'Align helper unavailable')

    # ------------------------------------------------------------------
    # Internal helpers
    def _scene_object_count(self) -> int:
        return count_world_children(self._get_stage)

    def _get_stage(self):
        try:
            return self._scene_builder._usd_context.get_stage()
        except Exception:
            return None
