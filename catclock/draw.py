# -*- coding: utf-8 -*-
"""程序化矢量绘制：猫/动物、帽子、道具、天气图标、托盘图标。"""
import math

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QLinearGradient, QRadialGradient,
    QPixmap, QFont, QIcon,
)

from . import data as D
from .util import _mix, _q_luma
from .data import (_HEAD, _EYE, _EYE_DEFAULT, _TAIL, _HAND, _HAT, _HAT_EXT,
                   _BODY_SHAPE, _TOP_EXT)

CHARACTERS = D.CHARACTERS
STYLES = D.STYLES


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


def draw_cat(p, cx, cy, s, colors=None, blink=False, excited=False, sleepy=False,
             scared=False, look=(0.0, 0.0), mood=None, action=None, action_k=0.0,
             tail_phase=None, t=0.0, dim25=False, pet_k=None, ear_tw=None,
             body=False, prop=None, hat="auto", acc="auto"):
    """画一只可爱的猫脑袋。s 为整体直径；look 为瞳孔偏移(-1..1)；mood 已弃用，请用 action
    action: 待机动作（stretch/yawn/wave/tail_wag），action_k 为 0..1 进度
    tail_phase 摇尾；dim25=2.5D 模式；pet_k 摸猫进度 0..1；ear_tw=(方向±1, 进度0..1) 耳抖
    body=半身模式（圆身体+前爪）；prop=手上的道具；hat=帽子；acc=配饰"""
    if colors is None:
        colors = CHARACTERS["橘猫"]
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    cy += math.sin(t) * s * 0.018          # 呼吸浮动（上下）
    s *= 1.0 + 0.006 * math.sin(t * 1.15)  # A1：胸腔起伏，静止时也是「活的」
    # 兼容旧 mood 参数，实际统一走 action
    if action is None and mood is not None:
        action = mood
        action_k = 1.0
    if action == "sneeze":                   # 打喷嚏：先缩后弹 + 眯眼
        k = _ease(action_k)
        if k < 0.30:
            f = -0.07 * (k / 0.30)
        elif k < 0.55:
            f = 0.09 * ((k - 0.30) / 0.25)
        else:
            f = 0.09 * max(0.0, 1.0 - (k - 0.55) / 0.45)
        s *= 1.0 + f
        blink = True
    if action == "spin":                     # 追尾巴：整体转一圈
        p.translate(cx, cy)
        p.rotate(360.0 * _ease(action_k))
        p.translate(-cx, -cy)
    if action == "stretch":                  # 伸懒腰：整体放大一点 + 眯眼
        s *= 1.0 + 0.05 * _ease(action_k)
        blink = True
    if action == "tail_wag" and tail_phase is not None:
        tail_phase = _ease(action_k) * 8.0 * math.pi
    if action == "pack":                     # A2：收拾包——小幅前倾颠动，像在往包里塞东西
        k = _ease(action_k)
        b = math.sin(k * math.pi * 3.0)
        s *= 1.0 + 0.022 * b
        cy += 0.018 * s * b
        blink = k > 0.5

    lw = max(0.9, s * 0.017)                  # A1：主描边，细节线全部由它派生
    dark = _q_luma(colors["fur"]) < 0.42      # 深毛色：描边向浅色靠拢，避免糊成一团
    # A3：暗色角色描边只混 52%（原 72% 太浅，轮廓会浮起来发糊）
    line_c = _mix(colors["line"], colors["fur_l"], 0.52) if dark else QColor(colors["line"])
    outline = _line(line_c, lw)
    lod = _lod(s)                             # A7：细节层级
    rim = float(colors.get("rim", 1.0))       # A2/A3：暗色角色加强边缘光提升可读性

    # ---- 2.5D：落地软阴影（不参与倾斜） ----
    if dim25:
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 42))
        sy0 = (cy + 1.02 * s) if body else (cy + 0.35 * s)
        sw0 = 0.48 if body else 0.36
        p.drawEllipse(QRectF(cx - sw0 * s, sy0, 2 * sw0 * s, 0.105 * s))
        p.restore()
        # 2.5D：视差倾斜（随瞳孔方向） + 摸猫挤压拉伸（squash & stretch）
        p.save()
        p.translate(cx, cy)
        p.rotate(max(-1.0, min(1.0, look[0])) * 5.0)
        q = 0.0
        if pet_k is not None:
            q = math.sin(max(0.0, min(1.0, pet_k)) * math.pi)
        p.scale(1.0 - 0.045 * q, 1.0 + 0.055 * q)
        p.translate(-cx, -cy)

    shape = colors.get("shape", "cat")     # 动物脸型（默认猫）
    hw, hh, hdy = _HEAD.get(shape, (0.88, 0.86, 0.0))   # 物种头型：宽 / 高 / 中心偏移
    head_rect = QRectF(cx - hw / 2 * s, cy + (hdy - hh / 2) * s, hw * s, hh * s)
    head_top = head_rect.top()

    # ---- 尾巴（最底层；按物种分样式，不再所有角色共用猫尾） ----
    if tail_phase is not None:
        if body:
            bx, by = cx - 0.46 * s, cy + 0.66 * s
        else:
            bx, by = cx - 0.38 * s, cy + 0.32 * s
        sw = math.sin(tail_phase) * 0.18 * s
        ttype = _TAIL.get(shape, "cat")
        fd = QColor(colors["fur_d"])
        fl = QColor(colors["fur_l"])
        p.setBrush(Qt.BrushStyle.NoBrush)

        if ttype == "puff":                    # 绒球尾（兔 / 羊）
            pr = s * (0.145 if shape == "rabbit" else 0.105)
            px, py = bx - 0.09 * s, by - 0.05 * s
            ball_c = QColor(colors.get("wool") or colors["fur_l"])
            p.setPen(outline)
            p.setBrush(ball_c)
            p.drawEllipse(QRectF(px - pr, py - pr, 2 * pr, 2 * pr))
            p.setPen(Qt.PenStyle.NoPen)        # 边缘小绒毛
            for i in range(5 if lod == 0 else 7):       # A7：小尺寸少两撮，避免糊
                a = math.radians(i * 51 + 12)
                p.drawEllipse(QRectF(px + math.cos(a) * pr * 0.86 - pr * 0.33,
                                     py + math.sin(a) * pr * 0.86 - pr * 0.33,
                                     pr * 0.66, pr * 0.66))
        elif ttype == "curl_up":               # 狗：短粗上翘，摇得欢
            k = math.sin(tail_phase * 2.4) * 0.11 * s
            p.setPen(QPen(fd, max(2.4, s * 0.078), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            tp = QPainterPath()
            tp.moveTo(bx, by + 0.02 * s)
            tp.cubicTo(bx - 0.11 * s + k, by - 0.02 * s,
                       bx - 0.18 * s + k * 1.2, by - 0.22 * s,
                       bx - 0.07 * s + k * 1.5, by - 0.35 * s)
            p.drawPath(tp)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fl)
            p.drawEllipse(QRectF(bx - 0.115 * s + k * 1.5, by - 0.42 * s,
                                 s * 0.095, s * 0.095))
        elif ttype == "curl":                  # 猪：卷曲小尾
            p.setPen(QPen(fd, max(1.8, s * 0.050), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            r0 = s * 0.082
            p.drawArc(QRectF(bx - 0.13 * s - r0, by - 0.20 * s - r0, 2 * r0, 2 * r0),
                      -25 * 16, 300 * 16)
            p.drawArc(QRectF(bx - 0.13 * s - r0 * 0.52, by - 0.17 * s - r0 * 0.52,
                             2 * r0 * 0.52, 2 * r0 * 0.52), 115 * 16, 300 * 16)
        elif ttype == "brush":                 # 马 / 牛：下垂刷子尾
            k = math.sin(tail_phase * 1.3) * 0.07 * s
            tip_c = QColor(colors.get("mane") or colors["fur_d"])
            p.setPen(QPen(fd, max(2.6, s * 0.070), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            ex_, ey_ = bx - 0.11 * s + k, by + 0.19 * s
            p.drawLine(QPointF(bx, by - 0.05 * s), QPointF(ex_, ey_))
            p.setPen(QPen(tip_c, max(1.4, s * 0.028), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            for dx in (-0.055, -0.018, 0.020):
                p.drawLine(QPointF(ex_, ey_ - 0.02 * s),
                           QPointF(ex_ + dx * s, ey_ + 0.15 * s))
        elif ttype == "fin":                   # 龙：粗锥尾 + 侧鳍
            k = math.sin(tail_phase * 1.1) * 0.10 * s
            p.setPen(QPen(fd, max(3.0, s * 0.085), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            tp = QPainterPath()
            tp.moveTo(bx + 0.02 * s, by)
            tp.cubicTo(bx - 0.17 * s + k, by + 0.05 * s,
                       bx - 0.32 * s + k * 1.5, by - 0.10 * s,
                       bx - 0.42 * s + k * 2, by - 0.28 * s)
            p.drawPath(tp)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#8ECCB8"))
            for fx, fy, fs in ((bx - 0.15 * s + k * 0.7, by + 0.03 * s, 0.095),
                               (bx - 0.29 * s + k * 1.3, by - 0.07 * s, 0.078)):
                fp = QPainterPath()
                fp.moveTo(fx, fy)
                fp.lineTo(fx - fs * s * 0.9, fy - fs * s * 1.25)
                fp.lineTo(fx + fs * s * 0.30, fy - fs * s * 0.25)
                fp.closeSubpath()
                p.drawPath(fp)
        elif ttype == "coil":                  # 蛇：无尾，身后盘绕一圈
            p.setPen(QPen(fd, max(2.6, s * 0.078), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawArc(QRectF(bx - 0.34 * s, by - 0.14 * s, 0.66 * s, 0.44 * s),
                      190 * 16, 210 * 16)
            p.setPen(QPen(fl, max(1.2, s * 0.026), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawArc(QRectF(bx - 0.25 * s, by - 0.05 * s, 0.48 * s, 0.30 * s),
                      205 * 16, 170 * 16)
        elif ttype == "feather":               # 鸡：扇形尾羽
            fc = QColor(colors.get("comb") or "#E0524C")
            p.setPen(QPen(fc, max(2.0, s * 0.048), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            for i in range(4):
                a = math.radians(98 + i * 21 + math.sin(tail_phase * 0.8 + i) * 8)
                L = s * (0.30 if i in (1, 2) else 0.24)
                p.drawLine(QPointF(bx, by - 0.02 * s),
                           QPointF(bx + math.cos(a) * L, by - math.sin(a) * L - 0.02 * s))
            p.setPen(_line(QColor("#C43C38"), lw * 1.18))
            p.drawLine(QPointF(bx, by - 0.02 * s),
                       QPointF(bx + math.cos(math.radians(128)) * s * 0.30,
                               by - math.sin(math.radians(128)) * s * 0.30 - 0.02 * s))
        elif ttype == "whip":                  # 鼠：细长鞭尾
            k = math.sin(tail_phase * 1.5)
            p.setPen(QPen(fd, max(1.2, s * 0.026), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            tp = QPainterPath()
            tp.moveTo(bx, by)
            tp.cubicTo(bx - 0.26 * s, by + 0.02 * s + k * 0.05 * s,
                       bx - 0.44 * s, by - 0.11 * s + k * 0.13 * s,
                       bx - 0.58 * s, by - 0.01 * s + k * 0.20 * s)
            p.drawPath(tp)
        elif ttype == "long":                  # 猴：长弯尾，末端卷
            k = math.sin(tail_phase * 1.4) * 0.13 * s
            p.setPen(QPen(fd, max(2.0, s * 0.046), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            tp = QPainterPath()
            tp.moveTo(bx, by)
            tp.cubicTo(bx - 0.27 * s + k, by + 0.11 * s,
                       bx - 0.43 * s + k, by - 0.14 * s,
                       bx - 0.30 * s + k, by - 0.34 * s)
            p.drawPath(tp)
            p.drawArc(QRectF(bx - 0.38 * s + k, by - 0.44 * s, s * 0.15, s * 0.15),
                      80 * 16, 280 * 16)
        else:                                  # 默认猫尾：细长弯钩
            tail = QPainterPath()
            tail.moveTo(bx, by)
            tail.cubicTo(bx - 0.18 * s, by + 0.08 * s,
                         bx - 0.16 * s + sw, by - 0.14 * s,
                         bx - 0.04 * s + sw * 1.7, by - 0.24 * s)
            p.setPen(QPen(fd, max(2.0, s * 0.055), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawPath(tail)
            p.setPen(QPen(fl, max(1.0, s * 0.020), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            tail2 = QPainterPath()
            tail2.moveTo(bx - 0.02 * s, by - 0.015 * s)
            tail2.cubicTo(bx - 0.17 * s, by + 0.05 * s,
                          bx - 0.15 * s + sw, by - 0.13 * s,
                          bx - 0.05 * s + sw * 1.6, by - 0.21 * s)
            p.drawPath(tail2)

    # ---- 角（牛/龙，耳根被头盖住，先画） ----
    if shape in ("ox", "dragon"):
        for sign in (-1, 1):
            h = QPainterPath()
            if shape == "ox":
                # 牛角：更大弯曲，加白色尖端
                horn_c = "#E3D5B8"
                tip_c = "#F8F4ED"
                h.moveTo(cx + sign * 0.22 * s, cy - 0.30 * s)
                h.cubicTo(cx + sign * 0.44 * s, cy - 0.42 * s,
                          cx + sign * 0.55 * s, cy - 0.58 * s,
                          cx + sign * 0.50 * s, cy - 0.74 * s)
                h.cubicTo(cx + sign * 0.43 * s, cy - 0.60 * s,
                          cx + sign * 0.33 * s, cy - 0.50 * s,
                          cx + sign * 0.17 * s, cy - 0.40 * s)
                h.closeSubpath()
                p.setPen(outline)
                p.setBrush(QColor(horn_c))
                p.drawPath(h)
                # 白色尖端
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(tip_c))
                tip = QPainterPath()
                tip.moveTo(cx + sign * 0.50 * s, cy - 0.74 * s)
                tip.cubicTo(cx + sign * 0.52 * s, cy - 0.78 * s,
                            cx + sign * 0.46 * s, cy - 0.80 * s,
                            cx + sign * 0.45 * s, cy - 0.74 * s)
                tip.cubicTo(cx + sign * 0.47 * s, cy - 0.70 * s,
                            cx + sign * 0.49 * s, cy - 0.70 * s,
                            cx + sign * 0.50 * s, cy - 0.74 * s)
                tip.closeSubpath()
                p.drawPath(tip)
            else:
                # 龙角：圆润分叉鹿角
                horn_c = "#F2E6C8"
                base_x = cx + sign * 0.18 * s
                base_y = cy - 0.36 * s
                branch = QPainterPath()
                branch.moveTo(base_x, base_y)
                branch.cubicTo(base_x + sign * 0.10 * s, cy - 0.46 * s,
                               base_x + sign * 0.08 * s, cy - 0.60 * s,
                               base_x + sign * 0.02 * s, cy - 0.72 * s)
                branch.cubicTo(base_x + sign * 0.12 * s, cy - 0.62 * s,
                               base_x + sign * 0.22 * s, cy - 0.55 * s,
                               base_x + sign * 0.20 * s, cy - 0.44 * s)
                branch.cubicTo(base_x + sign * 0.14 * s, cy - 0.52 * s,
                               base_x + sign * 0.08 * s, cy - 0.44 * s,
                               base_x, base_y)
                branch.closeSubpath()
                p.setPen(outline)
                p.setBrush(QColor(horn_c))
                p.drawPath(branch)
                # 圆润角尖
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(horn_c))
                for ax, ay in ((base_x + sign * 0.02 * s, cy - 0.72 * s),
                               (base_x + sign * 0.20 * s, cy - 0.44 * s)):
                    p.drawEllipse(QRectF(ax - 0.05 * s, ay - 0.05 * s,
                                         0.10 * s, 0.10 * s))

    # ---- 耳朵（按物种分形状） ----
    ear_shapes = {"rat": "round", "monkey": "monkey", "rabbit": "long",
                  "dog": "flop", "pig": "flop", "sheep": "sheep_flop",
                  "snake": "none", "rooster": "none",
                  "tiger": "tiger", "horse": "horse", "dragon": "dragon"}
    eshape = ear_shapes.get(shape, "tri")
    for idx, sign in enumerate((-1, 1)):
        if eshape == "none":
            break
        tw_rot = 0.0
        if dim25 and ear_tw and ear_tw[0] == sign:
            tw_rot = math.sin(max(0.0, min(1.0, ear_tw[1])) * math.pi) * 11.0 * sign
            bx, by = cx + sign * 0.28 * s, cy - 0.30 * s
            p.save()
            p.translate(bx, by)
            p.rotate(tw_rot)
            p.translate(-bx, -by)
        ear_c = colors["ears"][idx] or colors["fur"]
        if eshape == "round":                 # 圆耳（鼠）
            ecx, ecy = cx + sign * 0.335 * s, cy - 0.385 * s
            p.setPen(outline)
            p.setBrush(QColor(ear_c))
            p.drawEllipse(QRectF(ecx - 0.145 * s, ecy - 0.145 * s, 0.29 * s, 0.29 * s))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(colors["ear_in"]))
            p.drawEllipse(QRectF(ecx - 0.082 * s, ecy - 0.082 * s, 0.164 * s, 0.164 * s))
        elif eshape == "monkey":              # 猴：大而圆的耳朵
            ecx, ecy = cx + sign * 0.36 * s, cy - 0.32 * s
            p.setPen(outline)
            p.setBrush(QColor(ear_c))
            p.drawEllipse(QRectF(ecx - 0.18 * s, ecy - 0.18 * s, 0.36 * s, 0.36 * s))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(colors["ear_in"]))
            p.drawEllipse(QRectF(ecx - 0.11 * s, ecy - 0.11 * s, 0.22 * s, 0.22 * s))
        elif eshape == "long":                # 长耳（兔，收短防出界；留出 0.86 top 余量）
            p.save()
            p.translate(cx + sign * 0.19 * s, cy - 0.38 * s)
            p.rotate(sign * -10)
            p.setPen(outline)
            p.setBrush(QColor(ear_c))
            p.drawEllipse(QRectF(-0.082 * s, -0.45 * s, 0.164 * s, 0.50 * s))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(colors["ear_in"]))
            p.drawEllipse(QRectF(-0.046 * s, -0.38 * s, 0.092 * s, 0.34 * s))
            p.restore()
        elif eshape == "tiger":               # 虎：小圆耳，后压
            ecx, ecy = cx + sign * 0.32 * s, cy - 0.32 * s
            p.setPen(outline)
            p.setBrush(QColor(ear_c))
            p.drawEllipse(QRectF(ecx - 0.11 * s, ecy - 0.10 * s, 0.22 * s, 0.20 * s))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(colors["ear_in"]))
            p.drawEllipse(QRectF(ecx - 0.06 * s, ecy - 0.06 * s, 0.12 * s, 0.11 * s))
        elif eshape == "horse":               # 马：长尖耳
            ear = QPainterPath()
            ear.moveTo(cx + sign * 0.30 * s, cy - 0.18 * s)
            ear.cubicTo(cx + sign * 0.42 * s, cy - 0.24 * s,
                        cx + sign * 0.48 * s, cy - 0.50 * s,
                        cx + sign * 0.34 * s, cy - 0.62 * s)
            ear.cubicTo(cx + sign * 0.25 * s, cy - 0.48 * s,
                        cx + sign * 0.24 * s, cy - 0.30 * s,
                        cx + sign * 0.18 * s, cy - 0.22 * s)
            ear.closeSubpath()
            p.setPen(outline)
            p.setBrush(QColor(ear_c))
            p.drawPath(ear)
            inner = QPainterPath()
            inner.moveTo(cx + sign * 0.31 * s, cy - 0.24 * s)
            inner.cubicTo(cx + sign * 0.38 * s, cy - 0.34 * s,
                          cx + sign * 0.34 * s, cy - 0.48 * s,
                          cx + sign * 0.28 * s, cy - 0.42 * s)
            inner.cubicTo(cx + sign * 0.26 * s, cy - 0.34 * s,
                          cx + sign * 0.26 * s, cy - 0.28 * s,
                          cx + sign * 0.26 * s, cy - 0.24 * s)
            inner.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(colors["ear_in"]))
            p.drawPath(inner)
        elif eshape == "sheep_flop":         # 羊：宽大下垂耳（毛绒感）
            ear = QPainterPath()
            ear.moveTo(cx + sign * 0.30 * s, cy - 0.34 * s)
            ear.cubicTo(cx + sign * 0.64 * s, cy - 0.40 * s,
                        cx + sign * 0.68 * s, cy - 0.02 * s,
                        cx + sign * 0.52 * s, cy + 0.22 * s)
            ear.cubicTo(cx + sign * 0.42 * s, cy + 0.06 * s,
                        cx + sign * 0.33 * s, cy - 0.10 * s,
                        cx + sign * 0.22 * s, cy - 0.20 * s)
            ear.closeSubpath()
            p.setPen(outline)
            p.setBrush(QColor(colors["fur_d"]))
            p.drawPath(ear)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(colors["ear_in"]))
            p.drawEllipse(QRectF(cx + sign * 0.42 * s - 0.085 * s, cy - 0.14 * s,
                                 0.17 * s, 0.24 * s))
            # 羊毛绒边：耳廓外沿三个小弧
            p.setPen(_line(QColor(colors["wool"] if colors.get("wool") else colors["fur_l"]),
                           lw * 0.82))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for k in (0.0, 0.35, 0.70):
                p.drawArc(QRectF(cx + sign * (0.36 + k * 0.16) * s - 0.09 * s,
                                 cy + (-0.30 + k * 0.34) * s,
                                 0.18 * s, 0.18 * s),
                          (200 if sign < 0 else 120) * 16, 140 * 16)
        elif eshape == "dragon":             # 龙：细长尖耳（向后上方挑起）
            ear = QPainterPath()
            ear.moveTo(cx + sign * 0.30 * s, cy - 0.20 * s)
            ear.cubicTo(cx + sign * 0.44 * s, cy - 0.34 * s,
                        cx + sign * 0.51 * s, cy - 0.52 * s,
                        cx + sign * 0.38 * s, cy - 0.66 * s)
            ear.cubicTo(cx + sign * 0.30 * s, cy - 0.48 * s,
                        cx + sign * 0.26 * s, cy - 0.32 * s,
                        cx + sign * 0.19 * s, cy - 0.24 * s)
            ear.closeSubpath()
            p.setPen(outline)
            p.setBrush(QColor(ear_c))
            p.drawPath(ear)
            inner = QPainterPath()
            inner.moveTo(cx + sign * 0.31 * s, cy - 0.26 * s)
            inner.cubicTo(cx + sign * 0.40 * s, cy - 0.38 * s,
                          cx + sign * 0.38 * s, cy - 0.52 * s,
                          cx + sign * 0.34 * s, cy - 0.44 * s)
            inner.cubicTo(cx + sign * 0.31 * s, cy - 0.36 * s,
                          cx + sign * 0.29 * s, cy - 0.30 * s,
                          cx + sign * 0.28 * s, cy - 0.26 * s)
            inner.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(colors["ear_in"]))
            p.drawPath(inner)
        elif eshape == "flop":                # 垂耳（狗/猪）
            ear = QPainterPath()
            ear.moveTo(cx + sign * 0.34 * s, cy - 0.30 * s)
            ear.cubicTo(cx + sign * 0.58 * s, cy - 0.34 * s,
                        cx + sign * 0.62 * s, cy - 0.05 * s,
                        cx + sign * 0.50 * s, cy + 0.14 * s)
            ear.cubicTo(cx + sign * 0.42 * s, cy + 0.02 * s,
                        cx + sign * 0.36 * s, cy - 0.12 * s,
                        cx + sign * 0.26 * s, cy - 0.20 * s)
            ear.closeSubpath()
            p.setPen(outline)
            p.setBrush(QColor(colors["fur_d"]))
            p.drawPath(ear)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(colors["ear_in"]))
            p.drawEllipse(QRectF(cx + sign * 0.40 * s - 0.075 * s, cy - 0.16 * s,
                                 0.15 * s, 0.20 * s))
        else:                                 # 默认三角耳（猫/龙/牛）
            ear = QPainterPath()
            ear.moveTo(cx + sign * 0.36 * s, cy - 0.18 * s)
            ear.cubicTo(cx + sign * 0.52 * s, cy - 0.44 * s,
                        cx + sign * 0.34 * s, cy - 0.60 * s,
                        cx + sign * 0.15 * s, cy - 0.44 * s)
            ear.closeSubpath()
            p.setPen(outline)
            p.setBrush(QColor(ear_c))
            p.drawPath(ear)
            inner = QPainterPath()
            inner.moveTo(cx + sign * 0.33 * s, cy - 0.25 * s)
            inner.cubicTo(cx + sign * 0.43 * s, cy - 0.41 * s,
                          cx + sign * 0.31 * s, cy - 0.50 * s,
                          cx + sign * 0.20 * s, cy - 0.38 * s)
            inner.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(colors["ear_in"]))
            p.drawPath(inner)
        if tw_rot:
            p.restore()

    # ---- 半身：圆润身体（头之前绘制，头会自然盖住肩线） ----
    if body:
        body_k = _BODY_SHAPE.get(shape, "round")
        if body_k == "slim":          # 狗 / 猴：略修长
            bw, shw = s * 0.86, s * 0.52
            by0, by1 = cy + s * 0.24, cy + s * 1.04
            belly_w, belly_h = 0.18, 0.46
        elif body_k == "long":          # 马 / 蛇：修长
            bw, shw = s * 0.82, s * 0.50
            by0, by1 = cy + s * 0.22, cy + s * 1.08
            belly_w, belly_h = 0.34, 0.42
        elif body_k == "wide":        # 牛 / 猪：宽厚
            bw, shw = s * 0.98, s * 0.62
            by0, by1 = cy + s * 0.26, cy + s * 1.00
            belly_w, belly_h = 0.24, 0.40
        else:                         # 圆润标准
            bw, shw = s * 0.92, s * 0.58
            by0, by1 = cy + s * 0.24, cy + s * 1.02
            belly_w, belly_h = 0.21, 0.48
        bp = QPainterPath()
        bp.moveTo(cx - shw / 2, by0)
        bp.cubicTo(cx - bw / 2, by0 + 0.10 * s,
                   cx - bw / 2, by1 - 0.20 * s,
                   cx - bw / 2, by1 - 0.14 * s)
        bp.quadTo(cx, by1 + 0.08 * s, cx + bw / 2, by1 - 0.14 * s)
        bp.cubicTo(cx + bw / 2, by1 - 0.20 * s,
                   cx + bw / 2, by0 + 0.10 * s,
                   cx + shw / 2, by0)
        bp.closeSubpath()
        bg = QLinearGradient(cx, by0, cx, by1)
        bg.setColorAt(0, QColor(colors["fur"]))
        bg.setColorAt(1, QColor(colors["fur_d"]))
        p.setPen(outline)
        p.setBrush(bg)
        p.drawPath(bp)
        # 肚皮浅色
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(colors["fur_l"]))
        p.drawEllipse(QRectF(cx - belly_w * s, by0 + 0.10 * s,
                             2 * belly_w * s, belly_h * s))
        # 蛇 / 龙：鳞纹（仅在身体 clip 内）
        if shape in ("snake", "dragon") and lod >= 1:   # A7：小尺寸省略鳞纹
            p.setClipPath(bp)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(colors["fur_d"]))
            for row in range(5):
                for col in range(-2, 3):
                    px = cx + col * 0.13 * s
                    py = by0 + 0.18 * s + row * 0.13 * s
                    p.drawEllipse(QRectF(px - 0.045 * s, py - 0.03 * s,
                                         0.09 * s, 0.06 * s))
            p.setClipping(False)
        # 底部暗边（体积感）
        p.setClipPath(bp)
        shade = QColor(colors["fur_d"])
        shade.setAlpha(90)
        p.setBrush(shade)
        p.drawEllipse(QRectF(cx - 0.50 * s, by1 - 0.30 * s, 1.00 * s, 0.44 * s))
        p.setClipping(False)
        # A2：身体左上受光（与头部同向），避免身体像一块平涂色块
        p.setClipPath(bp)
        a0 = int(30 * rim)
        bgr = QRadialGradient(cx - 0.24 * s, by0 + 0.14 * s, 0.74 * s)
        bgr.setColorAt(0, QColor(255, 255, 255, a0))
        bgr.setColorAt(0.60, QColor(255, 255, 255, int(a0 * 0.34)))
        bgr.setColorAt(1, QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bgr)
        p.drawRect(QRectF(cx - bw / 2 - 0.1 * s, by0 - 0.1 * s,
                          bw + 0.2 * s, (by1 - by0) + 0.3 * s))
        p.setClipping(False)

    # ---- 头 ----
    grad = QLinearGradient(cx, cy - 0.44 * s, cx, cy + 0.46 * s)
    grad.setColorAt(0, QColor(colors["fur"]))
    grad.setColorAt(1, QColor(colors["fur_d"]))
    p.setPen(outline)
    p.setBrush(grad)
    p.drawEllipse(head_rect)

    # ---- 斑块 ----
    if colors.get("patches"):
        head_clip = QPainterPath()
        head_clip.addEllipse(head_rect)
        p.setClipPath(head_clip)
        for pt in colors["patches"]:
            p.setPen(Qt.PenStyle.NoPen)
            r = QRectF(cx + pt["x"] * s, cy + pt["y"] * s,
                       pt["w"] * s, pt["h"] * s)
            if pt.get("feather"):
                # 羽化边缘：中心色 → 边缘透明
                g = QRadialGradient(r.center(), max(r.width(), r.height()) * 0.55)
                g.setColorAt(0, QColor(pt["c"]))
                g.setColorAt(0.55, QColor(pt["c"]))
                g.setColorAt(1, _mix(pt["c"], "#000000", 0.0))
                g.setColorAt(1, QColor(0, 0, 0, 0))
                p.setBrush(g)
            else:
                p.setBrush(QColor(pt["c"]))
            p.drawEllipse(r)
        p.setClipping(False)

    # ---- 虎斑 ----
    if colors.get("tabby"):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(colors["tabby_c"]))
        for off, hh, ww in ((-0.15, 0.10, 0.026), (0.0, 0.13, 0.030), (0.15, 0.10, 0.026)):
            p.drawRoundedRect(QRectF(cx + off * s - ww * s / 2, cy - 0.40 * s, ww * s, hh * s),
                              ww * s / 2, ww * s / 2)

    # ---- 物种特征：鸡冠 / 鬃毛 / 羊毛卷 / 虎纹 ----
    if shape == "rooster":
        p.setPen(outline)
        p.setBrush(QColor(colors["comb"]))
        for dx, r in ((-0.13, 0.095), (0.0, 0.115), (0.13, 0.095)):
            p.drawEllipse(QRectF(cx + dx * s - r * s, cy - 0.575 * s, 2 * r * s, 0.22 * s))
    if shape == "horse":
        # 马鬃：更大更蓬松，覆盖头顶到后颈
        p.setPen(outline)
        p.setBrush(QColor(colors["mane"]))
        mane = QPainterPath()
        mane.moveTo(cx - 0.30 * s, cy - 0.30 * s)
        mane.cubicTo(cx - 0.18 * s, cy - 0.66 * s,
                     cx - 0.05 * s, cy - 0.68 * s,
                     cx, cy - 0.64 * s)
        mane.cubicTo(cx + 0.05 * s, cy - 0.68 * s,
                     cx + 0.18 * s, cy - 0.66 * s,
                     cx + 0.30 * s, cy - 0.30 * s)
        mane.cubicTo(cx + 0.22 * s, cy - 0.42 * s,
                     cx + 0.10 * s, cy - 0.40 * s,
                     cx, cy - 0.44 * s)
        mane.cubicTo(cx - 0.10 * s, cy - 0.40 * s,
                     cx - 0.22 * s, cy - 0.42 * s,
                     cx - 0.30 * s, cy - 0.30 * s)
        mane.closeSubpath()
        p.drawPath(mane)
        # 鬃毛纹理
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(_line(_mix(colors["mane"], "#000000", 0.25), lw * 0.90))
        for dx in (-0.12, -0.04, 0.04, 0.12):
            p.drawLine(QPointF(cx + dx * s, cy - 0.52 * s),
                       QPointF(cx + dx * s, cy - 0.40 * s))
        # 鬃毛顶部高光
        p.setPen(Qt.PenStyle.NoPen)
        hl = QColor("#FFFFFF")
        hl.setAlpha(70)
        p.setBrush(hl)
        p.drawEllipse(QRectF(cx - 0.05 * s, cy - 0.64 * s, 0.10 * s, 0.14 * s))
    if shape == "sheep":
        p.setPen(outline)
        p.setBrush(QColor(colors["wool"]))
        for dx, dy, r in ((-0.38, -0.24, 0.19), (-0.20, -0.42, 0.20), (0.0, -0.48, 0.21),
                          (0.20, -0.42, 0.20), (0.38, -0.24, 0.19),
                          (-0.44, -0.02, 0.17), (0.44, -0.02, 0.17)):
            p.drawEllipse(QRectF(cx + dx * s - r * s, cy + dy * s - r * s,
                                 2 * r * s, 2 * r * s))
    if shape == "tiger":
        tiger_clip = QPainterPath()
        tiger_clip.addEllipse(head_rect)
        p.setClipPath(tiger_clip)
        tc = _mix(colors["tabby_c"], "#3E2A1A", 0.35)
        p.setPen(_line(QColor(tc), lw * 2.20))
        p.setBrush(Qt.BrushStyle.NoBrush)
        # 额头王字：三横一竖
        p.drawLine(QPointF(cx, cy - 0.38 * s), QPointF(cx, cy - 0.26 * s))
        for dy in (-0.35, -0.31, -0.27):
            p.drawLine(QPointF(cx - 0.10 * s, cy + dy * s),
                       QPointF(cx + 0.10 * s, cy + dy * s))
        # 脸颊粗条纹
        for sign in (-1, 1):
            for y0, ln in ((0.00, 0.12), (0.08, 0.11), (0.16, 0.09)):
                p.drawLine(QPointF(cx + sign * 0.34 * s, cy + y0 * s),
                           QPointF(cx + sign * (0.34 + ln) * s, cy + (y0 + 0.03) * s))
        p.setClipping(False)
    if shape == "dragon":
        # 龙：脸颊两侧加鬓毛
        p.setPen(outline)
        p.setBrush(QColor(colors.get("mane") or colors["fur_d"]))
        for sign in (-1, 1):
            tuft = QPainterPath()
            tuft.moveTo(cx + sign * 0.16 * s, cy - 0.10 * s)
            tuft.cubicTo(cx + sign * 0.26 * s, cy + 0.05 * s,
                         cx + sign * 0.30 * s, cy + 0.22 * s,
                         cx + sign * 0.22 * s, cy + 0.32 * s)
            tuft.cubicTo(cx + sign * 0.18 * s, cy + 0.22 * s,
                         cx + sign * 0.14 * s, cy + 0.08 * s,
                         cx + sign * 0.10 * s, cy - 0.02 * s)
            tuft.closeSubpath()
            p.drawPath(tuft)

    # ---- 脸颊浅色 ----
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(colors["fur_l"]))
    p.drawEllipse(QRectF(cx - 0.24 * s, cy + 0.08 * s, 0.48 * s, 0.26 * s))
    if shape == "monkey":                  # 猴子心形脸补丁
        heart = QPainterPath()
        heart.addEllipse(QRectF(cx - 0.22 * s, cy - 0.22 * s, 0.22 * s, 0.22 * s))
        heart.addEllipse(QRectF(cx, cy - 0.22 * s, 0.22 * s, 0.22 * s))
        tri = QPainterPath()
        tri.moveTo(cx - 0.22 * s, cy - 0.11 * s)
        tri.lineTo(cx + 0.22 * s, cy - 0.11 * s)
        tri.lineTo(cx, cy + 0.18 * s)
        tri.closeSubpath()
        heart = heart.united(tri)
        p.drawPath(heart)

    # ---- 下巴阴影（贴合头部的下缘暗部） ----
    head_clip = QPainterPath()
    head_clip.addEllipse(head_rect)
    p.setClipPath(head_clip)
    chin = QColor(colors["fur_d"])
    chin.setAlpha(130)
    p.setBrush(chin)
    p.drawEllipse(QRectF(cx - 0.32 * s, cy + 0.24 * s, 0.64 * s, 0.30 * s))

    # ---- A2：统一光照（左上受光），让头有体积而不是平涂色块 ----
    a0 = int(36 * rim)
    rg = QRadialGradient(cx - 0.20 * s, head_top + 0.16 * s, 0.78 * s)
    rg.setColorAt(0, QColor(255, 255, 255, a0))
    rg.setColorAt(0.55, QColor(255, 255, 255, int(a0 * 0.38)))
    rg.setColorAt(1, QColor(255, 255, 255, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(rg)
    p.drawEllipse(head_rect)
    if lod >= 1:
        # 上缘内高光（rim light）：暗色角色靠它从背景里「浮」出来
        ins = lw * 0.85
        p.setPen(_line(QColor(255, 255, 255, int(58 * rim)), lw * 0.85, join=False))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(head_rect.adjusted(ins, ins * 0.55, -ins, -ins * 1.75))
    p.setClipping(False)

    # ---- 腮红 ----
    p.setBrush(QColor(255, 150, 170, 105))
    for sign in (-1, 1):
        p.drawEllipse(QRectF(cx + sign * 0.30 * s - 0.085 * s, cy + 0.04 * s, 0.17 * s, 0.105 * s))

    # ---- 头顶帽子：auto 按物种默认，可显式指定或 none ----
    hat_style = _HAT.get(shape, "none") if hat in (None, "auto") else hat
    _draw_hat(p, cx, cy, s, colors, outline, hat_style,
              head_top, hw, t)

    # ---- 配饰（帽子之后、胡须之前） ----
    acc_style = "none" if acc in (None, "auto") else acc
    _draw_acc(p, cx, cy, s, colors, outline, acc_style, head_top)

    # ---- 胡须（猫/鼠/兔/虎/龙；深毛色用浅须，浅毛色用经典橘须） ----
    if shape in ("cat", "rat", "rabbit", "tiger", "dragon"):
        hp = _line(QColor("#CFC9DC") if dark else QColor("#E0AC76"), lw * 0.78)
        p.setPen(hp)
        dys = (-0.03, 0.11) if lod == 0 else (-0.03, 0.04, 0.11)   # A7：小尺寸少一根
        mid = (len(dys) - 1) / 2.0
        for sign in (-1, 1):
            for k, dy in enumerate(dys):
                y = cy + dy * s
                x0 = cx + sign * 0.17 * s
                p.drawLine(
                    QPointF(x0, y),
                    QPointF(x0 + sign * 0.26 * s, y + (k - mid) * s * 0.045),
                )

    # ---- 眼睛（按物种差异化：位置 / 大小 / 竖瞳） ----
    eye_dy, ewk, ehk, slit = _EYE.get(shape, _EYE_DEFAULT)
    eye_y = cy + (-0.02 + eye_dy) * s
    ew2, ehh = ewk * s, ehk * s
    for sign in (-1, 1):
        ex = cx + sign * 0.185 * s
        if excited:
            star = QPainterPath()
            R, r2 = s * 0.10, s * 0.045
            for i in range(8):
                rad = math.radians(-90 + i * 45)
                rad2 = R if i % 2 == 0 else r2
                x = ex + rad2 * math.cos(rad)
                y = eye_y + rad2 * math.sin(rad)
                if i == 0:
                    star.moveTo(x, y)
                else:
                    star.lineTo(x, y)
            star.closeSubpath()
            p.setPen(_line(QColor("#E8930C"), lw * 0.85))
            p.setBrush(QColor("#FFD34D"))
            p.drawPath(star)
        elif blink or sleepy:
            p.setPen(_line(QColor(colors["eye"]), lw * 1.85))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(ex - ew2 * 1.25, eye_y - ehh * 0.29,
                             ew2 * 2.50, ehh * 0.58), 180 * 16, 180 * 16)
        else:                             # 物种眼型 + 虹膜渐变 + 双高光（瞳孔跟随 look 偏移）
            lx = max(-1.0, min(1.0, look[0])) * s * 0.030
            ly = max(-1.0, min(1.0, look[1])) * s * 0.022
            p.setPen(Qt.PenStyle.NoPen)
            if colors.get("pupil"):            # 熊猫式：白眼 + 深色瞳孔
                p.setBrush(QColor(colors["eye"]))
            else:                              # 虹膜上浅下深，更有神
                g = QLinearGradient(ex, eye_y - ehh / 2, ex, eye_y + ehh / 2)
                g.setColorAt(0, QColor(colors["eye"]))
                g.setColorAt(1, _mix(colors["eye"], "#14100E", 0.5))
                p.setBrush(g)
            p.drawEllipse(QRectF(ex - ew2, eye_y - ehh / 2, 2 * ew2, ehh))
            # 虹膜外圈细眼线
            p.setPen(_line(_mix(colors["eye"], "#14100E", 0.55), lw * 0.72, join=False))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(ex - ew2, eye_y - ehh / 2, 2 * ew2, ehh))
            p.setPen(Qt.PenStyle.NoPen)
            if colors.get("pupil"):            # 熊猫式：白眼 + 深色瞳孔（高光缩小）
                pw, ph = ew2 * 0.44, ehh * 0.20
                p.setBrush(QColor(colors["pupil"]))
                p.drawEllipse(QRectF(ex - pw + lx, eye_y - ph + ly + ehh * 0.04,
                                     2 * pw, 2 * ph))
                p.setBrush(QColor("#FFFFFF"))
                p.drawEllipse(QRectF(ex + ew2 * 0.16 + lx, eye_y - ehh * 0.10 + ly,
                                     ew2 * 0.26, ew2 * 0.26))
            elif slit:                         # 龙 / 蛇：竖缝瞳 + 金色虹膜
                p.setBrush(QColor("#12100E"))
                pw, ph = ew2 * 0.30, ehh * 0.42
                p.drawEllipse(QRectF(ex - pw + lx, eye_y - ph + ly, 2 * pw, 2 * ph))
                p.setBrush(QColor(255, 255, 255, 200))
                p.drawEllipse(QRectF(ex + ew2 * 0.28 + lx, eye_y - ehh * 0.34 + ly,
                                     ew2 * 0.34, ehh * 0.24))
            else:
                p.setBrush(QColor("#FFFFFF"))
                p.drawEllipse(QRectF(ex + ew2 * 0.12 + lx, eye_y - ehh * 0.33 + ly,
                                     ew2 * 0.76, ehh * 0.29))
                if lod >= 1:              # A7：小尺寸只留主高光，避免眼睛糊成一团
                    p.drawEllipse(QRectF(ex - ew2 * 0.70 + lx, eye_y + ehh * 0.10 + ly,
                                         ew2 * 0.35, ehh * 0.13))

    # ---- 鼻子 & 嘴（按物种分形状；打哈欠统一 O 形嘴） ----
    mouth_pen = _line(line_c, lw * 1.30)
    if action == "yawn":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#7A4A3A"))
        k = _ease(action_k)
        p.drawEllipse(QRectF(cx - s * 0.040 * k, cy + 0.125 * s,
                             s * 0.080 * k, s * 0.095 * k))
        if k > 0.3:                     # 泪珠在哈欠后半段出现
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#8EC9E8"))
            p.drawEllipse(QRectF(cx + 0.20 * s, cy - 0.10 * s, s * 0.045, s * 0.06))
    elif shape == "pig":                 # 猪：更大圆鼻 + 鼻孔
        p.setPen(outline)
        p.setBrush(QColor(colors["nose"]))
        p.drawEllipse(QRectF(cx - 0.17 * s, cy + 0.045 * s, 0.34 * s, 0.23 * s))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#A85060"))
        for sign in (-1, 1):
            p.drawEllipse(QRectF(cx + sign * 0.070 * s - 0.032 * s, cy + 0.11 * s,
                                 0.064 * s, 0.085 * s))
        p.setPen(mouth_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(cx - 0.05 * s, cy + 0.27 * s, 0.10 * s, 0.07 * s), 200 * 16, 140 * 16)
    elif shape == "dog":                 # 狗：大黑鼻 + 吐舌
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(colors["nose"]))
        p.drawEllipse(QRectF(cx - 0.085 * s, cy + 0.045 * s, 0.17 * s, 0.13 * s))
        p.setBrush(QColor(255, 255, 255, 170))
        p.drawEllipse(QRectF(cx - 0.050 * s, cy + 0.065 * s, 0.035 * s, 0.028 * s))
        p.setPen(mouth_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(cx - 0.11 * s, cy + 0.15 * s, 0.11 * s, 0.10 * s), 200 * 16, 120 * 16)
        p.drawArc(QRectF(cx, cy + 0.15 * s, 0.11 * s, 0.10 * s), 220 * 16, 120 * 16)
        wag = math.sin(t * 6.0) * 0.012 * s
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#F2909C"))
        p.drawEllipse(QRectF(cx - 0.055 * s + wag, cy + 0.235 * s, 0.11 * s, 0.13 * s))
        p.setPen(_line(QColor("#D86A7A"), lw * 0.78))
        p.drawLine(QPointF(cx + wag, cy + 0.25 * s), QPointF(cx + wag, cy + 0.33 * s))
    elif shape == "ox":                  # 牛：宽鼻 + 鼻孔
        p.setPen(outline)
        p.setBrush(QColor("#EBD9C0"))
        p.drawRoundedRect(QRectF(cx - 0.20 * s, cy + 0.09 * s, 0.40 * s, 0.19 * s),
                          0.09 * s, 0.09 * s)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#8A6A58"))
        for sign in (-1, 1):
            p.drawEllipse(QRectF(cx + sign * 0.085 * s - 0.030 * s, cy + 0.135 * s,
                                 0.060 * s, 0.075 * s))
        p.setPen(mouth_pen)
        p.drawArc(QRectF(cx - 0.06 * s, cy + 0.285 * s, 0.12 * s, 0.08 * s), 200 * 16, 140 * 16)
    elif shape == "horse":               # 马：长脸底部宽鼻
        p.setPen(outline)
        p.setBrush(QColor(colors["nose"]))
        p.drawRoundedRect(QRectF(cx - 0.155 * s, cy + 0.19 * s, 0.31 * s, 0.15 * s),
                          0.07 * s, 0.07 * s)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(_line(line_c, lw * 1.20))
        for sign in (-1, 1):
            p.drawEllipse(QRectF(cx + sign * 0.062 * s - 0.028 * s, cy + 0.225 * s,
                                 0.056 * s, 0.070 * s))
        p.setPen(mouth_pen)
        p.drawArc(QRectF(cx - 0.05 * s, cy + 0.345 * s, 0.10 * s, 0.07 * s), 200 * 16, 140 * 16)
    elif shape == "rabbit":              # 兔：小鼻 + 门牙
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(colors["nose"]))
        nose = QPainterPath()
        nose.moveTo(cx - s * 0.034, cy + 0.115 * s)
        nose.lineTo(cx + s * 0.034, cy + 0.115 * s)
        nose.lineTo(cx, cy + 0.160 * s)
        nose.closeSubpath()
        p.drawPath(nose)
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(_line(line_c, lw * 0.85))
        p.drawRoundedRect(QRectF(cx - 0.052 * s, cy + 0.195 * s, 0.104 * s, 0.085 * s),
                          0.02 * s, 0.02 * s)
        p.drawLine(QPointF(cx, cy + 0.195 * s), QPointF(cx, cy + 0.28 * s))
    elif shape == "rooster":             # 鸡：喙 + 肉垂
        bc = QColor(colors["nose"])
        p.setPen(outline)
        p.setBrush(bc)
        upper = QPainterPath()
        upper.moveTo(cx - 0.10 * s, cy + 0.025 * s)
        upper.lineTo(cx + 0.10 * s, cy + 0.025 * s)
        upper.lineTo(cx, cy + 0.115 * s)
        upper.closeSubpath()
        p.drawPath(upper)
        lower = QPainterPath()
        lower.moveTo(cx - 0.055 * s, cy + 0.125 * s)
        lower.lineTo(cx + 0.055 * s, cy + 0.125 * s)
        lower.lineTo(cx, cy + 0.185 * s)
        lower.closeSubpath()
        p.drawPath(lower)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(colors["comb"]))
        p.drawEllipse(QRectF(cx - 0.045 * s, cy + 0.150 * s, 0.09 * s, 0.14 * s))
    elif shape == "snake":               # 蛇：无鼻，吐信子
        p.setPen(mouth_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(cx - 0.07 * s, cy + 0.10 * s, 0.14 * s, 0.09 * s), 200 * 16, 140 * 16)
        if (t % 6.0) < 0.9:
            p.setPen(_line(QColor("#E85A6A"), lw * 0.95))
            ty = cy + 0.19 * s
            p.drawLine(QPointF(cx, ty), QPointF(cx, ty + 0.07 * s))
            p.drawLine(QPointF(cx, ty + 0.07 * s), QPointF(cx - 0.035 * s, ty + 0.105 * s))
            p.drawLine(QPointF(cx, ty + 0.07 * s), QPointF(cx + 0.035 * s, ty + 0.105 * s))
    elif shape == "monkey":              # 猴：小鼻 + 咧嘴
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(colors["nose"]))
        p.drawEllipse(QRectF(cx - 0.05 * s, cy + 0.075 * s, 0.10 * s, 0.07 * s))
        p.setPen(mouth_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(cx - 0.13 * s, cy + 0.09 * s, 0.13 * s, 0.13 * s), 200 * 16, 120 * 16)
        p.drawArc(QRectF(cx, cy + 0.09 * s, 0.13 * s, 0.13 * s), 220 * 16, 120 * 16)
    else:                                # 默认猫式：三角鼻 + W 嘴
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(colors["nose"]))
        nose = QPainterPath()
        nose.moveTo(cx - s * 0.045, cy + 0.115 * s)
        nose.lineTo(cx + s * 0.045, cy + 0.115 * s)
        nose.lineTo(cx, cy + 0.170 * s)
        nose.closeSubpath()
        p.drawPath(nose)
        # 鼻头高光（全部角色通用，鼻子更立体）
        p.setBrush(QColor(255, 255, 255, 150))
        p.drawEllipse(QRectF(cx - s * 0.032, cy + 0.116 * s, s * 0.030, s * 0.021))
        p.setPen(mouth_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(cx - s * 0.090, cy + 0.125 * s, s * 0.090, s * 0.090), 200 * 16, 120 * 16)
        p.drawArc(QRectF(cx, cy + 0.125 * s, s * 0.090, s * 0.090), 220 * 16, 120 * 16)

    # ---- 害怕汗滴（雷暴） ----
    if scared:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#8EC9E8"))
        p.drawEllipse(QRectF(cx + 0.24 * s, cy - 0.42 * s, 0.10 * s, 0.14 * s))

    # ---- 半身：手臂 + 爪掌 + 道具 ----
    if body:
        # 肩线位置与圆润身体对齐：头盖住肩线上方，手臂从身体两侧自然伸出
        body_k = _BODY_SHAPE.get(shape, "round")
        if body_k == "slim":
            shw = s * 0.52
        elif body_k == "long":
            shw = s * 0.50
        elif body_k == "wide":
            shw = s * 0.62
        else:
            shw = s * 0.58
        sx = shw / 2
        sy0 = cy + 0.42 * s                          # 肩线（身体顶部，被头盖住）
        sway = math.sin(t * 1.1) * 0.014 * s
        # 默认姿态：双手自然垂在身体两侧（掌心朝身体内侧）
        L = (cx - sx, sy0, cx - (sx + 0.16 * s), cy + 0.78 * s + sway,
             cx - (sx + 0.24 * s), cy + 0.58 * s, 1.0, 0.0)
        R = (cx + sx, sy0, cx + (sx + 0.16 * s), cy + 0.78 * s - sway,
             cx + (sx + 0.24 * s), cy + 0.58 * s, -1.0, 0.0)
        if action == "wave" and body:               # 挥手：右手抬起左右摆动
            k = _ease(action_k)
            wave = math.sin(k * math.pi * 3.5) * 0.09 * s
            R = (cx + sx, sy0,
                 cx + (sx + 0.16 * s) + wave,
                 cy + 0.78 * s - 0.45 * s * k - sway,
                 cx + (sx + 0.24 * s) + wave * 1.2,
                 cy + 0.58 * s - 0.40 * s * k,
                 -1.0, 0.0)
        if prop == "coffee":                        # 双手捧杯到身前（掌心朝上）
            L = (cx - sx, sy0, cx - 0.24 * s, cy + 0.82 * s + sway,
                 cx - 0.50 * s, cy + 0.60 * s, 0.0, -1.0)
            R = (cx + sx, sy0, cx + 0.24 * s, cy + 0.82 * s - sway,
                 cx + 0.50 * s, cy + 0.60 * s, 0.0, -1.0)
        elif prop == "coin":                        # 双手捧金币（掌心朝上）
            L = (cx - sx, sy0, cx - 0.26 * s, cy + 0.80 * s + sway,
                 cx - 0.52 * s, cy + 0.62 * s, 0.0, -1.0)
            R = (cx + sx, sy0, cx + 0.26 * s, cy + 0.80 * s - sway,
                 cx + 0.52 * s, cy + 0.62 * s, 0.0, -1.0)
        elif prop == "heart":                       # 双手捧爱心（掌心朝上）
            L = (cx - sx, sy0, cx - 0.26 * s, cy + 0.80 * s + sway,
                 cx - 0.52 * s, cy + 0.62 * s, 0.0, -1.0)
            R = (cx + sx, sy0, cx + 0.26 * s, cy + 0.80 * s - sway,
                 cx + 0.52 * s, cy + 0.62 * s, 0.0, -1.0)
        elif prop == "bag":                         # 右手拎包（掌心朝内/左）
            R = (cx + sx, sy0, cx + (sx + 0.16 * s), cy + 0.74 * s - sway,
                 cx + (sx + 0.24 * s), cy + 0.56 * s, -1.0, 0.0)
        elif prop == "fan":                         # 右手举扇（掌心朝内/左）
            R = (cx + sx, sy0 - 0.02 * s, cx + (sx + 0.16 * s), cy + 0.46 * s,
                 cx + (sx + 0.24 * s), cy + 0.36 * s, -1.0, 0.0)
        elif prop == "umbrella":                    # 右手举伞（掌心朝内/左）
            R = (cx + sx, sy0 - 0.04 * s, cx + sx * 0.90, cy + 0.16 * s,
                 cx + (sx + 0.06 * s), cy + 0.26 * s, -1.0, 0.0)
        elif prop == "scarf":                       # 冷：双手抱胸（掌心朝内）
            L = (cx - sx, sy0, cx - 0.22 * s, cy + 0.72 * s + sway,
                 cx - 0.48 * s, cy + 0.58 * s, 1.0, 0.0)
            R = (cx + sx, sy0, cx + 0.22 * s, cy + 0.72 * s - sway,
                 cx + 0.48 * s, cy + 0.58 * s, -1.0, 0.0)
        if excited and prop is None:                # 快下班：双手举起欢呼（掌心朝前）
            L = (cx - sx, sy0, cx - 0.54 * s, cy + 0.24 * s,
                 cx - 0.60 * s, cy + 0.30 * s, 0.0, -1.0)
            R = (cx + sx, sy0, cx + 0.54 * s, cy + 0.24 * s,
                 cx + 0.60 * s, cy + 0.30 * s, 0.0, -1.0)
        if pet_k is not None:                       # 被摸头：双手捧脸（掌心朝上偏内）
            k = math.sin(max(0.0, min(1.0, pet_k)) * math.pi) * 0.9
            tgt = ((cx - 0.40 * s, cy + 0.18 * s), (cx + 0.40 * s, cy + 0.18 * s))
            new = []
            for a, (tx, ty) in zip((L, R), tgt):
                nx = 0.55 if a[2] < cx else -0.55   # 掌心朝脸（内侧 + 上）
                ny = -0.84
                new.append((a[0], a[1],
                            a[2] + (tx - a[2]) * k, a[3] + (ty - a[3]) * k,
                            a[4] + (tx - a[4]) * k * 0.6,
                            a[5] + (ty - a[5]) * k * 0.6,
                            nx, ny))
            L, R = new

        hand_kind = _HAND.get(colors.get("shape", "cat"), "paw")

        # 围巾先画（绕脖子，手臂抱在围巾上）
        if prop == "scarf":
            _draw_prop(p, "scarf", cx, cy, s, colors)

        # 手臂：锥形，从身体侧面伸出
        if hand_kind != "none":
            for a in (L, R):
                _draw_arm(p, a[0], a[1], a[2], a[3], a[4], a[5], s, colors, outline)

        # 道具（双手/单手），画在手臂之后、手掌之前
        if prop and prop != "scarf":
            if prop in ("coffee", "coin"):
                _draw_prop(p, prop, cx, cy, s, colors)
            elif prop in ("bag", "fan", "umbrella"):
                _draw_prop(p, prop, cx, cy, s, colors, side="R", wx=R[2], wy=R[3])

        # 手掌覆盖道具，形成"握住"
        if hand_kind != "none":
            for a in (L, R):
                _draw_hand(p, a[2], a[3], s, colors, outline, hand_kind,
                           palm_nx=a[6], palm_ny=a[7])

    # ---- Zzz ----
    if sleepy:
        for i, (dx, dy, a) in enumerate(((0.34, -0.44, 230), (0.50, -0.60, 190), (0.64, -0.76, 150))):
            zz = s * (0.085 + i * 0.022)
            zx, zy = cx + dx * s, cy + dy * s
            z = QPainterPath()
            z.moveTo(zx - zz / 2, zy - zz / 2)
            z.lineTo(zx + zz / 2, zy - zz / 2)
            z.lineTo(zx - zz / 2, zy + zz / 2)
            z.lineTo(zx + zz / 2, zy + zz / 2)
            p.setPen(QPen(QColor(255, 255, 255, a), max(1.3, s * 0.022), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawPath(z)

    if dim25:
        p.restore()          # 收尾视差倾斜/挤压变换

    p.restore()


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
    draw_cat(p, size / 2, size * 0.56, size * 0.82, colors)
    p.end()
    return QIcon(pm)

