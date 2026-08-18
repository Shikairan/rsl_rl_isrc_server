#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
sg docker -c "docker build -f serverB/Dockerfile.v3-C -t rsl_rl_isrc:v3-C ."
