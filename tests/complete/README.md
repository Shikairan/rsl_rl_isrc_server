# 完整全链路测试

一条客户端路径从头走到尾，不拆层、不拆联调用例。本链路会经 `obs_pub_endpoint` 订阅画面，并在终端 / NFS 输出 obs 帧。

- 方案：[PLAN.md](PLAN.md)
- 脚本：[`run.sh`](run.sh) / [`run.py`](run.py)（按步骤执行并把真实结果写回 `PLAN.md`）
- 阶段：登录 → 挂载 → 内部检查 → 运行容器（含画面口） → 执行开训 → 等待 + SUB 收帧 → 查看结果（含 obs）

```bash
bash /home/isrc5090/149server/tests/complete/run.sh
```

现场：NFS `10.250.30.115`，Server A `10.213.35.42:8017`（`INTEGRATION_A_PORT`）。账号 `alice` / `alice-dev`。镜像 `rsl_rl_isrc:v3-C`。训练：`jobs/complete_obs_smoke.py`（G1 1 iter，开 ZMQ obs）。

相关目录：

- 单元（一项一能力）：`tests/units/`
- 联调（I-01～I-08、I-OBS-01～04）：`tests/integration/`
