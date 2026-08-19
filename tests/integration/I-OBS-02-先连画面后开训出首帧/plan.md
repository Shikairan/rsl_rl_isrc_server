# I-OBS-02 先连画面后开训出首帧

## 测什么

按真实客户端顺序：先 `login` / `containers/start` 拿到 `obs_pub_endpoint` 并连接画面口；随后再对 `server_b_endpoint` 发起训练，宿主机 SUB 能收到至少一帧 JSON 画面数据。

这条用例验证的是完整链路：

`Client SUB -> obs_pub_endpoint -> 15557 -> obsserver -> HTTP relay -> ObsInstrServer -> 训练`

## 依赖什么

- **依赖**：I-OBS-01；单元 `T-OBS-06` 已绿；`rsl_rl_isrc:v3-C`；宿主机至少 2 张 GPU。
- **不依赖**：alice/bob 双用户隔离。

## 前置条件

- A 常驻。
- `/workspace/jobs/` 下准备一份**会开 obs** 的极短训练脚本或包装脚本；**不要**带 `--no-zmq-obs`。
- client 侧用 SUB 连 `obs_pub_endpoint`，允许等待 60s。

```bash
A=http://10.213.35.42:8000
TOKEN=$(curl -sS -X POST $A/login -H 'content-type: application/json' \
  -d '{"username":"alice","password":"alice-dev"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
```

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | start `v3-C` 申请 2 GPU | `curl -sS -X POST $A/containers/start -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"image":"rsl_rl_isrc:v3-C","gpu_count":2}'` | HTTP 200；返回 `server_b_endpoint` 与 `obs_pub_endpoint` | PASS；退出码 0；输出：-rw-rw-r-- 1 isrc5090 isrc5090 310 Aug 18 19:01 /mnt/nfs/alice/jobs/obs_iobs02_smoke.py |
| 2 | 先连画面口 | `python3` SUB `tcp://$OBS_EP`，`RCVTIMEO=60000` | 连接成功；先无消息也正常 | PASS；HTTP 200 body={"server_b_endpoint": "10.213.35.42:31000", "obs_pub_endpoint": "10.213.35.42:32000", "container_status": "running", "container_name": "runner-alice", "nfs_mount_path": "/workspace"} |
| 3 | 对 B 发起短训练 | `curl -sS -X POST http://$EP/tasks/start -H 'content-type: application/json' -d '{"script_path":"jobs/<obs_smoke>.py","torchrun_args":["--nproc_per_node","2","--standalone"],"script_args":["--max-iterations","1"]}'` | HTTP 202；拿到 `task_id` | PASS；退出码 0；输出：{"task_id": "t-1", "frame": [[[0.8647451400756836, 0.3887401521205902, 0.7984024286270142], [-0.015115750022232533, 0.006550956051796675, 0.00015763593546580523, 0.9998642802238464], [-0.04433643817901611, 0.09725047647953033, 0.09105551242828369, 0.31314772367477417, -0.20392243564128876, -0.021056275814771652, -0.026255184784531593, 0.08008196949958801, 0… |
| 4 | 等 SUB 收首帧 | 等待 SUB 进程输出 | 收到至少一帧 JSON 数组；元素行为 `[位置,姿态,关节]` | PASS；frame_head=[[[0.8647451400756836, 0.3887401521205902, 0.7984024286270142], [-0.015115750022232533, 0.006550956051796675, 0.00015763593546580523, 0.9998642802238464], [-0.04433643817901611, 0.09725047647953033, 0.09105551242828369, 0.31314772367477417, -0.20392243564128876, -0.021056275814771652, -0.02625518478 |
| 5 | 任务结束后看状态 | `curl -sS http://$EP/tasks/$TASK_ID/status` | `succeeded` / `exit_code=0` | PASS；{'task_id': 't-1', 'status': 'succeeded', 'exit_code': 0, 'started_at': '2026-08-18T11:01:23.279286+00:00', 'finished_at': '2026-08-18T11:01:30.202564+00:00'} |
| 6 | stop 容器 | `curl -sS -X POST $A/containers/stop -H "Authorization: Bearer $TOKEN"` | HTTP 200 | PASS；HTTP 200 body={"status":"stopped"} |

## 通过标准

不手工 `docker run`，只经 A + B + 任务接口拿到首帧。若暂时没有可放在 `/workspace/jobs/` 的 obs smoke 脚本，本项先记 `TODO`，不要退回到手工容器联调冒充通过。
