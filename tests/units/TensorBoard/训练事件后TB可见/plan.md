# T-TB-04 训练事件后 TB 可见

## 测什么

容器起来后在 `/workspace/logs/tensorboard` 写一条 scalar；TensorBoard HTTP 仍 200（页面能打开）。完整 G1 曲线留给端到端。

## 依赖什么

- **依赖**：T-TB-03；alice 容器可 start；镜像含 torch / tensorboard。
- **不依赖**：多卡 G1。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | start v3-D | `POST /containers/start` | 200；有 `tensorboard_endpoint` | PASS；HTTP 200 tb=10.213.35.42:33000 |
| 2 | 容器内写 event | `docker exec runner-alice python3 -c SummaryWriter...` | 退出码 0 | PASS；退出码 0；输出：ok |
| 3 | HTTP TB | `curl http://{tensorboard_endpoint}/` | HTTP 200 | PASS；ready=True HTTP 200 body=<!doctype html><meta name="tb-relative-root" content="./"><!doctype html><!--
@license
Copyright 2019 The TensorFlow Authors. All Rights Reserved.

Licensed und |
| 4 | stop | `POST /containers/stop` | 200 | PASS；HTTP 200 {"status":"stopped"} |

## 通过标准

写 event 不把 TensorBoard 打挂；地址可打开。
