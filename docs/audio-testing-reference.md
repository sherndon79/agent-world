# Audio Generator Testing Reference

## Quick Testing Commands

### Music Generation (MusicGen)

**Basic Music Generation:**
```bash
curl -X POST http://localhost:8084/generate \
  -H "Content-Type: application/json" \
  -d '{
    "tension_level": "climax",
    "intensity": 0.9,
    "genre": "orchestral",
    "tempo": "fast",
    "duration": 10.0
  }' --output test_music.wav
```

**Via Orchestrator (SRT Stream to Port 9003):**
```bash
curl -X POST http://localhost:3001/api/audio/music \
  -H "Content-Type: application/json" \
  -d '{
    "tension_level": "climax",
    "intensity": 0.9,
    "genre": "orchestral",
    "tempo": "fast"
  }'
```

### Narration (Kokoro TTS)

**Via Orchestrator (SRT Stream to Port 9001):**
```bash
curl -X POST http://localhost:3001/api/audio/narration \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The battle reaches its climax as our heroes face their greatest challenge yet. The fate of the world hangs in the balance!",
    "voice": "af_heart:60,af_bella:40",
    "emotion": "intense",
    "volume": 0.7
  }'
```

### Synchronized Multi-Channel Playback

**NEW: Synchronized Narration + Music (Perfect Timing):**
```bash
curl -X POST http://localhost:8080/api/sync \
  -H "Content-Type: application/json" \
  -d '{
    "sync_id": "scene_1",
    "channels": {
      "narration": {
        "text": "The epic battle reaches its climax as our heroes face their greatest challenge!",
        "voice": "af_heart:60,af_bella:40",
        "emotion": "intense"
      },
      "music": {
        "tension_level": "climax",
        "intensity": 0.9,
        "genre": "orchestral",
        "tempo": "fast"
      }
    }
  }'
```

**How It Works:**
- Narration generates quickly (~0.1s) and waits
- Music generates slower (~4s)
- **Both start streaming simultaneously** when all are ready
- Total wait time = slowest channel (music ~4s)
- **Auto-ducking**: Music/ambient automatically reduce to 30% volume during narration
  - Smooth 50ms fade in/out transitions
  - Background returns to full volume after narration ends

**Supported Channels in Sync:**
- `narration` - Narration TTS
- `music` - Music generation
- `ambient` - Ambient audio
- `commentary` - Commentary TTS

**Example with 3 channels:**
```bash
curl -X POST http://localhost:8080/api/sync \
  -H "Content-Type: application/json" \
  -d '{
    "sync_id": "scene_forest_battle",
    "channels": {
      "narration": {
        "text": "You enter the dark forest as tension builds.",
        "voice": "af_heart",
        "emotion": "suspenseful"
      },
      "music": {
        "tension_level": "high",
        "intensity": 0.7,
        "genre": "orchestral"
      },
      "ambient": {
        "environment": "forest",
        "time_of_day": "night",
        "weather": "foggy"
      }
    }
  }'
```

### Legacy: Non-Synchronized Test (Music drowns out narration)

**OLD: Sequential triggering without sync:**
```bash
curl -X POST http://localhost:3001/api/audio/narration \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The battle reaches its climax as our heroes face their greatest challenge yet. The fate of the world hangs in the balance!",
    "voice": "af_heart:60,af_bella:40",
    "emotion": "intense",
    "volume": 0.7
  }' && sleep 2 && curl -X POST http://localhost:3001/api/audio/music \
  -H "Content-Type: application/json" \
  -d '{
    "tension_level": "climax",
    "intensity": 0.9,
    "genre": "orchestral",
    "tempo": "fast"
  }'
```
⚠️ **Note:** This approach has timing issues and no auto-ducking

## Performance Metrics (MusicGen on RTX 4090)

- **Model Load Time**: 3.2 seconds (first time only, then cached)
- **Generation Time**: 4.3 seconds for 10-second audio (~0.43x realtime)
- **Total Latency**: 7.6 seconds (including HTTP overhead)
- **GPU VRAM Usage**: +3.6GB (from 8.8GB Kokoro to 12.4GB total)
- **Available VRAM**: 12.2GB remaining for Isaac Sim

## Audio Specifications

- **Sample Rate**: 48kHz (upsampled from MusicGen's native 32kHz)
- **Channels**: Stereo (2 channels)
- **Format**: Float32 PCM
- **SRT Container**: MPEG-TS with AAC encoding
- **Bitrate**: 160kbps

## Auto-Ducking Configuration

### Current Settings
- **Enabled**: Yes (automatic)
- **Duck Ratio**: 30% (background channels reduce to 30% volume)
- **Fade Duration**: 50ms (smooth transitions)
- **Foreground Channels**: narration, commentary (trigger ducking)
- **Background Channels**: music, ambient (get ducked)

### Behavior
- When narration/commentary plays, music/ambient automatically reduce to 30%
- Smooth 50ms fade prevents jarring volume changes
- Background returns to full volume after narration ends
- Works automatically with synchronized playback via `/api/sync`

### Example Log Output
```
🔉 Ducked [music] to 30% for 5.6s (foreground audio present)
```

### SRT Port Mapping
- **Port 9001**: Narration (Kokoro TTS)
- **Port 9002**: Ambient (Procedural)
- **Port 9003**: Music (MusicGen)
- **Port 9004**: Commentary (Kokoro TTS)

## MusicGen Parameters

### Tension Levels
- `low`: "calm, peaceful, relaxed"
- `neutral`: "steady, balanced"
- `high`: "tense, dramatic, building"
- `climax`: "epic, intense, climactic, powerful"

### Intensity (0.0 - 1.0)
- `0.0`: "very subtle, quiet"
- `0.3`: "gentle, soft"
- `0.5`: "moderate"
- `0.7`: "energetic, strong"
- `1.0`: "very powerful, loud"

### Tempo
- `slow`: "slow tempo, 60 bpm"
- `moderate`: "moderate tempo, 100 bpm"
- `fast`: "fast tempo, 140 bpm"

### Genre
- `orchestral`: Epic orchestral music
- `electronic`: Electronic/synth music
- `ambient`: Ambient soundscapes
- `rock`: Rock music

## Example Prompts Generated

**Climax Example:**
```
orchestral music, epic, intense, climactic, powerful, energetic, strong, fast tempo, 140 bpm, instrumental, seamless loop
```

**Calm Example:**
```
ambient music, calm, peaceful, relaxed, gentle, soft, slow tempo, 60 bpm, instrumental, seamless loop
```
