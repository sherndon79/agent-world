"""
OpenAPI specification for WorldViewer API.
"""
from typing import Dict, Any


def build_openapi_spec(port: int) -> Dict[str, Any]:
    base_url = f"http://localhost:{port}"
    return {
        'openapi': '3.0.0',
        'info': {'title': 'Agent WorldViewer API', 'version': '0.1.0'},
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
            '/metrics': {'get': {'summary': 'Metrics (JSON)', 'responses': {'200': {'description': 'OK'}}}},
            '/metrics.prom': {'get': {'summary': 'Metrics (Prometheus text)', 'responses': {'200': {'description': 'OK'}}}},
            '/camera/status': {'get': {'summary': 'Camera status', 'responses': {'200': {'description': 'OK'}}}},
            '/get_asset_transform': {'get': {'summary': 'Get asset transform info', 'responses': {'200': {'description': 'OK'}}}},
            '/camera/set_position': {'post': {'summary': 'Set camera position', 'responses': {'200': {'description': 'OK'}}}},
            '/camera/frame_object': {'post': {'summary': 'Frame object', 'responses': {'200': {'description': 'OK'}}}},
            '/camera/orbit': {'post': {'summary': 'Orbit camera', 'responses': {'200': {'description': 'OK'}}}},
            '/camera/smooth_move': {'post': {'summary': 'Cinematic smooth move', 'responses': {'200': {'description': 'OK'}}}},
            '/camera/stop_movement': {'post': {'summary': 'Stop movement', 'responses': {'200': {'description': 'OK'}}}},
            '/camera/movement_status': {'get': {'summary': 'Movement status', 'responses': {'200': {'description': 'OK'}}}},
        }
    }
