#!/usr/bin/env bash
set -u
ROOT=/home/isrc5090/149server/tests/integration
fail=0
run() {
  local id="$1"
  local dir="$2"
  echo "===== $id $dir ====="
  python3 "$ROOT/$dir/run.py" || fail=1
}
run I-01 I-01-alice主链路
run I-02 I-02-start幂等与current
run I-03 I-03-单任务锁
run I-OBS-01 I-OBS-01-画面地址返回与映射
run I-OBS-02 I-OBS-02-先连画面后开训出首帧
run I-OBS-03 I-OBS-03-同容器重复开训地址不变
run I-05 I-05-路径守卫
run I-06 I-06-容器被杀后重建
run I-04 I-04-bob隔离
run I-OBS-04 I-OBS-04-alice与bob画面隔离
run I-07 I-07-同容器双卡DDP
run I-08 I-08-指定GPU4到7的4卡DDP全链路
exit "$fail"
