# 联调测试

总方案：[PLAN.md](PLAN.md)

本目录只放联调方案与执行脚本。每条用例：

- `plan.md`：测什么 / 依赖 / 步骤表（含真实结果列）
- `run.sh` / `run.py`：按步骤执行并把真实结果写回 `plan.md`
- `result.log` / `result.json`：最近一次执行的完整记录

与 `tests/units/` 的差别：联调按客户端路径一次拉齐 NFS + Server A + Docker + Server B + GPU；禁止把手工 `docker run` 当主路径。脚本会复用 `http://10.213.35.42:8000` 上已有的 Server A；若未探活则按现场配置拉起（`0.0.0.0:8000`，默认 sqlite，不用单元测试临时库）。

全部执行：

```bash
bash /home/isrc5090/149server/tests/integration/run_all.sh
```

单条：`bash /home/isrc5090/149server/tests/integration/I-01-alice主链路/run.sh`

| 编号 | 标题 | 目录 |
|------|------|------|
| [I-01](I-01-alice主链路/plan.md) | alice 登录到 GPU 训练再停干净 | `I-01-alice主链路/` |
| [I-02](I-02-start幂等与current/plan.md) | 重复 start 与 current | `I-02-start幂等与current/` |
| [I-03](I-03-单任务锁/plan.md) | 平台拉起的 B 上第二任务 409 | `I-03-单任务锁/` |
| [I-04](I-04-bob隔离/plan.md) | bob 容器看不到 alice 文件 | `I-04-bob隔离/` |
| [I-05](I-05-路径守卫/plan.md) | 经 A 拉起的容器上越界 400 | `I-05-路径守卫/` |
| [I-06](I-06-容器被杀后重建/plan.md) | 外部删容器后再 start 能重建 | `I-06-容器被杀后重建/` |
| [I-07](I-07-同容器双卡DDP/plan.md) | 同一 runner 内 2 卡 G1 DDP | `I-07-同容器双卡DDP/` |
| [I-08](I-08-指定GPU4到7的4卡DDP全链路/plan.md) | 指定 GPU 4–7、WORLD_SIZE=4 的全链路 | `I-08-指定GPU4到7的4卡DDP全链路/` |
| [I-OBS-01](I-OBS-01-画面地址返回与映射/plan.md) | 画面地址返回与映射 | `I-OBS-01-画面地址返回与映射/` |
| [I-OBS-02](I-OBS-02-先连画面后开训出首帧/plan.md) | 先连画面后开训出首帧 | `I-OBS-02-先连画面后开训出首帧/` |
| [I-OBS-03](I-OBS-03-同容器重复开训地址不变/plan.md) | 同容器重复开训地址不变 | `I-OBS-03-同容器重复开训地址不变/` |
| [I-OBS-04](I-OBS-04-alice与bob画面隔离/plan.md) | alice 与 bob 画面隔离 | `I-OBS-04-alice与bob画面隔离/` |

建议顺序：I-01 → I-02 → I-03 → I-OBS-01 → I-OBS-02 → I-OBS-03 → I-05 → I-06 → I-04 → I-OBS-04 → I-07 → I-08。
