# Changelog

All notable changes to the Agent WorldBuilder extension will be documented in this file.

## [0.1.0] - 2025-08-22

### Added
- Initial release of Agent WorldBuilder extension
- Thread-safe USD scene management with queue-based operations
- HTTP API server on port 8899 for external integration
- Core object creation:
  - Primitive objects (cube, sphere, cylinder, cone)
  - Batch creation for multiple objects
  - USD asset placement via reference
  - Asset transformation capabilities
- Scene management operations:
  - Complete scene structure queries
  - Element listing and removal
  - Batch clearing and management
  - Scene health monitoring
- Spatial intelligence system:
  - Query objects by semantic type
  - Spatial bounds queries
  - Proximity-based object detection
- Transform operations:
  - Bounding box calculations
  - Ground level detection algorithms
  - Object alignment capabilities
- Request status tracking for queued operations
- MCP server integration with full endpoint coverage
- Prometheus metrics endpoint
- Comprehensive error handling and logging

### Technical Details
- Follows Agent World extension architecture patterns
- Thread-safe USD operations via main thread processing
- RESTful HTTP API design with OpenAPI specification
- Queue-based request processing for USD safety
- Real-time status monitoring and health checks
- Spatial intelligence algorithms for scene analysis

### Dependencies
- Isaac Sim 5.0+
- omni.usd
- omni.ui

### API Endpoints
- 16 total endpoints covering object creation, scene management, spatial queries, and system operations
- Full MCP integration for AI agent workflows
- Prometheus metrics for monitoring and observability