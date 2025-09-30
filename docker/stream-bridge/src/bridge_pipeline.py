#!/usr/bin/env python3
"""
Stream Bridge - Dynamic GStreamer Pipeline

Receives SRT video + audio streams, mixes, and outputs to RTMP + SRT monitoring.
Based on validated test_rtmp_srt_with_tones.py pipeline.
"""

import logging
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

logger = logging.getLogger(__name__)

Gst.init(None)


class StreamBridgePipeline:
    """Dynamic GStreamer pipeline for stream bridging."""

    def __init__(self, rtmp_url: str, srt_monitor_port: int = 9998, source_type: str = "srt", num_audio_channels: int = 4):
        self.rtmp_url = rtmp_url
        self.srt_monitor_port = srt_monitor_port
        self.source_type = source_type  # "srt" or "test"
        self.num_audio_channels = num_audio_channels  # Number of external audio inputs
        self.pipeline = None
        self.loop = None
        self.audio_channels = {}  # Track audio channel elements (channel_id -> elements dict)
        self.video_src = None
        self.test_tone_volume_elem = None  # Track test tone volume element
        self.stats = {
            'started': False,
            'state': 'NULL',
            'source_type': source_type,
            'audio_channels_count': num_audio_channels,
            'bus_messages': {
                'error': [],
                'warning': [],
                'info': []
            }
        }

    def build_pipeline(self):
        """Build the GStreamer pipeline."""
        logger.info(f"Building stream bridge pipeline with source_type={self.source_type}")

        # Create pipeline
        self.pipeline = Gst.Pipeline.new("stream-bridge")

        # Video path - varies by source type
        if self.source_type == "test":
            # Test pattern video source
            video_src = Gst.ElementFactory.make("videotestsrc", "video-src")
            video_src.set_property("pattern", 0)  # SMPTE color bars
            video_src.set_property("is-live", True)

            video_caps = Gst.ElementFactory.make("capsfilter", "video-caps")
            video_caps.set_property("caps",
                Gst.Caps.from_string("video/x-raw,format=I420,width=1920,height=1080,framerate=30/1"))

            videoconvert = Gst.ElementFactory.make("videoconvert", "videoconvert")

            # Try NVIDIA encoder first, fallback to x264enc
            nvh264enc = Gst.ElementFactory.make("nvh264enc", "nvh264enc")
            if nvh264enc:
                nvh264enc.set_property("bitrate", 2000)
                # Add preset for better compatibility
                nvh264enc.set_property("preset", "low-latency-hq")
                encoder = nvh264enc
                logger.info("Using nvh264enc encoder")
            else:
                # Fallback to software encoder
                encoder = Gst.ElementFactory.make("x264enc", "x264enc")
                encoder.set_property("bitrate", 2000)
                encoder.set_property("tune", "zerolatency")
                logger.info("Using x264enc encoder (nvh264enc not available)")

            h264parse = Gst.ElementFactory.make("h264parse", "h264parse")
            h264parse.set_property("config-interval", -1)  # Insert SPS/PPS for compatibility
            video_queue = Gst.ElementFactory.make("queue", "video-queue")

            video_elements = [video_src, video_caps, videoconvert, encoder, h264parse, video_queue]
        else:
            # SRT input → MPEG-TS demux → H.264 parse → mux
            video_src = Gst.ElementFactory.make("srtsrc", "video-src")
            video_src.set_property("uri", "srt://0.0.0.0:9999?mode=listener&latency=200&transtype=live&rcvbuf=1048576&sndbuf=1048576&payloadsize=1316&tlpktdrop=1")

            tsdemux = Gst.ElementFactory.make("tsdemux", "tsdemux")
            h264parse = Gst.ElementFactory.make("h264parse", "h264parse")
            video_queue = Gst.ElementFactory.make("queue", "video-queue")

            video_elements = [video_src, tsdemux, h264parse, video_queue]

        self.video_src = video_src

        # Audio mixer with keepalive (ignore-inactive-pads allows it to start without all inputs ready)
        audiomixer = Gst.ElementFactory.make("audiomixer", "mixer")
        audiomixer.set_property("ignore-inactive-pads", True)

        # Silent audio keepalive (channel 0) - prevents mixer stalling
        silence_src = Gst.ElementFactory.make("audiotestsrc", "silence")
        silence_src.set_property("wave", "silence")
        silence_src.set_property("is-live", True)

        silence_caps = Gst.ElementFactory.make("capsfilter", "silence-caps")
        silence_caps.set_property("caps",
            Gst.Caps.from_string("audio/x-raw,rate=48000,channels=2"))

        # Internal test tone (440Hz) - controllable via API
        test_tone_src = Gst.ElementFactory.make("audiotestsrc", "test-tone")
        test_tone_src.set_property("wave", "sine")
        test_tone_src.set_property("freq", 440)
        test_tone_src.set_property("is-live", True)

        test_tone_caps = Gst.ElementFactory.make("capsfilter", "test-tone-caps")
        test_tone_caps.set_property("caps",
            Gst.Caps.from_string("audio/x-raw,rate=48000,channels=2"))

        test_tone_volume = Gst.ElementFactory.make("volume", "test-tone-volume")
        test_tone_volume.set_property("volume", 0.0)  # Start with tone OFF
        self.test_tone_volume_elem = test_tone_volume  # Store reference for API control

        # Pre-configured external audio input channels (1-N on ports 9001-900N)
        audio_channel_elements = []
        for channel_id in range(1, self.num_audio_channels + 1):
            port = 9000 + channel_id
            logger.info(f"Creating audio channel {channel_id} on port {port}")

            # UDP audio source - receives raw audio over UDP (simple and reliable for local streaming)
            src = Gst.ElementFactory.make("udpsrc", f"audio-src-{channel_id}")
            src.set_property("port", port)
            src.set_property("caps", Gst.Caps.from_string("application/x-rtp"))

            # RTP depayloader for audio
            rtpdepay = Gst.ElementFactory.make("rtpL16depay", f"audio-rtpdepay-{channel_id}")

            # Leaky queue after source to prevent blocking when no data
            queue_src = Gst.ElementFactory.make("queue", f"audio-queue-src-{channel_id}")
            queue_src.set_property("max-size-buffers", 10)
            queue_src.set_property("leaky", 2)  # 2 = downstream (drop old data)

            # Convert to proper format
            audioconvert_ch = Gst.ElementFactory.make("audioconvert", f"audio-convert-{channel_id}")
            audioresample = Gst.ElementFactory.make("audioresample", f"audio-resample-{channel_id}")

            # Another leaky queue before mixer to prevent blocking
            queue_mixer = Gst.ElementFactory.make("queue", f"audio-queue-mixer-{channel_id}")
            queue_mixer.set_property("max-size-buffers", 10)
            queue_mixer.set_property("leaky", 2)  # 2 = downstream

            # Volume control (default 1.0 = 100%)
            volume_elem = Gst.ElementFactory.make("volume", f"volume-{channel_id}")
            volume_elem.set_property("volume", 1.0)

            # Caps filter
            caps = Gst.ElementFactory.make("capsfilter", f"audio-caps-{channel_id}")
            caps.set_property("caps",
                Gst.Caps.from_string("audio/x-raw,rate=48000,channels=2"))

            # Store elements for this channel
            self.audio_channels[channel_id] = {
                'port': port,
                'src': src,
                'rtpdepay': rtpdepay,
                'queue_src': queue_src,
                'audioconvert': audioconvert_ch,
                'audioresample': audioresample,
                'queue_mixer': queue_mixer,
                'volume': volume_elem,
                'caps': caps
            }

            # Collect for pipeline addition
            audio_channel_elements.extend([src, rtpdepay, queue_src, audioconvert_ch, audioresample, queue_mixer, volume_elem, caps])

        # Audio encoding
        audioconvert = Gst.ElementFactory.make("audioconvert", "audioconvert")
        voaacenc = Gst.ElementFactory.make("voaacenc", "aacenc")
        voaacenc.set_property("bitrate", 128000)
        aacparse = Gst.ElementFactory.make("aacparse", "aacparse")

        # FLV muxer
        flvmux = Gst.ElementFactory.make("flvmux", "mux")
        flvmux.set_property("streamable", True)

        # Tee for dual output
        tee = Gst.ElementFactory.make("tee", "tee")

        # RTMP output branch
        rtmp_queue = Gst.ElementFactory.make("queue", "rtmp-queue")
        rtmp_sink = Gst.ElementFactory.make("rtmpsink", "rtmp-sink")
        rtmp_sink.set_property("location", self.rtmp_url)
        rtmp_sink.set_property("sync", False)
        rtmp_sink.set_property("async", False)

        # SRT monitoring output branch
        srt_queue = Gst.ElementFactory.make("queue", "srt-queue")
        srt_sink = Gst.ElementFactory.make("srtsink", "srt-sink")
        srt_sink.set_property("uri",
            f"srt://0.0.0.0:{self.srt_monitor_port}?mode=listener&latency=200")
        srt_sink.set_property("sync", False)
        srt_sink.set_property("async", False)

        # Add elements to pipeline
        elements = video_elements + [
            silence_src, silence_caps,
            test_tone_src, test_tone_caps, test_tone_volume,
            audiomixer
        ] + audio_channel_elements + [
            audioconvert, voaacenc, aacparse,
            flvmux, tee,
            rtmp_queue, rtmp_sink,
            srt_queue, srt_sink
        ]

        for elem in elements:
            self.pipeline.add(elem)

        # Link video path based on source type
        if self.source_type == "test":
            # Test: videotestsrc → caps → convert → encoder → h264parse → queue
            video_src.link(video_caps)
            video_caps.link(videoconvert)
            videoconvert.link(encoder)
            encoder.link(h264parse)
            h264parse.link(video_queue)
        else:
            # SRT: srtsrc → tsdemux (dynamic pad) → h264parse → queue
            video_src.link(tsdemux)

            # tsdemux has dynamic pads, connect when video pad appears
            def on_pad_added(element, pad):
                pad_name = pad.get_name()
                logger.info(f"tsdemux pad added: {pad_name}")
                if pad.get_current_caps():
                    caps_str = pad.get_current_caps().to_string()
                    if "video" in caps_str:
                        sink_pad = h264parse.get_static_pad("sink")
                        if not sink_pad.is_linked():
                            pad.link(sink_pad)
                            logger.info("Linked tsdemux video pad to h264parse")

            tsdemux.connect("pad-added", on_pad_added)
            h264parse.link(video_queue)

        # Link audio path: silence → mixer
        silence_src.link(silence_caps)
        silence_caps.link(audiomixer)

        # Link test tone → volume → mixer
        test_tone_src.link(test_tone_caps)
        test_tone_caps.link(test_tone_volume)
        test_tone_volume.link(audiomixer)
        logger.info("Linked internal test tone (440Hz @ 30%) to mixer")

        # Link external audio channels: src → rtpdepay → queue → convert → resample → queue → volume → caps → mixer
        for channel_id in range(1, self.num_audio_channels + 1):
            ch = self.audio_channels[channel_id]
            ch['src'].link(ch['rtpdepay'])
            ch['rtpdepay'].link(ch['queue_src'])
            ch['queue_src'].link(ch['audioconvert'])
            ch['audioconvert'].link(ch['audioresample'])
            ch['audioresample'].link(ch['queue_mixer'])
            ch['queue_mixer'].link(ch['volume'])
            ch['volume'].link(ch['caps'])
            ch['caps'].link(audiomixer)
            logger.info(f"Audio channel {channel_id} linked to mixer")

        # Link mixer → encoder → mux
        audiomixer.link(audioconvert)
        audioconvert.link(voaacenc)
        voaacenc.link(aacparse)

        # Link muxer → tee → outputs
        flvmux.link(tee)

        # RTMP branch
        tee.link(rtmp_queue)
        rtmp_queue.link(rtmp_sink)

        # SRT branch
        tee.link(srt_queue)
        srt_queue.link(srt_sink)

        # Request pads for muxer
        # Video pad
        video_queue_pad = video_queue.get_static_pad("src")
        mux_video_pad = flvmux.get_request_pad("video")
        video_queue_pad.link(mux_video_pad)

        # Audio pad
        aac_pad = aacparse.get_static_pad("src")
        mux_audio_pad = flvmux.get_request_pad("audio")
        aac_pad.link(mux_audio_pad)

        logger.info("Pipeline built successfully")
        return True

    def get_audio_channel_info(self, channel_id: int):
        """Get information about an audio channel."""
        if channel_id not in self.audio_channels:
            return None

        ch = self.audio_channels[channel_id]
        return {
            'channel_id': channel_id,
            'port': ch['port'],
            'volume': ch['volume'].get_property('volume')
        }

    def set_channel_volume(self, channel_id: int, volume: float):
        """Set volume for a specific audio channel."""
        if channel_id not in self.audio_channels:
            logger.error(f"Audio channel {channel_id} not found")
            return False

        volume_elem = self.audio_channels[channel_id]['volume']
        volume_elem.set_property("volume", volume)
        logger.info(f"Set channel {channel_id} volume to {volume}")
        return True

    def set_test_tone_volume(self, volume: float):
        """Set volume for the internal test tone (0.0 = off)."""
        if not self.test_tone_volume_elem:
            logger.error("Test tone volume element not available")
            return False

        self.test_tone_volume_elem.set_property("volume", volume)
        state = "OFF" if volume == 0 else f"ON at {int(volume * 100)}%"
        logger.info(f"Test tone {state}")
        return True

    def start(self):
        """Start the pipeline."""
        if not self.pipeline:
            self.build_pipeline()

        logger.info("Starting stream bridge pipeline")
        ret = self.pipeline.set_state(Gst.State.PLAYING)

        if ret == Gst.StateChangeReturn.FAILURE:
            logger.error("Failed to start pipeline")
            self.stats['started'] = False
            self.stats['state'] = 'FAILED'
            return False

        logger.info("Pipeline started successfully")
        self.stats['started'] = True
        self.stats['state'] = 'PLAYING'
        return True

    def stop(self):
        """Stop the pipeline."""
        if self.pipeline:
            logger.info("Stopping stream bridge pipeline")
            self.pipeline.set_state(Gst.State.NULL)
            self.stats['state'] = 'NULL'
            self.stats['started'] = False
            logger.info("Pipeline stopped")

    def run(self):
        """Run the pipeline with GLib main loop."""
        self.start()

        # Create main loop
        self.loop = GLib.MainLoop()

        # Add bus watch
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

        try:
            logger.info("Running main loop")
            self.loop.run()
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.stop()

    def _on_bus_message(self, bus, message):
        """Handle bus messages."""
        t = message.type

        if t == Gst.MessageType.EOS:
            logger.info("End of stream")
            self.stats['bus_messages']['info'].append('End of stream')
            self.loop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Pipeline error: {err.message}")
            logger.debug(f"Debug info: {debug}")
            self.stats['bus_messages']['error'].append({
                'message': err.message,
                'debug': debug
            })
            self.loop.quit()
        elif t == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            logger.warning(f"Pipeline warning: {warn.message}")
            self.stats['bus_messages']['warning'].append({
                'message': warn.message,
                'debug': debug
            })
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old_state, new_state, pending_state = message.parse_state_changed()
                self.stats['state'] = new_state.value_nick.upper()
                logger.info(f"Pipeline state changed: {old_state.value_nick} -> {new_state.value_nick}")

    def get_stats(self):
        """Get current pipeline statistics."""
        stats = self.stats.copy()

        # Get current pipeline state if available
        if self.pipeline:
            state_result = self.pipeline.get_state(0)
            if state_result[0] == Gst.StateChangeReturn.SUCCESS:
                stats['state'] = state_result[1].value_nick.upper()

        # Add audio channel details
        stats['audio_channels'] = {
            channel_id: {
                'port': self.audio_channels[channel_id]['src'].get_property('uri'),
                'volume': self.audio_channels[channel_id]['volume'].get_property('volume')
            }
            for channel_id in self.audio_channels
        }

        return stats