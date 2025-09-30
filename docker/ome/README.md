# OvenMediaEngine Setup

OvenMediaEngine (OME) provides WebRTC playback and RTMP forwarding to YouTube.

## Architecture

```
Isaac Sim → WorldStreamer → SRT → OME → WebRTC (local viewing)
                                     ↓
                                   YouTube (RTMP forwarding)
```

## Setup

1. **Configure YouTube URL**:
   Edit `.env` and set your YouTube stream key:
   ```bash
   YOUTUBE_RTMP_URL=rtmp://a.rtmp.youtube.com/live2/YOUR_STREAM_KEY
   ```

2. **Build and start OME**:
   ```bash
   docker-compose build
   docker-compose up -d
   ```

3. **Check logs**:
   ```bash
   docker-compose logs -f
   ```

## Usage

### Stream to OME

WorldStreamer automatically streams to SRT port 9999, which OME ingests.

Start WorldStreamer streaming:
```bash
curl -X POST http://localhost:9500/worldstreamer/start_streaming
```

### View Stream

Open `webrtc-player.html` in your browser to view the stream via WebRTC.

## Applications

OME has two applications configured:

1. **`app`** - Basic WebRTC playback (no YouTube forwarding)
   - SRT Input: `srt://localhost:9999?streamid=default/app/isaac`
   - WebRTC: `ws://localhost:3333/app/isaac`

2. **`stream`** - WebRTC playback + YouTube forwarding
   - SRT Input: `srt://localhost:9999?streamid=default/stream/isaac`
   - WebRTC: `ws://localhost:3333/stream/isaac`
   - Forwards to YouTube automatically

## Ports

- `9999` - SRT input (from WorldStreamer)
- `1935` - RTMP input (optional)
- `3333` - WebRTC signaling
- `3478` - WebRTC TCP
- `10000-10009` - WebRTC UDP
- `8081` - API
- `8080` - HLS (unused)

## Testing

1. Build and start OME: `docker-compose build && docker-compose up -d`
2. Start WorldStreamer streaming: `curl -X POST http://localhost:9500/worldstreamer/start_streaming`
3. Open webrtc-player.html to view stream
4. Check YouTube Studio to see if forwarding works

Note: The stream ID from WorldStreamer is `default/app/isaac`, so the WebRTC URL is `ws://localhost:3333/app/isaac`
