#!/bin/bash
# Bluetooth auto-connect script
# Replace MAC address below with your headphone MAC address

MAC=" B0:38:E2:19:DC:CC"

echo "Waiting for bluetooth service..."
sleep 10

echo "Attempting to connect to headphones: $MAC"
for i in 1 2 3 4 5; do
    bluetoothctl connect $MAC
    sleep 3
    STATUS=$(bluetoothctl info $MAC | grep "Connected: yes")
    if [ -n "$STATUS" ]; then
        echo "Bluetooth connected successfully."
        exit 0
    fi
    echo "Retrying bluetooth connection attempt $i..."
done

echo "Bluetooth connection failed after 5 attempts."
exit 1
