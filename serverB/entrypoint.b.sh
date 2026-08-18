#!/bin/bash
set -euo pipefail
export SERVER_B_WORKSPACE_ROOT="${SERVER_B_WORKSPACE_ROOT:-/workspace}"
export SERVER_B_LAUNCHER="${SERVER_B_LAUNCHER:-torchrun}"
export PYTHONPATH="/opt/serverB${PYTHONPATH:+:$PYTHONPATH}"
cd /opt/serverB
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080
