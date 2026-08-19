# I-06 容器被杀后重建

## 测什么

客户端经 A 拉起容器后，有人在宿主机上把 `runner-alice` 停掉/删掉。再 `POST /containers/start` 应清理遗留并重建，B `/health` 重新可用。

后台 reconciler（计划里「30s 内注册表标异常遗留」）当前是占位模块；本项验收**客户端可见行为**：`current` 不再当作 running，再次 start 能重建。不要求等 30s 轮询。

## 依赖什么

- **依赖**：I-01 / I-02 的 start、current、stop。
- **不依赖**：训练、bob、多卡。

## 前置条件

A 常驻。执行本项的 shell 能 `sg docker`。

```bash
A=http://10.213.35.42:8000
TOKEN=$(curl -sS -X POST $A/login -H 'content-type: application/json' \
  -d '{"username":"alice","password":"alice-dev"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | start | `curl -sS -X POST $A/containers/start -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"image":"rsl_rl_isrc:v3-B","gpu_count":0}'` | HTTP 200；记下旧 `server_b_endpoint` | PASS；HTTP 200 endpoint=10.213.35.42:31000 body={'server_b_endpoint': '10.213.35.42:31000', 'obs_pub_endpoint': '10.213.35.42:32000', 'container_status': 'running', 'container_name': 'runner-alice', 'nfs_mount_path': '/workspace'} |
| 2 | 外部杀掉容器 | `sg docker -c 'docker rm -f runner-alice'` | 容器消失；`docker ps` 无 `runner-alice` | PASS；退出码 0；docker=无；输出：runner-alice |
| 3 | current | `curl -sS -o /tmp/i06cur.json -w '%{http_code}' -H "Authorization: Bearer $TOKEN" $A/containers/current` | 非 200（无可用 running 容器，例如 404） | PASS；HTTP 404 body={"detail":{"error":"no container"}} |
| 4 | 再 start | 命令同步骤 1 | HTTP 200；`container_name=runner-alice`；`container_status=running`；endpoint 可用（端口可与步骤 1 不同） | PASS；HTTP 200 old=10.213.35.42:31000 new=10.213.35.42:31000 body={'server_b_endpoint': '10.213.35.42:31000', 'obs_pub_endpoint': '10.213.35.42:32000', 'container_status': 'running', 'container_name': 'runner-alice', 'nfs_mount_path': '/workspace'} |
| 5 | 新 endpoint 探活 | `curl -sS http://$NEW_EP/health` | HTTP 200 | PASS；HTTP 200 body={"status":"ok"} |
| 6 | 停干净 | `curl -sS -X POST $A/containers/stop -H "Authorization: Bearer $TOKEN"` | HTTP 200；无 `runner-alice` | PASS；HTTP 200 body={"status":"stopped"} docker=无 |

## 通过标准

外部 `docker rm -f` 之后，再次经 A start 能拉起新的 `v3-B` 并健康检查通过。步骤 2 的 docker 命令是**故障注入**，不是客户端主路径。
