# T-A-08 健康检查失败回收（mock）

## 测什么

容器起来后 /health 失败：502，强制 rm，释放端口，清除注册表。

## 依赖什么

- **依赖**：mock health_fn 返回 False。
- **不依赖**：真实镜像。

## 前置条件

conda activate serverA。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 跑健康失败用例 | `conda activate serverA && cd /home/isrc5090/149server/serverA && pytest tests/test_containers.py::test_start_health_fail_returns_502 -q` | PASSED；HTTP 502；remove_force 被调用；registry.get('alice') 为 None | PASS；退出码 0；输出：. [100%] =============================== warnings summary =============================== ../../miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1 /home/isrc5090/miniconda3/envs/serverA/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install… |

## 通过标准

失败不留下 running 注册记录和占用端口。
