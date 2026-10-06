# -*- coding: utf-8 -*-
"""A2：猫的各部件绘制（爪 / 手 / 手臂 / 帽子 / 配饰 / 道具）。

从 draw.py 拆出：draw.py 只保留 draw_cat 主流程，部件细节集中在这里，
改帽子或加道具时不用再在 1800 行的文件里翻。
"""
import math

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QLinearGradient, QRadialGradient,
    QFont,
)

from . import data as D
from .util import _mix, _q_luma
from .data import (_HEAD, _EYE, _EYE_DEFAULT, _TAIL, _HAND, _HAT, _HAT_EXT,
                   _BODY_SHAPE, _TOP_EXT)
from .gfx import _ease, _ease_out, _lod, _line

CHARACTERS = D.CHARACTERS
STYLES = D.STYLES


def _draw_paw(p, x, y, s, colors, outline, r):
    """标准掌心朝上的猫爪（局部标准方向：肉垫在 y- 侧）。由 _draw_hand 统一旋转。"""
    p.setPen(outline)
    p.setBrush(QColor(colors["fur_l"]))
    p.drawEllipse(QRectF(x - r, y - r * 0.94, 2 * r, 1.88 * r))
    # 小趾垫（在椭圆上方，即掌心侧）
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(colors["nose"]))
    for dx in (-0.50, 0.0, 0.50):
        p.drawEllipse(QRectF(x + dx * r - r * 0.19, y - r * 1.06,
                             r * 0.38, r * 0.34))
    # 大肉垫（心形，在掌心侧）
    pad = QPainterPath()
    pad.moveTo(x - r * 0.44, y - r * 0.50)
    pad.quadTo(x - r * 0.50, y - r * 1.00, x, y - r * 1.10)
    pad.quadTo(x + r * 0.50, y - r * 1.00, x + r * 0.44, y - r * 0.50)
    pad.quadTo(x, y - r * 0.30, x - r * 0.44, y - r * 0.50)
    pad.closeSubpath()
    p.drawPath(pad)
    # 高光
    p.setBrush(QColor(255, 255, 255, 90))
    p.drawEllipse(QRectF(x - r * 0.26, y - r * 0.66, r * 0.22, r * 0.16))


