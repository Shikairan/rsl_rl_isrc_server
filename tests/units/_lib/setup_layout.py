#!/usr/bin/env python3
"""Rename case dirs to Chinese names and emit per-case run.py / run.sh."""

from __future__ import annotations

import shutil
from pathlib import Path

TESTS = Path("/home/isrc5090/149server/tests")

# old_rel, case_id, new_rel, title
LAYOUT = [
    ("A-nfs/T-NFS-01", "T-NFS-01", "NFS/导出列表可见", "导出列表可见"),
    ("A-nfs/T-NFS-02", "T-NFS-02", "NFS/alice读写回115", "alice 读写回 115"),
    ("A-nfs/T-NFS-03", "T-NFS-03", "NFS/bob独立挂载与隔离", "bob 独立挂载与隔离"),
    ("A-nfs/T-NFS-04", "T-NFS-04", "NFS/卸载后重挂alice", "卸载后重挂 alice"),
    ("A-nfs/T-NFS-05", "T-NFS-05", "NFS/nfs-server重启后导出仍在", "nfs-server 重启后导出仍在"),
    ("B-auth/T-A-01", "T-A-01", "ServerA认证/健康检查", "健康检查"),
    ("B-auth/T-A-02", "T-A-02", "ServerA认证/登录成功", "登录成功"),
    ("B-auth/T-A-03", "T-A-03", "ServerA认证/登录失败", "登录失败"),
    ("B-auth/T-A-04", "T-A-04", "ServerA认证/无Token拒绝容器接口", "无 Token 拒绝容器接口"),
    ("B-auth/T-A-05", "T-A-05", "ServerA认证/docker关闭时容器接口503", "docker 关闭时容器接口 503"),
    ("C-containers/T-A-06", "T-A-06", "容器API/start成功_mock", "start 成功（mock Docker）"),
    ("C-containers/T-A-07", "T-A-07", "容器API/start幂等_mock", "start 幂等（mock）"),
    ("C-containers/T-A-08", "T-A-08", "容器API/健康检查失败回收_mock", "健康检查失败回收（mock）"),
    ("C-containers/T-A-09", "T-A-09", "容器API/current与stop_mock", "current 与 stop（mock）"),
    ("C-containers/T-A-10", "T-A-10", "容器API/真实Docker_start", "真实 Docker start"),
    ("D-docker-nfs/T-D-01", "T-D-01", "Docker绑定NFS/容器看见NFS文件", "容器看见 NFS 文件"),
    ("D-docker-nfs/T-D-02", "T-D-02", "Docker绑定NFS/容器写回NFS", "容器写回 NFS"),
    ("D-docker-nfs/T-D-03", "T-D-03", "Docker绑定NFS/容器挂载用户隔离", "容器挂载用户隔离"),
    ("E-torchrun/T-E-01", "T-E-01", "torchrun与CUDA/旧镜像CPU_torchrun调度冒烟", "旧镜像 CPU torchrun 调度冒烟"),
    ("E-torchrun/T-E-02", "T-E-02", "torchrun与CUDA/官方GPU_torchrun", "官方 GPU torchrun"),
    ("E-torchrun/T-E-03", "T-E-03", "torchrun与CUDA/自定义镜像仍能GPU_torchrun", "自定义镜像仍能 GPU torchrun"),
    ("F-rsl/T-F-01", "T-F-01", "rsl_rl_isrc算法/镜像内包可import", "镜像内包可 import"),
    ("F-rsl/T-F-02", "T-F-02", "rsl_rl_isrc算法/G1_MuJoCo_PPO_DDP双卡smoke", "G1 MuJoCo PPO DDP 双卡 smoke"),
    ("F-rsl/T-F-03", "T-F-03", "rsl_rl_isrc算法/DDP扩到4卡", "DDP 扩到 4 卡"),
    ("F-rsl/T-F-04", "T-F-04", "rsl_rl_isrc算法/ZMQ观测通道", "ZMQ 观测通道"),
    ("I-obs/T-OBS-01", "T-OBS-01", "观测转发/pytest转发冒烟", "obsserver pytest 转发冒烟"),
    ("I-obs/T-OBS-02", "T-OBS-02", "观测转发/v3-C镜像含obsserver", "v3-C 镜像含 obsserver"),
    ("I-obs/T-OBS-03", "T-OBS-03", "观测转发/容器入口与B并存", "容器入口：转发与 B 并存"),
    ("I-obs/T-OBS-04", "T-OBS-04", "观测转发/POST中继到画面PUB", "POST 中继 → 画面 PUB"),
    ("I-obs/T-OBS-05", "T-OBS-05", "观测转发/中继环境变量", "中继环境变量"),
    ("I-obs/T-OBS-06", "T-OBS-06", "观测转发/训练开ZMQ经中继出画面", "训练开 ZMQ 经中继出画面（可选）"),
    ("I-obs/T-OBS-07", "T-OBS-07", "观测转发/ServerA返回画面地址", "Server A 返回 obs_pub_endpoint"),
    ("J-tb/T-TB-01", "T-TB-01", "TensorBoard/v3-D镜像含tensorboard", "v3-D 镜像含 tensorboard"),
    ("J-tb/T-TB-02", "T-TB-02", "TensorBoard/手工映射6006可打开", "手工映射 6006 可打开"),
    ("J-tb/T-TB-03", "T-TB-03", "TensorBoard/ServerA返回TB地址", "Server A 返回 tensorboard_endpoint"),
    ("J-tb/T-TB-04", "T-TB-04", "TensorBoard/训练事件后TB可见", "训练写 event 后 TB 可见"),
    ("J-tb/T-TB-05", "T-TB-05", "TensorBoard/alice与bob隔离", "alice 与 bob TensorBoard 隔离"),
    ("J-tb/T-TB-06", "T-TB-06", "TensorBoard/stop释放端口", "stop 释放 TensorBoard 端口"),
    ("G-server-b/T-B-01", "T-B-01", "ServerB/健康检查", "Server B 健康检查"),
    ("G-server-b/T-B-02", "T-B-02", "ServerB/路径守卫", "路径守卫"),
    ("G-server-b/T-B-03", "T-B-03", "ServerB/单任务锁", "单任务锁"),
    ("G-server-b/T-B-04", "T-B-04", "ServerB/start_status_logs_stop", "start / status / logs / stop"),
    ("G-server-b/T-B-05", "T-B-05", "ServerB/打入训练镜像后健康检查", "打入训练镜像后健康检查"),
    ("H-e2e/T-E2E-01", "T-E2E-01", "端到端/登录到任务全链路", "登录到任务全链路"),
    ("H-e2e/T-E2E-02", "T-E2E-02", "端到端/同一容器跑G1_DDP", "同一容器跑 G1 DDP"),
]

