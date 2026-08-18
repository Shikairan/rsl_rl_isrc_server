# T-B-04 start / status / logs / stop

## 测什么

用 NFS jobs/train.py 走完启停与日志轮询；stop 后进程组退出。

## 依赖什么

- **依赖**：T-B-01、T-D-01、T-E-02 同类脚本。
- **不依赖**：Server A。

## 前置条件

容器挂载 /mnt/nfs/alice:/workspace，镜像含 torchrun。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | start | `curl -sS -X POST http://127.0.0.1:18080/tasks/start -H 'content-type: application/json' -d '{"script_path":"jobs/train.py","torchrun_args":["--nproc_per_node","1","--standalone"],"script_args":["--epochs","1"]}'` | 202；task_id；status=running | PASS；HTTP 202 body={"task_id":"t-1","status":"running","started_at":"2026-08-18T02:33:06.724296+00:00"} |
| 2 | status 轮询直到结束 | `curl -sS http://127.0.0.1:18080/tasks/<task_id>/status` | 最终 succeeded 或 failed/stopped；含 exit_code | PASS；HTTP 轮询结果 {'task_id': 't-1', 'status': 'succeeded', 'exit_code': 0, 'started_at': '2026-08-18T02:33:06.724296+00:00', 'finished_at': '2026-08-18T02:33:11.499279+00:00'} |
| 3 | 任务运行中拉日志 | `curl -sS 'http://127.0.0.1:18080/tasks/<task_id>/logs?since=0'` | 运行中返回 lines 与 next_offset；结束后再查应为 404（方案：任务结束释放日志） | PASS；运行中拿到日志=True body={"next_offset":130,"lines":["rank=0 local_rank=0 device=cuda:0 torch=2.11.0+cu128 cuda=True nproc=1","epoch=1/1 loss=0.822198","wrote /workspace/jobs/last_run.txt"]} |
| 4 | 若仍 running 则 stop | `curl -sS -X POST http://127.0.0.1:18080/tasks/<task_id>/stop` | status=stopped；容器内无残留 torchrun 进程组 | PASS；HTTP 404 body={"detail":{"error":"logs released"}} |

## 通过标准

四个接口行为符合 IMPLEMENTATION_PLAN 5.1。
