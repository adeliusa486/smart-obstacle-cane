#!/bin/bash

echo "=== Smart Cane Starting ===" 

# Kill everything that could hold the camera
sudo pkill -9 -f python3 2>/dev/null
sudo pkill -9 -f libcamera 2>/dev/null
sudo pkill -9 -f rpicam 2>/dev/null
sudo fuser -k /dev/video0 2>/dev/null
sudo fuser -k /dev/video1 2>/dev/null
sudo fuser -k /dev/video2 2>/dev/null

sleep 3

# Connect bluetooth
if [ -f /home/pi/bt_connect.sh ]; then
    bash /home/pi/bt_connect.sh
fi

sleep 2

# Start main script
exec python3 /home/pi/ai_test_picamera2.py
