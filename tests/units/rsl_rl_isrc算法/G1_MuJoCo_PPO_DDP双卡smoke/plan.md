# T-F-02 G1 MuJoCo PPO DDP 双卡 smoke

## 测什么

torchrun 双进程：MuJoCo CPU 仿真 + 策略 GPU；2 iteration 跑完。

## 依赖什么

- **依赖**：T-F-01；至少 2 张可见 GPU；--shm-size 与 --ipc=host。
- **不依赖**：Server A、NFS、ZMQ 观测服务。

## 前置条件

工作目录镜像内 /opt/rsl_rl_isrc；scene.xml 在包内 robotmodel/g1_description/。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 双卡 DDP smoke | `docker run --rm --gpus 2 --shm-size=16g --ipc=host -w /opt/rsl_rl_isrc rsl_rl_isrc:v3 torchrun --standalone --nnodes=1 --nproc_per_node=2 rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py --num-envs 16 --max-iterations 2 --no-zmq-obs` | 退出码 0；日志含 world_size=2、total_envs=32、sim_device=cpu、policy_device=cuda:0；出现 Learning iteration 0/2 与 1/2；无 NCCL 崩溃 | PASS；退出码 0；输出：[rank0] 未显式指定 --obs-server-host，自动推断为 172.17.0.12 ActorCriticRecurrent.__init__ got unexpected arguments, which will be ignored: dict_keys(['policy_class_name']) Actor MLP: Sequential( (0): Linear(in_features=128, out_features=512, bias=True) (1): ELU(alpha=1.0) (2): Linear(in_features=512, out_features=256, bias=True) (3): ELU(alpha=1.0) (4): Linear(in_fea… |

## 通过标准

2 卡 2 iteration 正常结束。

## 备注

不要用 --gpus device=0,1 与 Count 混用，本机 Docker 会报 cannot set both Count and DeviceIDs。用 --gpus 2。
