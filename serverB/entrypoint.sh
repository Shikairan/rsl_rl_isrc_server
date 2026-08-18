#!/bin/bash
set -euo pipefail
export SERVER_B_WORKSPACE_ROOT="${SERVER_B_WORKSPACE_ROOT:-/workspace}"
export SERVER_B_LAUNCHER="${SERVER_B_LAUNCHER:-torchrun}"
export PYTHONPATH="/opt${PYTHONPATH:+:$PYTHONPATH}:/opt/serverB"

export OBS_HTTP_HOST="${OBS_HTTP_HOST:-127.0.0.1}"
export OBS_HTTP_PORT="${OBS_HTTP_PORT:-15558}"
export OBS_HTTP_PATH="${OBS_HTTP_PATH:-/post}"
export OBS_PUB_BIND="${OBS_PUB_BIND:-0.0.0.0}"
export OBS_PUB_PORT="${OBS_PUB_PORT:-15557}"
export RSL_RL_ISRC_OBS_RELAY_URL="${RSL_RL_ISRC_OBS_RELAY_URL:-http://127.0.0.1:15558/post}"
export RSL_RL_ISRC_OBS_RELAY_TIMEOUT="${RSL_RL_ISRC_OBS_RELAY_TIMEOUT:-0.05}"

_obs_loop() {
  while true; do
    python3 -m obsserver || true
    sleep 1
  done
}

if [ "${OBS_ENABLE:-1}" != "0" ]; then
  _obs_loop &
fi

cd /opt/serverB
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080
