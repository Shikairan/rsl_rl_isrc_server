# T-OBS-07 Server A 返回 obs_pub_endpoint（预留）

## 测什么

Server A 实现 obsserver PLAN §5 后：`POST /containers/start`、`GET /containers/current`、`POST /login` 在容器 running 时返回 `obs_pub_endpoint`（如 `10.213.35.42:32xxx`）；`docker run` 映射 `32xxx→15557`；就绪检查含画面口 TCP。

## 依赖什么

- **依赖**：T-OBS-03、T-A-10；Server A 代码已合入端口池与字段；镜像 `rsl_rl_isrc:v3-C`。
- **不依赖**：client 真 SUB、训练。

## 前置条件

Server A 常驻；`docker.enabled=true`；alice token。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | start 指定 v3-C | `curl -sS -X POST http://10.213.35.42:8000/containers/start -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"image":"rsl_rl_isrc:v3-C","gpu_count":0}'` | 200；含 `obs_pub_endpoint` 与 `server_b_endpoint` | PASS；HTTP 200 server_b=10.213.35.42:31000 obs_pub=10.213.35.42:32000 body={"server_b_endpoint":"10.213.35.42:31000","obs_pub_endpoint":"10.213.35.42:32000","container_status":"running","container_name":"runner-alice","nfs_mount_path":"/workspace"} |
| 2 | login 也带地址 | `curl -sS -X POST .../login ...`（容器已在跑） | 200；`obs_pub_endpoint` 与 start 一致 | PASS；HTTP 200 server_b=10.213.35.42:31000 obs_pub=10.213.35.42:32000 body={"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbGljZSIsImV4cCI6MTc4NzEzNzIxNiwiaWF0IjoxNzg3MDUwODE2fQ.tF6eqH2SuVyK4zs6NFvEjPvwOvOoA3rrgl6kgFdH770","expires_at":"2026-08-19T11:00:16.043143Z","nfs_host":"10.250.30.115","nfs_export_path":"/mnt/dockerContainer/nfs/alice","server_b_endpoint":"10.213.35.42:31000","obs_pub_endpoint":"10.213.35.42:32000"} |
| 3 | 宿主机 TCP 画面口 | `python3 -c "import socket;..."` 连返回的 host:port | 能连通 | PASS；obs_pub=10.213.35.42:32000 tcp_ready=True probe=ok |
| 4 | docker ps 映射 | `sg docker -c 'docker ps --filter name=runner-alice --format "{{.Ports}}"'` | 含 `32xxx->15557/tcp` | PASS；退出码 0；输出：10.213.35.42:31000->8080/tcp, 10.213.35.42:32000->15557/tcp |
| 5 | 幂等不偷偷重建 | 连续两次 start | 同一 `obs_pub_endpoint`；**不**因缺字段自动 rm 容器 | PASS；current HTTP 200 obs_pub=10.213.35.42:32000 start2 HTTP 200 obs_pub=10.213.35.42:32000 same_name=True |
| 6 | stop 释放 | `POST /containers/stop` | 200；端口释放 | PASS；HTTP 200 body={"status":"stopped"} |

## 通过标准

A 只负责**映射与返回地址**；不转发位姿。本项 **TODO**，等 Server A 改完再跑。

## 明确不做（本轮单元）

- 不测 alice/bob 画面串流（留给 integration）。
- A **不**替用户 stop 再 start 升级老容器（见 PLAN：用户自己关重建）。
