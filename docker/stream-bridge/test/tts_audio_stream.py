#!/usr/bin/env python3
"""
TTS Audio Stream - Send text-to-speech audio to stream-bridge via UDP RTP

Uses pyttsx3 to generate speech and GStreamer to stream as RTP to UDP port.
"""

import pyttsx3
import tempfile
import os
import sys
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Initialize GStreamer
Gst.init(None)

def generate_speech_file(text, output_file):
    """Generate speech audio file using pyttsx3."""
    engine = pyttsx3.init()
    engine.save_to_file(text, output_file)
    engine.runAndWait()
    print(f"Generated speech audio: {output_file}")

def stream_audio_to_udp_gst(audio_file, host, port):
    """Stream audio file to UDP port as RTP using GStreamer."""

    # Build GStreamer pipeline:
    # filesrc → decodebin → audioconvert → audioresample → capsfilter → rtpL16pay → udpsink
    pipeline_str = (
        f'filesrc location="{audio_file}" ! '
        f'decodebin ! '
        f'audioconvert ! '
        f'audioresample ! '
        f'audio/x-raw,rate=48000,channels=2,format=S16BE ! '
        f'rtpL16pay ! '
        f'udpsink host={host} port={port}'
    )

    print(f"Streaming to {host}:{port}...")
    print(f"Pipeline: {pipeline_str}")

    # Create pipeline
    pipeline = Gst.parse_launch(pipeline_str)

    # Create main loop
    loop = GLib.MainLoop()

    # Bus message handler
    def on_message(bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            print("Stream completed")
            loop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err.message}")
            print(f"Debug: {debug}")
            loop.quit()
        elif t == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            print(f"Warning: {warn.message}")
        return True

    # Add bus watch
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", on_message)

    # Start pipeline
    pipeline.set_state(Gst.State.PLAYING)

    try:
        loop.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        pipeline.set_state(Gst.State.NULL)

    return True

def main():
    # Configuration
    text = "Hello world"
    udp_host = "172.18.0.2"  # stream-bridge container IP
    udp_port = 9001  # Channel 1

    # Allow override via command line
    if len(sys.argv) > 1:
        text = ' '.join(sys.argv[1:])

    print(f"Text: {text}")
    print(f"Target: {udp_host}:{udp_port}")

    # Generate speech to temporary file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        audio_file = tmp.name

    try:
        generate_speech_file(text, audio_file)
        stream_audio_to_udp_gst(audio_file, udp_host, udp_port)
    finally:
        # Cleanup
        if os.path.exists(audio_file):
            os.remove(audio_file)
            print(f"Cleaned up: {audio_file}")

if __name__ == '__main__':
    main()
