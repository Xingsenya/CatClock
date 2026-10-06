# -*- coding: utf-8 -*-
"""A2：绘图基础工具（缓动 / 细节层级 / 统一线条）。

从 draw.py 拆出来，供 draw.py / parts.py / icons.py 共用，避免基础工具
被巨型模块绑架、也避免未来反向 import 造成循环依赖。
"""
import math  # noqa: F401 - 保留给下游 `from .gfx import math` 的旧写法

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPen

from .util import _mix, _q_luma  # noqa: F401 - 转出给下游使用


def _ease(t):
    """smoothstep：0..1 进入和退出都更柔和。"""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _ease_out(t):
    """淡入（快起慢收）。"""
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) * (1.0 - t)


def _lod(s):
    """细节层级（A7）：小尺寸自动减细节，避免线条挤成一团。
    0 = 最小尺寸（只留主结构）/ 1 = 常规 / 2 = 放大后的完整细节"""
    return 0 if s < 72 else (1 if s < 88 else 2)


def _line(color, w, join=True):
    """统一线条（A1）：圆头圆角 + 统一下限，替代各处散落的 max(1.0, s*k)。"""
    pen = QPen(color if isinstance(color, QColor) else QColor(color),
               max(0.7, float(w)))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    if join:
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen
