"""
HTTP request handler for WorldSurveyor API endpoints (unified).

This refactor aligns routes with the unified agent_world_http.py service and
standardizes endpoint naming. Isaac Sim specific APIs are only imported when
executed on the main thread via the API interface camera queue.
"""

import json
import logging
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Any, List, Optional

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

# WaypointManager is accessed via api_interface; no direct import required here


# Import centralized version management (optional)
def _find_and_import_versions():
    try:
        import sys
        # Strategy 1: Search upward in directory tree for agentworld-extensions
        current = Path(__file__).resolve()
        for _ in range(10):
            if current.name == 'agentworld-extensions' or (current / 'agent_world_versions.py').exists():
                sys.path.insert(0, str(current))
                from agent_world_versions import get_version, get_service_name
                return get_version, get_service_name
            if current.parent == current:
                break
            current = current.parent
        # Strategy 2: Environment variable fallback
        env_path = os.getenv('AGENT_WORLD_VERSIONS_PATH')
        if env_path:
            sys.path.insert(0, env_path)
            from agent_world_versions import get_version, get_service_name
            return get_version, get_service_name
        return None, None
    except Exception:
        return None, None


try:
    get_version, get_service_name = _find_and_import_versions()
    VERSION_AVAILABLE = get_version is not None
except Exception:
    VERSION_AVAILABLE = False

logger = logging.getLogger(__name__)

# Optional request validation
try:
    from pydantic import BaseModel, conlist, Field
    _PydAvailable = True
except Exception:
    _PydAvailable = False


def _first(param_val, default=None):
    """Utility to extract scalar from parse_qs-style values."""
    if isinstance(param_val, list):
        return param_val[0] if param_val else default
    return param_val if param_val is not None else default


def _parse_bool(val, default=False):
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ('1', 'true', 'yes', 'on')
    if isinstance(val, list):
        return _parse_bool(val[0] if val else default, default)
    return default


