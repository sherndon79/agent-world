OvenMediaEngine (OME) — Local Media Router

Quick start
- Requirements: Docker + Docker Compose v2
- Start: `docker compose up -d` (from this directory)
- Stop: `docker compose down`

Exposed ports
- 9999/udp: SRT ingest
- 3333: WebRTC signaling (WS), 3334: WebRTC signaling (WSS)
- 10000–10010/udp: WebRTC ICE RTP/RTCP
- 8080: HTTP/LL‑HLS
- 1935: RTMP ingest (optional)

Agent World SRT defaults
- Our SRT extension uses: `srt://127.0.0.1:9999?mode=caller&latency=50&transtype=live&streamid=default/app/isaac`
- OME defaults accept `default/app/isaac` (vhost/app/stream) without extra config.

Playback (WebRTC)
- Serve `agent-world/docs/ome-webrtc-player.html` over HTTP (e.g., from repo root: `python3 -m http.server 9000`).
- Open http://localhost:9000/agent-world/docs/ome-webrtc-player.html
- Enter signaling URL: `ws://localhost:3333/app/isaac` and click Play.

Environment overrides
- See `.env` to change image/name. Defaults are sensible for local dev.

