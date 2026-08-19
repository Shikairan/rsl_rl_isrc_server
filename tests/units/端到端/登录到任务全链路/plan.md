# T-E2E-01 登录到任务全链路

## 测什么

客户端 login 拿到 NFS 与 token → Server A start 容器 → 调 Server B 跑 torchrun → 拉日志 → stop。

## 依赖什么

- **依赖**：T-NFS-02、T-A-02、T-B-01、T-B-04、T-E-03。
- **不依赖**：G1 DDP（那是 T-E2E-02）。

## 前置条件

Server A 运行中且 nfs.enabled / docker.enabled 按现场打开；镜像含 Server B。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 登录 | `curl -sS -X POST http://10.213.35.42:8000/login -H 'content-type: application/json' -d '{"username":"alice","password":"alice-dev"}'` | 200；nfs_host=10.250.30.115；有 token | PASS；HTTP 200 nfs_host=10.250.30.115 token_len=147 |
| 2 | start 容器 | `curl -sS -X POST http://10.213.35.42:8000/containers/start -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"image":"rsl_rl_isrc:v3-sb","gpu_count":1}'` | 200；container_status=running；返回 server_b_endpoint | PASS；HTTP 200 endpoint=10.213.35.42:31000 body={"server_b_endpoint":"10.213.35.42:31000","obs_pub_endpoint":"10.213.35.42:32000","container_status":"running","container_name":"runner-alice","nfs_mount_path":"/workspace"} |
| 3 | 向 Server B start 任务 | `curl -sS -X POST http://$SERVER_B/tasks/start -H 'content-type: application/json' -d '{"script_path":"jobs/train.py","torchrun_args":["--nproc_per_node","1","--standalone"],"script_args":["--epochs","1"]}'` | 202 running | PASS；HTTP 202 body={"task_id":"t-1","status":"running","started_at":"2026-08-18T11:00:33.561380+00:00"} |
| 4 | logs 与 status | `curl -sS http://$SERVER_B/tasks/$TID/status` | 最终 succeeded | PASS；{'task_id': 't-1', 'status': 'succeeded', 'exit_code': 0, 'started_at': '2026-08-18T11:00:33.561380+00:00', 'finished_at': '2026-08-18T11:00:37.979190+00:00'} |
| 5 | 停容器 | `curl -sS -X POST http://10.213.35.42:8000/containers/stop -H "Authorization: Bearer $TOKEN" ` | {"status":"stopped"} | PASS；HTTP 200 body={"status":"stopped"} |

## 通过标准

全链路一次成功，无需手工 docker run。