def _draw_hand(p, x, y, s, colors, outline, kind="paw", palm_nx=0, palm_ny=1):
    """按物种画手。x,y 为腕点；手掌从腕点沿掌心法向伸出，并与手腕圆润融合。
    掌心法向 (palm_nx,palm_ny)：(0,-1)=掌心朝上，(0,1)=掌心朝下，(±1,0)=掌心朝身体侧。
    kind: paw / dog_paw / hoof / cloven / monkey / wing / claw / fingers / puff_paw / none。
    """
    if kind == "none":
        return
    L = math.hypot(palm_nx, palm_ny)
    if L < 0.001:
        nx, ny = 0.0, -1.0
    else:
        nx, ny = palm_nx / L, palm_ny / L
    r = s * 0.105
    # 手掌中心：从腕点沿掌心法向伸出，让手腕嵌入手掌内部
    hx = x + nx * r * 0.55
    hy = y + ny * r * 0.55
    p.save()
    p.translate(hx, hy)
    angle = math.degrees(math.atan2(nx, -ny))
    p.rotate(angle)
    p.translate(-hx, -hy)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    wr_w = s * 0.10
    lw = outline.widthF() if isinstance(outline, QPen) else max(0.9, s * 0.017)
    base_col = _mix(colors["fur_l"], "#FFFFFF", 0.06)
    pad_col = colors.get("nose") or colors.get("ear_in") or "#E8A3A3"
    detail = _lod(s)          # A7：按实际绘制尺寸分级（原阈值 120/200 永远取不到）

    # 腕球：与手臂末端同色，盖住手臂-手掌接缝
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(base_col))
    p.drawEllipse(QRectF(x - wr_w * 0.55, y - wr_w * 0.55,
                         wr_w * 1.10, wr_w * 1.10))

    # 手掌主体：圆润拳套 + 趾瓣（不再是光溜溜的蛋）
    a, b = r * 0.92, r * 0.74
    lobes = {"paw": 3, "dog_paw": 4, "monkey": 4, "fingers": 4,
             "puff_paw": 2, "claw": 3}.get(kind, 0)
    hp = QPainterPath()
    hp.addEllipse(QRectF(hx - a, hy - b, a * 2, b * 2))
    if lobes and detail >= 1:
        lr = r * 0.34
        for i in range(lobes):
            t2 = (i / (lobes - 1) - 0.5) if lobes > 1 else 0.0
            hp.addEllipse(QRectF(hx + t2 * a * 1.15 - lr, hy - b * 0.62 - lr,
                                 lr * 2, lr * 2))
        if detail >= 2 and kind in ("paw", "dog_paw", "monkey"):
            tr = r * 0.26                       # 拇指（掌心侧偏外）
            hp.addEllipse(QRectF(hx - a * 0.88 - tr, hy - b * 0.10 - tr,
                                 tr * 2, tr * 2))
        hp = hp.simplified()
    p.setPen(outline)
    p.setBrush(QColor(base_col))
    p.drawPath(hp)

    if kind == "hoof":                                  # 马 / 牛 / 羊：单蹄
        hc = _mix(colors["fur_d"], "#3B2A22", 0.42)
        p.setBrush(QColor(hc))
        p.drawRoundedRect(QRectF(hx - r * 0.74, hy + r * 0.18,
                                 r * 1.48, r * 1.16), r * 0.38, r * 0.38)
        if detail >= 1:
            p.setPen(_line(_mix(hc, "#000000", 0.30), lw * 0.80))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(QPointF(hx, hy + r * 0.30), QPointF(hx, hy + r * 0.92))
    elif kind == "cloven":                              # 猪：两瓣蹄
        hc = _mix(colors["fur_d"], "#3B2A22", 0.28)
        p.setBrush(QColor(hc))
        for dx in (-0.38, 0.38):
            p.drawRoundedRect(QRectF(hx + dx * r - r * 0.30, hy + r * 0.22,
                                     r * 0.60, r * 1.12), r * 0.26, r * 0.26)
    elif kind == "monkey":                              # 猴：肉色掌 + 四指
        pc = colors.get("ear_in") or "#F5CBA7"
        p.setPen(outline)
        p.setBrush(QColor(pc))
        p.drawEllipse(QRectF(hx - r * 0.82, hy - r * 0.72, r * 1.64, r * 1.44))
        if detail >= 1:
            p.setPen(_line(_mix(pc, "#6B4A33", 0.45), lw * 0.82))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for dx in (-0.50, -0.17, 0.17, 0.50):
                p.drawLine(QPointF(hx + dx * r, hy - r * 0.60),
                           QPointF(hx + dx * r * 1.08, hy - r * 0.94))
    elif kind == "wing":                                # 鸡：翅膀
        wc = colors.get("comb") or colors["fur_d"]
        p.setBrush(QColor(colors["fur_l"]))
        wp = QPainterPath()
        wp.moveTo(hx - r * 0.22, hy - r * 0.72)
        wp.quadTo(hx + r * 0.86, hy - r * 0.28, hx + r * 0.42, hy + r * 0.74)
        wp.quadTo(hx + r * 0.04, hy + r * 0.40, hx - r * 0.22, hy + r * 0.22)
        wp.closeSubpath()
        p.drawPath(wp)
        if detail >= 1:
            p.setPen(_line(QColor(wc), lw * 0.80))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for k in (0.20, 0.54, 0.88):
                p.drawLine(QPointF(hx - r * 0.08 + r * k * 0.22,
                                   hy - r * 0.34 + r * k * 0.26),
                           QPointF(hx + r * 0.44, hy - r * 0.42 + r * k * 1.04))
    elif kind == "claw":                                # 龙：掌 + 三爪
        p.setBrush(QColor(colors["fur_l"]))
        p.drawEllipse(QRectF(hx - r * 0.78, hy - r * 0.76,
                             r * 1.56, r * 1.52))
        p.setPen(outline)
        p.setBrush(QColor(colors["fur_d"]))
        for dx in (-0.50, 0.0, 0.50):
            tri = QPainterPath()
            tri.moveTo(hx + dx * r - r * 0.18, hy - r * 0.44)
            tri.lineTo(hx + dx * r + r * 0.18, hy - r * 0.44)
            tri.lineTo(hx + dx * r, hy - r * 0.98)
            tri.closeSubpath()
            p.drawPath(tri)
    elif kind == "fingers":                             # 鼠：细指
        p.setBrush(QColor(colors["fur_l"]))
        p.drawEllipse(QRectF(hx - r * 0.74, hy - r * 0.70,
                             r * 1.48, r * 1.40))
        if detail >= 1:
            p.setPen(_line(outline.color(), lw * 0.92))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for dx in (-0.52, -0.17, 0.17, 0.52):
                p.drawLine(QPointF(hx + dx * r * 0.82, hy - r * 0.28),
                           QPointF(hx + dx * r * 1.00, hy - r * 0.88))
    elif kind == "puff_paw":                            # 兔：绒掌
        p.setBrush(QColor(colors["fur_l"]))
        p.drawEllipse(QRectF(hx - r * 0.74, hy - r * 0.70,
                             r * 1.48, r * 1.40))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(pad_col))
        p.drawEllipse(QRectF(hx - r * 0.24, hy - r * 0.42,
                             r * 0.48, r * 0.36))
    elif kind == "dog_paw":                             # 狗：四趾 + 大肉垫
        p.setBrush(QColor(colors["fur_l"]))
        p.drawEllipse(QRectF(hx - r * 0.88, hy - r * 0.82,
                             r * 1.76, r * 1.64))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(pad_col))
        for dx in (-0.54, -0.18, 0.18, 0.54):
            p.drawEllipse(QRectF(hx + dx * r - r * 0.13, hy - r * 0.86,
                                 r * 0.26, r * 0.26))
        p.drawEllipse(QRectF(hx - r * 0.40, hy - r * 0.50,
                             r * 0.80, r * 0.66))
        if detail >= 2:
            p.setBrush(QColor(255, 255, 255, 80))
            p.drawEllipse(QRectF(hx - r * 0.26, hy - r * 0.34,
                                 r * 0.22, r * 0.15))
    else:                                               # paw：猫爪
        p.setBrush(QColor(colors["fur_l"]))
        p.drawEllipse(QRectF(hx - r * 0.86, hy - r * 0.82,
                             r * 1.72, r * 1.64))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(pad_col))
        # 大肉垫
        pad = QPainterPath()
        pad.moveTo(hx - r * 0.36, hy - r * 0.42)
        pad.quadTo(hx - r * 0.42, hy - r * 0.82, hx, hy - r * 0.92)
        pad.quadTo(hx + r * 0.42, hy - r * 0.82, hx + r * 0.36, hy - r * 0.42)
        pad.quadTo(hx, hy - r * 0.26, hx - r * 0.36, hy - r * 0.42)
        pad.closeSubpath()
        p.drawPath(pad)
        if detail >= 1:
            for dx in (-0.42, 0.0, 0.42):
                p.drawEllipse(QRectF(hx + dx * r - r * 0.15, hy - r * 0.88,
                                     r * 0.30, r * 0.26))
        if detail >= 2:
            p.setBrush(QColor(255, 255, 255, 80))
            p.drawEllipse(QRectF(hx - r * 0.22, hy - r * 0.56,
                                 r * 0.18, r * 0.13))
    p.restore()


