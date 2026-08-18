# T-OBS-05 中继环境变量

## 测什么

`v3-C` 容器默认注入 `RSL_RL_ISRC_OBS_RELAY_URL=http://127.0.0.1:15558/post` 与短超时 `RSL_RL_ISRC_OBS_RELAY_TIMEOUT=0.05`，训练侧 **ObsInstrServer** 开中继时会 POST 到本机转发（算法包本身不改）。

## 依赖什么

- **依赖**：T-OBS-02；镜像 `rsl_rl_isrc:v3-C`。
- **不依赖**：Server A、真训练。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 读 RELAY_URL | `sg docker -c 'docker run --rm rsl_rl_isrc:v3-C printenv RSL_RL_ISRC_OBS_RELAY_URL'` | `http://127.0.0.1:15558/post` | PASS；退出码 0；输出：http://127.0.0.1:15558/post |
| 2 | 读超时 | `sg docker -c 'docker run --rm rsl_rl_isrc:v3-C printenv RSL_RL_ISRC_OBS_RELAY_TIMEOUT'` | `0.05` | PASS；退出码 0；输出：0.05 |
| 3 | OBS_ENABLE 默认开 | `sg docker -c 'docker run --rm rsl_rl_isrc:v3-C printenv OBS_ENABLE'` | `1` 或空（entrypoint 默认当 1） | PASS；退出码 0；输出：1 |
| 4 | v3-B 无 RELAY_URL | `sg docker -c 'docker run --rm rsl_rl_isrc:v3-B printenv RSL_RL_ISRC_OBS_RELAY_URL'` | 空（未设置） | PASS；退出码 1 |

## 通过标准

v3-C 自带中继指向本机转发；v3-B 不带。Server A 日后 `docker run` 仍应注入相同变量（见 obsserver PLAN §5）。
