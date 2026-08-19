# K8s 多机多卡方案（提案）

> **效力：提案。** 不是下一阶段实现合同，也不替代 [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)（验证版唯一依据）。
> **本轮只落本文档。** 不改 Server A/B、测试、[`docs/CLIENT.md`](docs/CLIENT.md)、其它计划文件。
> 文内条目标 **约束 / 推荐 / 未定**。推荐可以推翻；未定等单独 grilling。

现行验证版：单机多卡用本机 `docker run` + 长驻 `runner-{user}` + `torchrun --standalone`。K8s **只用于多机多卡**。两条后端要解耦；以后会切成全 K8s（见 §8）。

---

## 1. 为什么单机 Docker 扩不到多机

| 环节 | 现在（验证版） | 多机时 |
|------|----------------|--------|
| 起环境 | Server A 本机 `docker run`，`DeviceRequest(count=gpu_count)` | Docker 只管本机 GPU |
| 工作区 | 宿主机 `mount` NFS，再 bind `/mnt/nfs/{user}:/workspace` | K8s 路径不要再经宿主机挂载 |
| 开训 | 同一只容器里 `torchrun --standalone --nproc_per_node=N` | `--standalone` 等于 `nnodes=1` |

**约束：** 一只 Pod / 一只容器不能跨 Node。要 2 机 × 4 卡，必须是 **2 个 GPU Pod**，再用 `torchrun --nnodes=2`（或等价）组 DDP。

NFS 只保证脚本和 checkpoint 各 Pod 看得见。梯度通信走节点间网络（NCCL），不走 NFS。

---

## 2. 目标：双后端（解耦）

```
客户端
  ├─ 本机挂 NFS（仍是 10.250.30.115，登录返回的导出路径）
  └─ POST /containers/start     ← 同一 URL
        │
        ▼
   Server A（控制面，无 GPU）
        │
        ├─ nnodes 缺省或 =1  →  Docker 后端（现状，不改）
        │     docker run runner-{user}
        │     -v /mnt/nfs/{user}:/workspace
        │     --gpus N
        │     长驻 Server B :8080 → /tasks/start → torchrun --standalone
        │
        └─ nnodes>=2         →  K8s 后端（本提案）
              创建 PyTorchJob（短命）
              每个 replica 挂同一用户 PVC → /workspace
              NCCL 走 Pod 网络
```

**推荐分流：** 同一 `POST /containers/start`；`nnodes>=2` 走 K8s，否则走 Docker。内部两套后端，互不调用。

**未定（客户端处理）：** 单机这次 POST 表示「起长驻环境」，多机这次 POST 表示「起一轮训练」。同一 URL、两套语义，由 **client** 解释请求字段和返回值。本文不规定 Server A 是否在 `nnodes>=2` 时要求 `script_path`，也不规定还要不要返回长驻的 `server_b_endpoint`。

字段名 `nnodes`、`gpu_count` 如何映射到每 Pod 的 `nvidia.com/gpu`，观测口怎么出，均为 **未定**。

---

## 3. NFS：所有 K8s Pod 看见同一目录

Docker 路径维持现状（A 可选 `mount`，再 bind）。下面只约束 **K8s 路径**。

**约束：**

- 每个训练 Pod **自己**挂 NFS，声明 `ReadWriteMany`。
- 导出沿用 [`nfsserver/config/users.yaml`](nfsserver/config/users.yaml)：`10.250.30.115:/mnt/dockerContainer/nfs/{user}`。
- 容器内仍是 `/workspace`（与 [`serverA/config/server.yaml`](serverA/config/server.yaml) 的 `container_workspace` 一致）。
- `nfsvers=4`。
- 不用 hostPath、不用在 A 里对 K8s 节点做 `mount -t nfs`、不用 `ReadWriteOnce`。
- 导出网段已是 `10.0.0.0/8`，须覆盖全部 GPU Node IP。

**推荐：** 按用户一块 PV/PVC（alice / bob 隔离），不要把导出根挂给全平台。静态 PV 先够用；NFS CSI 可选。现有 `no_root_squash` 可先留；也可用 `fsGroup` 对齐 UID。

笔记本客户端继续按 `CLIENT.md` 直接挂 115，不经过 K8s。

---

## 4. 多机多卡怎么起

**约束：** K8s 腿是短命 GPU Pod，一轮训练结束 Pod 就没了。不要把 Docker 的长驻 `runner-{user}` 生命周期套到多机上。

