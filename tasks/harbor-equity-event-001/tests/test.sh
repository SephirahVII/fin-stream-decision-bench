#!/bin/bash
# Shared-mode verifier: evidence is frozen by the desk daemon in /opt/desk/state.
set -u
mkdir -p /logs/verifier
printf '0.0\n' > /logs/verifier/reward.txt
cd /tests || exit 1
python3 grade.py > /logs/verifier/test_stdout.txt 2>&1
exit 0
