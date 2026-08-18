"""容器常驻画面转发：本机收 ObsInstrServer 的 HTTP 中继，再 PUB 给宿主机。"""

from obsserver.transform import transform

__all__ = ["transform"]