def _draw_arm(p, sx, sy, ex, ey, bx, by, s, colors, outline):
    """锥形手臂：肩部粗、腕部细，与手掌自然过渡。手臂末端到达腕点 (ex,ey)。"""
    sh_w = s * 0.18
    wr_w = s * 0.10
    n = 24
    left, right = [], []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt * mt * sx + 2 * mt * t * bx + t * t * ex
        y = mt * mt * sy + 2 * mt * t * by + t * t * ey
        tx = 2 * mt * (bx - sx) + 2 * t * (ex - bx)
        ty = 2 * mt * (by - sy) + 2 * t * (ey - by)
        L = math.hypot(tx, ty)
        if L < 0.001:
            nx, ny = 0, 1
        else:
            nx, ny = -ty / L, tx / L
        w = sh_w * (1 - t) + wr_w * t
        left.append((x + nx * w * 0.5, y + ny * w * 0.5))
        right.append((x - nx * w * 0.5, y - ny * w * 0.5))
    path = QPainterPath()
    path.moveTo(left[0][0], left[0][1])
    for pt in left[1:]:
        path.lineTo(pt[0], pt[1])
    for pt in reversed(right):
        path.lineTo(pt[0], pt[1])
    path.closeSubpath()
    g = QLinearGradient(sx, sy, ex, ey)
    g.setColorAt(0, QColor(colors["fur"]))
    g.setColorAt(1, QColor(colors["fur_l"]))
    p.setPen(outline)
    p.setBrush(g)
    p.drawPath(path)
    # 肩部圆球：抹掉手臂根部与身体之间的硬接缝
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(colors["fur"]))
    p.drawEllipse(QRectF(sx - sh_w * 0.40, sy - sh_w * 0.40,
                         sh_w * 0.80, sh_w * 0.80))


def _draw_hat(p, cx, cy, s, colors, outline, style, head_top, hw=0.88, t=0.0):
    """头顶帽子。style: cap / beanie / beret / straw / party / crown / santa / cny。"""
    if style == "none":
        return
    top = head_top
    lw = outline.widthF() if isinstance(outline, QPen) else max(0.9, s * 0.017)
    p.setPen(outline)
    if style == "cap":
        # 棒球帽：圆顶 + 前挑帽檐 + 顶纽
        cap_c = "#E8734A"
        dome = QPainterPath()
        dome.moveTo(cx - 0.40 * s, top + 0.16 * s)
        dome.cubicTo(cx - 0.42 * s, top - 0.06 * s,
                     cx + 0.42 * s, top - 0.06 * s,
                     cx + 0.40 * s, top + 0.16 * s)
        dome.quadTo(cx, top + 0.26 * s, cx - 0.40 * s, top + 0.16 * s)
        dome.closeSubpath()
        p.setBrush(QColor(cap_c))
        p.drawPath(dome)
        brim = QPainterPath()
        brim.moveTo(cx + 0.02 * s, top + 0.13 * s)
        brim.quadTo(cx + 0.36 * s, top + 0.06 * s, cx + 0.52 * s, top + 0.16 * s)
        brim.quadTo(cx + 0.36 * s, top + 0.22 * s, cx + 0.02 * s, top + 0.21 * s)
        brim.closeSubpath()
        p.setBrush(QColor(_mix(cap_c, "#000000", 0.18)))
        p.drawPath(brim)
        p.setBrush(QColor(cap_c))
        p.drawEllipse(QRectF(cx - 0.045 * s, top - 0.075 * s, 0.09 * s, 0.075 * s))
    elif style == "beanie":
        # 毛线帽：圆顶 + 翻边 + 绒球
        bean_c = "#7FA8D9"
        dome = QPainterPath()
        dome.moveTo(cx - 0.40 * s, top + 0.14 * s)
        dome.cubicTo(cx - 0.42 * s, top - 0.12 * s,
                     cx + 0.42 * s, top - 0.12 * s,
                     cx + 0.40 * s, top + 0.14 * s)
        dome.closeSubpath()
        p.setBrush(QColor(bean_c))
        p.drawPath(dome)
        p.setBrush(QColor(_mix(bean_c, "#FFFFFF", 0.25)))
        p.drawRoundedRect(QRectF(cx - 0.41 * s, top + 0.07 * s,
                                 0.82 * s, 0.13 * s), 0.05 * s, 0.05 * s)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(cx - 0.085 * s, top - 0.23 * s, 0.17 * s, 0.15 * s))
    elif style == "beret":
        # 贝雷帽：扁圆盘斜戴 + 小茎
        ber_c = "#B14A5A"
        p.save()
        p.translate(cx - 0.06 * s, top + 0.02 * s)
        p.rotate(-8)
        p.setBrush(QColor(ber_c))
        p.drawEllipse(QRectF(-0.42 * s, -0.13 * s, 0.84 * s, 0.26 * s))
        p.setBrush(QColor(_mix(ber_c, "#000000", 0.15)))
        p.drawEllipse(QRectF(-0.30 * s, -0.04 * s, 0.60 * s, 0.10 * s))
        p.restore()
        p.setBrush(QColor(_mix(ber_c, "#000000", 0.3)))
        p.drawEllipse(QRectF(cx - 0.10 * s, top - 0.135 * s, 0.08 * s, 0.06 * s))
    elif style == "straw":
        # 草帽：宽檐 + 浅 dome + 带子
        st_c = "#E8C87E"
        p.setBrush(QColor(_mix(st_c, "#000000", 0.12)))
        p.drawEllipse(QRectF(cx - 0.58 * s, top - 0.015 * s, 1.16 * s, 0.13 * s))
        dome = QPainterPath()
        dome.moveTo(cx - 0.30 * s, top + 0.03 * s)
        dome.cubicTo(cx - 0.32 * s, top - 0.14 * s,
                     cx + 0.32 * s, top - 0.14 * s,
                     cx + 0.30 * s, top + 0.03 * s)
        dome.closeSubpath()
        p.setBrush(QColor(st_c))
        p.drawPath(dome)
        p.setBrush(QColor("#D65A5A"))
        p.drawRoundedRect(QRectF(cx - 0.30 * s, top - 0.035 * s,
                                 0.60 * s, 0.075 * s), 0.03 * s, 0.03 * s)
    elif style == "party":
        # 派对帽：斜锥 + 白条纹 + 绒球
        cone_c = "#7FB5E8"
        p.setBrush(QColor(cone_c))
        cone = QPainterPath()
        cone.moveTo(cx - 0.30 * s, top + 0.10 * s)
        cone.lineTo(cx + 0.06 * s, top - 0.40 * s)
        cone.lineTo(cx + 0.30 * s, top + 0.10 * s)
        cone.closeSubpath()
        p.drawPath(cone)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        for k in (0.30, 0.58):       # 两条斜向白纹
            yb = top + 0.10 * s - k * 0.50 * s
            p.drawEllipse(QRectF(cx - 0.30 * s + k * 0.36 * s - 0.11 * s, yb - 0.028 * s,
                                 0.22 * s, 0.056 * s))
        p.setPen(outline)
        p.setBrush(QColor("#FFD666"))
        p.drawEllipse(QRectF(cx - 0.02 * s, top - 0.50 * s, 0.16 * s, 0.14 * s))
    elif style == "crown":
        # 皇冠：金圈 + 三尖 + 宝石
        gd_c = "#F2C14E"
        p.setBrush(QColor(gd_c))
        band = QPainterPath()
        band.moveTo(cx - 0.30 * s, top + 0.10 * s)
        band.lineTo(cx - 0.30 * s, top - 0.02 * s)
        band.lineTo(cx - 0.15 * s, top + 0.05 * s)
        band.lineTo(cx, top - 0.10 * s)
        band.lineTo(cx + 0.15 * s, top + 0.05 * s)
        band.lineTo(cx + 0.30 * s, top - 0.02 * s)
        band.lineTo(cx + 0.30 * s, top + 0.10 * s)
        band.closeSubpath()
        p.drawPath(band)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#E85A6E"))
        p.drawEllipse(QRectF(cx - 0.045 * s, top + 0.015 * s, 0.09 * s, 0.09 * s))
        p.setBrush(QColor(255, 255, 255, 90))
        p.drawEllipse(QRectF(cx - 0.26 * s, top - 0.01 * s, 0.07 * s, 0.05 * s))
    elif style == "santa":
        # 圣诞帽：红圆顶 + 白翻边 + 大白绒球
        red = "#C0392B"
        white = "#F2F0EC"
        p.setPen(outline)
        dome = QPainterPath()
        dome.moveTo(cx - 0.38 * s, top + 0.12 * s)
        dome.cubicTo(cx - 0.40 * s, top - 0.18 * s,
                     cx + 0.05 * s, top - 0.26 * s,
                     cx + 0.18 * s, top - 0.36 * s)
        dome.cubicTo(cx + 0.22 * s, top - 0.16 * s,
                     cx + 0.40 * s, top - 0.06 * s,
                     cx + 0.38 * s, top + 0.12 * s)
        dome.closeSubpath()
        p.setBrush(QColor(red))
        p.drawPath(dome)
        p.setBrush(QColor(white))
        p.drawRoundedRect(QRectF(cx - 0.39 * s, top + 0.06 * s,
                                 0.78 * s, 0.14 * s), 0.06 * s, 0.06 * s)
        p.drawEllipse(QRectF(cx + 0.10 * s, top - 0.46 * s, 0.16 * s, 0.14 * s))
    elif style == "cny":
        # 春节福帽：红圆顶 + 金边 + 金色福字 + 顶球
        red = "#C62D2D"
        gold = "#E8B923"
        p.setPen(outline)
        p.setBrush(QColor(red))
        dome = QPainterPath()
        dome.moveTo(cx - 0.40 * s, top + 0.12 * s)
        dome.cubicTo(cx - 0.40 * s, top - 0.10 * s,
                     cx + 0.40 * s, top - 0.10 * s,
                     cx + 0.40 * s, top + 0.12 * s)
        dome.closeSubpath()
        p.drawPath(dome)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(_line(QColor(gold), lw * 1.18))
        p.drawEllipse(QRectF(cx - 0.38 * s, top + 0.05 * s, 0.76 * s, 0.12 * s))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(gold))
        p.drawEllipse(QRectF(cx - 0.085 * s, top - 0.22 * s, 0.17 * s, 0.15 * s))
        p.setFont(QFont("Microsoft YaHei", int(s * 0.13), QFont.Weight.Bold))
        p.setPen(_line(QColor(gold), lw * 0.71))
        p.drawText(QRectF(cx - 0.22 * s, top - 0.03 * s, 0.44 * s, 0.20 * s),
                   Qt.AlignmentFlag.AlignCenter, "福")
    elif style == "witch":
        # 万圣巫师帽：黑尖顶（微弯）+ 紫宽檐 + 金扣带
        p.setPen(outline)
        blk = "#3B2F45"
        cone = QPainterPath()
        cone.moveTo(cx - 0.36 * s, top + 0.10 * s)
        cone.cubicTo(cx - 0.30 * s, top - 0.10 * s,
                     cx + 0.02 * s, top - 0.24 * s,
                     cx + 0.30 * s, top - 0.52 * s)
        cone.cubicTo(cx + 0.20 * s, top - 0.20 * s,
                     cx + 0.36 * s, top - 0.02 * s,
                     cx + 0.36 * s, top + 0.10 * s)
        cone.closeSubpath()
        p.setBrush(QColor(blk))
        p.drawPath(cone)
        p.setBrush(QColor("#7B4BA8"))
        p.drawEllipse(QRectF(cx - 0.52 * s, top + 0.06 * s, 1.04 * s, 0.17 * s))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#E8B923"))
        p.drawRoundedRect(QRectF(cx - 0.34 * s, top + 0.05 * s,
                                 0.68 * s, 0.09 * s), 0.03 * s, 0.03 * s)


