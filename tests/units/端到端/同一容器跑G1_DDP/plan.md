# T-E2E-02 同一容器跑 G1 DDP

## 测什么

Server A start 时 gpu_count=2，容器内执行与 T-F-02 相同的 torchrun DDP 命令。

## 依赖什么

- **依赖**：T-E2E-01、T-F-02。
- **不依赖**：ZMQ（可继续 --no-zmq-obs）。

## 前置条件

镜像同时具备 Server B 与 /opt/rsl_rl_isrc。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | start 申请 2 GPU | `curl -sS -X POST http://10.213.35.42:8000/containers/start -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"image":"rsl_rl_isrc:v3-sb","gpu_count":2}'` | 200；容器可见 2 张 GPU | PASS；login HTTP 200；start HTTP 200 body={"server_b_endpoint":"10.213.35.42:31000","container_status":"running","container_name":"runner-alice","nfs_mount_path":"/workspace"} |
| 2 | 经 Server B 或 docker exec 跑 DDP smoke | `torchrun --standalone --nproc_per_node=2 rsl_rl_isrc/tests/test_ppo_g1_mujoco_ddp.py --num-envs 16 --max-iterations 2 --no-zmq-obs` | 与 T-F-02 相同：world_size=2，2 iteration，退出码 0 | PASS；退出码 0；输出：[rank0] 未显式指定 --obs-server-host，自动推断为 172.17.0.9 ActorCriticRecurrent.__init__ got unexpected arguments, which will be ignored: dict_keys(['policy_class_name']) Actor MLP: Sequential( (0): Linear(in_features=128, out_features=512, bias=True) (1): ELU(alpha=1.0) (2): Linear(in_features=512, out_features=256, bias=True) (3): ELU(alpha=1.0) (4): Linear(in_feat… |
| 3 | stop | `curl -sS -X POST http://10.213.35.42:8000/containers/stop -H "Authorization: Bearer $TOKEN" ` | stopped | PASS；HTTP 200 body={"status":"stopped"} |

## 通过标准

平台拉起的容器内 DDP 与手工 docker run 结果一致。
