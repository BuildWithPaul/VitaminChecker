#!/bin/sh
set -e

# Ensure uploads directory exists and is writable.
# Volume mounts may replace /app/uploads with a host dir owned by root.
# This script runs as root before dropping privileges.
mkdir -p /app/uploads
chown -R appuser:appuser /app/uploads 2>/dev/null || true

# Drop to appuser and exec the CMD
exec su -s /bin/sh appuser -c "exec $*"