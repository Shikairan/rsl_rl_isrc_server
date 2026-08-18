#!/usr/bin/env bash
# 用官方 local/torchrun:0.01 挂载 alice NFS，执行 /workspace/jobs/train.py
set -euo pipefail
IMAGE="${IMAGE:-local/torchrun:0.01}"
NAME="${NAME:-runner-alice-nfs}"
HOST_WS="${HOST_WS:-/mnt/nfs/alice}"

exec docker run --rm \
  --name "$NAME" \
  -v "${HOST_WS}:/workspace" \
  --gpus 1 \
  --cpus 4 \
  --memory 8g \
  "$IMAGE" \
  torchrun --nproc_per_node=1 --standalone /workspace/jobs/train.py --epochs 3
