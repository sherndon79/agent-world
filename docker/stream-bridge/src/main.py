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
from pathlib import Path
from flask import Flask, jsonify, request
from dotenv import load_dotenv

# Load environment variables from config/.env
config_env = Path(__file__).parent.parent / "config" / ".env"
if config_env.exists():
    load_dotenv(config_env)
    logging.info(f"Loaded environment from {config_env}")
else:
    logging.warning(f"Config file not found: {config_env}")

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


@app.route('/metrics', methods=['GET'])
def metrics():
    """Get pipeline metrics and statistics."""
    if not pipeline:
        return jsonify({
            'pipeline_exists': False,
            'state': 'NOT_CREATED'
        })

    stats = pipeline.get_stats()
    return jsonify({
        'pipeline_exists': True,
        'pipeline_state': stats['state'],
        'started': stats['started'],
        'audio_channels_count': stats['audio_channels_count'],
        'audio_channels': stats.get('audio_channels', {}),
        'bus_messages': {
            'errors': len(stats['bus_messages']['error']),
            'warnings': len(stats['bus_messages']['warning']),
            'info': len(stats['bus_messages']['info'])
        },
        'recent_errors': stats['bus_messages']['error'][-5:],
        'recent_warnings': stats['bus_messages']['warning'][-5:]
    })


@app.route('/status', methods=['GET'])
def status():
    """Get detailed pipeline status."""
    if not pipeline:
        return jsonify({
            'pipeline_exists': False,
            'message': 'No pipeline created yet'
        })

    stats = pipeline.get_stats()
    return jsonify({
        'pipeline_exists': True,
        'state': stats['state'],
        'started': stats['started'],
        'audio_channels': stats.get('audio_channels', {}),
        'bus_messages': stats['bus_messages']
    })


@app.route('/start', methods=['POST'])
def start_streaming():
    """Start the streaming pipeline."""
    global pipeline

    data = request.json or {}

    # Get RTMP URL from request, or build from env vars
    rtmp_url = data.get('rtmp_url')
    if not rtmp_url:
        # Try to build from environment variables
        rtmp_primary = os.getenv('RTMP_PRIMARY_URL')
        rtmp_key = os.getenv('RTMP_STREAM_KEY')

        if rtmp_primary and rtmp_key:
            rtmp_url = f"{rtmp_primary}/{rtmp_key}"
            logger.info(f"Using RTMP URL from environment: {rtmp_primary}/***")
        else:
            return jsonify({
                'success': False,
                'error': 'rtmp_url required (not provided and not found in environment)'
            }), 400

    srt_monitor_port = data.get('srt_monitor_port', int(os.getenv('SRT_MONITOR_PORT', 9998)))
    source_type = data.get('source_type', 'srt')  # "srt" or "test"

    try:
        if pipeline:
            logger.warning("Pipeline already running, stopping first")
            pipeline.stop()

        pipeline = StreamBridgePipeline(rtmp_url, srt_monitor_port, source_type)

        # Start pipeline in background thread
        thread = threading.Thread(target=pipeline.run, daemon=True)
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Streaming started',
            'rtmp_url': rtmp_url,
            'srt_monitor_port': srt_monitor_port,
            'source_type': source_type
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


@app.route('/audio/channels', methods=['GET'])
def list_audio_channels():
    """List all audio channels and their status."""
    global pipeline

    if not pipeline:
        return jsonify({
            'success': False,
            'error': 'Pipeline not running'
        }), 400

    try:
        channels = []
        for channel_id in pipeline.audio_channels.keys():
            info = pipeline.get_audio_channel_info(channel_id)
            if info:
                channels.append(info)

        return jsonify({
            'success': True,
            'channels': channels
        })

    except Exception as e:
        logger.error(f"Failed to list audio channels: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/audio/<int:channel_id>', methods=['GET'])
def get_audio_channel(channel_id):
    """Get information about a specific audio channel."""
    global pipeline

    if not pipeline:
        return jsonify({
            'success': False,
            'error': 'Pipeline not running'
        }), 400

    try:
        info = pipeline.get_audio_channel_info(channel_id)

        if not info:
            return jsonify({
                'success': False,
                'error': f'Channel {channel_id} not found'
            }), 404

        return jsonify({
            'success': True,
            **info
        })

    except Exception as e:
        logger.error(f"Failed to get audio channel info: {e}")
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


@app.route('/audio/test-tone', methods=['POST'])
def toggle_test_tone():
    """Toggle the internal test tone on/off or set its volume."""
    global pipeline

    if not pipeline:
        return jsonify({
            'success': False,
            'error': 'Pipeline not running'
        }), 400

    data = request.json or {}
    volume = data.get('volume')  # If provided, set volume; if 0, turn off

    if volume is None:
        return jsonify({
            'success': False,
            'error': 'volume required (0.0 to turn off, 0.0-1.0 to set level)'
        }), 400

    try:
        success = pipeline.set_test_tone_volume(volume)

        if not success:
            return jsonify({
                'success': False,
                'error': 'Test tone not available'
            }), 404

        state = "off" if volume == 0 else "on"
        return jsonify({
            'success': True,
            'message': f'Test tone {state}',
            'volume': volume
        })

    except Exception as e:
        logger.error(f"Failed to set test tone: {e}")
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
    logger.info("SRT Video Input: srt://0.0.0.0:9999?mode=listener")
    logger.info("SRT Audio Inputs: srt://0.0.0.0:9001-9010?mode=listener")
    logger.info("SRT Monitoring Output: srt://0.0.0.0:9998?mode=listener")
    logger.info("=" * 70)

    # Start Flask API
    app.run(host='0.0.0.0', port=8080, debug=False)


if __name__ == '__main__':
    main()