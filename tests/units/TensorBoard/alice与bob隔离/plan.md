# T-TB-05 alice 与 bob TensorBoard 隔离

## 测什么

alice 与 bob 各起一只容器，`tensorboard_endpoint` 端口不同；互不占用对方地址。

## 依赖什么

- **依赖**：T-TB-03；alice / bob NFS 均已挂。
- **不依赖**：训练。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | alice start | alice token `POST /containers/start` | 200；记下 `TB_A` | PASS；HTTP 200 tb=10.213.35.42:33000 |
| 2 | bob start | bob token start | 200；记下 `TB_B` | PASS；HTTP 200 tb=10.213.35.42:33001 |
| 3 | 比较 | 两地址 | 不同且都含 `:33` | PASS；alice=10.213.35.42:33000 bob=10.213.35.42:33001 |
| 4 | stop 两人 | 各自 stop | 200 | PASS；issued stop |

## 通过标准

两人 TensorBoard 端口隔离。
