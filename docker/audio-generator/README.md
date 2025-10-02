# Agent Adventures Audio Generator

Multi-channel AI audio generation container for Agent Adventures interactive streaming platform.

## Overview

This container generates 4 channels of AI-powered audio synchronized with the Agent Adventures story state:

| Channel | Port | Purpose | AI Model |
|---------|------|---------|----------|
| 1 | 9001 | Narration | Kokoro TTS (native) / ElevenLabs |
| 2 | 9002 | Ambient/Environmental | ElevenLabs SFX / Stable Audio |
| 3 | 9003 | Dynamic Music | Mubert / Stable Audio |
| 4 | 9004 | Commentary | Kokoro TTS (native) / ElevenLabs |

## Architecture

```
Agent Adventures Story State (Redis) → Audio Generator Container
                                              ↓
                                    ┌─────────────────────┐
                                    │  4 Channel Output   │
                                    │  via SRT Streaming  │
                                    └─────────────────────┘
                                              ↓
                                    OBS (receives 4 SRT streams)
                                              ↓
                                    Multi-Platform Broadcast
```

## Prerequisites

- Docker with NVIDIA runtime
- CUDA-compatible GPU (RTX 3060 or better recommended)
- API keys for cloud models (optional, see .env.example)
- Redis server for Story State (can run in separate container)

## Quick Start

1. **Copy environment file:**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

2. **Build and run:**
   ```bash
   docker compose up --build
   ```

3. **Configure OBS:**
   - Add 4 Media Sources with SRT URLs:
     - `srt://localhost:9001?mode=listener` (Narration - 80% volume)
     - `srt://localhost:9002?mode=listener` (Ambient - 30% volume)
     - `srt://localhost:9003?mode=listener` (Music - 40% volume)
     - `srt://localhost:9004?mode=listener` (Commentary - 100% volume)

4. **Health check:**
   ```bash
   curl http://localhost:8080/health
   ```

## Configuration

### AI Model Selection

Edit `.env` to choose models for each channel:

**Narration (Channel 1):**
- `kokoro` - Self-hosted, native PyTorch pipeline, supports voice blending
- `elevenlabs` - Cloud API, best quality, <100ms latency

**Ambient (Channel 2):**
- `elevenlabs` - Cloud API, seamless looping
- `stable-audio` - Cloud API, detailed control

**Music (Channel 3):**
- `mubert` - Cloud API, real-time streaming
- `stable-audio` - Cloud API, high quality

**Commentary (Channel 4):**
- `elevenlabs` - Cloud API, distinct voice
- `live-mic` - Direct microphone input

### Story State Integration

The container subscribes to Redis pub/sub for story state updates:

```python
# Story state schema (audio-relevant fields)
{
  "narrative": {
    "current_narration": "Text to speak...",
    "tension_level": "rising_action"  # drives music intensity
  },
  "scene": {
    "environment": "forest",  # ambient sounds
    "time_of_day": "evening",
    "weather": "calm"
  },
  "audio": {
    "commentary_queue": ["Audience voted 67% for..."]
  }
}
```

## Development

### Local Development

```bash
# Mount source for live editing
docker compose up

# Watch logs
docker compose logs -f audio-generator
```

### Testing Individual Channels

```bash
# Test narration channel
curl -X POST http://localhost:8080/api/narration \
  -H "Content-Type: application/json" \
  -d '{"text": "Testing narration channel"}'

# Test ambient channel
curl -X POST http://localhost:8080/api/ambient \
  -H "Content-Type: application/json" \
  -d '{"scene": "forest at evening, calm weather"}'
```

### Adding New AI Models

1. Add model dependencies to `Dockerfile`
2. Create model interface in `src/models/`
3. Update `src/channel_manager.py` to use new model
4. Update `.env.example` with new configuration

## API Endpoints

- `GET /health` - Health check
- `GET /status` - Channel status and metrics
- `POST /api/narration` - Generate narration audio
- `POST /api/ambient` - Generate ambient audio
- `POST /api/music` - Generate music
- `POST /api/commentary` - Generate commentary
- `GET /metrics` - Prometheus metrics

## Monitoring

### Metrics

- Audio generation latency (p50, p95, p99)
- SRT connection status
- Model inference times
- Queue depths per channel

### Logs

Structured JSON logs:
```json
{
  "timestamp": "2025-10-01T12:34:56Z",
  "level": "INFO",
  "channel": "narration",
  "event": "audio_generated",
  "duration_ms": 187,
  "model": "kokoro"
}
```

## Troubleshooting

### No audio in OBS
- Check SRT connection: `docker compose logs audio-generator | grep SRT`
- Verify OBS Media Source mode is set to `listener`
- Check firewall/network settings for UDP ports 9001-9004

### High latency
- Reduce model quality settings in `.env`
- Enable model caching
- Check GPU utilization: `nvidia-smi`

### GPU out of memory
- Reduce concurrent channels
- Lower model sizes
- Increase VRAM allocation

## Cost Analysis

### Self-Hosted (Kokoro)
- **Hardware:** GPU instance (~$200/month)
- **API Costs:** $0
- **Total:** ~$200/month

### Cloud APIs (ElevenLabs + Mubert)
- **ElevenLabs:** ~$50-200/month
- **Mubert:** ~$50-100/month
- **Total:** ~$100-300/month

## References

- [Agent Adventures Architecture](../../agentworld_docs_archive_092925/dev_docs/agent_adventures_multichannel_audio_integration.md)
- Kokoro TTS (`kokoro` PyPI package)
- [ElevenLabs API](https://elevenlabs.io/docs)
- [Mubert API](https://mubert.com/api)
- [SRT Protocol](https://github.com/Haivision/srt)
