# Changelog

All notable changes to the Agent WorldSurveyor extension will be documented in this file.

## [0.1.0] - 2025-08-22

### Added
- Initial release of Agent WorldSurveyor extension
- Thread-safe waypoint management with queue-based operations
- HTTP API server on port 8891 for external integration
- Core waypoint operations:
  - Create waypoints with multiple types (POI, camera, object anchor, etc.)
  - List and query waypoints with filtering
  - Remove individual waypoints
  - Clear all waypoints functionality
- Hierarchical group management system:
  - Create nested waypoint groups
  - Add/remove waypoints from groups
  - Complete group hierarchy queries
  - Group-based waypoint organization
- Visual marker system:
  - Real-time 3D scene markers using debug draw
  - Global and individual marker visibility controls
  - Color-coded markers by waypoint type
- Data persistence and transfer:
  - Export waypoints and groups to JSON
  - Import waypoint data with merge/replace options
  - SQLite database for persistent storage
- Spatial planning features:
  - Multiple waypoint types for different use cases
  - Target-based camera positioning waypoints
  - Scene navigation and planning support
- MCP server integration with full endpoint coverage
- Prometheus metrics endpoint
- Comprehensive error handling and logging
- Web-based waypoint manager interface

### Technical Details
- Follows Agent World extension architecture patterns
- Thread-safe operations via main thread processing
- RESTful HTTP API design with OpenAPI specification
- SQLite database for waypoint persistence
- Debug draw integration for 3D markers
- Hierarchical group system with nested relationships
- Real-time marker visibility management

### Dependencies
- Isaac Sim 5.0+
- omni.usd
- omni.ui
- omni.kit.viewport.utility
- omni.kit.widget.toolbar
- isaacsim.util.debug_draw

### API Endpoints
- 19 total endpoints covering waypoint management, group operations, visualization, and data transfer
- Full MCP integration for AI agent workflows
- Prometheus metrics for monitoring and observability

### Configuration
- Supports authentication toggle via Isaac Sim settings
- Configurable via worldsurveyor_config.json
- Multiple waypoint types for various use cases