#!/bin/bash

echo "8BitDo Controller Connection Script"
echo "=================================="

# Controller MAC address
CONTROLLER_MAC="E4:17:D8:37:9F:0A"

# Disconnect other controllers that might interfere
echo "Disconnecting interfering devices..."
bluetoothctl disconnect D0:27:98:AA:2C:9B 2>/dev/null
bluetoothctl disconnect E4:17:D8:37:9F:07 2>/dev/null

# Make sure our controller is trusted
echo "Setting controller as trusted..."
bluetoothctl trust $CONTROLLER_MAC

# Connect to our controller
echo "Connecting to 8BitDo controller..."
bluetoothctl connect $CONTROLLER_MAC

# Check connection status
sleep 2
if bluetoothctl info $CONTROLLER_MAC | grep -q "Connected: yes"; then
    echo "✅ Controller connected successfully!"
    echo "Battery level: $(bluetoothctl info $CONTROLLER_MAC | grep 'Battery Percentage' | cut -d'(' -f2 | cut -d')' -f1)"
else
    echo "❌ Failed to connect controller"
    echo "Try pressing a button on the controller and run this script again"
fi

echo ""
echo "Ready to use with: python3 backshot2.py" 