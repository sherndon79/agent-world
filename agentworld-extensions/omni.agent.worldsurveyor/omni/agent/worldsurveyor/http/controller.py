"""Controller functions for WorldSurveyor HTTP routes."""

from __future__ import annotations

from typing import Any, Callable, Dict

from agentworld_core.logging import module_logger

from ..errors import WorldSurveyorError, ValidationFailure, MethodNotAllowed, error_response
from ..transport import normalize_transport_response

logger = module_logger(service='worldsurveyor', component='controller')


class WorldSurveyorController:
    """Coordinate request validation and service execution for WorldSurveyor."""

    def __init__(self, service) -> None:
        self._service = service

    # Basic endpoints ---------------------------------------------------------
    def get_health(self) -> Dict[str, Any]:
        return self._safe_call('get_health', self._service.get_health, 'HEALTH_FAILED')

    def get_metrics(self) -> Dict[str, Any]:
        return self._safe_call('get_metrics', self._service.get_metrics, 'METRICS_FAILED')

    def get_prometheus_metrics(self) -> Dict[str, Any]:
        return self._safe_call('get_prometheus_metrics', self._service.get_prometheus_metrics, 'PROMETHEUS_METRICS_FAILED')

    # Marker endpoints --------------------------------------------------------
    def set_markers_visible(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('set_markers_visible', lambda: self._service.set_markers_visible(payload), 'SET_MARKERS_VISIBLE_FAILED')

    def set_individual_marker_visible(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('set_individual_marker_visible', lambda: self._service.set_individual_marker_visible(payload), 'SET_INDIVIDUAL_MARKER_VISIBLE_FAILED')

    def set_selective_markers_visible(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('set_selective_markers_visible', lambda: self._service.set_selective_markers_visible(payload), 'SET_SELECTIVE_MARKERS_VISIBLE_FAILED')

    def debug_status(self) -> Dict[str, Any]:
        return self._safe_call('debug_status', self._service.get_debug_status, 'DEBUG_STATUS_FAILED')

    # Waypoint endpoints ------------------------------------------------------
    def waypoints_summary(self) -> Dict[str, Any]:
        return self._safe_call('waypoints_summary', self._service.get_waypoints_summary, 'WAYPOINTS_SUMMARY_FAILED')

    def create_waypoint(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('create_waypoint', lambda: self._service.create_waypoint(payload), 'CREATE_WAYPOINT_FAILED')

    def list_waypoints(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('list_waypoints', lambda: self._service.list_waypoints(payload), 'LIST_WAYPOINTS_FAILED')

    def update_waypoint(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('update_waypoint', lambda: self._service.update_waypoint(payload), 'UPDATE_WAYPOINT_FAILED')

    def remove_waypoint(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('remove_waypoint', lambda: self._service.remove_waypoint(payload), 'REMOVE_WAYPOINT_FAILED')

    def remove_selected_waypoints(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('remove_selected_waypoints', lambda: self._service.remove_selected_waypoints(payload), 'REMOVE_SELECTED_WAYPOINTS_FAILED')

    def clear_waypoints(self) -> Dict[str, Any]:
        return self._safe_call('clear_waypoints', self._service.clear_waypoints, 'CLEAR_WAYPOINTS_FAILED')

    def export_waypoints(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('export_waypoints', lambda: self._service.export_waypoints(payload), 'EXPORT_WAYPOINTS_FAILED')

    def import_waypoints(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('import_waypoints', lambda: self._service.import_waypoints(payload), 'IMPORT_WAYPOINTS_FAILED')

    def goto_waypoint(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('goto_waypoint', lambda: self._service.goto_waypoint(payload), 'GOTO_WAYPOINT_FAILED')

    # Group endpoints ---------------------------------------------------------
    def groups_summary(self) -> Dict[str, Any]:
        return self._safe_call('groups_summary', self._service.groups_summary, 'GROUPS_SUMMARY_FAILED')

    def create_group(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('create_group', lambda: self._service.create_group(payload), 'CREATE_GROUP_FAILED')

    def list_groups(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('list_groups', lambda: self._service.list_groups(payload), 'LIST_GROUPS_FAILED')

    def get_group(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('get_group', lambda: self._service.get_group(payload), 'GET_GROUP_FAILED')

    def update_group(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('update_group', lambda: self._service.update_group(payload), 'UPDATE_GROUP_FAILED')

    def remove_group(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('remove_group', lambda: self._service.remove_group(payload), 'REMOVE_GROUP_FAILED')

    def clear_groups(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('clear_groups', lambda: self._service.clear_groups(payload), 'CLEAR_GROUPS_FAILED')

    def group_hierarchy(self) -> Dict[str, Any]:
        return self._safe_call('group_hierarchy', self._service.group_hierarchy, 'GROUP_HIERARCHY_FAILED')

    def add_waypoint_to_groups(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('add_waypoint_to_groups', lambda: self._service.add_waypoint_to_groups(payload), 'ADD_WAYPOINT_TO_GROUPS_FAILED')

    def remove_waypoint_from_groups(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('remove_waypoint_from_groups', lambda: self._service.remove_waypoint_from_groups(payload), 'REMOVE_WAYPOINT_FROM_GROUPS_FAILED')

    def get_waypoint_groups(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('get_waypoint_groups', lambda: self._service.get_waypoint_groups(payload), 'GET_WAYPOINT_GROUPS_FAILED')

    def get_group_waypoints(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('get_group_waypoints', lambda: self._service.get_group_waypoints(payload), 'GET_GROUP_WAYPOINTS_FAILED')

    def get_waypoint_types(self) -> Dict[str, Any]:
        return self._safe_call('get_waypoint_types', lambda: self._service.get_waypoint_types(), 'GET_WAYPOINT_TYPES_FAILED')

    # ------------------------------------------------------------------
    def _safe_call(self, operation: str, func: Callable[[], Dict[str, Any]], default_error_code: str) -> Dict[str, Any]:
        try:
            response = func()
        except MethodNotAllowed as exc:
            return error_response('METHOD_NOT_ALLOWED', exc.message, details=exc.details)
        except ValidationFailure as exc:
            logger.warning('validation_failed', extra={'operation': operation, 'error': exc.message})
            return error_response('VALIDATION_ERROR', exc.message, details=exc.details)
        except WorldSurveyorError as exc:
            logger.error('worldsurveyor_error', extra={'operation': operation, 'error': exc.message})
            return error_response(exc.code, exc.message, details=exc.details)
        except Exception as exc:  # pragma: no cover - unexpected failure
            logger.exception('controller_unhandled', extra={'operation': operation, 'error': str(exc)})
            response = error_response(default_error_code, str(exc))

        return normalize_transport_response(operation, response, default_error_code=default_error_code)


__all__ = ["WorldSurveyorController"]