RUN_PY = """#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
from cases import execute

if __name__ == "__main__":
    raise SystemExit(execute({cid!r}, Path(__file__).resolve().parent))
"""

RUN_SH = """#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec python3 ./run.py
"""


def main() -> None:
    for old_rel, cid, new_rel, _title in LAYOUT:
        src = TESTS / old_rel
        dst = TESTS / new_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists() and src.resolve() != dst.resolve():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.move(str(src), str(dst))
        dst.mkdir(parents=True, exist_ok=True)
        (dst / "run.py").write_text(RUN_PY.format(cid=cid), encoding="utf-8")
        (dst / "run.sh").write_text(RUN_SH, encoding="utf-8")
        (dst / "run.py").chmod(0o755)
        (dst / "run.sh").chmod(0o755)
        print(f"{cid} -> {new_rel}")

    # drop emptied english category dirs
    for name in [
        "A-nfs",
        "B-auth",
        "C-containers",
        "D-docker-nfs",
        "E-torchrun",
        "F-rsl",
        "I-obs",
        "G-server-b",
        "H-e2e",
    ]:
        p = TESTS / name
        if p.is_dir() and not any(p.iterdir()):
            p.rmdir()

    rows = ["| 编号 | 标题 | 目录 | 脚本 |", "|------|------|------|------|"]
    for _old, cid, new_rel, title in LAYOUT:
        rows.append(
            f"| [{cid}]({new_rel}/plan.md) | {title} | `{new_rel}/` | [`run.sh`]({new_rel}/run.sh) |"
        )
    readme = f"""# 独立测试用例索引

一项一目录（中文名），目录内：

- `plan.md`：测什么 / 依赖 / 步骤表（含真实结果列）
- `run.sh` / `run.py`：按步骤执行并把真实结果写回 `plan.md`
- `result.log` / `result.json`：最近一次执行的完整记录

现场：NFS `10.250.30.115`，Server A `10.213.35.42`。

总方案：[TEST_PLAN.md](TEST_PLAN.md)

{chr(10).join(rows)}

## 目录分组

- `NFS/`
- `ServerA认证/`
- `容器API/`
- `Docker绑定NFS/`
- `torchrun与CUDA/`
- `rsl_rl_isrc算法/`
- `观测转发/`
- `ServerB/`
- `端到端/`

全部执行：`bash /home/isrc5090/149server/tests/run_all.sh`
"""
    (TESTS / "README.md").write_text(readme, encoding="utf-8")

    all_sh = ["#!/usr/bin/env bash", "set -u", "ROOT=/home/isrc5090/149server/tests", "fail=0"]
    for _old, cid, new_rel, _title in LAYOUT:
        all_sh.append(f'echo "===== {cid} {new_rel} ====="')
        all_sh.append(f'python3 "$ROOT/{new_rel}/run.py" || fail=1')
    all_sh.append('exit "$fail"')
    (TESTS / "run_all.sh").write_text("\n".join(all_sh) + "\n", encoding="utf-8")
    (TESTS / "run_all.sh").chmod(0o755)

    plan = TESTS / "TEST_PLAN.md"
    text = plan.read_text(encoding="utf-8")
    for old_rel, _cid, new_rel, _title in LAYOUT:
        text = text.replace(f"{old_rel}/plan.md", f"{new_rel}/plan.md")
    plan.write_text(text, encoding="utf-8")
    print("layout done")


if __name__ == "__main__":
    main()
