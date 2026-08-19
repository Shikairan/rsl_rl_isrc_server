# T-OBS-01 obsserver pytest 转发冒烟

## 测什么

宿主机上跑 `obsserver/tests`：转换函数默认原样、`POST /post` 立刻 200、合法 JSON 能从 PUB 收到、坏 JSON 仍 200 但不发帧、错误路径 404。

## 依赖什么

- **依赖**：`149server/obsserver` 源码、`pyzmq`（本机或 conda env）。
- **不依赖**：Docker、GPU、Server A/B、训练、`ObsInstrServer`。

## 前置条件

```bash
python3 -m pip install pyzmq pytest   # 若未装
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 进入目录跑 pytest | `cd 149server/obsserver && python3 -m pytest -q` | 退出码 0；至少 4 passed | PASS；退出码 0；输出：...... [100%] 6 passed in 1.86s |
| 2 | （可选）手工 SUB 冒烟 | 终端 A：`PYTHONPATH=src python3 -m obsserver`；终端 B：`curl -X POST http://127.0.0.1:15558/post -H 'content-type: application/json' -d '[[[0,0,1],[0,0,0,1],[0]]]'` | curl 返回 `ok`；SUB 端收到与 POST 相同的 JSON 数组 |  |

## 通过标准

pytest 全绿。失败先查本机是否缺 `pyzmq`，不要改训练或 Docker。

## 与方案关系

对应 [obsserver/PLAN.md](../../../../obsserver/PLAN.md) 落地顺序第 2 步「转发进程；本机 POST 能从画面口看到」的**无 Docker** 子集。
