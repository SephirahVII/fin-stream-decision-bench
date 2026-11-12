#!/bin/bash
# Root entrypoint: start the desk daemon, then keep the container alive.
set -u
mkdir -p /run/desk /opt/desk/state /app/evidence /app/.desk /logs/verifier /tests
chmod 700 /opt/desk/state
python3 -B /opt/desk/daemon.py >>/opt/desk/state/daemon.log 2>&1 &
for _ in $(seq 1 100); do
  if [ -S /run/desk/desk.sock ]; then break; fi
  sleep 0.1
done
if [ ! -S /run/desk/desk.sock ]; then
  echo "desk daemon failed to start" >&2
  cat /opt/desk/state/daemon.log >&2 || true
  exit 1
fi
chmod 666 /run/desk/desk.sock || true
exec "$@"
