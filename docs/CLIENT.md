# 客户端接入说明

这份文档给 **子网里的另一台机器** 用，一般是一台 **Ubuntu 笔记本**：上面跑你的 Python / Qt 程序。笔记本 **不用装 Docker、不用装显卡驱动、不用管训练机器内部**。

笔记本只做四件事：登录、把网盘挂到本机、让平台去开训、把画面订阅过来显示。

---

## 0. 你按这张表做就行

平台地址：`http://10.213.35.42:8017`  
网盘机器：`10.250.30.115`  
笔记本要和它们在同一网段（`10.x`），能 ping 通。

| 顺序 | 你在笔记本上做什么 | 程序帮你调什么 | 抄哪一节 | 成功之后你手里有什么 | 下一步 |
|------|--------------------|----------------|----------|----------------------|--------|
| 1 | 输入账号密码，点登录 | `POST /login` | **§2.2 登录** | 通行证 `token`；网盘主机和路径 | 去挂网盘 |
| 2 | 把网盘挂到本机一个文件夹 | 本机 `mount` | **§3 挂网盘**（命令在 §3.2，Python §3.3，Qt §3.4） | 例如能打开 `/mnt/nfs/carol` | 把脚本拷进去 |
| 3 | 把训练脚本拷进该文件夹的 `jobs/` | 不用调平台，就是拷文件 | 无（本机拷文件） | 例如本机能看见 `jobs/train.py` | 去启动环境 |
| 4 | 点「启动训练环境」，GPU 数量填你要用的卡数 | `POST /containers/start` | **§2.3 启动环境** | **发命令的地址**、**看画面的地址** | 可先连画面 |
| 5 | 点「连接画面」（建议先连再开训） | 用看画面的地址做 ZMQ 订阅 | **§4 看画面** | 窗口连上了；还没开训时是空的，正常 | 去开训 |
| 6 | 点「开始训练」，脚本填 `jobs/train.py`（不要填本机绝对路径） | 对「发命令的地址」`POST /tasks/start` | **§2.5 开始训练** | 得到 `task_id`，日志开始刷，画面开始动 | 等它跑 |
| 7 | 看日志 / 画面；要停就点「停止训练」 | 问进度、拉日志见 §2.5 表；停训 `POST /tasks/{id}/stop` | **进度/日志 §2.5**；**停训 §2.6** | 停了之后环境还在，画面停在最后一帧，可以再开训 | 用完再关环境 |
| 8 | 用完点「关闭环境」 | `POST /containers/stop` | **§2.4 关闭环境** | 两个地址作废 | 下次要训从第 4 步再来 |

POST 的 curl / Python / Qt 写法都在第 **2** 节：先看 **§2.1 样板**，再打开上表对应小节复制。

可以做成按钮、不是每次都要点：

| 按钮 | 调什么 | 抄哪一节 | 干什么 |
|------|--------|----------|--------|
| 查看当前环境 | `GET /containers/current` | **§2.3**（返回和启动环境相同） | 已经启动过，把两个地址再取回来 |
| 环境是否就绪 | 对发命令的地址 `GET /health` | **§2.5** 底部「训练中查询」 | 通了再开训 |
| 卸载网盘 | 本机 `umount` | **§3.2** 最后一条 | 关环境并且不再拷文件之后再卸；训练当中不要卸 |

几条别踩：

- 网盘地址用 **登录返回的**，不要写死别人的路径。
- 开训路径写成 `jobs/train.py`，不要写成 `/mnt/nfs/carol/jobs/train.py`。
- 想看出画面，开训参数里不要带 `--no-zmq-obs`。
- 日志要在训练还在跑时拉，跑完再拉是空的。
- 「停止训练」只停这一轮；「关闭环境」才把训练环境拆掉。下次再训要重新走第 4 步。
- 看画面只连 **自己的** 看画面地址。连错就会看到别人的机器人。

---

## 1. 账号

密码都是 `{用户名}-dev`。登录成功后会告诉你该挂哪块网盘，下表只是对照：

