# T-B-02 路径守卫

## 测什么

script_path 越出 /workspace（.. 或绝对路径）返回 400。

## 依赖什么

- **依赖**：T-B-01。
- **不依赖**：真实 torchrun 成功。

## 前置条件

容器已起，8080 可访问。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 相对路径穿越 | `curl -sS -o /tmp/b02a.json -w '%{http_code}' -X POST http://127.0.0.1:18080/tasks/start -H 'content-type: application/json' -d '{"script_path":"../etc/passwd","torchrun_args":["--standalone"],"script_args":[]}'` | HTTP 400 | PASS；HTTP 400 body={"detail":{"error":"script_path escapes workspace"}} |
| 2 | 绝对路径 | `curl -sS -o /tmp/b02b.json -w '%{http_code}' -X POST http://127.0.0.1:18080/tasks/start -H 'content-type: application/json' -d '{"script_path":"/etc/passwd","torchrun_args":["--standalone"],"script_args":[]}'` | HTTP 400 | PASS；HTTP 400 body={"detail":{"error":"script_path must be relative to workspace"}} |

## 通过标准

两类非法路径均为 400，不启动进程。
