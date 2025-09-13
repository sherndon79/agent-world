# Agent WorldStreamer (SRT)

Low-latency SRT streaming control for Isaac Sim. Captures a viewport and streams via an external GStreamer/NVENC pipeline using MPEG-TS/H.264 over SRT.

Overview
- Decoupled: extension provides control API; encoding runs externally.
- Configured via unified `agentworld-extensions/agent-world-config.json` under `worldstreamer.srt`.
- Default SRT URI targets OME: `srt://127.0.0.1:9999?mode=caller&latency=50&transtype=live&streamid=default/app/isaac`.

HTTP API
- POST `/streaming/start` – Start SRT streaming
- POST `/streaming/stop` – Stop streaming
- GET `/streaming/status` – Streaming status
- GET `/streaming/urls` – Current SRT-related URLs
- POST `/streaming/environment/validate` – Check environment prerequisites

Config keys (unified)
- `server_port` (default 8908)
- `encoding_fps`, `encoding_bitrate`, `encoder_type`
- `srt_url` – full SRT caller URI; streamid mapping auto-appended for OME if missing

Notes
- Pair with OME for WebRTC playback and LL‑HLS.
- Keep latency low with small queues and `sync=false` at the sink.
