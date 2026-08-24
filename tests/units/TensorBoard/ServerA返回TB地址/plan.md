# T-TB-03 Server A 返回 tensorboard_endpoint

## 测什么

`POST /containers/start`、`GET /containers/current`、`POST /login` 在容器 running 时返回 `tensorboard_endpoint`（如 `10.213.35.42:33xxx`）；`docker run` 映射 `33xxx→6006`。

## 依赖什么

- **依赖**：T-TB-01；Server A 代码已合入 33xxx 端口池；镜像 `rsl_rl_isrc:v3-D`；alice NFS 已挂。
- **不依赖**：真实 G1 训练。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | start v3-D | `POST /containers/start {"image":"rsl_rl_isrc:v3-D","gpu_count":0}` | 200；含 `tensorboard_endpoint` | PASS；HTTP 200 tb=10.213.35.42:33000 body={"server_b_endpoint":"10.213.35.42:31000","obs_pub_endpoint":"10.213.35.42:32000","tensorboard_endpoint":"10.213.35.42:33000","container_status":"running","container_name":"runner-alice","nfs_mount_path":"/workspace"} |
| 2 | login 也带地址 | `POST /login`（容器已在跑） | 200；与 start 一致 | PASS；HTTP 200 tb=10.213.35.42:33000 |
| 3 | TCP 连通 TB 口 | 连返回的 host:port | 能连通 | PASS；tb=10.213.35.42:33000 tcp=True probe=ok |
| 4 | docker ps 映射 | `docker ps --filter name=runner-alice --format '{{.Ports}}'` | 含 `33xxx->6006/tcp` | PASS；退出码 0；输出：10.213.35.42:33000->6006/tcp, 10.213.35.42:31000->8080/tcp, 10.213.35.42:32000->15557/tcp |
| 5 | current + 再 start | 幂等 | 同一 `tensorboard_endpoint` | PASS；current=10.213.35.42:33000 start2=10.213.35.42:33000 |
| 6 | stop | `POST /containers/stop` | 200 stopped | PASS；HTTP 200 body={"status":"stopped"} |

## 通过标准

A 映射并返回 TensorBoard 地址；不要求页面里已有 scalar。
