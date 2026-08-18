#!/usr/bin/env bash
# 在 115 本机执行（备用）。日常请在开发机: python nfsctl.py apply
set -euo pipefail
ROOT="/mnt/dockerContainer/nfs"
USERS=(alice bob carol dave eve frank)
sudo mkdir -p "$ROOT"
for u in "${USERS[@]}"; do
  sudo mkdir -p "$ROOT/$u"
done
sudo chmod 0777 "$ROOT"
for u in "${USERS[@]}"; do
  sudo chmod 0777 "$ROOT/$u"
done
sudo tee /etc/exports >/dev/null << 'EOF'
# 149server nfsserver
/mnt/dockerContainer/nfs       10.0.0.0/8(rw,sync,no_subtree_check,no_root_squash)
/mnt/dockerContainer/nfs/alice 10.0.0.0/8(rw,sync,no_subtree_check,no_root_squash)
/mnt/dockerContainer/nfs/bob   10.0.0.0/8(rw,sync,no_subtree_check,no_root_squash)
/mnt/dockerContainer/nfs/carol 10.0.0.0/8(rw,sync,no_subtree_check,no_root_squash)
/mnt/dockerContainer/nfs/dave  10.0.0.0/8(rw,sync,no_subtree_check,no_root_squash)
/mnt/dockerContainer/nfs/eve   10.0.0.0/8(rw,sync,no_subtree_check,no_root_squash)
/mnt/dockerContainer/nfs/frank 10.0.0.0/8(rw,sync,no_subtree_check,no_root_squash)
EOF
sudo exportfs -ra
sudo systemctl enable --now nfs-server
sudo exportfs -v
