#!/bin/bash
# Test external audio input - simplest possible case
# Two separate processes: sender and receiver

echo "Testing external audio input via UDP/RTP"
echo "=========================================="
echo ""
echo "Starting receiver (will play audio for 30 seconds)..."
echo ""

# Start receiver in background
gst-launch-1.0 -v \
    udpsrc port=9001 caps='application/x-rtp,clock-rate=48000' \
    ! rtpL16depay \
    ! audioconvert \
    ! audioresample \
    ! autoaudiosink \
    &

RECEIVER_PID=$!
sleep 2

echo ""
echo "Starting sender (440Hz tone)..."
echo "You should hear a tone..."
echo ""

# Start sender
gst-launch-1.0 -v \
    audiotestsrc wave=sine freq=440 is-live=true \
    ! audio/x-raw,rate=48000,channels=2,format=S16BE \
    ! rtpL16pay pt=96 \
    ! application/x-rtp,clock-rate=48000 \
    ! udpsink host=localhost port=9001 &

SENDER_PID=$!

# Let it run for 10 seconds
sleep 10

# Cleanup
echo ""
echo "Stopping..."
kill $SENDER_PID $RECEIVER_PID 2>/dev/null
wait 2>/dev/null

echo "Test complete"
