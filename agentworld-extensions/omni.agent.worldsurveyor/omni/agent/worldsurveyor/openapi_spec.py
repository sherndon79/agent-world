"""
OpenAPI specification for WorldSurveyor API (unified routes).
"""

from typing import Dict, Any


def build_openapi_spec(port: int) -> Dict[str, Any]:
    """Build OpenAPI specification for WorldSurveyor API (unified)."""
    base_url = f"http://localhost:{port}"
    return {
        'openapi': '3.0.0',
        'info': {'title': 'Agent WorldSurveyor API', 'version': '0.1.0'},
        'servers': [{'url': base_url}],
        'paths': {
            '/health': {'get': {'summary': 'Health', 'responses': {'200': {'description': 'OK'}}}},
            '/metrics': {'get': {'summary': 'Metrics (JSON)', 'responses': {'200': {'description': 'OK'}}}},
            '/metrics.prom': {'get': {'summary': 'Metrics (Prometheus)', 'responses': {'200': {'description': 'OK'}}}},

            '/markers/visible': {'post': {'summary': 'Set markers visible', 'responses': {'200': {'description': 'OK'}}}},
            '/markers/individual': {
                'post': {
                    'summary': 'Set individual marker visibility',
                    'responses': {'200': {'description': 'OK'}}
                }
            },
            '/markers/selective': {
                'post': {
                    'summary': 'Enable selective visibility for a list of waypoint IDs',
                    'responses': {'200': {'description': 'OK'}}
                }
            },
            '/markers/debug': {'get': {'summary': 'Debug draw status', 'responses': {'200': {'description': 'OK'}}}},

            '/waypoints/create': {'post': {'summary': 'Create waypoint', 'responses': {'200': {'description': 'OK'}}}},
            '/waypoints/list': {
                'get': {
                    'summary': 'List waypoints',
                    'parameters': [
                        {'name': 'waypoint_type', 'in': 'query', 'required': False, 'schema': {'type': 'string'}},
                        {'name': 'group_id', 'in': 'query', 'required': False, 'schema': {'type': 'string'}},
                    ],
                    'responses': {'200': {'description': 'OK'}}
                }
            },
            '/waypoints/update': {'post': {'summary': 'Update waypoint', 'responses': {'200': {'description': 'OK'}}}},
            '/waypoints/remove': {'post': {'summary': 'Remove waypoint', 'responses': {'200': {'description': 'OK'}}}},
            '/waypoints/clear': {'post': {'summary': 'Clear all waypoints', 'responses': {'200': {'description': 'OK'}}}},
            '/waypoints/export': {
                'get': {
                    'summary': 'Export waypoints',
                    'parameters': [
                        {'name': 'include_groups', 'in': 'query', 'required': False, 'schema': {'type': 'boolean'}},
                    ],
                    'responses': {'200': {'description': 'OK'}}
                }
            },
            '/waypoints/import': {'post': {'summary': 'Import waypoints', 'responses': {'200': {'description': 'OK'}}}},
            '/waypoints/goto': {'post': {'summary': 'Goto waypoint', 'responses': {'200': {'description': 'OK'}}}},

            '/groups/create': {'post': {'summary': 'Create group', 'responses': {'200': {'description': 'OK'}}}},
            '/groups/list': {
                'get': {
                    'summary': 'List groups',
                    'parameters': [{'name': 'parent_group_id', 'in': 'query', 'required': False, 'schema': {'type': 'string'}}],
                    'responses': {'200': {'description': 'OK'}}
                }
            },
            '/groups/get': {
                'get': {
                    'summary': 'Get group',
                    'parameters': [{'name': 'group_id', 'in': 'query', 'required': True, 'schema': {'type': 'string'}}],
                    'responses': {'200': {'description': 'OK'}}
                }
            },
            '/groups/remove': {'post': {'summary': 'Remove group', 'responses': {'200': {'description': 'OK'}}}},
            '/groups/hierarchy': {'get': {'summary': 'Group hierarchy', 'responses': {'200': {'description': 'OK'}}}},
            '/groups/add_waypoint': {'post': {'summary': 'Add waypoint to groups', 'responses': {'200': {'description': 'OK'}}}},
            '/groups/remove_waypoint': {'post': {'summary': 'Remove waypoint from groups', 'responses': {'200': {'description': 'OK'}}}},
            '/groups/of_waypoint': {
                'get': {
                    'summary': 'Groups containing a waypoint',
                    'parameters': [{'name': 'waypoint_id', 'in': 'query', 'required': True, 'schema': {'type': 'string'}}],
                    'responses': {'200': {'description': 'OK'}}
                }
            },
            '/groups/waypoints': {
                'get': {
                    'summary': 'Waypoints in a group',
                    'parameters': [
                        {'name': 'group_id', 'in': 'query', 'required': True, 'schema': {'type': 'string'}},
                        {'name': 'include_nested', 'in': 'query', 'required': False, 'schema': {'type': 'boolean'}},
                    ],
                    'responses': {'200': {'description': 'OK'}}
                }
            },
        }
    }