**推荐：** Kubeflow Training Operator 的 `PyTorchJob`（Master + Worker，`nvidia.com/gpu`，`torchrun --nnodes`）。集群须装 **Training Operator** 和 **NVIDIA GPU Operator**（或 device plugin）。镜像须进仓库，每个 Node 都能 pull。

NCCL：**推荐**先 TCP 打通（必要时 `NCCL_IB_DISABLE=1`），再考虑 IB；按网卡设 `NCCL_SOCKET_IFNAME`。

Indexed Job + headless Service 做 rendezvous 是备选，本文 debug 清单不维护那一套，避免和 PyTorchJob 漂移。

---

## 5. YAML 示例（可 `kubectl apply`，非规范）

debug / 手工打通时：把本节复制成文件（或管道）执行 `kubectl apply -f`。仓库 **不另建** `k8s/examples/`。

**前提：** 已装 NVIDIA GPU Operator（或等价 device plugin）和 Kubeflow Training Operator。没有 Operator 时 `kind: PyTorchJob` 会 apply 失败。

下面以 **alice、2 机 × 4 卡** 为例。换用户则改 PV `path`、PVC 名、Job 名。`storage` 容量是声明，NFS 不按它限额。

```yaml
# 示例：alice 工作区。非规范清单。
apiVersion: v1
kind: PersistentVolume
metadata:
  name: nfs-alice
spec:
  capacity:
    storage: 1Ti
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  mountOptions:
    - nfsvers=4
  nfs:
    server: 10.250.30.115
    path: /mnt/dockerContainer/nfs/alice
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: workspace-alice
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: ""
  volumeName: nfs-alice
  resources:
    requests:
      storage: 1Ti
---
apiVersion: kubeflow.org/v1
kind: PyTorchJob
metadata:
  name: alice-ddp
spec:
  pytorchReplicaSpecs:
    Master:
      replicas: 1
      restartPolicy: OnFailure
      template:
        spec:
          containers:
            - name: pytorch
              image: rsl_rl_isrc:v3-C
              command:
                - torchrun
                - --nnodes=2
                - --nproc_per_node=4
                - --rdzv_backend=c10d
                - --rdzv_id=alice-ddp
                - --rdzv_endpoint=$(MASTER_ADDR):29400
                - /workspace/jobs/train.py
              resources:
                limits:
                  nvidia.com/gpu: 4
              volumeMounts:
                - name: workspace
                  mountPath: /workspace
          volumes:
            - name: workspace
              persistentVolumeClaim:
                claimName: workspace-alice
    Worker:
      replicas: 1
      restartPolicy: OnFailure
      template:
        spec:
          containers:
            - name: pytorch
              image: rsl_rl_isrc:v3-C
              command:
                - torchrun
                - --nnodes=2
                - --nproc_per_node=4
                - --rdzv_backend=c10d
                - --rdzv_id=alice-ddp
                - --rdzv_endpoint=$(MASTER_ADDR):29400
                - /workspace/jobs/train.py
              resources:
                limits:
                  nvidia.com/gpu: 4
              volumeMounts:
                - name: workspace
                  mountPath: /workspace
          volumes:
            - name: workspace
              persistentVolumeClaim:
                claimName: workspace-alice
```

先 apply PV/PVC，两个普通 Pod（可不同 Node）都挂 `workspace-alice` 做一次读写，再 apply `PyTorchJob`。

Operator 通常会注入 `MASTER_ADDR` / `RANK` / `WORLD_SIZE`。若 replica 里 `$(MASTER_ADDR)` 未展开，按所装 Operator 文档改 `command`，或改用它默认入口，不要同时维护第二套原生 Job YAML。

---

## 6. 落地顺序（推荐）

1. GPU 节点装 GPU Operator，单 Pod `nvidia.com/gpu: 1` 能 `nvidia-smi`。
2. 装 Training Operator。
3. apply §5 的 PV/PVC；两 Pod 共挂、一边写一边读。
4. apply §5 的 `PyTorchJob`（可先减卡数）打通 rendezvous，再加满 GPU。
5. 再改 Server A：加 K8s 后端，与 `DockerMgr` 并列；`nnodes>=2` 分流。现行 Docker 单机路径保持可运行。

---

## 7. 以后（推荐，不本轮做）

Server A 创建 Job 时，把生成的 YAML **打进日志**，便于对照 `kubectl apply` debug。本轮不实现。

---

## 8. 以后全 K8s（一句话）

删掉 Docker 后端；K8s 也接 `nnodes=1`（单 Pod 多卡）。怎么切、旧 URL 是否还指向 `/containers/start`，**未定**。

解耦的意义：届时是删后端，不是重写控制面。