| 用户 | 登录后网盘路径（也会在返回里给） | 笔记本上建议挂到 |
|------|----------------------------------|------------------|
| `alice` | `/mnt/dockerContainer/nfs/alice` | `/mnt/nfs/alice` |
| `bob` | `/mnt/dockerContainer/nfs/bob` | `/mnt/nfs/bob` |
| `carol` | `/mnt/dockerContainer/nfs/carol` | `/mnt/nfs/carol` |
| `dave` | `/mnt/dockerContainer/nfs/dave` | `/mnt/nfs/dave` |
| `eve` | `/mnt/dockerContainer/nfs/eve` | `/mnt/nfs/eve` |
| `frank` | `/mnt/dockerContainer/nfs/frank` | `/mnt/nfs/frank` |

通行证大约 24 小时过期，重新登录即可，已经启动的环境还在。

启动环境时 `image` 填这个固定字符串（复制即可，不用理解）：`rsl_rl_isrc:v3-C`

---

## 2. 怎么发 POST（curl / Python / Qt）

全部是 JSON。登录之后，凡是打 `http://10.213.35.42:8017` 的请求（登录除外）都要带：

```http
Authorization: Bearer <token>
```

「发命令的地址」来自第 4 步，例如 `10.213.35.42:31002`。对它发开训 / 停训 **不要** 再带上面的通行证。

`关闭环境`、`停止训练` 也是 POST，body 用 `{}`。

### 2.1 复制用的样板

**curl**

```bash
A=http://10.213.35.42:8017
# 有 token 时加：-H "Authorization: Bearer $TOKEN"
```

**Python**（笔记本自带即可，不用装别的）

```python
import json
import urllib.error
import urllib.request

A = "http://10.213.35.42:8017"

def post_json(url, body=None, token=None):
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return e.code, parsed
```

**Qt（C++）**

```cpp
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>

const QString kA = QStringLiteral("http://10.213.35.42:8017");

QNetworkReply *postJson(QNetworkAccessManager *nam,
                        const QUrl &url,
                        const QJsonObject &body,
                        const QByteArray &token = {})
{
    QNetworkRequest req(url);
    req.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
    if (!token.isEmpty())
        req.setRawHeader("Authorization", "Bearer " + token);
    return nam->post(req, QJsonDocument(body).toJson(QJsonDocument::Compact));
}

// finished 里：
// int code = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
// QJsonObject obj = QJsonDocument::fromJson(reply->readAll()).object();
```

PySide / PyQt 同样用 `QNetworkAccessManager.post`，头和 JSON 与上面一致。

### 2.2 登录 `POST /login`

```json
{"username":"carol","password":"carol-dev"}
```

成功时你要留下：`token`、`nfs_host`、`nfs_export_path`。  
如果这个账号已经有环境在跑，还会直接带回两个地址。

```bash
curl -sS -X POST "$A/login" \
  -H 'content-type: application/json' \
  -d '{"username":"carol","password":"carol-dev"}'
```

```python
code, login = post_json(f"{A}/login", {"username": "carol", "password": "carol-dev"})
token = login["token"]
nfs_host = login["nfs_host"]
nfs_export = login["nfs_export_path"]
```

```cpp
QNetworkReply *r = postJson(nam, QUrl(kA + "/login"),
    QJsonObject{{"username", "carol"}, {"password", "carol-dev"}});
```

失败一般是账号密码不对。

### 2.3 启动环境 `POST /containers/start`

```json
{"image":"rsl_rl_isrc:v3-C","gpu_count":2}
```

`gpu_count` 填要用几张卡。`cpu`、`memory` 可省略。

成功时你要留下：

| 返回字段 | 你当它是什么 |
|----------|----------------|
| `server_b_endpoint` | **发命令的地址**，后面开训/停训/拉日志都打它 |
| `obs_pub_endpoint` | **看画面的地址**，可视化连它 |

已经启动过再点一次，还是这两地址，不会另开一套。

```bash
curl -sS -X POST "$A/containers/start" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"image":"rsl_rl_isrc:v3-C","gpu_count":2}'
```

