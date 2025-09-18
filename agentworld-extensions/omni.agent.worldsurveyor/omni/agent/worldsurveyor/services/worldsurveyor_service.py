"""Service layer for WorldSurveyor operations."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from ..errors import error_response, ValidationFailure, MethodNotAllowed


def _asdict_waypoints(waypoints: List[Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for waypoint in waypoints:
        if hasattr(waypoint, "model_dump"):
            result.append(waypoint.model_dump())
        elif hasattr(waypoint, "to_dict"):
            result.append(waypoint.to_dict())
        elif hasattr(waypoint, "__dict__"):
            result.append(dict(waypoint.__dict__))
        else:
            try:
                result.append(asdict(waypoint))
            except Exception:  # pragma: no cover - fallback for plain dicts
                result.append(dict(waypoint))
    return result


class WorldSurveyorService:
    """Wrap WaypointManager operations for HTTP/MCP transports."""

    def __init__(self, api_interface) -> None:
        self._api = api_interface
        self._manager = getattr(api_interface, "waypoint_manager", None)
        self._config = getattr(api_interface, "_config", None)

    # ------------------------------------------------------------------
    # Basic endpoints
    def get_health(self) -> Dict[str, Any]:
        port = self._api.get_port() if hasattr(self._api, "get_port") else 8891
        waypoint_count = self._manager.get_waypoint_count() if self._manager else 0
        visible_markers = self._manager.get_visible_marker_count() if self._manager else 0
        return {
            "success": True,
            "service": "Agent WorldSurveyor API",
            "version": "0.1.0",
            "url": f"http://localhost:{port}",
            "waypoint_count": waypoint_count,
            "visible_markers": visible_markers,
        }

    def get_metrics(self) -> Dict[str, Any]:
        if hasattr(self._api, "metrics"):
            try:
                return self._api.metrics.get_json_metrics()
            except Exception:  # pragma: no cover - metrics optional
                pass
        stats = getattr(self._api, "_api_stats", {})
        return {"success": True, "metrics": stats}

    def get_prometheus_metrics(self) -> Dict[str, Any]:
        if hasattr(self._api, "metrics"):
            try:
                return {
                    "success": True,
                    "_raw_text": self._api.metrics.get_prometheus_metrics(),
                }
            except Exception:  # pragma: no cover
                pass
        return error_response("PROMETHEUS_METRICS_UNAVAILABLE", "Prometheus metrics not available")

    # ------------------------------------------------------------------
    # Marker endpoints
    def set_markers_visible(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        visible = bool(payload.get("visible"))
        if not self._manager:
            return error_response("MANAGER_UNAVAILABLE", "Waypoint manager unavailable")
        self._manager.set_markers_visible(visible)
        return {"success": True, "visible": visible}

    def set_individual_marker_visible(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        waypoint_id = payload.get("waypoint_id")
        visible = payload.get("visible", True)
        if not waypoint_id:
            raise ValidationFailure("waypoint_id is required", details={"parameter": "waypoint_id"})
        if not self._manager:
            return error_response("MANAGER_UNAVAILABLE", "Waypoint manager unavailable")
        self._manager.set_individual_marker_visible(waypoint_id, bool(visible))
        return {"success": True, "waypoint_id": waypoint_id, "visible": bool(visible)}

    def set_selective_markers_visible(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        waypoint_ids = payload.get("waypoint_ids") or payload.get("waypoints")
        if not isinstance(waypoint_ids, list) or not waypoint_ids:
            raise ValidationFailure("waypoint_ids must be a non-empty list", details={"parameter": "waypoint_ids"})
        if not self._manager:
            return error_response("MANAGER_UNAVAILABLE", "Waypoint manager unavailable")
        self._manager.set_selective_visibility(set(waypoint_ids))
        return {"success": True, "waypoint_ids": waypoint_ids}

    def get_debug_status(self) -> Dict[str, Any]:
        if not self._manager:
            return error_response("MANAGER_UNAVAILABLE", "Waypoint manager unavailable")
        return {"success": True, "status": self._manager.get_debug_status()}

    # ------------------------------------------------------------------
    # Waypoint operations
    def get_waypoints_summary(self) -> Dict[str, Any]:
        count = self._manager.get_waypoint_count() if self._manager else 0
        return {"success": True, "waypoint_count": count}

    def create_waypoint(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self._manager:
            return error_response("MANAGER_UNAVAILABLE", "Waypoint manager unavailable")
        position = payload.get("position")
        if not isinstance(position, (list, tuple)) or len(position) != 3:
            raise ValidationFailure("position must be [x, y, z]", details={"parameter": "position"})
        target = payload.get("target")
        if target is not None and (not isinstance(target, (list, tuple)) or len(target) != 3):
            raise ValidationFailure("target must be [x, y, z]", details={"parameter": "target"})
        waypoint_id = self._manager.create_waypoint(
            position=tuple(position),
            waypoint_type=payload.get("waypoint_type", "point_of_interest"),
            name=payload.get("name"),
            target=tuple(target) if target else None,
            metadata=payload.get("metadata", {}),
            group_ids=payload.get("group_ids"),
        )
        return {"success": True, "waypoint_id": waypoint_id}

    def list_waypoints(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self._manager:
            return error_response("MANAGER_UNAVAILABLE", "Waypoint manager unavailable")
        waypoint_type = payload.get("waypoint_type")
        group_id = payload.get("group_id")
        waypoints = self._manager.list_waypoints(waypoint_type, group_id)
        return {"success": True, "waypoints": _asdict_waypoints(waypoints), "count": len(waypoints)}

    def update_waypoint(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        waypoint_id = payload.get("waypoint_id")
        if not waypoint_id:
            raise ValidationFailure("waypoint_id is required", details={"parameter": "waypoint_id"})
        updates = {key: payload[key] for key in ("name", "waypoint_type", "notes", "metadata") if key in payload}
        if "target" in payload:
            target = payload["target"]
            if target is not None and (not isinstance(target, (list, tuple)) or len(target) != 3):
                raise ValidationFailure("target must be [x, y, z]", details={"parameter": "target"})
            updates["target"] = tuple(target) if target else None
        if "position" in payload:
            position = payload["position"]
            if not isinstance(position, (list, tuple)) or len(position) != 3:
                raise ValidationFailure("position must be [x, y, z]", details={"parameter": "position"})
            updates["position"] = tuple(position)
        updated = self._manager.update_waypoint(waypoint_id, **updates)
        if not updated:
            return error_response("NOT_FOUND", f"Waypoint {waypoint_id} not found")
        waypoint = self._manager.get_waypoint(waypoint_id)
        return {"success": True, "waypoint": asdict(waypoint) if waypoint else updates}

    def remove_waypoint(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        waypoint_id = payload.get("waypoint_id") or payload.get("id")
        if not waypoint_id:
            raise ValidationFailure("waypoint_id is required", details={"parameter": "waypoint_id"})
        removed = self._manager.remove_waypoint(waypoint_id)
        if not removed:
            return error_response("NOT_FOUND", f"Waypoint {waypoint_id} not found")
        return {"success": True, "waypoint_id": waypoint_id}

    def remove_selected_waypoints(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        waypoint_ids = payload.get("waypoint_ids") or payload.get("ids")
        if not isinstance(waypoint_ids, list) or not waypoint_ids:
            raise ValidationFailure("waypoint_ids must be a non-empty list", details={"parameter": "waypoint_ids"})
        removed = self._manager.remove_waypoints(waypoint_ids)
        return {"success": True, "removed": removed}

    def clear_waypoints(self) -> Dict[str, Any]:
        cleared = self._manager.clear_waypoints() if self._manager else 0
        return {"success": True, "removed": cleared}

    def export_waypoints(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        include_groups = bool(payload.get("include_groups", True))
        if not self._manager:
            return error_response("MANAGER_UNAVAILABLE", "Waypoint manager unavailable")
        data = self._manager.export_waypoints(include_groups=include_groups)
        return {"success": True, "export": data}

    def import_waypoints(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        merge_mode = payload.get('merge_mode', 'replace')
        data = payload.get('import_data') or payload.get('export') or payload
        if not isinstance(data, dict):
            raise ValidationFailure('import_data must be an object', details={'parameter': 'import_data'})
        stats = self._manager.import_waypoints(data, merge_mode)
        return {
            'success': True,
            'imported_waypoints': stats.get('waypoints_imported', 0),
            'imported_groups': stats.get('groups_imported', 0),
            'errors': stats.get('errors', 0),
        }

    def goto_waypoint(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        waypoint_id = payload.get('waypoint_id')
        if not waypoint_id:
            raise ValidationFailure('waypoint_id is required', details={'parameter': 'waypoint_id'})
        return self._queue_camera_operation('goto_waypoint', {'waypoint_id': waypoint_id})

    # ------------------------------------------------------------------
    # Group operations
    def groups_summary(self) -> Dict[str, Any]:
        groups = self._manager.list_groups() if self._manager else []
        return {'success': True, 'group_count': len(groups)}

    def create_group(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = payload.get('name')
        if not name:
            raise ValidationFailure('name is required', details={'parameter': 'name'})
        parent_id = payload.get('parent_group_id')
        description = payload.get('description')
        group_id = self._manager.create_group(name=name, parent_group_id=parent_id, description=description)
        return {'success': True, 'group_id': group_id}

    def list_groups(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        parent_id = payload.get('parent_group_id')
        groups = self._manager.list_groups(parent_id)
        return {'success': True, 'groups': groups}

    def get_group(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        group_id = payload.get('group_id')
        if not group_id:
            raise ValidationFailure('group_id is required', details={'parameter': 'group_id'})
        group = self._manager.get_group(group_id)
        if not group:
            return error_response('NOT_FOUND', f'Group {group_id} not found')
        return {'success': True, 'group': group}

    def remove_group(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        group_id = payload.get('group_id')
        if not group_id:
            raise ValidationFailure('group_id is required', details={'parameter': 'group_id'})
        cascade = bool(payload.get('cascade', False))
        removed = self._manager.remove_group(group_id, cascade=cascade)
        if not removed:
            return error_response('NOT_FOUND', f'Group {group_id} not found')
        return {'success': True, 'group_id': group_id, 'cascade': cascade}

    def group_hierarchy(self) -> Dict[str, Any]:
        hierarchy = self._manager.get_group_hierarchy()
        return {'success': True, 'hierarchy': hierarchy}

    def add_waypoint_to_groups(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        waypoint_id = payload.get('waypoint_id')
        group_ids = payload.get('group_ids') or []
        if not waypoint_id:
            raise ValidationFailure('waypoint_id is required', details={'parameter': 'waypoint_id'})
        if not isinstance(group_ids, list) or not group_ids:
            raise ValidationFailure('group_ids must be a non-empty list', details={'parameter': 'group_ids'})
        added = self._manager.add_waypoint_to_groups(waypoint_id, group_ids)
        return {'success': True, 'added': added}

    def remove_waypoint_from_groups(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        waypoint_id = payload.get('waypoint_id')
        group_ids = payload.get('group_ids') or []
        if not waypoint_id:
            raise ValidationFailure('waypoint_id is required', details={'parameter': 'waypoint_id'})
        if not isinstance(group_ids, list) or not group_ids:
            raise ValidationFailure('group_ids must be a non-empty list', details={'parameter': 'group_ids'})
        removed = self._manager.remove_waypoint_from_groups(waypoint_id, group_ids)
        return {'success': True, 'removed': removed}

    def get_waypoint_groups(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        waypoint_id = payload.get('waypoint_id')
        if not waypoint_id:
            raise ValidationFailure('waypoint_id is required', details={'parameter': 'waypoint_id'})
        groups = self._manager.get_waypoint_groups(waypoint_id)
        return {'success': True, 'groups': groups}

    def get_group_waypoints(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        group_id = payload.get('group_id')
        if not group_id:
            raise ValidationFailure('group_id is required', details={'parameter': 'group_id'})
        include_nested = bool(payload.get('include_nested', False))
        waypoints = self._manager.get_group_waypoints(group_id, include_nested)
        return {'success': True, 'waypoints': _asdict_waypoints(waypoints)}

    # ------------------------------------------------------------------
    # Internal helpers
    def _queue_camera_operation(self, operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not hasattr(self._api, '_camera_queue'):
            return error_response('CAMERA_QUEUE_UNAVAILABLE', 'Camera queue is not available')
        import time
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

        with self._api._queue_lock:
            self._api._camera_queue.append(request)
            self._api._request_tracking[request_id] = request

        return {
            'success': True,
            'request_id': request_id,
            'operation': operation,
            'status': 'queued',
        }


__all__ = ['WorldSurveyorService']
