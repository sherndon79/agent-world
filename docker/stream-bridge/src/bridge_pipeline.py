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

    def __init__(self, rtmp_url: str, srt_monitor_port: int = 9998):
        self.rtmp_url = rtmp_url
        self.srt_monitor_port = srt_monitor_port
        self.pipeline = None
        self.loop = None
        self.audio_channels = {}  # Track audio channel elements

    def build_pipeline(self):
        """Build the GStreamer pipeline."""
        logger.info("Building stream bridge pipeline")

        # Create pipeline
        self.pipeline = Gst.Pipeline.new("stream-bridge")

        # Video path: SRT input → H.264 decode → encode → mux
        video_src = Gst.ElementFactory.make("srtsrc", "video-src")
        video_src.set_property("uri", "srt://0.0.0.0:9000?mode=listener")

        # TODO: Add H.264 demux/decode when receiving MPEG-TS
        # For now, assume raw H.264 input

        # Audio mixer with keepalive
        audiomixer = Gst.ElementFactory.make("audiomixer", "mixer")

        # Silent audio keepalive (channel 0)
        silence_src = Gst.ElementFactory.make("audiotestsrc", "silence")
        silence_src.set_property("wave", "silence")
        silence_src.set_property("is-live", True)

        silence_caps = Gst.ElementFactory.make("capsfilter", "silence-caps")
        silence_caps.set_property("caps",
            Gst.Caps.from_string("audio/x-raw,rate=48000,channels=2"))

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
        elements = [
            silence_src, silence_caps, audiomixer,
            audioconvert, voaacenc, aacparse,
            flvmux, tee,
            rtmp_queue, rtmp_sink,
            srt_queue, srt_sink
        ]

        for elem in elements:
            self.pipeline.add(elem)

        # Link audio path: silence → mixer → encoder → mux
        silence_src.link(silence_caps)
        silence_caps.link(audiomixer)
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
        aac_pad = aacparse.get_static_pad("src")
        mux_audio_pad = flvmux.get_request_pad("audio")
        aac_pad.link(mux_audio_pad)

        logger.info("Pipeline built successfully")
        return True

    def add_audio_channel(self, channel_id: int, srt_port: int, volume: float = 1.0):
        """Add a dynamic audio input channel."""
        logger.info(f"Adding audio channel {channel_id} on port {srt_port} with volume {volume}")

        # Create SRT audio source
        src = Gst.ElementFactory.make("srtsrc", f"audio-src-{channel_id}")
        src.set_property("uri", f"srt://0.0.0.0:{srt_port}?mode=listener")

        # Audio decode (assume AAC for now)
        # TODO: Add proper audio demux/decode

        # Volume control
        volume_elem = Gst.ElementFactory.make("volume", f"volume-{channel_id}")
        volume_elem.set_property("volume", volume)

        # Caps filter
        caps = Gst.ElementFactory.make("capsfilter", f"audio-caps-{channel_id}")
        caps.set_property("caps",
            Gst.Caps.from_string("audio/x-raw,rate=48000,channels=2"))

        # Add to pipeline
        self.pipeline.add(src)
        self.pipeline.add(volume_elem)
        self.pipeline.add(caps)

        # Link to mixer
        mixer = self.pipeline.get_by_name("mixer")
        src.link(volume_elem)
        volume_elem.link(caps)
        caps.link(mixer)

        # Store reference
        self.audio_channels[channel_id] = {
            'src': src,
            'volume': volume_elem,
            'caps': caps
        }

        # Sync state if pipeline is running
        if self.pipeline.get_state(0)[1] == Gst.State.PLAYING:
            src.sync_state_with_parent()
            volume_elem.sync_state_with_parent()
            caps.sync_state_with_parent()

        logger.info(f"Audio channel {channel_id} added")

    def set_channel_volume(self, channel_id: int, volume: float):
        """Set volume for a specific audio channel."""
        if channel_id not in self.audio_channels:
            logger.error(f"Audio channel {channel_id} not found")
            return False

        volume_elem = self.audio_channels[channel_id]['volume']
        volume_elem.set_property("volume", volume)
        logger.info(f"Set channel {channel_id} volume to {volume}")
        return True

    def start(self):
        """Start the pipeline."""
        if not self.pipeline:
            self.build_pipeline()

        logger.info("Starting stream bridge pipeline")
        ret = self.pipeline.set_state(Gst.State.PLAYING)

        if ret == Gst.StateChangeReturn.FAILURE:
            logger.error("Failed to start pipeline")
            return False

        logger.info("Pipeline started successfully")
        return True

    def stop(self):
        """Stop the pipeline."""
        if self.pipeline:
            logger.info("Stopping stream bridge pipeline")
            self.pipeline.set_state(Gst.State.NULL)
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
            self.loop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Pipeline error: {err.message}")
            logger.debug(f"Debug info: {debug}")
            self.loop.quit()
        elif t == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            logger.warning(f"Pipeline warning: {warn.message}")