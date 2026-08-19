# T-B-03 单任务锁

## 测什么

同一容器已有 running 任务时再 start 返回 409。

## 依赖什么

- **依赖**：T-B-01；NFS 上有可跑脚本（可用 sleep 脚本）。
- **不依赖**：多卡。

## 前置条件

容器 -v NFS:/workspace。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 启动一个较长任务 | `curl -sS -X POST http://127.0.0.1:18080/tasks/start -H 'content-type: application/json' -d '{"script_path":"jobs/train.py","torchrun_args":["--nproc_per_node","1","--standalone"],"script_args":["--epochs","999"]}'` | 202，status=running，返回 task_id | PASS；HTTP 202 body={"task_id":"t-1","status":"running","started_at":"2026-08-18T11:00:20.742306+00:00"} |
| 2 | 立即再 start | `curl -sS -o /tmp/b03.json -w '%{http_code}' -X POST http://127.0.0.1:18080/tasks/start -H 'content-type: application/json' -d '{"script_path":"jobs/train.py","torchrun_args":["--standalone"],"script_args":[]}'` | HTTP 409 | PASS；HTTP 409 body={"detail":{"error":"a task is already running"}} |
| 3 | 停止任务 | `curl -sS -X POST http://127.0.0.1:18080/tasks/<task_id>/stop` | 幂等成功，status=stopped | PASS；HTTP 200 body={"status":"stopped"} |

## 通过标准

并发第二任务 409。
