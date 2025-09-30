#!/usr/bin/env python3
"""
TTS Audio Stream (Continuous) - Loop audio to stream-bridge via UDP RTP

Uses pyttsx3 to generate speech and GStreamer to continuously stream as RTP.
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

def stream_audio_to_udp_gst_continuous(audio_file, host, port, duration_sec=15):
    """Stream audio file to UDP port as RTP using GStreamer, looping for specified duration."""

    # Build GStreamer pipeline with audiotestsrc for continuous tone + filesrc for speech mixed
    # Use filesrc with loop via seek, or just play multiple times
    pipeline_str = (
        f'filesrc location="{audio_file}" ! '
        f'wavparse ! '
        f'audioconvert ! '
        f'audioresample ! '
        f'audio/x-raw,rate=48000,channels=2,format=S16BE ! '
        f'rtpL16pay pt=96 ! '
        f'application/x-rtp,clock-rate=48000 ! '
        f'udpsink host={host} port={port}'
    )

    print(f"Streaming to {host}:{port} for {duration_sec} seconds...")
    print(f"Pipeline: {pipeline_str[:80]}...")

    # Create pipeline
    pipeline = Gst.parse_launch(pipeline_str)

    # Create main loop
    loop = GLib.MainLoop()

    play_count = [0]

    # Bus message handler
    def on_message(bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            # Loop the audio by seeking back to start
            play_count[0] += 1
            print(f"Loop {play_count[0]}, seeking to start...")
            pipeline.seek_simple(
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                0
            )
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

    # Add timeout to quit after specified duration
    def timeout_quit():
        print(f"\n{duration_sec} seconds elapsed, stopping stream")
        loop.quit()
        return False

    GLib.timeout_add_seconds(duration_sec, timeout_quit)

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
    udp_host = "localhost"  # Send to localhost (mapped to container)
    udp_port = 9001  # Channel 1
    duration_sec = 15  # How long to stream (seconds)

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
        stream_audio_to_udp_gst_continuous(audio_file, udp_host, udp_port, duration_sec)
    finally:
        # Cleanup
        if os.path.exists(audio_file):
            os.remove(audio_file)
            print(f"Cleaned up: {audio_file}")

if __name__ == '__main__':
    main()
