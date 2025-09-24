from __future__ import annotations

import threading
from collections import deque
from typing import Any, Dict

from omni.agent.worldsurveyor.http.controller import WorldSurveyorController
from omni.agent.worldsurveyor.services.worldsurveyor_service import WorldSurveyorService
from agentworld_core.requests import RequestTracker


class DummyWaypointManager:
    def __init__(self) -> None:
        self._waypoints: Dict[str, Dict[str, Any]] = {}
        self._groups: Dict[str, Dict[str, Any]] = {}
        self._counter = 0
        self.markers_visible = True
        self._group_membership: Dict[str, set[str]] = {}

    def get_waypoint_count(self) -> int:
        return len(self._waypoints)

    def get_visible_marker_count(self) -> int:
        return len(self._waypoints) if self.markers_visible else 0

    def create_waypoint(self, *, position, waypoint_type, name=None, target=None, metadata=None, group_ids=None) -> str:
        self._counter += 1
        waypoint_id = f"wp_{self._counter}"
        self._waypoints[waypoint_id] = {
            'id': waypoint_id,
            'position': position,
            'waypoint_type': waypoint_type,
            'name': name,
            'target': target,
            'metadata': metadata or {},
            'group_ids': group_ids or [],
        }
        self._group_membership.setdefault(waypoint_id, set()).update(group_ids or [])
        return waypoint_id

    def list_waypoints(self, waypoint_type=None, group_id=None):
        values = list(self._waypoints.values())
        return [type('Waypoint', (), wp)() for wp in values]

    def set_markers_visible(self, visible: bool):
        self.markers_visible = visible

    def set_individual_marker_visible(self, waypoint_id: str, visible: bool):
        item = self._waypoints.get(waypoint_id)
        if item:
            item['visible'] = visible

    def set_selective_visibility(self, waypoint_ids):
        for wp_id in self._waypoints.keys():
            self._waypoints[wp_id]['visible'] = wp_id in waypoint_ids

    def remove_waypoint(self, waypoint_id: str) -> bool:
        return self._waypoints.pop(waypoint_id, None) is not None

    def remove_waypoints(self, waypoint_ids):
        removed = 0
        for wp_id in waypoint_ids:
            if self._waypoints.pop(wp_id, None) is not None:
                removed += 1
        return removed

    def clear_waypoints(self):
        count = len(self._waypoints)
        self._waypoints.clear()
        return count

    def export_waypoints(self, include_groups=True):
        return {'waypoints': list(self._waypoints.values())}

    def import_waypoints(self, data, merge_mode='replace'):
        return {'waypoints_imported': len(data.get('waypoints', [])), 'groups_imported': 0, 'errors': 0}

    def update_waypoint(self, waypoint_id, **updates):
        if waypoint_id not in self._waypoints:
            return False
        self._waypoints[waypoint_id].update(updates)
        return True

    def get_waypoint(self, waypoint_id):
        wp = self._waypoints.get(waypoint_id)
        if wp:
            return type('Waypoint', (), wp)
        return None

    def list_groups(self, parent_group_id=None):
        return list(self._groups.values())

    def get_group(self, group_id):
        return self._groups.get(group_id)

    def remove_group(self, group_id, cascade=False):
        return self._groups.pop(group_id, None) is not None

    def create_group(self, name, parent_group_id=None, description=None, color=None):
        group_id = f"grp_{len(self._groups) + 1}"
        self._groups[group_id] = {
            'id': group_id,
            'name': name,
            'parent_group_id': parent_group_id,
            'description': description,
            'color': color,
        }
        return group_id

    def get_group_hierarchy(self):
        return {
            'hierarchy': list(self._groups.values()),
            'total_groups': len(self._groups),
        }

    def add_waypoint_to_groups(self, waypoint_id, group_ids):
        membership = self._group_membership.setdefault(waypoint_id, set())
        before = len(membership)
        membership.update(group_ids)
        return len(membership) - before

    def remove_waypoint_from_groups(self, waypoint_id, group_ids):
        membership = self._group_membership.setdefault(waypoint_id, set())
        removed = 0
        for gid in group_ids:
            if gid in membership:
                membership.remove(gid)
                removed += 1
        return removed

    def get_waypoint_groups(self, waypoint_id):
        membership = self._group_membership.get(waypoint_id, set())
        return [self._groups[g] for g in membership if g in self._groups]

    def get_group_waypoints(self, group_id, include_nested=False):
        return self.list_waypoints()


