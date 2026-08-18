# I-02 start 幂等与 current

## 测什么

同一用户容器已在跑时再次 `POST /containers/start` 不新建；`GET /containers/current` 与 start 返回一致。

## 依赖什么

- **依赖**：I-01 步骤 1–5 能过（A 常驻、alice 能 start `v3-B`）。
- **不依赖**：训练任务、bob、多卡。

## 前置条件

Server A 常驻。开始前无 `runner-alice`，或先 stop 干净。

```bash
A=http://10.213.35.42:8000
TOKEN=$(curl -sS -X POST $A/login -H 'content-type: application/json' \
  -d '{"username":"alice","password":"alice-dev"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 第一次 start | `curl -sS -X POST $A/containers/start -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"image":"rsl_rl_isrc:v3-B","gpu_count":1}'` | HTTP 200；记下 `server_b_endpoint` 与 `container_name` | PASS；HTTP 200 endpoint=10.213.35.42:31000 body={'server_b_endpoint': '10.213.35.42:31000', 'container_status': 'running', 'container_name': 'runner-alice', 'nfs_mount_path': '/workspace'} |
| 2 | 立即再 start | 命令同步骤 1 | HTTP 200；`server_b_endpoint` 与步骤 1 **相同**；`container_name` 仍为 `runner-alice` | PASS；HTTP 200 ep1=10.213.35.42:31000 ep2=10.213.35.42:31000 body={'server_b_endpoint': '10.213.35.42:31000', 'container_status': 'running', 'container_name': 'runner-alice', 'nfs_mount_path': '/workspace'} |
| 3 | current | `curl -sS -H "Authorization: Bearer $TOKEN" $A/containers/current` | HTTP 200；字段与步骤 1/2 一致；`container_status=running` | PASS；HTTP 200 body={"server_b_endpoint":"10.213.35.42:31000","container_status":"running","container_name":"runner-alice","nfs_mount_path":"/workspace"} |
| 4 | 映射端口仍活 | `curl -sS http://$SERVER_B/health` | HTTP 200 | PASS；HTTP 200 body={"status":"ok"} |
| 5 | 停干净 | `curl -sS -X POST $A/containers/stop -H "Authorization: Bearer $TOKEN"` | HTTP 200；`{"status":"stopped"}` | PASS；HTTP 200 body={"status":"stopped"} |
| 6 | stop 后再 start | 命令同步骤 1 | HTTP 200；可分配新的 `31xxx`；B `/health` 仍 200 | PASS；HTTP 200 endpoint=10.213.35.42:31000 health=200 {"status":"ok"} |
| 7 | 收尾 stop | `curl -sS -X POST $A/containers/stop -H "Authorization: Bearer $TOKEN"` | HTTP 200；`docker ps` 无 `runner-alice` | PASS；HTTP 200 body={"status":"stopped"}；docker=无 |

## 通过标准

重复 start 不新建第二只容器；current 与 start 对齐；stop 后再 start 能重建。
