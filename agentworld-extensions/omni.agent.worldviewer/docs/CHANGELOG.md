# Changelog

All notable changes to the Agent WorldViewer extension will be documented in this file.

## [0.1.0] - 2025-08-22

### Added
- Initial release of Agent WorldViewer extension
- Thread-safe camera control system with queue-based operations
- HTTP API server on port 8900 for external integration
- Core camera operations:
  - Set camera position and target
  - Frame objects in viewport automatically
  - Orbital camera positioning with spherical coordinates
  - Get current camera status
- Smooth cinematic movement system:
  - Smooth camera transitions between positions
  - Multiple easing functions (linear, ease_in_out, bounce, elastic)
  - Configurable duration and movement control
  - Stop active movements capability
- Asset transform queries:
  - Get position, rotation, scale information for scene objects
  - Multiple calculation modes (auto, center, pivot, bounds)
  - Bounding box information
- Real-time status monitoring:
  - Camera position and orientation tracking
  - Movement status and progress
  - Extension health monitoring
- MCP server integration with full endpoint coverage
- Prometheus metrics endpoint for monitoring
- Comprehensive error handling and logging
- Thread-safe background processing

### Technical Details
- Follows Agent World extension architecture patterns
- Thread-safe USD operations via main thread processing
- RESTful HTTP API design with OpenAPI specification
- Real-time camera control with smooth transitions
- Hardware-optimized viewport manipulation
- Automatic resource management and cleanup

### Dependencies
- Isaac Sim 5.0+
- omni.usd
- omni.ui
- omni.kit.viewport.utility

### API Endpoints
- 8 total endpoints covering camera control, cinematic movement, asset queries, and system monitoring
- Full MCP integration for AI agent workflows
- Prometheus metrics for performance monitoring

### Architecture Features
- Direct viewport camera manipulation
- Smooth cinematic movement engine with easing
- Asset query system for scene introspection
- Thread-safe operations with main thread coordination
- Integration with WorldSurveyor waypoints for spatial planning

### Relationship to WorldSurveyor
- WorldViewer provides camera movement and viewport control
- WorldSurveyor waypoints serve as spatial planning and camera presets
- Designed to work together for comprehensive scene navigation