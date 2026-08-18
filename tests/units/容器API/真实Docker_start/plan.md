# T-A-10 真实 Docker start（需 Server B /health）

## 测什么

用真实 Docker socket 创建容器并绑定 10.213.35.42:31xxx→8080。本项不测训练，只测健康检查通过。

## 依赖什么

- **依赖**：本机 docker 组；T-A-02；镜像在 8080 提供 GET /health（T-B-01）。当前 rsl_rl_isrc:v3 无 Server B，本项预期会被挡住。
- **不依赖**：GPU、rsl 训练、torchrun 任务。

## 前置条件

用户 `isrc5090` 已在 docker 组（必要时 `newgrp docker`）。

```bash
export SERVER_A_DOCKER_ENABLED=true
export SERVER_A_NFS_ENABLED=false
conda activate serverA
cd /home/isrc5090/149server/serverA
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 登录 | `TOKEN=$(curl -sS -X POST http://127.0.0.1:8000/login -H 'content-type: application/json' -d '{"username":"alice","password":"alice-dev"}' \| python -c 'import sys,json;print(json.load(sys.stdin)["token"])')<br>echo "token_len=${#TOKEN}" ` | TOKEN 非空 | PASS；HTTP 200 token_len=147 |
| 2 | start（镜像须带 :8080 /health；无 Server B 时不要用 v3 指望 200） | `curl -sS -X POST http://127.0.0.1:8000/containers/start -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"image":"<含 Server B 的镜像>","gpu_count":0}'` | HTTP 200；container_name=runner-alice；server_b_endpoint 形如 10.213.35.42:31xxx。若镜像无 /health：HTTP 502 且容器被 rm（符合当前 v3） | PASS；HTTP 200 endpoint=10.213.35.42:31000 body={"server_b_endpoint":"10.213.35.42:31000","container_status":"running","container_name":"runner-alice","nfs_mount_path":"/workspace"} |
| 3 | 对返回端口做健康检查 | `curl -sS http://10.213.35.42:<host_port>/health` | 200 {"status":"ok"}（仅当上一步 200） | PASS；HTTP 200 body={"status":"ok"} |
| 4 | current 与 stop | `curl -sS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/containers/current<br>curl -sS -X POST -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/containers/stop` | current 与 start 结构一致；stop 返回 {"status":"stopped"}；docker ps 无 runner-alice | PASS；current HTTP 200 {"server_b_endpoint":"10.213.35.42:31000","container_status":"running","container_name":"runner-alice","nfs_mount_path":"/workspace"}；stop HTTP 200 {"status":"stopped"}；docker=无 runner-alice |

## 通过标准

真实容器能起、健康检查过、能停干净。在 T-B-01 完成前本项可不判失败（502 为契约未满足）。

## 备注

阻塞项：Server B 尚未打入镜像。
