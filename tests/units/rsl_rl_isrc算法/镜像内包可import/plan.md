# T-F-01 镜像内包可 import

## 测什么

rsl_rl_isrc:v3 中 rsl_rl_isrc / torch / mujoco 可导入，且 CUDA 可见。

## 依赖什么

- **依赖**：镜像 rsl_rl_isrc:v3。
- **不依赖**：NFS、多卡、Server A。

## 前置条件

无需挂载 NFS。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 容器内 import | `docker run --rm --gpus 1 rsl_rl_isrc:v3 python -c "import rsl_rl_isrc, torch, mujoco; print(rsl_rl_isrc.__file__); print(torch.__version__, torch.cuda.is_available()); print(mujoco.__version__)" ` | 打印 /opt/rsl_rl_isrc/rsl_rl_isrc/__init__.py；torch 2.11.0+cu128 True；mujoco 3.11.0 | PASS；退出码 0；输出：/opt/rsl_rl_isrc/rsl_rl_isrc/__init__.py 2.11.0+cu128 True 3.11.0 |

## 通过标准

三库可导入且 cuda True。