def _draw_acc(p, cx, cy, s, colors, outline, style, head_top):
    """配饰：眼镜 / 墨镜 / 耳机 / 领结，在帽子之后、胡须之前绘制。"""
    if not style or style == "auto" or style == "none":
        return
    line_c = colors.get("line", "#4A3B33")
    lw = outline.widthF() if isinstance(outline, QPen) else max(0.9, s * 0.017)
    if style == "glasses":
        r = s * 0.18
        p.setPen(_line(QColor(line_c), lw * 0.82))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for sign in (-1, 1):
            p.drawEllipse(QRectF(cx + sign * 0.175 * s - r,
                                 cy - 0.02 * s - r * 0.85,
                                 r * 2, r * 1.7))
        p.drawLine(QPointF(cx - 0.05 * s, cy - 0.05 * s),
                   QPointF(cx + 0.05 * s, cy - 0.05 * s))
    elif style == "sunglasses":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2A2520"))
        for sign in (-1, 1):
            p.drawEllipse(QRectF(cx + sign * 0.17 * s - s * 0.15,
                                 cy - 0.03 * s - s * 0.11,
                                 s * 0.30, s * 0.22))
        p.drawRect(QRectF(cx - s * 0.05, cy - s * 0.08, s * 0.10, s * 0.04))
    elif style == "headphones":
        cup = "#3A3A3A"
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(cup))
        for sign in (-1, 1):
            p.drawEllipse(QRectF(cx + sign * 0.44 * s - s * 0.09,
                                 cy - 0.05 * s - s * 0.14,
                                 s * 0.18, s * 0.28))
        p.setPen(_line(QColor(cup), lw * 1.18))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(cx - 0.44 * s, cy - 0.42 * s, 0.88 * s, 0.50 * s),
                  0, 180 * 16)
    elif style == "bowtie":
        p.setPen(outline)
        p.setBrush(QColor("#E85A6E"))
        bx, by = cx, cy + 0.32 * s
        w, h = s * 0.18, s * 0.10
        tri1 = QPainterPath()
        tri1.moveTo(bx, by)
        tri1.lineTo(bx - w, by - h)
        tri1.lineTo(bx - w, by + h)
        tri1.closeSubpath()
        p.drawPath(tri1)
        tri2 = QPainterPath()
        tri2.moveTo(bx, by)
        tri2.lineTo(bx + w, by - h)
        tri2.lineTo(bx + w, by + h)
        tri2.closeSubpath()
        p.drawPath(tri2)
        p.setBrush(QColor("#C43E54"))
        p.drawEllipse(QRectF(bx - s * 0.03, by - s * 0.03, s * 0.06, s * 0.06))



