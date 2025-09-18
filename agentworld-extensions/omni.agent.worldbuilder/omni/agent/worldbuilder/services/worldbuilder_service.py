"""Business logic for WorldBuilder HTTP routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
import time

from ..scene_builder import SceneElement, AssetPlacement, PrimitiveType

try:
    from agent_world_versions import get_version, get_service_name
    VERSION_AVAILABLE = True
except ImportError:
    get_version = get_service_name = None
    VERSION_AVAILABLE = False


class WorldBuilderService:
    """Wrap USD operations exposed through the HTTP API."""

    def __init__(self, api_interface):
        self._api = api_interface

    # ------------------------------------------------------------------
    # Helper properties
    @property
    def _scene_builder(self):
        return self._api._scene_builder

    @property
    def _stats(self) -> Dict[str, Any]:
        return getattr(self._api, '_api_stats', {})

    # ------------------------------------------------------------------
    # Basic endpoints
    def get_stats(self) -> Dict[str, Any]:
        return {
            'success': True,
            'stats': self._stats.copy(),
            'timestamp': datetime.now().isoformat()
        }

    def get_health(self) -> Dict[str, Any]:
        port = self._api.get_port() if self._api else 8899
        scene_object_count = self._count_scene_objects()

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
        metrics = self._collect_metrics()
        return {'success': True, 'metrics': metrics}

    def get_prometheus_metrics(self) -> str:
        metrics = self._collect_metrics()
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
            self._stats['scene_elements_created'] = self._stats.get('scene_elements_created', 0) + 1
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
            return {'success': False, 'error': 'element_path is required'}
        return self._scene_builder.remove_element_from_stage(element_path)

    def clear_path(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._scene_builder.clear_stage_path(payload['path'])

    # ------------------------------------------------------------------
    # Queries
    def get_scene(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = payload.get('path', '/World')
        include_metadata = payload.get('include_metadata', True)
        return self._scene_builder.get_scene_contents(path, include_metadata)

    def get_scene_status(self) -> Dict[str, Any]:
        return self._scene_builder.get_scene_status()

    def list_elements(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        filter_type = payload.get('filter_type', '') if payload else ''
        return self._scene_builder.list_elements_in_scene(filter_type)

    def get_batch_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        batch_name = payload.get('batch_name')
        if not batch_name:
            return {'success': False, 'error': 'batch_name is required'}
        return self._scene_builder.get_batch_info(batch_name)

    def list_batches(self) -> Dict[str, Any]:
        return self._scene_builder.list_batches()

    def get_request_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request_id = payload.get('request_id')
        if not request_id:
            return {'success': False, 'error': 'request_id is required'}
        return self._scene_builder.get_request_status(request_id)

    def query_objects_by_type(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        object_type = payload.get('type') or payload.get('object_type')
        if not object_type:
            return {'success': False, 'error': 'type parameter is required'}
        return self._scene_builder.query_objects_by_type(object_type)

    def query_objects_in_bounds(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        min_bounds = payload.get('min') or payload.get('min_bounds')
        max_bounds = payload.get('max') or payload.get('max_bounds')
        if not min_bounds or not max_bounds:
            return {'success': False, 'error': 'Bounds must include min and max values'}
        min_bounds = self._ensure_vector(min_bounds)
        max_bounds = self._ensure_vector(max_bounds)
        return self._scene_builder.query_objects_in_bounds(min_bounds, max_bounds)

    def query_objects_near_point(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        point = payload.get('point')
        if not point:
            return {'success': False, 'error': 'point parameter is required'}
        point = self._ensure_vector(point)
        radius = payload.get('radius', 5.0)
        return self._scene_builder.query_objects_near_point(point, radius)

    def calculate_bounds(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        objects = payload.get('objects', [])
        if not objects:
            return {'success': False, 'error': 'objects list is required'}
        return self._scene_builder.calculate_bounds(objects)

    def find_ground_level(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        position = payload.get('position')
        if not position:
            return {'success': False, 'error': 'position parameter is required'}
        position = self._ensure_vector(position)
        radius = payload.get('search_radius', 10.0)
        if hasattr(self._api, '_find_ground_level'):
            return self._api._find_ground_level(position, radius)
        return {'success': False, 'error': 'Ground level helper unavailable'}

    def align_objects(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        objects = payload.get('objects', [])
        axis = payload.get('axis')
        alignment = payload.get('alignment', 'center')
        spacing = payload.get('spacing')
        if not objects or not axis:
            return {'success': False, 'error': 'objects and axis are required'}
        if hasattr(self._api, '_align_objects'):
            return self._api._align_objects(objects, axis, alignment, spacing)
        return {'success': False, 'error': 'Align helper unavailable'}

    # ------------------------------------------------------------------
    # Internal helpers
    def _count_scene_objects(self) -> int:
        try:
            stage = self._scene_builder._usd_context.get_stage()
            if not stage:
                return 0
            world_prim = stage.GetPrimAtPath('/World')
            if not world_prim:
                return 0
            return len(list(world_prim.GetAllChildren()))
        except Exception:
            return 0

    def _collect_metrics(self) -> Dict[str, Any]:
        stats = self._stats
        scene_object_count = self._count_scene_objects()

        start_time = stats.get('start_time')
        uptime = 0.0
        if start_time:
            try:
                if isinstance(start_time, str):
                    start_timestamp = datetime.fromisoformat(start_time.replace('Z', '+00:00')).timestamp()
                else:
                    start_timestamp = float(start_time)
                uptime = time.time() - start_timestamp  # type: ignore[name-defined]
            except Exception:
                uptime = 0.0

        return {
            'requests_received': stats.get('requests_received', 0),
            'errors': stats.get('failed_requests', 0),
            'elements_created': stats.get('elements_created', 0),
            'batches_created': stats.get('batches_created', 0),
            'assets_placed': stats.get('assets_placed', 0),
            'objects_queried': stats.get('objects_queried', 0),
            'transformations_applied': stats.get('transformations_applied', 0),
            'uptime_seconds': uptime,
            'scene_object_count': scene_object_count,
            'server_running': True,
            'start_time': start_time,
        }

    def _ensure_vector(self, value: Any) -> List[float]:
        """Convert query parameters into a numeric [x, y, z] vector."""
        if isinstance(value, list):
            if len(value) == 1 and isinstance(value[0], str):
                value = value[0]
            else:
                value = [float(x) for x in value]
        if isinstance(value, str):
            value = [float(part.strip()) for part in value.split(',')]
        if len(value) != 3:
            raise ValueError('Vector must contain exactly three values')
        return [float(x) for x in value]