```python
code, started = post_json(
    f"{A}/containers/start",
    {"image": "rsl_rl_isrc:v3-C", "gpu_count": 2},
    token=token,
)
ep = started["server_b_endpoint"]
obs = started["obs_pub_endpoint"]
```

```cpp
QNetworkReply *r = postJson(nam, QUrl(kA + "/containers/start"),
    QJsonObject{{"image", "rsl_rl_isrc:v3-C"}, {"gpu_count", 2}},
    token);
```

若看画面的地址是空的：先关闭环境，再启动一次。

### 2.4 关闭环境 `POST /containers/stop`

```bash
curl -sS -X POST "$A/containers/stop" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{}'
```

```python
post_json(f"{A}/containers/stop", {}, token=token)
```

```cpp
postJson(nam, QUrl(kA + "/containers/stop"), QJsonObject{}, token);
```

### 2.5 开始训练（打「发命令的地址」，不要通行证）

```json
{
  "script_path": "jobs/train.py",
  "torchrun_args": ["--nproc_per_node", "2", "--standalone"],
  "script_args": []
}
```

`--nproc_per_node` 的数字要和第 4 步的 GPU 数量一致。同一时间只能跑一份训练。

```bash
curl -sS -X POST "http://$EP/tasks/start" \
  -H 'content-type: application/json' \
  -d '{"script_path":"jobs/train.py","torchrun_args":["--nproc_per_node","2","--standalone"],"script_args":[]}'
```

```python
code, task = post_json(
    f"http://{ep}/tasks/start",
    {
        "script_path": "jobs/train.py",
        "torchrun_args": ["--nproc_per_node", "2", "--standalone"],
        "script_args": [],
    },
)
task_id = task["task_id"]
```

```cpp
QNetworkReply *r = postJson(nam, QUrl(QString("http://%1/tasks/start").arg(ep)),
    QJsonObject{
        {"script_path", "jobs/train.py"},
        {"torchrun_args", QJsonArray{"--nproc_per_node", "2", "--standalone"}},
        {"script_args", QJsonArray{}},
    });
```

文件找不到、路径写成了绝对路径 → 失败。已经有一份在跑 → 先停再开。

训练中查询：

| 你想知道 | 调什么 |
|----------|--------|
| 还在跑吗 | `GET http://{发命令的地址}/tasks/{task_id}/status` |
| 日志 | `GET http://{发命令的地址}/tasks/{task_id}/logs?since=0`（下次把返回的 `next_offset` 填回去） |
| 环境通不通 | `GET http://{发命令的地址}/health` |

### 2.6 停止训练 `POST /tasks/{task_id}/stop`

只停这一轮，环境还在，画面停最后一帧。

```bash
curl -sS -X POST "http://$EP/tasks/$TASK_ID/stop" \
  -H 'content-type: application/json' -d '{}'
```

```python
post_json(f"http://{ep}/tasks/{task_id}/stop", {})
```

```cpp
postJson(nam, QUrl(QString("http://%1/tasks/%2/stop").arg(ep, taskId)), QJsonObject{});
```

---

## 3. 笔记本怎么挂网盘（Ubuntu）

训练脚本要放在网盘上，平台的训练环境才能看见。挂在 **你这台笔记本** 上，不是挂在训练机器上。

### 3.1 先装工具（做一次）

```bash
sudo apt update
sudo apt install nfs-common
```

装好后有：`showmount`、`mount`、`umount`。再确认本机能通网盘机：

```bash
ping -c 2 10.250.30.115
showmount -e 10.250.30.115
```

列表里应有登录返回的那条路径。没有 → 检查是不是连错网、是不是 VPN/Clash 把网盘 IP 拐走了。若 Clash 把 `10.250.30.115` 变成 `198.18.x.x`：

```bash
sudo ip rule add to 10.250.30.115 lookup main pref 8000
```

### 3.2 挂上（每次登录后，用返回值填）

