# T-OBS-03 容器入口：转发与 Server B 并存

## 测什么

`v3-C` 容器起来后：**同时**有 Server B `/health` 与转发进程日志（绑定 `127.0.0.1:15558` → PUB `15557`）。不跑训练。

## 依赖什么

- **依赖**：T-OBS-02；镜像 `rsl_rl_isrc:v3-C`。
- **不依赖**：Server A、NFS、GPU、`POST /tasks/start`。

## 前置条件

宿主机 `18080`、`15557` 未被长期占用（本用例 `--rm` 临时映射）。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 后台起容器 | `sg docker -c 'docker run -d --name obs-entry --rm -p 127.0.0.1:18080:8080 -p 127.0.0.1:15557:15557 rsl_rl_isrc:v3-C'` | 返回 container id；inspect running | PASS；退出码 0；health_ready=True；输出：c79bdf67ad068a296633d18c9d4ea09cb4fc3046830655c0c92f85be45c7e7dd |
| 2 | Server B 健康 | `curl -sS -m 3 http://127.0.0.1:18080/health` | `{"status":"ok"}` | PASS；HTTP 200 body={"status":"ok"} |
| 3 | 转发日志 | `sg docker -c 'docker logs obs-entry 2>&1 \| tail -5'` | 含 `obsserver http://127.0.0.1:15558/post -> pub tcp://0.0.0.0:15557` | PASS；退出码 0；输出：INFO: 172.17.0.1:46866 - "GET /health HTTP/1.1" 200 OK INFO: 172.17.0.1:46868 - "GET /health HTTP/1.1" 200 OK INFO: 172.17.0.1:46876 - "GET /health HTTP/1.1" 200 OK 2026-08-18 07:41:28,666 INFO obsserver: obsserver http://127.0.0.1:15558/post -> pub tcp://0.0.0.0:15557 INFO: Started server process [1] INFO: Waiting for application startup. INFO: Application… |
| 4 | 画面口 TCP | `python3 -c "import socket;s=socket.create_connection(('127.0.0.1',15557),2);s.close();print('ok')"` | 打印 ok（无 SUB 数据也正常） | PASS；退出码 0；输出：ok |
| 5 | 清理 | `sg docker -c 'docker stop obs-entry'` | 容器退出 | PASS；退出码 0；输出：obs-entry |

## 通过标准

B 与转发都在；15557 能连上。失败先看 ENTRYPOINT 是否把转发 watch 起来，不要查训练。