def _draw_prop(p, prop, cx, cy, s, colors, side=None, wx=None, wy=None):
    """画半身状态道具。双手道具用 cx,cy；单手道具用 wx,wy 并参考 side('L'/'R')。"""
    line_c = colors.get("line", "#4A3B33")
    lw = max(0.9, s * 0.017)          # 与主描边同体系（A1）
    if prop == "coffee":
        bw, bh = s * 0.32, s * 0.24
        bx, by = cx - bw / 2, cy + s * 0.76
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#F8F5F0"))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), s * 0.04, s * 0.04)
        # 杯口液体
        p.setBrush(QColor("#6B4C35"))
        p.drawEllipse(QRectF(bx + s * 0.02, by - s * 0.04,
                             bw - s * 0.04, s * 0.08))
        # 把手
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(_line(QColor("#D4CFC7"), lw * 1.06))
        p.drawArc(QRectF(bx + bw - s * 0.03, by + s * 0.04,
                         s * 0.10, s * 0.14), 0, 180 * 16)
        # 热气
        steam = QColor("#FFFFFF")
        steam.setAlpha(120)
        p.setPen(_line(steam, lw * 0.71))
        for dx in (-s * 0.06, 0, s * 0.06):
            p.drawArc(QRectF(cx + dx - s * 0.03, by - s * 0.14,
                             s * 0.06, s * 0.10), 0, 180 * 16)
    elif prop == "coin":
        r = s * 0.14
        x, y = cx, cy + s * 0.76
        p.setPen(_line(QColor("#B8860B"), lw * 0.82))
        p.setBrush(QColor("#FFD700"))
        p.drawEllipse(QRectF(x - r, y - r, r * 2, r * 2))
        p.setBrush(QColor("#F4C430"))
        p.drawEllipse(QRectF(x - r * 0.78, y - r * 0.78,
                             r * 1.56, r * 1.56))
        p.setPen(_line(QColor("#B8860B"), lw * 0.71))
        p.setFont(QFont("Segoe UI", int(s * 0.14), QFont.Weight.Bold))
        p.drawText(QRectF(x - r, y - r, r * 2, r * 2),
                   Qt.AlignmentFlag.AlignCenter, "¥")
    elif prop == "heart":
        sz = s * 0.30
        y = cy + s * 0.78
        p.setPen(_line(QColor("#C9426B"), lw * 0.82))
        p.setBrush(QColor("#F06B8A"))
        p.drawPath(heart_path(cx, y, sz))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 130))
        p.drawEllipse(QRectF(cx - sz * 0.40, y - sz * 0.44, sz * 0.20, sz * 0.16))
    elif prop == "bag":
        if wx is None or wy is None:
            return
        bw, bh = s * 0.22, s * 0.26
        bx = wx - bw * (0.2 if side == "R" else 0.8)
        by = wy + s * 0.06
        bag_c = colors.get("bag", "#C49A6C")
        p.setPen(_line(QColor(line_c), lw * 0.82))
        p.setBrush(QColor(bag_c))
        body = QPainterPath()
        body.moveTo(bx + bw * 0.15, by)
        body.lineTo(bx + bw * 0.85, by)
        body.lineTo(bx + bw, by + bh)
        body.lineTo(bx, by + bh)
        body.closeSubpath()
        p.drawPath(body)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(_line(QColor(line_c), lw * 0.94))
        p.drawArc(QRectF(bx + bw * 0.25, by - s * 0.08,
                         bw * 0.50, s * 0.12), 0, 180 * 16)
    elif prop == "fan":
        if wx is None or wy is None:
            return
        fx = wx + (s * 0.08 if side == "R" else -s * 0.08)
        fy = wy - s * 0.12
        r = s * 0.18
        p.setPen(_line(QColor(line_c), lw * 0.82))
        p.setBrush(QColor("#F8C3CD"))
        # 扇面：半扇形
        start = -150 * 16 if side == "R" else -30 * 16
        span = 120 * 16 if side == "R" else -120 * 16
        p.drawPie(QRectF(fx - r, fy - r * 0.55, r * 2, r * 1.45), start, span)
        # 扇骨
        p.setPen(_line(_mix(line_c, "#FFFFFF", 0.35), lw * 0.59))
        base_angs = (-160, -130, -100) if side == "R" else (-80, -50, -20)
        for ang in base_angs:
            rad = math.radians(ang)
            p.drawLine(QPointF(fx, fy),
                       QPointF(fx + math.cos(rad) * r * 0.9,
                               fy + math.sin(rad) * r * 0.9))
        # 柄
        p.setPen(_line(QColor(line_c), lw * 1.06))
        p.drawLine(QPointF(fx, fy), QPointF(wx, wy))
    elif prop == "umbrella":
        if wx is None or wy is None:
            return
        ux, uy = cx, cy - s * 0.38
        r = s * 0.32
        p.setPen(_line(QColor(line_c), lw * 0.82))
        p.setBrush(QColor("#F8C3CD"))
        p.drawEllipse(QRectF(ux - r, uy - r * 0.40, r * 2, r * 1.20))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(_line(QColor("#E89AAA"), lw * 0.94))
        p.drawArc(QRectF(ux - r * 0.92, uy + r * 0.12,
                         r * 1.84, r * 0.50), 0, 180 * 16)
        p.setPen(_line(QColor(line_c), lw * 1.06))
        p.drawLine(QPointF(ux, uy + r * 0.18), QPointF(wx, wy))
    elif prop == "scarf":
        # 围巾绕脖子，暖红色
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#D65A5A"))
        p.drawEllipse(QRectF(cx - s * 0.38, cy + s * 0.22,
                             s * 0.22, s * 0.18))
        p.drawEllipse(QRectF(cx + s * 0.16, cy + s * 0.22,
                             s * 0.22, s * 0.18))
        mid = QPainterPath()
        mid.moveTo(cx - s * 0.28, cy + s * 0.24)
        mid.quadTo(cx, cy + s * 0.36, cx + s * 0.28, cy + s * 0.24)
        mid.lineTo(cx + s * 0.26, cy + s * 0.32)
        mid.quadTo(cx, cy + s * 0.42, cx - s * 0.26, cy + s * 0.32)
        mid.closeSubpath()
        p.drawPath(mid)
