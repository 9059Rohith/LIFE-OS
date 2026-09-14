#!/bin/sh
set -eu

# Railway mounts a new volume as root. Do not change ownership outside the
# application-data mount before continuing as the unprivileged application user.
mkdir -p /app/data
chown -R --no-dereference lifeos:lifeos /app/data

exec setpriv --reuid=10001 --regid=10001 --init-groups sh -ec '
    python -m lifeos.migrate
    exec uvicorn lifeos.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
'
