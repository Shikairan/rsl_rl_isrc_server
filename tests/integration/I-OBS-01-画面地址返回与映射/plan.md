# I-OBS-01 画面地址返回与映射

## 测什么

经 `POST /containers/start` 拉起 `rsl_rl_isrc:v3-C` 后，Server A 返回 `obs_pub_endpoint`，`GET /containers/current` 与 `POST /login` 返回同一地址；宿主机 `docker ps` 可见 `32xxx->15557/tcp`，且 `obs_pub_endpoint` 可 TCP 连通。

这是 obs 联调的最小入口：**先有地址，再谈有没有画面**。

## 依赖什么

- **依赖**：单元 `T-OBS-07` 已绿；Server A 已支持 `obs_pub_endpoint`；镜像 `rsl_rl_isrc:v3-C` 已构建。
- **不依赖**：训练出帧、client 真订阅、GPU。

## 前置条件

```bash
A=http://10.213.35.42:8000
TOKEN=$(curl -sS -X POST $A/login -H 'content-type: application/json' \
  -d '{"username":"alice","password":"alice-dev"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | start 指定 `v3-C` | `curl -sS -X POST $A/containers/start -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"image":"rsl_rl_isrc:v3-C","gpu_count":0}'` | HTTP 200；返回 `server_b_endpoint` 与 `obs_pub_endpoint`（形如 `10.213.35.42:32xxx`） | PASS；HTTP 200 body={"server_b_endpoint": "10.213.35.42:31000", "obs_pub_endpoint": "10.213.35.42:32000", "container_status": "running", "container_name": "runner-alice", "nfs_mount_path": "/workspace"} |
| 2 | current 返回同一地址 | `curl -sS $A/containers/current -H "Authorization: Bearer $TOKEN"` | HTTP 200；`obs_pub_endpoint` 与步骤 1 一致 | PASS；HTTP 200 body={"server_b_endpoint":"10.213.35.42:31000","obs_pub_endpoint":"10.213.35.42:32000","container_status":"running","container_name":"runner-alice","nfs_mount_path":"/workspace"} |
| 3 | login 也带地址 | `curl -sS -X POST $A/login -H 'content-type: application/json' -d '{"username":"alice","password":"alice-dev"}'` | HTTP 200；`obs_pub_endpoint` 与步骤 1 一致 | PASS；HTTP 200 body={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbGljZSIsImV4cCI6MTc4NzEzNzI3OSwiaWF0IjoxNzg3MDUwODc5fQ.x-6N20XtElvfTqUKlRvpQQ4tW2jiX89T8qu5iJFjIqA", "expires_at": "2026-08-19T11:01:19.859962Z", "nfs_host": "10.250.30.115", "nfs_export_path": "/mnt/dockerContainer/nfs/alice", "server_b_endpoint": "10.213.35.42:31000", "obs_pub_endpoint": "10.213.35.42:32000"} |
| 4 | 检查 docker 端口映射 | `sg docker -c 'docker ps --filter name=runner-alice --format "{{.Ports}}"'` | 含 `32xxx->15557/tcp` 与 `31xxx->8080/tcp` | PASS；退出码 0；输出：10.213.35.42:31000->8080/tcp, 10.213.35.42:32000->15557/tcp |
| 5 | 宿主机 TCP 连画面口 | `python3 -c "import socket;s=socket.create_connection(('10.213.35.42',32xxx),2);s.close();print('ok')"` | 打印 `ok` | PASS；退出码 0；输出：ok |
| 6 | stop 清理 | `curl -sS -X POST $A/containers/stop -H "Authorization: Bearer $TOKEN"` | HTTP 200；容器删除 | PASS；HTTP 200 body={"status":"stopped"} |

## 通过标准

客户端经 A 拿到的 `obs_pub_endpoint` 可复用在 `start/current/login`，且宿主机端口映射真实存在。
