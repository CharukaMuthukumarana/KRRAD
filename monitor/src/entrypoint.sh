#!/bin/bash
set -e

echo "🔧 KRRAD eBPF Setup: Linking Kernel Headers..."

# 1. Get the Host's Kernel Version (e.g., 6.8.0-64-generic)
CURRENT_KERNEL=$(uname -r)
echo "   Host Kernel: $CURRENT_KERNEL"

# 2. Find the Headers we INSTALLED in the container (e.g., 6.8.0-31-generic)
# We look for the directory in /usr/src
INSTALLED_HEADERS=$(find /usr/src -maxdepth 1 -name "linux-headers-*-generic" -type d | head -n 1)

if [ -z "$INSTALLED_HEADERS" ]; then
    echo "❌ Error: No linux-headers found in /usr/src. Did the Docker build fail?"
    ls -l /usr/src
    exit 1
fi

echo "   Found Headers: $INSTALLED_HEADERS"

# 3. Create the Symlink trick
# BCC looks in /lib/modules/<CURRENT_KERNEL>/build
mkdir -p /lib/modules/$CURRENT_KERNEL
rm -f /lib/modules/$CURRENT_KERNEL/build
ln -s $INSTALLED_HEADERS /lib/modules/$CURRENT_KERNEL/build

echo "✅ Symlink created: /lib/modules/$CURRENT_KERNEL/build -> $INSTALLED_HEADERS"
echo "🚀 Starting Sensor..."

# 4. Run the original Python script
exec python3 src/loader.py