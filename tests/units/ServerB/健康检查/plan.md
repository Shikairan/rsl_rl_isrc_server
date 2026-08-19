# T-B-01 Server B /health

## 测什么

带 Server B 的镜像启动后，8080 返回 {"status":"ok"}。

## 依赖什么

- **依赖**：镜像 ENTRYPOINT/CMD 自动在 8080 起 Server B（尚未实现）。
- **不依赖**：NFS 训练、GPU。

## 前置条件

Server B 代码打入镜像后才能执行。当前 rsl_rl_isrc:v3 不满足。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 后台启动容器映射 8080 | `docker run -d --name sb-health --rm -p 18080:8080 <server-b-image>` | 容器 running | PASS；退出码 0；inspect=running；输出：96af23ea12f7b66aca77f68079742e313faa1b95f2ba064f7e00b42d18b4f038 |
| 2 | 打健康检查 | `curl -sS http://127.0.0.1:18080/health` | 200 {"status":"ok"} | PASS；HTTP 200 body={"status":"ok"} |
| 3 | 清理 | `docker stop sb-health` | 容器退出 | PASS；退出码 0；输出：sb-health |

## 通过标准

/health 为 ok。本项通过后才可做 T-A-10。
