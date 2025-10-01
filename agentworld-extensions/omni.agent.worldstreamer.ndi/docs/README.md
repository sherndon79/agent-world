# Agent WorldStreamer (NDI)

Low-latency NDI streaming control for Isaac Sim. Captures viewport and streams via GStreamer NDI plugin.

Overview
- Decoupled: extension provides control API; NDI streaming runs via GStreamer.
- Configured via unified `agentworld-extensions/agent-world-config.json` under `worldstreamer.ndi`.
- NDI streams are discoverable on the network with configurable source name.

HTTP API
- POST `/streaming/start` – Start NDI streaming
- POST `/streaming/stop` – Stop streaming
- GET `/streaming/status` – Streaming status
- GET `/streaming/urls` – Current NDI stream information
- POST `/streaming/environment/validate` – Check environment prerequisites

Config keys (unified)
- `server_port` (default 8909)
- `encoding_fps` – frames per second
- `ndi_name` – NDI source name (default: "Isaac Sim - Agent World")
- `ndi_groups` – Optional NDI groups (comma-separated)
- `clock_video` – Clock video timestamps (default: true)
- `enable_audio` – Enable audio streaming (default: false)

Notes
- NDI streams are automatically discoverable by NDI-compatible receivers
- No manual encoding configuration needed - NDI handles compression internally
- Lower latency than RTMP/SRT as NDI is optimized for LAN
