"""
WorldStreamer OpenAPI Specification

Defines OpenAPI specification for WorldStreamer streaming control API.
Provides comprehensive API documentation with authentication and response schemas.
"""

from typing import Dict, Any


def get_worldstreamer_openapi_spec(port: int = 8905, auth_enabled: bool = True) -> Dict[str, Any]:
    """
    Get WorldStreamer OpenAPI specification.
    
    Args:
        port: API server port
        auth_enabled: Whether authentication is enabled
        
    Returns:
        OpenAPI specification dictionary
    """
    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "WorldStreamer API",
            "description": "Isaac Sim SRT streaming control API for agent-world extensions",
            "version": "1.0.0",
            "contact": {
                "name": "Agent World Extensions",
                "url": "https://github.com/your-org/agent-world"
            }
        },
        "servers": [
            {
                "url": f"http://localhost:{port}",
                "description": "Local WorldStreamer API server"
            }
        ],
        "paths": {
            "/health": {
                "get": {
                    "summary": "Health Check",
                    "description": "Get WorldStreamer extension health status",
                    "operationId": "getHealth",
                    "responses": {
                        "200": {
                            "description": "Health status",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/HealthResponse"}
                                }
                            }
                        }
                    }
                }
            },
            "/streaming/start": {
                "post": {
                    "summary": "Start Streaming",
                    "description": "Start SRT streaming session in Isaac Sim",
                    "operationId": "startStreaming",
                    "requestBody": {
                        "description": "Streaming start parameters",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/StartStreamingRequest"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Streaming start result",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/StreamingResponse"}
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "500": {"$ref": "#/components/responses/InternalError"}
                    }
                }
            },
            "/streaming/stop": {
                "post": {
                    "summary": "Stop Streaming",
                    "description": "Stop active SRT streaming session",
                    "operationId": "stopStreaming", 
                    "responses": {
                        "200": {
                            "description": "Streaming stop result",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/StreamingResponse"}
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "500": {"$ref": "#/components/responses/InternalError"}
                    }
                }
            },
            "/streaming/status": {
                "get": {
                    "summary": "Get Streaming Status",
                    "description": "Get current SRT streaming status and information",
                    "operationId": "getStreamingStatus",
                    "responses": {
                        "200": {
                            "description": "Streaming status information",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/StatusResponse"}
                                }
                            }
                        },
                        "500": {"$ref": "#/components/responses/InternalError"}
                    }
                }
            },
            "/streaming/urls": {
                "get": {
                    "summary": "Get Streaming URI",
                    "description": "Get SRT streaming URI for connection",
                    "operationId": "getStreamingUrls",
                    "parameters": [
                        {
                            "name": "server_ip",
                            "in": "query",
                            "description": "Optional server IP override",
                            "schema": {"type": "string"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Streaming URLs",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/UrlsResponse"}
                                }
                            }
                        },
                        "500": {"$ref": "#/components/responses/InternalError"}
                    }
                }
            },
            "/streaming/environment/validate": {
                "get": {
                    "summary": "Validate Environment",
                    "description": "Validate Isaac Sim environment for SRT streaming",
                    "operationId": "validateEnvironment",
                    "responses": {
                        "200": {
                            "description": "Environment validation results",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ValidationResponse"}
                                }
                            }
                        },
                        "500": {"$ref": "#/components/responses/InternalError"}
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "HealthResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "service": {"type": "string"},
                        "status": {"type": "string", "enum": ["healthy", "degraded", "unhealthy"]},
                        "timestamp": {"type": "string", "format": "date-time"},
                        "details": {"type": "object"}
                    },
                    "required": ["success", "service", "status", "timestamp"]
                },
                "StartStreamingRequest": {
                    "type": "object",
                    "properties": {
                        "server_ip": {
                            "type": "string",
                            "description": "Optional server IP override for streaming URLs"
                        }
                    }
                },
                "StreamingResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "message": {"type": "string"},
                        "error": {"type": "string"},
                        "timestamp": {"type": "string", "format": "date-time"},
                        "streaming_info": {"$ref": "#/components/schemas/StreamingInfo"},
                        "session_info": {"$ref": "#/components/schemas/SessionInfo"},
                        "status": {"$ref": "#/components/schemas/StreamingStatus"}
                    },
                    "required": ["success", "timestamp"]
                },
                "StatusResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "timestamp": {"type": "string", "format": "date-time"},
                        "status": {"$ref": "#/components/schemas/StreamingStatus"}
                    },
                    "required": ["success", "timestamp"]
                },
                "UrlsResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "timestamp": {"type": "string", "format": "date-time"},
                        "urls": {"$ref": "#/components/schemas/StreamingUrls"}
                    },
                    "required": ["success", "timestamp"]
                },
                "ValidationResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "timestamp": {"type": "string", "format": "date-time"},
                        "validation": {"$ref": "#/components/schemas/EnvironmentValidation"}
                    },
                    "required": ["success", "timestamp"]
                },
                "StreamingInfo": {
                    "type": "object",
                    "properties": {
                        "port": {"type": "integer"},
                        "livestream_mode": {"type": "integer", "enum": [1, 2]},
                        "urls": {"$ref": "#/components/schemas/StreamingUrls"},
                        "start_time": {"type": "string", "format": "date-time"}
                    }
                },
                "SessionInfo": {
                    "type": "object",
                    "properties": {
                        "duration_seconds": {"type": "number"},
                        "stop_time": {"type": "string", "format": "date-time"}
                    }
                },
                "StreamingStatus": {
                    "type": "object",
                    "properties": {
                        "state": {"type": "string", "enum": ["inactive", "starting", "active", "stopping", "error"]},
                        "previous_state": {"type": "string"},
                        "last_state_change": {"type": "string", "format": "date-time"},
                        "is_active": {"type": "boolean"},
                        "is_error": {"type": "boolean"},
                        "port": {"type": "integer"},
                        "urls": {"$ref": "#/components/schemas/StreamingUrls"},
                        "metadata": {"type": "object"},
                        "start_time": {"type": "string", "format": "date-time"},
                        "uptime_seconds": {"type": "number"},
                        "stop_time": {"type": "string", "format": "date-time"},
                        "error_message": {"type": "string"}
                    }
                },
                "StreamingUrls": {
                    "type": "object",
                    "properties": {
                        "local_url": {"type": "string", "format": "uri"},
                        "local_network_url": {"type": "string", "format": "uri"},
                        "public_url": {"type": "string", "format": "uri"},
                        "connection_info": {
                            "type": "object",
                            "properties": {
                                "port": {"type": "integer"},
                                "protocol": {"type": "string"},
                                "client_path": {"type": "string"},
                                "local_ip": {"type": "string"},
                                "public_ip": {"type": "string"}
                            }
                        },
                        "recommendations": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                },
                "EnvironmentValidation": {
                    "type": "object",
                    "properties": {
                        "valid": {"type": "boolean"},
                        "warnings": {"type": "array", "items": {"type": "string"}},
                        "errors": {"type": "array", "items": {"type": "string"}},
                        "recommendations": {"type": "array", "items": {"type": "string"}},
                        "environment_details": {"type": "object"}
                    },
                    "required": ["valid"]
                },
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "enum": [False]},
                        "error": {"type": "string"},
                        "error_code": {"type": "string"},
                        "timestamp": {"type": "string", "format": "date-time"}
                    },
                    "required": ["success", "error", "error_code", "timestamp"]
                }
            },
            "responses": {
                "BadRequest": {
                    "description": "Bad Request",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    }
                },
                "Unauthorized": {
                    "description": "Authentication required",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    }
                },
                "InternalError": {
                    "description": "Internal Server Error",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    }
                }
            }
        }
    }
    
    # Add authentication if enabled
    if auth_enabled:
        spec["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "description": "Bearer token authentication using agent_world unified auth system"
            }
        }
        spec["security"] = [{"BearerAuth": []}]
        
        # Add auth error responses to endpoints
        for path_data in spec["paths"].values():
            for method_data in path_data.values():
                if "responses" in method_data:
                    method_data["responses"]["401"] = {"$ref": "#/components/responses/Unauthorized"}
    
    return spec
