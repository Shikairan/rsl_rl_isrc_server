"""发出格式的唯一修改点。默认原样拷贝。"""


def transform(payload):
    """把 HTTP 中继收到的 JSON 转成 PUB 出去的对象。

    这轮默认原样返回。以后 client 要别的样子，只改这个函数。

    默认入参/出参（与 ``ObsInstrServer._http_relay`` 一致）::

        [
          [[x, y, z], [qx, qy, qz, qw], [dof...]],
          ...
        ]

    最多 64 行由训练侧切片决定，这里不再裁。
    """
    return payload
