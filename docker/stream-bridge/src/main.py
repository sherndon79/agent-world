#!/usr/bin/env python3
"""
Stream Bridge - External GStreamer streaming service

Receives SRT streams from Isaac Sim, performs mixing/encoding/control,
outputs to YouTube RTMP and monitoring SRT.
"""

import logging
import sys
import os
import threading
from flask import Flask, jsonify, request

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s [%(name)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Check GStreamer availability
try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    Gst.init(None)
    logger.info("✓ GStreamer Python bindings available")
except Exception as e:
    logger.error(f"✗ GStreamer Python bindings not available: {e}")
    sys.exit(1)

from bridge_pipeline import StreamBridgePipeline

# Flask app for HTTP API
app = Flask(__name__)
pipeline = None


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'pipeline_active': pipeline is not None and pipeline.pipeline is not None
    })


@app.route('/start', methods=['POST'])
def start_streaming():
    """Start the streaming pipeline."""
    global pipeline

    data = request.json or {}
    rtmp_url = data.get('rtmp_url')
    srt_monitor_port = data.get('srt_monitor_port', 9998)

    if not rtmp_url:
        return jsonify({
            'success': False,
            'error': 'rtmp_url required'
        }), 400

    try:
        if pipeline:
            logger.warning("Pipeline already running, stopping first")
            pipeline.stop()

        pipeline = StreamBridgePipeline(rtmp_url, srt_monitor_port)

        # Start pipeline in background thread
        thread = threading.Thread(target=pipeline.run, daemon=True)
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Streaming started',
            'rtmp_url': rtmp_url,
            'srt_monitor_port': srt_monitor_port
        })

    except Exception as e:
        logger.error(f"Failed to start streaming: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/stop', methods=['POST'])
def stop_streaming():
    """Stop the streaming pipeline."""
    global pipeline

    try:
        if pipeline:
            pipeline.stop()
            pipeline = None

        return jsonify({
            'success': True,
            'message': 'Streaming stopped'
        })

    except Exception as e:
        logger.error(f"Failed to stop streaming: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/audio/add', methods=['POST'])
def add_audio_channel():
    """Add a dynamic audio input channel."""
    global pipeline

    if not pipeline:
        return jsonify({
            'success': False,
            'error': 'Pipeline not running'
        }), 400

    data = request.json or {}
    channel_id = data.get('channel_id')
    srt_port = data.get('srt_port')
    volume = data.get('volume', 1.0)

    if channel_id is None or srt_port is None:
        return jsonify({
            'success': False,
            'error': 'channel_id and srt_port required'
        }), 400

    try:
        pipeline.add_audio_channel(channel_id, srt_port, volume)

        return jsonify({
            'success': True,
            'message': f'Audio channel {channel_id} added',
            'channel_id': channel_id,
            'srt_port': srt_port,
            'volume': volume
        })

    except Exception as e:
        logger.error(f"Failed to add audio channel: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/audio/<int:channel_id>/volume', methods=['POST'])
def set_audio_volume(channel_id):
    """Set volume for a specific audio channel."""
    global pipeline

    if not pipeline:
        return jsonify({
            'success': False,
            'error': 'Pipeline not running'
        }), 400

    data = request.json or {}
    volume = data.get('volume')

    if volume is None:
        return jsonify({
            'success': False,
            'error': 'volume required'
        }), 400

    try:
        success = pipeline.set_channel_volume(channel_id, volume)

        if not success:
            return jsonify({
                'success': False,
                'error': f'Channel {channel_id} not found'
            }), 404

        return jsonify({
            'success': True,
            'message': f'Volume set for channel {channel_id}',
            'channel_id': channel_id,
            'volume': volume
        })

    except Exception as e:
        logger.error(f"Failed to set volume: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def main():
    """Main entry point for stream-bridge."""
    logger.info("=" * 70)
    logger.info("Stream Bridge Starting")
    logger.info("=" * 70)

    logger.info("Stream Bridge ready")
    logger.info("HTTP API: http://0.0.0.0:8080")
    logger.info("SRT Video Input: srt://0.0.0.0:9000?mode=listener")
    logger.info("SRT Audio Inputs: srt://0.0.0.0:9001-9010?mode=listener")
    logger.info("SRT Monitoring Output: srt://0.0.0.0:9998?mode=listener")
    logger.info("=" * 70)

    # Start Flask API
    app.run(host='0.0.0.0', port=8080, debug=False)


if __name__ == '__main__':
    main()