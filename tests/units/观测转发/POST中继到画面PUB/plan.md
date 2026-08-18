# T-OBS-04 POST 中继 → 画面 PUB

## 测什么

容器内对 `http://127.0.0.1:15558/post` 发一条与中继格式相同的 JSON（每机器人 `[位置,姿态,关节]`），宿主机 SUB `15557` 能收到**原样**数组。不写用户名。

## 依赖什么

- **依赖**：T-OBS-03 同款容器映射（8080 + 15557）。
- **不依赖**：Server A、`ObsInstrServer` 真跑、GPU。

## 前置条件

示例 payload（1 个机器人）：

```json
[[[0.1, 0.2, 0.9], [0.0, 0.0, 0.0, 1.0], [0.5, -0.3]]]
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 起容器 | 同 T-OBS-03 步骤 1，`--name obs-pub` | running | PASS；退出码 0；health_ready=True；输出：8ee5ea7da5aeb25ba132c490ad7e0d625523273c384d4d3f73e39bd11a3f0142 |
| 2 | 宿主机 SUB（后台） | `python3 - <<'PY' & sleep 0.3` … SUB 连 `tcp://127.0.0.1:15557`，收到一条消息后打印并退出 | 见下方脚本块 | PASS；退出码 0；输出：ok [[[0.1, 0.2, 0.9], [0.0, 0.0, 0.0, 1.0], [0.5, -0.3]]] |
| 3 | 容器内 POST | `sg docker -c 'docker exec obs-pub python3 -c "import json,urllib.request; urllib.request.urlopen(urllib.request.Request(\"http://127.0.0.1:15558/post\", data=json.dumps([[[0.1,0.2,0.9],[0,0,0,1],[0.5,-0.3]]]).encode(), headers={\"Content-Type\":\"application/json\"}, method=\"POST\")).read()"'` | 返回 `b'ok'` | PASS；退出码 0；输出：obs-pub |
| 4 | 确认 SUB 输出 | 等待 SUB 进程 | stdout 为与 POST 相同的 JSON 数组 |  |
| 5 | 清理 | `sg docker -c 'docker stop obs-pub'` | 退出 |  |

SUB 脚本参考：

```python
import json, time, zmq
ctx = zmq.Context()
s = ctx.socket(zmq.SUB)
s.setsockopt(zmq.SUBSCRIBE, b"")
s.connect("tcp://127.0.0.1:15557")
s.setsockopt(zmq.RCVTIMEO, 3000)
print(json.loads(s.recv().decode()))
```

## 通过标准

POST 200 + SUB 收到与 POST body 一致的 JSON。失败归属：转发进程未起、端口映射错、SUB 未先连上。

## 与 T-F-04 区别

[T-F-04](../../rsl_rl_isrc算法/ZMQ观测通道/plan.md) 测训练内 **ObsInstrServer PULL/REP**；本项只测 **常驻转发 HTTP→PUB**，不启动 torchrun。
