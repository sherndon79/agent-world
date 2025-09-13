# Agent WorldStreamer (RTMP)

Low-latency RTMP streaming control for Isaac Sim. Captures a viewport and streams via an external GStreamer/NVENC pipeline.

Overview
- Decoupled: extension provides control API; encoding runs externally.
- Configured via unified `agentworld-extensions/agent-world-config.json` under `worldstreamer.rtmp`.
- Good for pushing to RTMP servers (e.g., YouTube/Twitch via restreamers).

HTTP API
- POST `/streaming/start` – Start RTMP streaming
- POST `/streaming/stop` – Stop streaming
- GET `/streaming/status` – Streaming status
- GET `/streaming/urls` – Current RTMP-related URLs
- POST `/streaming/environment/validate` – Check environment prerequisites

Config keys (unified)
- `server_port` (default 8906)
- `encoding_fps`, `encoding_bitrate`, `encoder_type`
- `rtmp_port` is informational; target endpoints come from your media router/restreamer.

Notes
- Prefer a local media router (e.g., OME) for ingest/relay.
- For POC latency, tune GStreamer with small queues, keyint, and `sync=false` at the sink.
