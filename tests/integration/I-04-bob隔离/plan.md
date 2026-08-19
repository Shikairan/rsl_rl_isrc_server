# I-04 bob 隔离

## 测什么

alice / bob 各自 login、各自 `containers/start`。alice 的 runner 只 bind alice NFS；bob 的 runner 只 bind bob NFS。两边文件互不可见。

## 依赖什么

- **依赖**：单元 T-NFS-03（本机可挂 `/mnt/nfs/bob`）；I-01 主链路对 alice 已通。
- **不依赖**：训练、多卡。

## 前置条件

- A 常驻；`users.yaml` 有 bob。
- 本机 `/mnt/nfs/alice`、`/mnt/nfs/bob` 均已挂 115 对应导出。
- 开始前无 `runner-alice`、`runner-bob`。

```bash
A=http://10.213.35.42:8000
TA=$(curl -sS -X POST $A/login -H 'content-type: application/json' \
  -d '{"username":"alice","password":"alice-dev"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
TB=$(curl -sS -X POST $A/login -H 'content-type: application/json' \
  -d '{"username":"bob","password":"bob-dev"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 两边写标记 | `echo alice-only \| sudo tee /mnt/nfs/alice/alice_only.txt`；`echo bob-only \| sudo tee /mnt/nfs/bob/bob_only.txt` | 本机两边文件存在；alice 目录 `ls` 无 `bob_only.txt` | PASS；alice ls=alice_only.txt jobs logs mount_test.txt rsl_rl_isrc wheels；bob ls=bob_only.txt jobs logs |
| 2 | alice start | `curl -sS -X POST $A/containers/start -H "Authorization: Bearer $TA" -H 'content-type: application/json' -d '{"image":"rsl_rl_isrc:v3-B","gpu_count":0}'` | HTTP 200；`container_name=runner-alice`；记下 endpoint | PASS；HTTP 200 endpoint=10.213.35.42:31000 body={'server_b_endpoint': '10.213.35.42:31000', 'obs_pub_endpoint': '10.213.35.42:32000', 'container_status': 'running', 'container_name': 'runner-alice', 'nfs_mount_path': '/workspace'} |
| 3 | bob start | 同上，token 换 `$TB` | HTTP 200；`container_name=runner-bob`；endpoint 与 alice **不同端口** | PASS；HTTP 200 endpoint=10.213.35.42:31001 (alice=10.213.35.42:31000) body={'server_b_endpoint': '10.213.35.42:31001', 'obs_pub_endpoint': '10.213.35.42:32001', 'container_status': 'running', 'container_name': 'runner-bob', 'nfs_mount_path': '/workspace'} |
| 4 | alice 容器内看不到 bob 文件 | `sg docker -c 'docker exec runner-alice ls /workspace'`；`sg docker -c 'docker exec runner-alice test ! -f /workspace/bob_only.txt && echo isolated'` | 有 `alice_only.txt`；输出 `isolated`；无 `bob_only.txt` | PASS；ls=alice_only.txt jobs logs mount_test.txt rsl_rl_isrc wheels iso=isolated |
| 5 | bob 容器内看不到 alice 文件 | `sg docker -c 'docker exec runner-bob ls /workspace'`；`sg docker -c 'docker exec runner-bob test ! -f /workspace/alice_only.txt && echo isolated'` | 有 `bob_only.txt`；输出 `isolated`；无 `alice_only.txt` | PASS；ls=bob_only.txt jobs logs iso=isolated |
| 6 | 错 token 不能停对方容器 | `curl -sS -o /tmp/i04.json -w '%{http_code}' -X POST $A/containers/stop -H "Authorization: Bearer $TA"` 只应停 alice；bob `docker ps` 仍 Up | alice stop 200；`runner-bob` 仍在 | PASS；HTTP 200 body={"status":"stopped"}；runner-bob=runner-bob Up 3 seconds |
| 7 | 收尾 | bob 的 token 再 `POST /containers/stop` | `runner-alice`、`runner-bob` 均不在 | PASS；HTTP 200 body={"status":"stopped"} alice=无 bob=无 |

## 通过标准

两用户同时各有一只容器、各挂自己的 NFS、端口不同、文件互不可见。步骤 4/5 的 `docker exec` 只用于验收隔离，不是启动路径。
