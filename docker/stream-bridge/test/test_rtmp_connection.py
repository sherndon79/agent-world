#!/usr/bin/env python3
"""
Test RTMP connection to YouTube without full pipeline
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import sys

Gst.init(None)

def test_rtmp_connection(rtmp_url):
    """Test RTMP connection with minimal pipeline."""

    # Minimal test pipeline: videotestsrc + audiotestsrc → flvmux → rtmpsink
    pipeline_str = (
        'videotestsrc pattern=0 is-live=true ! '
        'video/x-raw,width=1280,height=720,framerate=30/1 ! '
        'videoconvert ! '
        'x264enc bitrate=2000 tune=zerolatency ! '
        'video/x-h264,profile=main ! '
        'h264parse ! '
        'flvmux name=mux streamable=true ! '
        f'rtmpsink location="{rtmp_url}" sync=false async=false '
        'audiotestsrc wave=silence is-live=true ! '
        'audio/x-raw,rate=48000,channels=2 ! '
        'audioconvert ! '
        'voaacenc bitrate=128000 ! '
        'aacparse ! '
        'mux.'
    )

    print(f"Testing RTMP connection to: {rtmp_url[:50]}...")
    print(f"Pipeline: {pipeline_str[:100]}...")

    pipeline = Gst.parse_launch(pipeline_str)

    loop = GLib.MainLoop()

    def on_message(bus, message):
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"\n❌ RTMP Connection FAILED")
            print(f"Error: {err.message}")
            print(f"Debug: {debug}")
            loop.quit()
            return False
        elif t == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            print(f"⚠️  Warning: {warn.message}")
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == pipeline:
                old, new, pending = message.parse_state_changed()
                print(f"State: {old.value_nick} → {new.value_nick}")
                if new == Gst.State.PLAYING:
                    print("✅ RTMP Connection SUCCESSFUL - Stream is flowing!")
                    # Let it run for 5 seconds then stop
                    GLib.timeout_add_seconds(5, lambda: loop.quit())
        return True

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", on_message)

    pipeline.set_state(Gst.State.PLAYING)

    try:
        loop.run()
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        pipeline.set_state(Gst.State.NULL)

if __name__ == '__main__':
    # Read RTMP URL from environment or command line
    import os

    rtmp_url = None
    if len(sys.argv) > 1:
        rtmp_url = sys.argv[1]
    else:
        rtmp_primary = os.getenv('RTMP_PRIMARY_URL', 'rtmp://a.rtmp.youtube.com/live2')
        rtmp_key = os.getenv('RTMP_STREAM_KEY', '')
        if rtmp_key:
            rtmp_url = f"{rtmp_primary}/{rtmp_key}"

    if not rtmp_url:
        print("Usage: python test_rtmp_connection.py <rtmp_url>")
        print("Or set RTMP_PRIMARY_URL and RTMP_STREAM_KEY environment variables")
        sys.exit(1)

    test_rtmp_connection(rtmp_url)
