#!/usr/bin/env python3
"""
Continuous Tone Test - Send a test tone to verify audio pipeline

Sends a continuous 440Hz sine wave via RTP to test if audio reaches output.
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import sys

Gst.init(None)

def stream_tone(host="localhost", port=9001, duration_sec=20):
    """Stream a continuous test tone."""

    # audiotestsrc → audioconvert → audioresample → caps → rtpL16pay → udpsink
    pipeline_str = (
        f'audiotestsrc wave=sine freq=440 is-live=true ! '
        f'audioconvert ! '
        f'audioresample ! '
        f'audio/x-raw,rate=48000,channels=2,format=S16BE ! '
        f'rtpL16pay pt=96 ! '
        f'application/x-rtp,clock-rate=48000 ! '
        f'udpsink host={host} port={port}'
    )

    print(f"Streaming 440Hz tone to {host}:{port} for {duration_sec} seconds...")
    print("You should hear a constant tone on the output stream.")

    pipeline = Gst.parse_launch(pipeline_str)
    loop = GLib.MainLoop()

    def on_message(bus, message):
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err.message}")
            loop.quit()
        elif t == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            print(f"Warning: {warn.message}")
        return True

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", on_message)

    pipeline.set_state(Gst.State.PLAYING)

    GLib.timeout_add_seconds(duration_sec, lambda: loop.quit())

    try:
        loop.run()
    except KeyboardInterrupt:
        print("\nStopped by user")
    finally:
        pipeline.set_state(Gst.State.NULL)
        print("Stream stopped")

if __name__ == '__main__':
    stream_tone()
