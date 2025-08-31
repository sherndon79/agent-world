# Changelog

All notable changes to the Agent WorldRecorder Extension will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-08-29

### Added
- **Kit-Native Implementation**: Complete rewrite using `omni.kit.capture.viewport` API
- **Video Recording**: MP4 video capture with configurable FPS, resolution, and duration
- **Screenshot Capture**: Single-frame PNG/JPG capture with immediate polling
- **HTTP API Compatibility**: Full compatibility with existing MCP WorldRecorder tools
- **Session Management**: Recording session tracking with unique session IDs
- **Thread-Safe Operations**: Main-thread task queue for Kit API operations
- **Authentication Support**: HMAC-SHA256 authentication with WWW-Authenticate headers
- **Status Monitoring**: Real-time recording status and output file tracking

### Changed
- **Replaced PyAV Dependency**: Eliminated external PyAV/FFmpeg requirements
- **Simplified Architecture**: Streamlined codebase from 1200+ to ~300 lines
- **Improved Reliability**: No external codec or installation dependencies
- **Enhanced Error Handling**: Better error messages and recovery mechanisms

### Removed
- **PyAV Integration**: Removed all PyAV-based video encoding code
- **External Dependencies**: No longer requires FFmpeg, codecs, or PyAV installation
- **Complex Fallbacks**: Eliminated PyAV availability checks and frame-mode fallbacks
- **Debug Endpoints**: Removed PyAV-specific debug and testing endpoints

### Technical Details
- Built on Isaac Sim's native capture system
- Uses `CaptureOptions` and `CaptureRangeType` for configuration
- Implements proper Kit main-thread execution for UI operations
- Maintains backward compatibility with all existing API endpoints
- Integrates with unified Agent World configuration and metrics systems

### Migration Notes
- Drop-in replacement for PyAV-based WorldRecorder
- Same HTTP API endpoints and parameter structure
- No changes required to MCP client code
- Improved performance and reduced installation complexity
- Original PyAV implementation archived as `worldrecorder_original_082925`

### Dependencies
```toml
[dependencies]
"omni.kit.capture.viewport" = {}
```

### Known Issues
- Frame sequence capture (interval-based) not yet implemented
- Output polling timeout set to 10 seconds (may need adjustment for long recordings)

### Planned Features
- **Frame Sequence Mode**: Timed frame capture (e.g., every 0.5s for 5 minutes)  
- **Enhanced Output Management**: Better output directory and naming controls
- **Recording Presets**: Predefined quality/resolution configurations
- **Batch Operations**: Multiple simultaneous recording sessions