```bash
NFS_HOST=10.250.30.115                          # 登录返回的 nfs_host
NFS_EXPORT=/mnt/dockerContainer/nfs/carol       # 登录返回的 nfs_export_path
MNT=/mnt/nfs/carol                              # 本机文件夹，自己定

sudo mkdir -p "$MNT"
sudo mount -t nfs -o vers=4 "$NFS_HOST:$NFS_EXPORT" "$MNT"

# 确认挂上了
findmnt "$MNT"
ls "$MNT/jobs"

# 用完、环境已关闭后再卸
sudo umount "$MNT"
```

文件管理器里「其它位置」去挂 NFS 往往不稳，接入请用上面这条 `mount`。

### 3.3 Python 里调挂载

```python
import subprocess

def mount_nfs(nfs_host, nfs_export, mnt):
    src = f"{nfs_host}:{nfs_export}"
    chk = subprocess.run(["findmnt", "-n", mnt], capture_output=True, text=True)
    if chk.returncode == 0 and src in (chk.stdout or ""):
        return
    subprocess.run(["sudo", "mkdir", "-p", mnt], check=True)
    subprocess.run(["sudo", "mount", "-t", "nfs", "-o", "vers=4", src, mnt], check=True)
```

没有图形密码框时，`sudo` 会要终端密码。Qt 程序更稳妥的做法：把 §3.2 命令显示给用户，让用户在终端执行；或弹出 pkexec。**不要把笔记本 sudo 密码写进程序。**

### 3.4 Qt 里调挂载

```cpp
#include <QProcess>

bool mountNfs(const QString &host, const QString &exportPath, const QString &mnt)
{
    QProcess chk;
    chk.start("findmnt", {QStringLiteral("-n"), mnt});
    chk.waitForFinished();
    if (chk.exitCode() == 0)
        return true;

    const QString src = host + ":" + exportPath;
    QProcess mk;
    mk.start("sudo", {"mkdir", "-p", mnt});
    mk.waitForFinished();
    if (mk.exitCode() != 0)
        return false;

    QProcess mntProc;
    mntProc.start("sudo", {"mount", "-t", "nfs", "-o", "vers=4", src, mnt});
    mntProc.waitForFinished();
    return mntProc.exitCode() == 0;
}
```

---

## 4. 看画面

第 4 步拿到的看画面地址形如 `10.213.35.42:32002`。笔记本用 **订阅** 去连：

```text
tcp://10.213.35.42:32002
```

订阅前缀填空。一帧是一条 UTF-8 JSON（不是带标签的文本）：

```json
[
  [[x, y, z], [qx, qy, qz, qw], [关节, ...]],
  ...
]
```

最多 64 个机器人。每一行三个数组：位置、姿态、关节。

**Python**（笔记本：`pip install pyzmq`）：

```python
import json
import zmq

host, port = obs.rsplit(":", 1)
ctx = zmq.Context()
sock = ctx.socket(zmq.SUB)
sock.setsockopt(zmq.SUBSCRIBE, b"")
sock.connect(f"tcp://{host}:{port}")
frame = json.loads(sock.recv().decode("utf-8"))
```

**Qt**：用 `cppzmq` / `nzmqt` 建 SUB，`connect("tcp://" + 看画面的地址)`，订阅空字符串，收到后当 JSON 解析。

训完没有新帧，画面停在最后一帧。同一环境再开下一轮训练，地址不变。

---

## 5. 笔记本连不上时先查这些

| 现象 | 先看 |
|------|------|
| ping 不通 `10.213.35.42` 或 `10.250.30.115` | 笔记本没进这张内网；关 VPN/Clash 或加 §3.1 那条路由 |
| 登录失败 | 账号密码；是不是打到了 `8017` 而不是别的端口 |
| 网盘挂不上 | 没装 `nfs-common`；没用登录返回的路径；`showmount -e` 没有自己那条 |
| 开训说找不到脚本 | 脚本没拷到网盘 `jobs/`；路径写成了本机绝对路径 |
| 已经有一份在跑 | 先点停止训练 |
| 有发命令的地址、画面地址是空的 | 关闭环境后再启动一次 |
| 窗口连上了但一直没机器人 | 还没开训；或开训带了 `--no-zmq-obs`；或连错了别人的画面地址 |
| 日志突然没有了 | 训练已经结束，只能在跑的时候拉 |
