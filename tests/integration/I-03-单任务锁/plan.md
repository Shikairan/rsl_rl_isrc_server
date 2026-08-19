# I-03 单任务锁

## 测什么

经 Server A 拉起的容器上，Server B 已有 running 任务时再 `POST /tasks/start` 返回 409；`POST /tasks/{id}/stop` 后可再开新任务。

## 依赖什么

- **依赖**：I-01 能 start 容器并打通 B；NFS 上 `jobs/train.py` 能跑较长轮次（`--epochs 999` 或等价）。
- **不依赖**：双卡、bob。

## 前置条件

A 常驻。先 start `runner-alice`（`rsl_rl_isrc:v3-B`，`gpu_count:1`），记下 `$SERVER_B`。

```bash
A=http://10.213.35.42:8000
TOKEN=$(curl -sS -X POST $A/login -H 'content-type: application/json' \
  -d '{"username":"alice","password":"alice-dev"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
EP=$(curl -sS -X POST $A/containers/start -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"image":"rsl_rl_isrc:v3-B","gpu_count":1}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["server_b_endpoint"])')
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 启动较长任务 | `curl -sS -X POST http://$EP/tasks/start -H 'content-type: application/json' -d '{"script_path":"jobs/train.py","torchrun_args":["--nproc_per_node","1","--standalone"],"script_args":["--epochs","999"]}'` | HTTP 202；`status=running`；记下 `task_id` | PASS；HTTP 202 body={'task_id': 't-1', 'status': 'running', 'started_at': '2026-08-18T11:01:10.835758+00:00'} |
| 2 | 立即再 start | `curl -sS -o /tmp/i03.json -w '%{http_code}' -X POST http://$EP/tasks/start -H 'content-type: application/json' -d '{"script_path":"jobs/train.py","torchrun_args":["--standalone"],"script_args":[]}'` | HTTP 409；body 含 `a task is already running` | PASS；HTTP 409 body={"detail":{"error":"a task is already running"}} |
| 3 | 停任务 | `curl -sS -X POST http://$EP/tasks/$TID/stop` | HTTP 200；`status=stopped` | PASS；HTTP 200 body={"status":"stopped"} |
| 4 | 再开短训 | `curl -sS -X POST http://$EP/tasks/start -H 'content-type: application/json' -d '{"script_path":"jobs/train.py","torchrun_args":["--nproc_per_node","1","--standalone"],"script_args":["--epochs","3"]}'` | HTTP 202；新 `task_id`；随后 status 可达 `succeeded` | PASS；HTTP 202 start={'task_id': 't-2', 'status': 'running', 'started_at': '2026-08-18T11:01:11.399579+00:00'} status={'task_id': 't-2', 'status': 'succeeded', 'exit_code': 0, 'started_at': '2026-08-18T11:01:11.399579+00:00', 'finished_at': '2026-08-18T11:01:15.506428+00:00'} |
| 5 | 停容器 | `curl -sS -X POST $A/containers/stop -H "Authorization: Bearer $TOKEN"` | HTTP 200；`{"status":"stopped"}` | PASS；HTTP 200 body={"status":"stopped"} |

## 通过标准

第二任务 409；停任务后可以再 start；不手工 `docker run`。
