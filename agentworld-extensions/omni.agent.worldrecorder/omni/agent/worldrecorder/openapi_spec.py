from typing import Dict, Any


def build_openapi_spec(port: int) -> Dict[str, Any]:
    return {
        'openapi': '3.0.0',
        'info': {
            'title': 'Agent VideoCapture API',
            'version': '0.1.0',
            'description': 'Video capture via omni.kit.capture.viewport without PyAV',
        },
        'servers': [{'url': f'http://localhost:{port}'}],
        'paths': {
            '/health': {'get': {'summary': 'Health', 'responses': {'200': {'description': 'OK'}}}},
            '/openapi.json': {'get': {'summary': 'OpenAPI', 'responses': {'200': {'description': 'Spec'}}}},
            '/metrics': {'get': {'summary': 'Metrics', 'responses': {'200': {'description': 'Metrics JSON'}}}},
            '/metrics.prom': {'get': {'summary': 'Prometheus metrics', 'responses': {'200': {'description': 'Text'}}}},
            '/viewport/capture_frame': {
                'post': {
                    'summary': 'Capture a single viewport frame',
                    'requestBody': {
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'object',
                                    'properties': {
                                        'output_path': {'type': 'string'},
                                        'width': {'type': 'integer'},
                                        'height': {'type': 'integer'},
                                        'file_type': {'type': 'string', 'default': '.png'}
                                    },
                                    'required': ['output_path']
                                }
                            }
                        }
                    },
                    'responses': {'200': {'description': 'Frame captured'}}
                }
            },
            '/video/status': {'get': {'summary': 'Capture status', 'responses': {'200': {'description': 'Status (includes session_id)'}}}},
            '/video/start': {
                'post': {
                    'summary': 'Start video capture',
                    'requestBody': {
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'object',
                                    'properties': {
                                        'session_id': {'type': 'string', 'description': 'Optional unique session identifier'},
                                        'output_path': {'type': 'string'},
                                        'fps': {'type': 'number', 'default': 24},
                                        'width': {'type': 'integer'},
                                        'height': {'type': 'integer'},
                                        'duration_sec': {'type': 'number'},
                                        'show_progress': {'type': 'boolean', 'default': False},
                                        'file_type': {'type': 'string', 'default': '.mp4'},
                                    },
                                    'required': ['output_path']
                                }
                            }
                        }
                    },
                    'responses': {'200': {'description': 'Started'}}
                }
            },
            '/video/stop': {'post': {'summary': 'Stop video capture', 'responses': {'200': {'description': 'Stopped'}}}},
            # Parity aliases
            '/recording/status': {'get': {'summary': 'Recording status', 'responses': {'200': {'description': 'OK'}}}},
            '/recording/start': {'post': {'summary': 'Start recording', 'responses': {'200': {'description': 'OK'}}}},
            '/recording/stop': {'post': {'summary': 'Stop recording', 'responses': {'200': {'description': 'OK'}}}},
        }
    }
