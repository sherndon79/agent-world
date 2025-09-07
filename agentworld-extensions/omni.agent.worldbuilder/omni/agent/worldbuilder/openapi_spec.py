"""
OpenAPI specification for WorldBuilder API.
"""
from typing import Dict, Any


def build_openapi_spec(port: int) -> Dict[str, Any]:
    base_url = f"http://localhost:{port}"
    return {
        'openapi': '3.0.0',
        'info': {'title': 'Agent WorldBuilder API', 'version': '0.1.0'},
        'servers': [{'url': base_url}],
        'components': {
            'securitySchemes': {
                'bearerAuth': {
                    'type': 'http',
                    'scheme': 'bearer',
                    'bearerFormat': 'JWT'
                },
                'hmacAuth': {
                    'type': 'apiKey',
                    'in': 'header',
                    'name': 'X-Signature',
                    'description': 'HMAC-SHA256 of "METHOD|PATH|X-Timestamp" with secret; include X-Timestamp header'
                }
            }
        },
        'security': [ {'bearerAuth': []}, {'hmacAuth': []} ],
        'paths': {
            '/health': {'get': {'summary': 'Health', 'responses': {'200': {'description': 'OK'}}}},
            '/scene_status': {'get': {'summary': 'Scene status', 'responses': {'200': {'description': 'OK'}}}},
            '/get_scene': {'get': {'summary': 'Get scene contents', 'responses': {'200': {'description': 'OK'}}}},
            '/metrics': {'get': {'summary': 'Metrics (JSON)', 'responses': {'200': {'description': 'OK'}}}},
            '/metrics.prom': {'get': {'summary': 'Metrics (Prometheus text)', 'responses': {'200': {'description': 'OK'}}}},
            '/add_element': {'post': {'summary': 'Add scene element', 'responses': {'200': {'description': 'OK'}}}},
            '/create_batch': {'post': {'summary': 'Create batch with elements', 'responses': {'200': {'description': 'OK'}}}},
            '/place_asset': {'post': {'summary': 'Place asset reference', 'responses': {'200': {'description': 'OK'}}}},
            '/transform_asset': {'post': {'summary': 'Transform asset (move/rotate/scale)', 'responses': {'200': {'description': 'OK'}}}},
            '/remove_element': {'post': {'summary': 'Remove element', 'responses': {'200': {'description': 'OK'}}}},
            '/clear_path': {'post': {'summary': 'Clear all elements at path', 'responses': {'200': {'description': 'OK'}}}},
            '/list_elements': {'get': {'summary': 'List elements at path', 'responses': {'200': {'description': 'OK'}}}},
            '/batch_info': {'get': {'summary': 'Get batch info', 'responses': {'200': {'description': 'OK'}}}},
            '/request_status': {'get': {'summary': 'Get request processing status', 'responses': {'200': {'description': 'OK'}}}},
            '/query/objects_by_type': {'get': {'summary': 'Query objects by type', 'responses': {'200': {'description': 'OK'}}}},
            '/query/objects_in_bounds': {'get': {'summary': 'Query objects in bounds', 'responses': {'200': {'description': 'OK'}}}},
            '/query/objects_near_point': {'get': {'summary': 'Query objects near point', 'responses': {'200': {'description': 'OK'}}}},
            '/transform/calculate_bounds': {'get': {'summary': 'Calculate bounds of selection', 'responses': {'200': {'description': 'OK'}}}},
            '/transform/find_ground_level': {'get': {'summary': 'Find ground level at position', 'responses': {'200': {'description': 'OK'}}}},
            '/transform/align_objects': {'post': {'summary': 'Align objects by rule', 'responses': {'200': {'description': 'OK'}}}},
        }
    }
