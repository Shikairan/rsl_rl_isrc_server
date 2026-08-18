# T-F-03 DDP 扩到 4 卡（可选）

## 测什么

nproc_per_node=4 时仍能完成至少 1 个 iteration。

## 依赖什么

- **依赖**：T-F-02；主机至少 4 张 GPU。
- **不依赖**：ZMQ。

## 前置条件

nvidia-smi -L 不少于 4。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 4 卡 1 个 iteration | `docker run --rm --gpus 4 --shm-size=16g --ipc=host -w /opt/rsl_rl_isrc rsl_rl_isrc:v3 torchrun --standalone --nnodes=1 --nproc_per_node=4 rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py --num-envs 8 --max-iterations 1 --no-zmq-obs` | 退出码 0；world_size=4；完成 iteration 0/1 | PASS；退出码 0；输出：[rank0] 未显式指定 --obs-server-host，自动推断为 172.17.0.9 ActorCriticRecurrent.__init__ got unexpected arguments, which will be ignored: dict_keys(['policy_class_name']) Actor MLP: Sequential( (0): Linear(in_features=128, out_features=512, bias=True) (1): ELU(alpha=1.0) (2): Linear(in_features=512, out_features=256, bias=True) (3): ELU(alpha=1.0) (4): Linear(in_feat… |

## 通过标准

4 进程 DDP 不 hang、不 NCCL 失败。
