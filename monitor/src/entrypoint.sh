#!/bin/bash
set -e

echo "🔧 KRRAD eBPF Setup: Linking Kernel Headers..."

CURRENT_KERNEL=$(uname -r)
echo "   Host Kernel: $CURRENT_KERNEL"

INSTALLED_HEADERS=$(find /usr/src -maxdepth 1 -name "linux-headers-*-generic" -type d | head -n 1)

if [ -z "$INSTALLED_HEADERS" ]; then
    echo "❌ Error: No linux-headers found in /usr/src. Did the Docker build fail?"
    ls -l /usr/src
    exit 1
fi

echo "   Found Headers: $INSTALLED_HEADERS"


mkdir -p /lib/modules/$CURRENT_KERNEL
rm -f /lib/modules/$CURRENT_KERNEL/build
ln -s $INSTALLED_HEADERS /lib/modules/$CURRENT_KERNEL/build

echo "Symlink created: /lib/modules/$CURRENT_KERNEL/build -> $INSTALLED_HEADERS"
echo "Starting Sensor..."

exec python3 src/loader.py