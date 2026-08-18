# T-OBS-02 v3-C 镜像含 obsserver

## 测什么

`rsl_rl_isrc:v3-C` 已打入转发模块；`import obsserver` 成功；镜像 EXPOSE 含 `15557`；ENTRYPOINT 仍为 `/opt/serverB/entrypoint.sh`（内含转发 watchdog）。

## 依赖什么

- **依赖**：本地已构建 `rsl_rl_isrc:v3-C`（`bash serverB/build.sh`）。
- **不依赖**：Server A、NFS、GPU、训练。

## 前置条件

```bash
sg docker -c 'docker images rsl_rl_isrc:v3-C --format "{{.ID}}"'
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 确认镜像存在 | `sg docker -c 'docker image inspect rsl_rl_isrc:v3-C --format "{{.Id}}"'` | 有 sha | PASS；退出码 0；输出：sha256:7e3e1f8913ef8ab409ba3a4069a07b686d83394b4d1567c722074031bce7fcae |
| 2 | 容器内 import | `sg docker -c 'docker run --rm rsl_rl_isrc:v3-C python3 -c "import obsserver; from obsserver.transform import transform; print(transform([[1]]))"'` | 退出码 0；打印 `[[1]]` | PASS；退出码 0；输出：[[1]] |
| 3 | 检查 EXPOSE | `sg docker -c 'docker image inspect rsl_rl_isrc:v3-C --format "{{json .Config.ExposedPorts}}"'` | 含 `8080/tcp` 与 `15557/tcp` | PASS；退出码 0；输出：{"15557/tcp":{},"8080/tcp":{}} |
| 4 | 对比 v3-B 无 obsserver | `sg docker -c 'docker run --rm rsl_rl_isrc:v3-B python3 -c "import obsserver"'` | 失败（ModuleNotFoundError） | PASS；退出码 1；输出：Traceback (most recent call last): File "<string>", line 1, in <module> ModuleNotFoundError: No module named 'obsserver' |

## 通过标准

v3-C 能 import；v3-B 不能 import obsserver（两者分工：B 只有 Server B，C = B + 转发）。
