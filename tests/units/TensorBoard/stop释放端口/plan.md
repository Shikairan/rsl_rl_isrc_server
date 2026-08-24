# T-TB-06 stop 释放 TensorBoard 端口

## 测什么

stop 之后 `tensorboard_endpoint` 对应宿主机端口不再监听；registry 不再占用该 33xxx。

## 依赖什么

- **依赖**：T-TB-03。
- **不依赖**：训练。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | start | `POST /containers/start` | 200；记下 TB 口 | PASS；HTTP 200 tb=10.213.35.42:33000 |
| 2 | 确认端口可连 | TCP connect | 成功 | PASS；10.213.35.42:33000 reachable=True |
| 3 | stop | `POST /containers/stop` | 200 | PASS；HTTP 200 {"status":"stopped"} |
| 4 | 再连原端口 | TCP connect | 失败 | PASS；10.213.35.42:33000 reachable=False |
| 5 | docker ps | `docker ps -f name=runner-alice` | 无该容器 | PASS；退出码 0 |

## 通过标准

stop 释放 33xxx。
