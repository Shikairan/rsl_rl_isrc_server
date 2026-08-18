# T-B-05 Server B 打入训练镜像后的健康检查

## 测什么

在 rsl_rl_isrc:v3（或后续 tag）上叠加 Server B 后，8080 /health 通过，从而解锁 T-A-10。

## 依赖什么

- **依赖**：T-B-01 实现；训练镜像仍含 torch 2.11+cu128。
- **不依赖**：完整 E2E。

## 前置条件

新镜像例如 rsl_rl_isrc:v3-sb。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 启动新镜像 | `docker run -d --name sb-v3 --rm -p 18080:8080 rsl_rl_isrc:v3-sb` | running | PASS；退出码 0；health_ready=True；输出：de10a72f0a133c0958be068e41b9696421df31e6ef6f35746e8a4f676eef3cef |
| 2 | health | `curl -sS http://127.0.0.1:18080/health` | {"status":"ok"} | PASS；HTTP 200 body={"status":"ok"} |
| 3 | 确认 torchrun 仍在 | `docker exec sb-v3 bash -lc 'command -v torchrun && python -c "import torch;print(torch.__version__)"'` | torchrun 存在；torch 仍为 2.11.0+cu128 | PASS；退出码 0；输出：/usr/local/bin/torchrun 2.11.0+cu128 |
| 4 | 清理 | `docker stop sb-v3` | 退出 | PASS；退出码 0；输出：sb-v3 |

## 通过标准

健康检查与 CUDA 训练栈同时存在。