class WorldSurveyorHTTPHandler(WorldHTTPHandler):
    """HTTP request handler for WorldSurveyor API endpoints (unified)."""

    api_interface = None

    def get_routes(self):  # type: ignore[override]
        """Return route mappings for unified HTTP handler."""
        return {
            # UI routes (serve waypoint manager page)
            '': self._handle_ui,
            'index.html': self._handle_ui,
            'waypoint_manager.html': self._handle_ui,
            'ui': self._handle_ui,
            # Waypoints
            'waypoints': self._handle_waypoints_summary,
            'waypoints/create': self._handle_create_waypoint,
            'waypoints/list': self._handle_list_waypoints,
            'waypoints/update': self._handle_update_waypoint,
            'waypoints/remove': self._handle_remove_waypoint,
            'waypoints/clear': self._handle_clear_waypoints,
            'waypoints/export': self._handle_export_waypoints,
            'waypoints/import': self._handle_import_waypoints,
            'waypoints/goto': self._handle_goto_waypoint,
            # Back-compat waypoint aliases
            'create_waypoint': self._handle_create_waypoint,
            'list_waypoints': self._handle_list_waypoints,
            'update_waypoint': self._handle_update_waypoint,
            'remove_waypoint': self._handle_remove_waypoint,
            'clear_all_waypoints': self._handle_clear_waypoints,
            'export_waypoints': self._handle_export_waypoints,
            'import_waypoints': self._handle_import_waypoints,
            'goto_waypoint': self._handle_goto_waypoint,
            # Groups
            'groups': self._handle_groups_summary,
            'groups/create': self._handle_create_group,
            'groups/list': self._handle_list_groups,
            'groups/get': self._handle_get_group,
            'groups/remove': self._handle_remove_group,
            'groups/hierarchy': self._handle_group_hierarchy,
            'groups/add_waypoint': self._handle_add_waypoint_to_groups,
            'groups/remove_waypoint': self._handle_remove_waypoint_from_groups,
            'groups/of_waypoint': self._handle_get_waypoint_groups,
            'groups/waypoints': self._handle_get_group_waypoints,
            # Back-compat group aliases
            'create_group': self._handle_create_group,
            'list_groups': self._handle_list_groups,
            'get_group': self._handle_get_group,
            'get_group_hierarchy': self._handle_group_hierarchy,
            'remove_group': self._handle_remove_group,
            'add_waypoint_to_groups': self._handle_add_waypoint_to_groups,
            'remove_waypoint_from_groups': self._handle_remove_waypoint_from_groups,
            'get_waypoint_groups': self._handle_get_waypoint_groups,
            'get_group_waypoints': self._handle_get_group_waypoints,
            # Markers
            'markers/visible': self._handle_set_markers_visible,
            'markers/individual': self._handle_set_individual_marker_visible,
            'markers/selective': self._handle_set_selective_markers_visible,
            'markers/debug': self._handle_debug_status,
            # Back-compat marker aliases
            'set_markers_visible': self._handle_set_markers_visible,
            'set_individual_marker_visible': self._handle_set_individual_marker_visible,
            'set_selective_markers_visible': self._handle_set_selective_markers_visible,
            'debug_status': self._handle_debug_status,
        }

    # ---------- Waypoints ----------
    def _handle_waypoints_summary(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        count = self.api_interface.waypoint_manager.get_waypoint_count()
        return {'success': True, 'waypoint_count': count}

    def _handle_create_waypoint(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return {'success': False, 'error': 'waypoints/create requires POST'}

        if _PydAvailable:
            class CreateWaypointModel(BaseModel):
                position: conlist(float, min_length=3, max_length=3)
                waypoint_type: str = Field(default='point_of_interest')
                name: Optional[str] = None
                target: conlist(float, min_length=3, max_length=3) | None = None
                metadata: dict = Field(default_factory=dict)
                group_ids: List[str] | None = None
            try:
                data = CreateWaypointModel(**data).model_dump()
            except Exception as ve:
                return {'success': False, 'error': f'Validation error: {ve}'}
        else:
            pos = data.get('position')
            if not pos or not isinstance(pos, (list, tuple)) or len(pos) != 3:
                return {'success': False, 'error': 'position must be [x,y,z]'}

        position = tuple(data['position'])
        target = tuple(data['target']) if data.get('target') else None
        waypoint_id = self.api_interface.waypoint_manager.create_waypoint(
            position=position,
            waypoint_type=data.get('waypoint_type', 'point_of_interest'),
            name=data.get('name'),
            target=target,
            metadata=data.get('metadata', {}),
            group_ids=data.get('group_ids')
        )
        return {'success': True, 'waypoint_id': waypoint_id}

    def _handle_list_waypoints(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        wp_type = _first(data.get('waypoint_type'))
        group_id = _first(data.get('group_id'))
        waypoints = self.api_interface.waypoint_manager.list_waypoints(wp_type, group_id)
        return {
            'success': True,
            'waypoints': [asdict(wp) for wp in waypoints],
            'count': len(waypoints)
        }

    def _handle_update_waypoint(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return {'success': False, 'error': 'waypoints/update requires POST'}
        waypoint_id = data.get('waypoint_id')
        if not waypoint_id:
            return {'success': False, 'error': 'waypoint_id is required'}

        updates: Dict[str, Any] = {}
        for key in ('name', 'waypoint_type', 'notes', 'metadata'):
            if key in data:
                updates[key] = data[key]
        updated = self.api_interface.waypoint_manager.update_waypoint(waypoint_id, **updates)
        return {'success': bool(updated), 'updated': bool(updated)}

    def _handle_remove_waypoint(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return {'success': False, 'error': 'waypoints/remove requires POST'}
        waypoint_id = data.get('waypoint_id')
        if not waypoint_id:
            return {'success': False, 'error': 'waypoint_id is required'}
        removed = self.api_interface.waypoint_manager.remove_waypoint(waypoint_id)
        return {'success': bool(removed), 'removed': bool(removed)}

    def _handle_clear_waypoints(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return {'success': False, 'error': 'waypoints/clear requires POST'}
        count = self.api_interface.waypoint_manager.clear_waypoints()
        return {'success': True, 'cleared': count}

    def _handle_export_waypoints(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        include_groups = _parse_bool(_first(data.get('include_groups'), True), True)
        exported = self.api_interface.waypoint_manager.export_waypoints(include_groups)
        return {'success': True, 'export': exported}

    def _handle_import_waypoints(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return {'success': False, 'error': 'waypoints/import requires POST'}
        merge_mode = data.get('merge_mode', 'replace')
        # Accept either full payload or nested under 'export'
        payload = data.get('export', data)
        stats = self.api_interface.waypoint_manager.import_waypoints(payload, merge_mode)
        return {'success': True, 'import_stats': stats}

    def _handle_goto_waypoint(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return {'success': False, 'error': 'waypoints/goto requires POST'}
        waypoint_id = data.get('waypoint_id')
        if not waypoint_id:
            return {'success': False, 'error': 'waypoint_id is required'}
        return self._queue_camera_operation('goto_waypoint', {'waypoint_id': waypoint_id})

    # ---------- Groups ----------
    def _handle_groups_summary(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        stats = self.api_interface.waypoint_manager._database.get_statistics()
        return {
            'success': True,
            'total_groups': stats.get('total_groups', 0),
            'total_waypoints': stats.get('total_waypoints', 0)
        }

    def _handle_create_group(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return {'success': False, 'error': 'groups/create requires POST'}
        name = data.get('name')
        if not name:
            return {'success': False, 'error': 'name is required'}
        description = data.get('description')
        parent_group_id = data.get('parent_group_id')
        color = data.get('color', '#4A90E2')
        group_id = self.api_interface.waypoint_manager.create_group(name, description, parent_group_id, color)
        return {'success': True, 'group_id': group_id}

    def _handle_list_groups(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        parent_group_id = _first(data.get('parent_group_id'))
        groups = self.api_interface.waypoint_manager.list_groups(parent_group_id)
        return {'success': True, 'groups': groups, 'count': len(groups)}

    def _handle_get_group(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        group_id = _first(data.get('group_id'))
        if not group_id:
            return {'success': False, 'error': 'group_id is required'}
        group = self.api_interface.waypoint_manager.get_group(group_id)
        if group:
            return {'success': True, 'group': group}
        return {'success': False, 'error': f'Group {group_id} not found'}

    def _handle_remove_group(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return {'success': False, 'error': 'groups/remove requires POST'}
        group_id = data.get('group_id')
        if not group_id:
            return {'success': False, 'error': 'group_id is required'}
        cascade = _parse_bool(data.get('cascade', False), False)
        removed = self.api_interface.waypoint_manager.remove_group(group_id, cascade)
        return {'success': bool(removed), 'removed': bool(removed)}

    def _handle_group_hierarchy(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        hierarchy = self.api_interface.waypoint_manager.get_group_hierarchy()
        return {'success': True, 'hierarchy': hierarchy['hierarchy'], 'total_groups': hierarchy['total_groups']}

    def _handle_add_waypoint_to_groups(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return {'success': False, 'error': 'groups/add_waypoint requires POST'}
        waypoint_id = data.get('waypoint_id')
        group_ids = data.get('group_ids', [])
        if not waypoint_id:
            return {'success': False, 'error': 'waypoint_id is required'}
        if not group_ids:
            return {'success': False, 'error': 'group_ids list is required'}
        added = self.api_interface.waypoint_manager.add_waypoint_to_groups(waypoint_id, group_ids)
        return {'success': True, 'added_to_groups': added}

    def _handle_remove_waypoint_from_groups(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return {'success': False, 'error': 'groups/remove_waypoint requires POST'}
        waypoint_id = data.get('waypoint_id')
        group_ids = data.get('group_ids', [])
        if not waypoint_id:
            return {'success': False, 'error': 'waypoint_id is required'}
        # If no group_ids provided, remove from all
        if not group_ids:
            current = self.api_interface.waypoint_manager.get_waypoint_groups(waypoint_id)
            group_ids = [g['id'] for g in current]
        removed = self.api_interface.waypoint_manager.remove_waypoint_from_groups(waypoint_id, group_ids) if group_ids else 0
        return {'success': True, 'removed_from_groups': removed}

    def _handle_get_waypoint_groups(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        waypoint_id = _first(data.get('waypoint_id'))
        if not waypoint_id:
            return {'success': False, 'error': 'waypoint_id is required'}
        groups = self.api_interface.waypoint_manager.get_waypoint_groups(waypoint_id)
        return {'success': True, 'groups': groups, 'count': len(groups)}

    def _handle_get_group_waypoints(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        group_id = _first(data.get('group_id'))
        include_nested = _parse_bool(_first(data.get('include_nested'), False), False)
        if not group_id:
            return {'success': False, 'error': 'group_id is required'}
        waypoints = self.api_interface.waypoint_manager.get_group_waypoints(group_id, include_nested)
        return {
            'success': True,
            'waypoints': [asdict(wp) for wp in waypoints],
            'count': len(waypoints)
        }

    # ---------- Markers ----------
    def _handle_set_markers_visible(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return {'success': False, 'error': 'markers/visible requires POST'}
        visible = _parse_bool(data.get('visible', True), True)
        self.api_interface.waypoint_manager.set_markers_visible(bool(visible))
        return {'success': True, 'markers_visible': bool(visible)}

    def _handle_set_individual_marker_visible(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return {'success': False, 'error': 'markers/individual requires POST'}
        waypoint_id = data.get('waypoint_id')
        if not waypoint_id:
            return {'success': False, 'error': 'waypoint_id is required'}
        visible = _parse_bool(data.get('visible', True), True)
        self.api_interface.waypoint_manager.set_individual_marker_visible(waypoint_id, bool(visible))
        return {'success': True, 'waypoint_id': waypoint_id, 'marker_visible': bool(visible)}

    def _handle_set_selective_markers_visible(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return {'success': False, 'error': 'markers/selective requires POST'}
        visible_waypoints = data.get('visible_waypoint_ids') or data.get('waypoint_ids') or []
        if not isinstance(visible_waypoints, list):
            return {'success': False, 'error': 'visible_waypoint_ids must be a list'}
        self.api_interface.waypoint_manager.set_selective_visibility(set(visible_waypoints))
        return {'success': True, 'visible_waypoint_ids': visible_waypoints}

    def _handle_debug_status(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        status = self.api_interface.waypoint_manager.get_debug_status()
        return {
            'success': True,
            'debug_status': status,
            'waypoint_count': self.api_interface.waypoint_manager.get_waypoint_count()
        }

    # ---------- UI ----------
    def _handle_ui(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            static_dir = Path(__file__).parent / 'static'
            html_path = static_dir / 'waypoint_manager.html'
            html = html_path.read_text(encoding='utf-8')
            return {'success': True, '_raw_text': html, '_content_type': 'text/html; charset=utf-8'}
        except Exception as e:
            return {'success': False, 'error': f'Failed to load UI: {e}'}

    # ---------- Camera queue helper ----------
    def _queue_camera_operation(self, operation: str, params: Dict) -> Dict:
        """Queue a camera operation for thread-safe processing on main thread."""
        import uuid
        request_id = f"camera_{operation}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"

        request = {
            'request_id': request_id,
            'operation': operation,
            'params': params,
            'timestamp': time.time(),
            'completed': False,
            'result': None,
            'error': None,
        }

        with self.api_interface._queue_lock:
            self.api_interface._camera_queue.append(request)
            self.api_interface._request_tracking[request_id] = request

        timeout = 5.0
        start = time.time()
        while not request['completed'] and (time.time() - start) < timeout:
            time.sleep(0.05)

        if request['completed']:
            if request.get('result'):
                return request['result']
            return {'success': False, 'error': request.get('error', 'Unknown error')}
        return {'success': False, 'error': 'Operation timed out waiting for main thread processing'}
