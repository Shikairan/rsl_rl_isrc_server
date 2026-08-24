# T-TB-01 v3-D 镜像含 tensorboard

## 测什么

`rsl_rl_isrc:v3-D` 已打入常驻 TensorBoard；CLI 可用；EXPOSE 含 `6006`。

## 依赖什么

- **依赖**：已构建 `rsl_rl_isrc:v3-D`（`bash serverB/build.sh`）。
- **不依赖**：Server A、NFS、GPU、训练。

## 前置条件

```bash
sg docker -c 'docker images rsl_rl_isrc:v3-D --format "{{.ID}}"'
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 确认镜像存在 | `sg docker -c 'docker image inspect rsl_rl_isrc:v3-D --format "{{.Id}}"'` | 有 sha | PASS；退出码 0；输出：sha256:14ac46e17e328e09dd48e4bce5624979a424a12df74cb237b8731978387ef593 |
| 2 | 容器内 tensorboard 版本 | `sg docker -c 'docker run --rm --entrypoint tensorboard rsl_rl_isrc:v3-D --version'` | 退出码 0 | PASS；退出码 0；输出：2.21.0 TensorFlow installation not found - running with reduced feature set. |
| 3 | 检查 EXPOSE | `sg docker -c 'docker image inspect rsl_rl_isrc:v3-D --format "{{json .Config.ExposedPorts}}"'` | 含 `8080/tcp`、`15557/tcp`、`6006/tcp` | PASS；退出码 0；输出：{"15557/tcp":{},"6006/tcp":{},"8080/tcp":{}} |

## 通过标准

v3-D 能跑 `tensorboard` CLI，且声明了 6006 端口。
