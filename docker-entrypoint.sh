#!/bin/bash
# Ensure uploads directory is writable by the container user.
# Bind mounts inherit host permissions which may not match the container user.
chmod 777 /app/uploads 2>/dev/null || true
exec "$@"
