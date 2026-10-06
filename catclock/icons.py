# -*- coding: utf-8 -*-
"""A2：图标与小型装饰件（爱心 / 天气图标 / 托盘图标 / 爪型光标）。

从 draw.py 拆出：这些都是「一次性画好就不变」的静态图形，和 draw_cat 的
逐帧矢量绘制不是一类东西，分开后 draw.py 只关心「猫怎么画」。
"""
import math

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QLinearGradient, QRadialGradient,
    QPixmap, QFont, QIcon, QCursor,
)

from . import data as D
from .util import _mix, _q_luma
from .gfx import _ease, _ease_out, _lod, _line

# 注意：draw_cat 在 draw.py，而 draw.py 又 re-export 本模块的函数。
# 顶层直接 import 会成环，所以放到函数里延迟导入（只在真正画图标时才触发）。
def _draw_cat(p, *a, **kw):
    """转发到 draw.draw_cat（延迟导入避免与 draw.py 形成循环依赖）。"""
    from .draw import draw_cat
    return draw_cat(p, *a, **kw)

CHARACTERS = D.CHARACTERS
STYLES = D.STYLES


def heart_path(cx, cy, s):
    """心形路径（参数方程），s 为尺寸"""
    pts = []
    n = 48
    for i in range(n):
        tt = 2 * math.pi * i / n
        hx = 16 * math.sin(tt) ** 3
        hy = 13 * math.cos(tt) - 5 * math.cos(2 * tt) - 2 * math.cos(3 * tt) - math.cos(4 * tt)
        pts.append(QPointF(cx + hx * s / 34.0, cy - hy * s / 34.0))
    path = QPainterPath(pts[0])
    for pt in pts[1:]:
        path.lineTo(pt)
    path.closeSubpath()
    return path