class DummyAPI:
    def __init__(self):
        self._config = type('Cfg', (), {'server_port': 8891})()
        self._api_stats = {'requests': 0}
        self.waypoint_manager = DummyWaypointManager()
        self._queue_lock = threading.Lock()
        self._camera_queue = deque()
        self._request_tracker = RequestTracker(ttl_seconds=30.0)

    def get_port(self):
        return 8891


def build_controller() -> WorldSurveyorController:
    api = DummyAPI()
    service = WorldSurveyorService(api)
    return WorldSurveyorController(service)


def test_create_waypoint_success():
    controller = build_controller()
    payload = {
        'position': [1.0, 2.0, 3.0],
        'waypoint_type': 'point_of_interest',
        'name': 'Test',
    }
    result = controller.create_waypoint(payload)
    assert result['success'] is True
    assert 'waypoint_id' in result


def test_create_waypoint_validation_error():
    controller = build_controller()
    result = controller.create_waypoint({'position': [1.0, 2.0]})
    assert result['success'] is False
    assert result['error_code'] == 'VALIDATION_ERROR'


def test_list_waypoints_returns_count():
    controller = build_controller()
    controller.create_waypoint({'position': [0, 0, 0]})
    response = controller.list_waypoints({})
    assert response['success'] is True
    assert response['count'] >= 1


def test_remove_waypoint_not_found():
    controller = build_controller()
    response = controller.remove_waypoint({'waypoint_id': 'missing'})
    assert response['success'] is False
    assert response['error_code'] == 'NOT_FOUND'


def test_set_markers_visible_updates_state():
    controller = build_controller()
    result = controller.set_markers_visible({'visible': False})
    assert result['success'] is True
    assert result['visible'] is False


def test_add_waypoint_to_groups_missing_waypoint_returns_not_found():
    controller = build_controller()
    manager = controller._service._manager  # type: ignore[attr-defined]
    group_id = manager.create_group(name='Exploration')

    response = controller.add_waypoint_to_groups({
        'waypoint_id': 'missing-waypoint',
        'group_ids': [group_id],
    })

    assert response['success'] is False
    assert response['error_code'] == 'NOT_FOUND'
    assert response['details']['waypoint_id'] == 'missing-waypoint'


def test_add_waypoint_to_groups_missing_group_returns_error():
    controller = build_controller()
    waypoint_resp = controller.create_waypoint({
        'position': [1.0, 2.0, 3.0],
        'waypoint_type': 'point_of_interest',
        'name': 'Test Waypoint',
    })
    waypoint_id = waypoint_resp['waypoint_id']

    response = controller.add_waypoint_to_groups({
        'waypoint_id': waypoint_id,
        'group_ids': ['non-existent-group'],
    })

    assert response['success'] is False
    assert response['error_code'] == 'GROUP_NOT_FOUND'
    assert 'non-existent-group' in response['details']['missing_group_ids']


def test_group_hierarchy_flattens_structure():
    controller = build_controller()
    group_resp = controller.create_group({'name': 'Exploration'})
    assert group_resp['success'] is True

    result = controller.group_hierarchy()
    assert result['success'] is True
    assert isinstance(result['hierarchy'], list)
    assert result['group_count'] == 1
    assert result['hierarchy'][0]['name'] == 'Exploration'


def test_remove_waypoint_groups_accepts_empty_list():
    controller = build_controller()
    waypoint = controller.create_waypoint({'position': [0, 0, 0], 'waypoint_type': 'point_of_interest'})
    waypoint_id = waypoint['waypoint_id']
    group_id = controller.create_group({'name': 'Exploration'})['group_id']
    add_response = controller.add_waypoint_to_groups({'waypoint_id': waypoint_id, 'group_ids': [group_id]})
    assert add_response['success'] is True

    remove_response = controller.remove_waypoint_from_groups({'waypoint_id': waypoint_id, 'group_ids': []})
    assert remove_response['success'] is True
    assert remove_response.get('cleared_all') is True

    groups_response = controller.get_waypoint_groups({'waypoint_id': waypoint_id})
    assert groups_response['success'] is True
    assert groups_response['groups'] == []
