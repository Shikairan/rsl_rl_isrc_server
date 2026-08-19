# T-F-04 ZMQ 观测通道（可选）

## 测什么

去掉 `--no-zmq-obs` 后 rank0 拉起 ObsInstrServer 的 PULL/REP。**只验训练内收件箱**，不含 HTTP 中继与画面 PUB；全链路见 [T-OBS-06](../../观测转发/训练开ZMQ经中继出画面/plan.md)（需 `rsl_rl_isrc:v3-C`）。

## 依赖什么

- **依赖**：T-F-02；镜像已装 pyzmq。
- **不依赖**：更长训练、Server A。

## 前置条件

默认端口 15555/15556 未被占用。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 双卡、开启 zmq obs、极短训练 | `docker run --rm --gpus 2 --shm-size=16g --ipc=host -p 15555:15555 -p 15556:15556 -w /opt/rsl_rl_isrc rsl_rl_isrc:v3 torchrun --standalone --nproc_per_node=2 rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py --num-envs 8 --max-iterations 1` | rank0 日志含 ObsInstrServer: PULL tcp://*:15555 与 REP tcp://*:15556；训练能结束或至少完成 iteration 0；退出码 0 | PASS；退出码 0；输出：[rank0] 未显式指定 --obs-server-host，自动推断为 172.17.0.12 ActorCriticRecurrent.__init__ got unexpected arguments, which will be ignored: dict_keys(['policy_class_name']) Actor MLP: Sequential( (0): Linear(in_features=128, out_features=512, bias=True) (1): ELU(alpha=1.0) (2): Linear(in_features=512, out_features=256, bias=True) (3): ELU(alpha=1.0) (4): Linear(in_fea… |

## 通过标准

ZMQ 服务按文档拉起且不阻断 1 个 iteration。