def draw_weather_icon(p, x, y, s, kind, t=0.0):
    """右上角天气小图标"""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    def cloud_path(cx, cy, k=1.0):
        path = QPainterPath()
        path.addEllipse(QRectF(cx - 0.55 * s * k, cy - 0.16 * s * k, 0.55 * s * k, 0.42 * s * k))
        path.addEllipse(QRectF(cx - 0.18 * s * k, cy - 0.44 * s * k, 0.62 * s * k, 0.64 * s * k))
        path.addEllipse(QRectF(cx + 0.16 * s * k, cy - 0.14 * s * k, 0.50 * s * k, 0.40 * s * k))
        path.addRect(QRectF(cx - 0.55 * s * k, cy + 0.02 * s * k, 1.18 * s * k, 0.24 * s * k))
        return path

    def draw_sun(cx, cy, r):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFD34D"))
        p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#FFC53D"), max(1.2, s * 0.055), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        for i in range(8):
            a = math.radians(i * 45)
            p.drawLine(QPointF(cx + math.cos(a) * r * 1.35, cy + math.sin(a) * r * 1.35),
                       QPointF(cx + math.cos(a) * r * 1.8, cy + math.sin(a) * r * 1.8))

    def draw_cloud(cx, cy, k, fill):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(fill))
        p.drawPath(cloud_path(cx, cy, k))

    if kind == "sun":
        draw_sun(x + s * 0.5, y + s * 0.5, s * 0.30)
    elif kind == "cloud-sun":
        draw_sun(x + s * 0.28, y + s * 0.30, s * 0.20)
        draw_cloud(x + s * 0.58, y + s * 0.62, 0.9, "#F0F0F0")
    elif kind == "cloud":
        draw_cloud(x + s * 0.5, y + s * 0.55, 1.0, "#D8DDE3")
    elif kind == "fog":
        draw_cloud(x + s * 0.5, y + s * 0.40, 0.85, "#E0E4E9")
        p.setPen(QPen(QColor("#B9C2CC"), max(1.0, s * 0.05), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        for yy in (0.64, 0.80):
            p.drawLine(QPointF(x + s * 0.18, y + s * yy), QPointF(x + s * 0.82, y + s * yy))
    elif kind == "rain":
        draw_cloud(x + s * 0.5, y + s * 0.40, 0.9, "#C9D4E0")
        p.setPen(QPen(QColor("#6FA8DC"), max(1.2, s * 0.06), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        for i, dx in enumerate((0.30, 0.50, 0.70)):
            off = (t * 0.7 + i * 0.35) % 0.35
            p.drawLine(QPointF(x + s * dx, y + s * (0.58 + off)),
                       QPointF(x + s * (dx - 0.07), y + s * (0.74 + off)))
    elif kind == "snow":
        draw_cloud(x + s * 0.5, y + s * 0.40, 0.9, "#E4EAF2")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        for i, dx in enumerate((0.30, 0.50, 0.70)):
            off = (t * 0.4 + i * 0.4) % 0.30
            p.drawEllipse(QRectF(x + s * dx - s * 0.045, y + s * (0.60 + off), s * 0.09, s * 0.09))
    elif kind == "thunder":
        draw_cloud(x + s * 0.5, y + s * 0.38, 0.9, "#B9C2CE")
        bx, by = x + s * 0.5, y + s * 0.50
        bolt = QPainterPath()
        bolt.moveTo(bx - 0.02 * s, by)
        bolt.lineTo(bx + 0.20 * s, by)
        bolt.lineTo(bx + 0.06 * s, by + 0.20 * s)
        bolt.lineTo(bx + 0.24 * s, by + 0.20 * s)
        bolt.lineTo(bx - 0.08 * s, by + 0.55 * s)
        bolt.lineTo(bx + 0.02 * s, by + 0.26 * s)
        bolt.lineTo(bx - 0.14 * s, by + 0.26 * s)
        bolt.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFD34D"))
        p.drawPath(bolt)
    p.restore()


def make_icon(size=128, char=None):
    colors = CHARACTERS.get(char) or CHARACTERS["橘猫"]
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    g = QRadialGradient(size * 0.36, size * 0.30, size * 0.95)
    g.setColorAt(0, QColor("#FFF8EF"))
    g.setColorAt(1, QColor("#FFD3AC"))
    p.setBrush(g)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(1.5, 1.5, size - 3, size - 3))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor("#FFC496"), size * 0.018))
    p.drawEllipse(QRectF(2, 2, size - 4, size - 4))
    _draw_cat(p, size / 2, size * 0.56, size * 0.82, colors)
    p.end()
    return QIcon(pm)


def make_tray_icon(size=64, char=None, text=""):
    """F4：托盘图标 —— 猫头 + 底部胶囊显示剩余时间（如 38 / 1h20）。"""
    colors = CHARACTERS.get(char) or CHARACTERS["橘猫"]
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    g = QRadialGradient(size * 0.36, size * 0.30, size * 0.95)
    g.setColorAt(0, QColor("#FFF8EF"))
    g.setColorAt(1, QColor("#FFD3AC"))
    p.setBrush(g)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(1.5, 1.5, size - 3, size - 3))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor("#FFC496"), size * 0.018))
    p.drawEllipse(QRectF(2, 2, size - 4, size - 4))
    if text:
        _draw_cat(p, size / 2, size * 0.46, size * 0.66, colors)
        # 底部胶囊：深色底 + 白字，小尺寸下也尽量能认出数字
        h = size * 0.28
        w = min(size - 3.0, max(size * 0.44, len(text) * size * 0.20))
        x, y = (size - w) / 2.0, size - h - 1.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(38, 32, 30, 232))
        p.drawRoundedRect(QRectF(x, y, w, h), h * 0.36, h * 0.36)
        p.setPen(QColor("#FFFFFF"))
        f = QFont("Segoe UI", int(size * (0.19 if len(text) <= 2 else 0.15)))
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(QRectF(x, y, w, h), Qt.AlignmentFlag.AlignCenter, text)
    else:
        _draw_cat(p, size / 2, size * 0.56, size * 0.82, colors)
    p.end()
    return QIcon(pm)


def make_paw_cursor(size=32):
    """E3：猫爪光标（程序绘制，不额外占资源体积）。热点放在爪心偏上。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    u = size / 32.0
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor("#4A3B33"), 1.5 * u)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(QColor("#FFF3E4"))
    p.drawEllipse(QRectF(9.0 * u, 14.0 * u, 14.0 * u, 11.0 * u))   # 掌垫
    for tx, ty, r in ((7.5, 9.0, 3.1), (12.5, 5.6, 3.3), (19.5, 5.6, 3.3), (24.5, 9.4, 3.1)):
        p.drawEllipse(QRectF((tx - r) * u, (ty - r) * u, 2 * r * u, 2 * r * u))
    p.end()
    return QCursor(pm, int(16 * u), int(7 * u))
