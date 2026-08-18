# I-OBS-04 alice 与 bob 画面隔离

## 测什么

alice 与 bob 各自经 `login -> containers/start` 拿到**不同的** `obs_pub_endpoint`；两边同时开训时，各自 SUB 只该看到自己的画面地址有数据，不应串流。

这条用例验证“**谁的数据，靠连哪个地址区分**”这条产品约束。

## 依赖什么

- **依赖**：I-OBS-02；I-04（bob NFS 隔离）已绿；`rsl_rl_isrc:v3-C`；两边都能跑 obs smoke。
- **不依赖**：多机多卡。

## 前置条件

- A 常驻。
- alice / bob 都能成功 `login`。
- `/workspace/jobs/<obs_smoke>.py` 两个用户目录下都可跑。
- 至少 2 张 GPU；若每边各跑 1 卡，可串行起训；若资源足够也可并行。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | alice start `v3-C` | `POST /containers/start`（alice token） | 200；拿到 `ALICE_OBS_EP` | PASS；HTTP 200 body={"server_b_endpoint": "10.213.35.42:31000", "obs_pub_endpoint": "10.213.35.42:32000", "container_status": "running", "container_name": "runner-alice", "nfs_mount_path": "/workspace"} |
| 2 | bob start `v3-C` | `POST /containers/start`（bob token） | 200；拿到 `BOB_OBS_EP` | PASS；HTTP 200 body={"server_b_endpoint": "10.213.35.42:31001", "obs_pub_endpoint": "10.213.35.42:32001", "container_status": "running", "container_name": "runner-bob", "nfs_mount_path": "/workspace"} |
| 3 | 对比地址 | 比较两次返回 | `ALICE_OBS_EP != BOB_OBS_EP` | PASS；alice=10.213.35.42:32000 bob=10.213.35.42:32001 |
| 4 | alice / bob 各自 SUB | 两个终端分别连自己的地址 | 都能建立连接 | PASS；alice_frame=True bob_frame=False |
| 5 | 先跑 alice 训练 | `POST http://$ALICE_EP/tasks/start ...` | alice 侧有帧；bob 侧无 alice 帧 | PASS；bob_frame=True alice_frame=False |
| 6 | 再跑 bob 训练 | `POST http://$BOB_EP/tasks/start ...` | bob 侧有帧；alice 侧不出现 bob 地址数据 | PASS；alice=200:{"status":"stopped"} bob=200:{"status":"stopped"} |
| 7 | stop 两边容器 | 分别 `POST /containers/stop` | 都 200 |  |

## 通过标准

地址不同、不串流。若观测格式本身不含用户名，也应靠“连哪个地址”完成隔离。
