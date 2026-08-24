# T-TB-02 手工映射 6006 可打开

## 测什么

`docker run -p 13306:6006` 后 TensorBoard HTTP 可访问。空 logdir 时页面仍应 200。

## 依赖什么

- **依赖**：T-TB-01；镜像 `rsl_rl_isrc:v3-D`。
- **不依赖**：Server A、训练。

## 详细测试步骤

| 步骤 | 操作 | 命令 | 预期 | 真实结果 |
|------|------|------|------|----------|
| 1 | 起容器映射 8080 与 6006 | `docker run -d --name tb-manual -p 127.0.0.1:18080:8080 -p 127.0.0.1:13306:6006 rsl_rl_isrc:v3-D` | running；B /health 就绪 | PASS；退出码 0；health=True tb=True；输出：55d4c8605d4ae58425e2346d5146a11ed0938e5ab7208e9d84c8f748129cde0e |
| 2 | HTTP TensorBoard | `curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:13306/` | HTTP 200 | PASS；HTTP 200 body=<!doctype html><meta name="tb-relative-root" content="./"><!doctype html><!--
@license
Copyright 2019 The TensorFlow Authors. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the  |
| 3 | 清理 | `docker rm -f tb-manual` | 容器删除 | PASS；退出码 0；输出：tb-manual |

## 通过标准

不经 Server A，手工端口映射也能打开 TensorBoard。
