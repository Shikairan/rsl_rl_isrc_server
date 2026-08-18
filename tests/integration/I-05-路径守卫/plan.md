# I-05 路径守卫

## 测什么

经 Server A 拉起的 `v3-B` 容器上，`script_path` 用 `..` 穿越或绝对路径时，Server B 返回 400，不启动进程。

## 依赖什么

- **依赖**：I-01 能 start 容器并打通 B `/health`。
- **不依赖**：训练成功、多卡、bob。

## 前置条件

A 常驻。alice start `rsl_rl_isrc:v3-B`（`gpu_count` 可为 0），记下 `$EP`。

```bash
A=http://10.213.35.42:8000
TOKEN=$(curl -sS -X POST $A/login -H 'content-type: application/json' \
  -d '{"username":"alice","password":"alice-dev"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
EP=$(curl -sS -X POST $A/containers/start -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"image":"rsl_rl_isrc:v3-B","gpu_count":0}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["server_b_endpoint"])')
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 相对路径穿越 | `curl -sS -o /tmp/i05a.json -w '%{http_code}' -X POST http://$EP/tasks/start -H 'content-type: application/json' -d '{"script_path":"../etc/passwd","torchrun_args":["--standalone"],"script_args":[]}'` | HTTP 400；`script_path escapes workspace` | PASS；HTTP 400 body={"detail":{"error":"script_path escapes workspace"}} |
| 2 | 绝对路径 | `curl -sS -o /tmp/i05b.json -w '%{http_code}' -X POST http://$EP/tasks/start -H 'content-type: application/json' -d '{"script_path":"/etc/passwd","torchrun_args":["--standalone"],"script_args":[]}'` | HTTP 400；`script_path must be relative to workspace` | PASS；HTTP 400 body={"detail":{"error":"script_path must be relative to workspace"}} |
| 3 | 镜像内算法绝对路径（对照 I-07） | `curl -sS -o /tmp/i05c.json -w '%{http_code}' -X POST http://$EP/tasks/start -H 'content-type: application/json' -d '{"script_path":"/opt/rsl_rl_isrc/rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py","torchrun_args":["--standalone"],"script_args":[]}'` | HTTP 400；同样拒绝对路径（G1 不在 `/workspace`） | PASS；HTTP 400 body={"detail":{"error":"script_path must be relative to workspace"}} |
| 4 | 合法相对路径仍可 start | `curl -sS -X POST http://$EP/tasks/start -H 'content-type: application/json' -d '{"script_path":"jobs/train.py","torchrun_args":["--nproc_per_node","1","--standalone"],"script_args":["--epochs","3"]}'` | HTTP 202 | PASS；HTTP 202 body={'task_id': 't-1', 'status': 'running', 'started_at': '2026-08-18T03:13:06.042981+00:00'} |
| 5 | 停容器 | `curl -sS -X POST $A/containers/stop -H "Authorization: Bearer $TOKEN"` | HTTP 200 | PASS；HTTP 200 body={"status":"stopped"} |

## 通过标准

非法路径均为 400、不启动进程；合法 `jobs/train.py` 仍 202。
