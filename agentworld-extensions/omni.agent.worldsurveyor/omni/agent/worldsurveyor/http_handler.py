"""HTTP handler bridging WorldSurveyor routes to controller/service stack."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from agentworld_core.logging import module_logger

from .http import WorldSurveyorController
from .services import WorldSurveyorService
from .errors import MethodNotAllowed, ValidationFailure, error_response

try:
    from agentworld_core.http import WorldHTTPHandler
    UNIFIED = True
except ImportError:  # pragma: no cover - Isaac fallback
    from http.server import BaseHTTPRequestHandler as WorldHTTPHandler  # type: ignore
    UNIFIED = False

logger = module_logger(service='worldsurveyor', component='http_handler')


class WorldSurveyorHTTPHandler(WorldHTTPHandler):
    """HTTP request handler for WorldSurveyor operations."""

    api_interface = None

    @property
    def controller(self) -> WorldSurveyorController:
        if not hasattr(self, '_controller'):
            service = WorldSurveyorService(self.api_interface)
            self._controller = WorldSurveyorController(service)
        return self._controller

    def get_routes(self):  # type: ignore[override]
        return {
            '': self._handle_ui,
            'index.html': self._handle_ui,
            'ui': self._handle_ui,
            'waypoint_manager.html': self._handle_ui,
            'waypoints': self._route_waypoints_summary,
            'waypoints/create': self._route_create_waypoint,
            'waypoints/list': self._route_list_waypoints,
            'waypoints/update': self._route_update_waypoint,
            'waypoints/remove': self._route_remove_waypoint,
            'waypoints/remove_selected': self._route_remove_selected,
            'waypoints/clear': self._route_clear_waypoints,
            'waypoints/export': self._route_export_waypoints,
            'waypoints/import': self._route_import_waypoints,
            'waypoints/goto': self._route_goto_waypoint,
            'groups': self._route_groups_summary,
            'groups/create': self._route_create_group,
            'groups/list': self._route_list_groups,
            'groups/get': self._route_get_group,
            'groups/update': self._route_update_group,
            'groups/remove': self._route_remove_group,
            'groups/clear': self._route_clear_groups,
            'groups/hierarchy': self._route_group_hierarchy,
            'groups/add_waypoint': self._route_add_waypoint_to_groups,
            'groups/remove_waypoint': self._route_remove_waypoint_from_groups,
            'groups/of_waypoint': self._route_get_waypoint_groups,
            'groups/waypoints': self._route_get_group_waypoints,
            'markers/visible': self._route_set_markers_visible,
            'markers/individual': self._route_set_individual_marker_visible,
            'markers/selective': self._route_set_selective_markers_visible,
            'markers/debug': self._route_debug_status,
            'waypoint_types': self._route_waypoint_types,
        }

    # ------------------------------------------------------------------
    def _route_waypoints_summary(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('waypoints requires GET', details={'method': method})
        return self.controller.waypoints_summary()

    def _route_create_waypoint(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('waypoints/create requires POST', details={'method': method})
        return self.controller.create_waypoint(data or {})

    def _route_list_waypoints(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('waypoints/list requires GET', details={'method': method})
        return self.controller.list_waypoints(self._normalize_query_params(data))

    def _route_update_waypoint(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('waypoints/update requires POST', details={'method': method})
        return self.controller.update_waypoint(data or {})

    def _route_remove_waypoint(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('waypoints/remove requires POST', details={'method': method})
        return self.controller.remove_waypoint(data or {})

    def _route_remove_selected(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('waypoints/remove_selected requires POST', details={'method': method})
        return self.controller.remove_selected_waypoints(data or {})

    def _route_clear_waypoints(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('waypoints/clear requires POST', details={'method': method})
        return self.controller.clear_waypoints()

    def _route_export_waypoints(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('waypoints/export requires GET', details={'method': method})
        return self.controller.export_waypoints(self._normalize_query_params(data))

    def _route_import_waypoints(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('waypoints/import requires POST', details={'method': method})
        return self.controller.import_waypoints(data or {})

    def _route_goto_waypoint(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('waypoints/goto requires POST', details={'method': method})
        return self.controller.goto_waypoint(data or {})

    def _route_groups_summary(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('groups requires GET', details={'method': method})
        return self.controller.groups_summary()

    def _route_create_group(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('groups/create requires POST', details={'method': method})
        return self.controller.create_group(data or {})

    def _route_list_groups(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('groups/list requires GET', details={'method': method})
        return self.controller.list_groups(self._normalize_query_params(data))

    def _route_get_group(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('groups/get requires GET', details={'method': method})
        return self.controller.get_group(self._normalize_query_params(data))

    def _route_update_group(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('groups/update requires POST', details={'method': method})
        return self.controller.update_group(data or {})

    def _route_remove_group(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('groups/remove requires POST', details={'method': method})
        return self.controller.remove_group(data or {})

    def _route_clear_groups(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('groups/clear requires POST', details={'method': method})
        return self.controller.clear_groups(data or {})

    def _route_group_hierarchy(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('groups/hierarchy requires GET', details={'method': method})
        return self.controller.group_hierarchy()

    def _route_add_waypoint_to_groups(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('groups/add_waypoint requires POST', details={'method': method})
        return self.controller.add_waypoint_to_groups(data or {})

    def _route_remove_waypoint_from_groups(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('groups/remove_waypoint requires POST', details={'method': method})
        return self.controller.remove_waypoint_from_groups(data or {})

    def _route_get_waypoint_groups(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('groups/of_waypoint requires GET', details={'method': method})
        return self.controller.get_waypoint_groups(self._normalize_query_params(data))

    def _route_get_group_waypoints(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('groups/waypoints requires GET', details={'method': method})
        return self.controller.get_group_waypoints(self._normalize_query_params(data))

    def _route_set_markers_visible(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('markers/visible requires POST', details={'method': method})
        return self.controller.set_markers_visible(data or {})

    def _route_set_individual_marker_visible(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('markers/individual requires POST', details={'method': method})
        return self.controller.set_individual_marker_visible(data or {})

    def _route_set_selective_markers_visible(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('markers/selective requires POST', details={'method': method})
        return self.controller.set_selective_markers_visible(data or {})

    def _route_debug_status(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('markers/debug requires GET', details={'method': method})
        return self.controller.debug_status()

    def _route_waypoint_types(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('waypoint_types requires GET', details={'method': method})
        return self.controller.get_waypoint_types()

    # ------------------------------------------------------------------
    def _normalize_query_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for key, value in (params or {}).items():
            if isinstance(value, list):
                normalized[key] = value[0] if len(value) == 1 else value
            else:
                normalized[key] = value
        return normalized

    def _handle_ui(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        static_path = Path(__file__).parent / 'static' / 'waypoint_manager.html'
        try:
            html = static_path.read_text(encoding='utf-8')
        except Exception as exc:  # pragma: no cover - UI optional in tests
            logger.warning('ui_render_failed', extra={'error': str(exc)})
            return error_response('UI_UNAVAILABLE', 'Waypoint manager UI unavailable')
        return {'success': True, '_raw_text': html, '_content_type': 'text/html; charset=utf-8'}

    def handle_one_request(self):  # type: ignore[override]
        try:
            super().handle_one_request()
        except MethodNotAllowed as exc:
            self._send_error_response(405, exc.message)
        except ValidationFailure as exc:
            self._send_error_response(400, exc.message)


__all__ = ['WorldSurveyorHTTPHandler']
