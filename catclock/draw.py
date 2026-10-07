# -*- coding: utf-8 -*-
"""程序化矢量绘制：猫/动物、帽子、道具、天气图标、托盘图标。"""
import math

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QLinearGradient, QRadialGradient,
    QPixmap, QFont, QIcon, QCursor,
)

from . import data as D
from .util import _mix, _q_luma
from .data import (_HEAD, _EYE, _EYE_DEFAULT, _TAIL, _TAIL_MOOD, _HAND, _HAT,
                   _HAT_EXT, _BODY_SHAPE, _TOP_EXT, _FACE, _EYE_STYLE,
                   _NOSE_STYLE, _POSE)

CHARACTERS = D.CHARACTERS
STYLES = D.STYLES


from .gfx import _ease, _ease_out, _lod, _line, _mix, _q_luma
from .parts import (_draw_paw, _draw_hand, _draw_arm, _draw_hat,
                    _draw_acc, _draw_prop)


def _head_path(rect, face):
    """A1：按脸型生成头部轮廓（默认 round = 椭圆）。

    face 见 data._FACE：
      wide  牛/猪/虎  下半更宽更饱满，头顶略收
      long  马/蛇     修长窄脸，往下收
      heart 猴        上宽下尖
      puffy 羊        羊毛波浪边缘
      sharp 鸡        上圆下尖，往喙收
      brow  龙        眉骨处两侧凸起
    """
    if not face or face == "round":
        pp = QPainterPath()
        pp.addEllipse(rect)
        return pp
    cx0, cy0 = rect.center().x(), rect.center().y()
    rx, ry = rect.width() / 2.0, rect.height() / 2.0
    N = 96
    pts = []
    for i in range(N):
        a = 2.0 * math.pi * i / N
        ca, sa = math.cos(a), math.sin(a)
        kx, ky = 1.0, 1.0
        up = max(0.0, -sa)          # 上半量 0..1
        dn = max(0.0, sa)           # 下半量 0..1
        if face == "wide":
            kx = 1.0 + 0.13 * dn - 0.05 * up
            ky = 1.0 + 0.04 * dn
        elif face == "long":
            kx = 1.0 - 0.20 * dn
            ky = 1.0 + 0.06 * dn
        elif face == "heart":
            kx = 1.0 - 0.30 * dn
            if sa < -0.55:                      # 顶部中央微凹，形成心形
                ky = 1.0 - 0.10 * (abs(sa) - 0.55) / 0.45
        elif face == "puffy":
            w = math.sin(a * 7.0) * 0.035 + math.sin(a * 11.0) * 0.022
            kx = ky = 1.0 + w
        elif face == "sharp":
            kx = 1.0 - 0.26 * dn
            ky = 1.0 + 0.05 * dn
        elif face == "brow":
            if sa < -0.25 and abs(ca) > 0.40:   # 眼上方两侧眉骨
                ky = 1.0 + 0.08 * (abs(ca) - 0.40) / 0.60
        pts.append(QPointF(cx0 + ca * rx * kx, cy0 + sa * ry * ky))
    pp = QPainterPath(pts[0])
    for pt in pts[1:]:
        pp.lineTo(pt)
    pp.closeSubpath()
    return pp


def draw_cat(p, cx, cy, s, colors=None, blink=False, excited=False, sleepy=False,
             scared=False, look=(0.0, 0.0), mood=None, action=None, action_k=0.0,
             tail_phase=None, t=0.0, dim25=False, pet_k=None, ear_tw=None,
             body=False, prop=None, hat="auto", acc="auto",
             eye_lid=0.0, mouth=None, mouth_open=0.0, tail_mood="calm"):
    """画一只可爱的猫脑袋。s 为整体直径；look 为瞳孔偏移(-1..1)；mood 已弃用，请用 action
    action: 待机动作（stretch/yawn/wave/tail_wag），action_k 为 0..1 进度
    tail_phase 摇尾；dim25=2.5D 模式；pet_k 摸猫进度 0..1；ear_tw=(方向±1, 进度0..1) 耳抖
    body=半身模式（圆身体+前爪）；prop=手上的道具；hat=帽子；acc=配饰

    1.5 新增：
      eye_lid   : 眼睑闭合度 0=睁开 1=全闭（A2，眨眼/犯困走同一条曲线）
      mouth     : 情绪口型 'smile' / 'flat' / 'frown' / None=经典 W 嘴（C1）
      mouth_open: 张嘴程度 0..1（C2，说话 / 喵叫时开合）
      tail_mood : 'calm' / 'happy' / 'angry' / 'scared' / 'focus'（E4）"""
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
    # A1：脸型轮廓（宽扁 / 修长 / 心形 / 蓬松 / 尖脸 / 眉骨）
    face = _FACE.get(shape, "round")
    head_path = _head_path(head_rect, face)

    # ---- 尾巴（最底层；按物种分样式，不再所有角色共用猫尾） ----
    if tail_phase is not None:
        if body:
            bx, by = cx - 0.46 * s, cy + 0.66 * s
        else:
            bx, by = cx - 0.38 * s, cy + 0.32 * s
        # sw 已被行波实现取代，保留注释备查
        # sw = math.sin(tail_phase) * 0.18 * s
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
        else:                                  # E1：默认猫尾 —— 行波摆动（根不动、尖端抖）
            amp, freq, lift = _TAIL_MOOD.get(tail_mood or "calm", (1.0, 1.0, 0.0))
            ph = tail_phase * freq
            p0 = (bx, by)
            p1 = (bx - 0.185 * s, by + 0.070 * s)
            p2 = (bx - 0.020 * s, by - (0.26 + lift) * s)

            def _bez(u):
                mt = 1.0 - u
                return (mt * mt * p0[0] + 2 * mt * u * p1[0] + u * u * p2[0],
                        mt * mt * p0[1] + 2 * mt * u * p1[1] + u * u * p2[1])

            N = 9
            pts = []
            for i in range(N + 1):
                u = i / float(N)
                x, y = _bez(u)
                # 行波：相位随位置滞后，振幅按 u^1.4 从根到尖递增
                w = math.sin(ph - u * 2.35) * 0.155 * s * amp * (u ** 1.4)
                pts.append(QPointF(x + w, y))
            # 分段绘制：根粗尖细（E1 附带的体积感），圆头保证接缝连续
            w0, w1 = max(2.2, s * 0.062), max(1.0, s * 0.024)
            for i in range(N):
                u = (i + 0.5) / float(N)
                p.setPen(QPen(fd, w0 + (w1 - w0) * u, Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap))
                p.drawLine(pts[i], pts[i + 1])
            # 尖端一抹亮色
            p.setPen(QPen(fl, max(1.0, s * 0.020), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawLine(pts[N - 2], pts[N])

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
                # A4：角面立体渐变（根亮尖沉）+ 外侧一道高光，不再是平涂色块
                g = QLinearGradient(cx + sign * 0.20 * s, cy - 0.28 * s,
                                    cx + sign * 0.52 * s, cy - 0.76 * s)
                g.setColorAt(0, QColor(horn_c))
                g.setColorAt(0.55, QColor(horn_c))
                g.setColorAt(1, _mix(horn_c, "#8A7460", 0.42))
                p.setBrush(g)
                p.drawPath(h)
                p.setPen(_line(QColor(255, 255, 255, 120), lw * 1.30))
                p.setBrush(Qt.BrushStyle.NoBrush)
                hl = QPainterPath()
                hl.moveTo(cx + sign * 0.26 * s, cy - 0.36 * s)
                hl.cubicTo(cx + sign * 0.44 * s, cy - 0.48 * s,
                           cx + sign * 0.54 * s, cy - 0.62 * s,
                           cx + sign * 0.49 * s, cy - 0.71 * s)
                p.drawPath(hl)
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
                # A4：龙角用珍珠渐变（根暖尖冷）+ 角身高光，有玉质感
                g = QLinearGradient(base_x, base_y,
                                    base_x + sign * 0.14 * s, cy - 0.74 * s)
                g.setColorAt(0, QColor("#FFF8E4"))
                g.setColorAt(0.50, QColor(horn_c))
                g.setColorAt(1, _mix(horn_c, "#9AAE9E", 0.48))
                p.setBrush(g)
                p.drawPath(branch)
                p.setPen(_line(QColor(255, 255, 255, 150), lw * 1.15))
                p.setBrush(Qt.BrushStyle.NoBrush)
                hl2 = QPainterPath()
                hl2.moveTo(base_x + sign * 0.03 * s, base_y - 0.03 * s)
                hl2.cubicTo(base_x + sign * 0.09 * s, cy - 0.47 * s,
                            base_x + sign * 0.07 * s, cy - 0.60 * s,
                            base_x + sign * 0.025 * s, cy - 0.69 * s)
                p.drawPath(hl2)
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
            # A4：内耳再叠一层亮粉心，兔耳不再是一片平涂
            p.setBrush(_mix(colors["ear_in"], "#FFFFFF", 0.50))
            p.drawEllipse(QRectF(-0.026 * s, -0.345 * s, 0.052 * s, 0.25 * s))
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
    p.drawPath(head_path)

    # ---- 斑块 ----
    if colors.get("patches"):
        head_clip = QPainterPath(head_path)
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
        tiger_clip = QPainterPath(head_path)
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
    head_clip = QPainterPath(head_path)
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
    p.drawPath(head_path)
    if lod >= 1:
        # 上缘内高光（rim light）：暗色角色靠它从背景里「浮」出来
        ins = lw * 0.85
        p.setPen(_line(QColor(255, 255, 255, int(58 * rim)), lw * 0.85, join=False))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(_head_path(head_rect.adjusted(ins, ins * 0.55, -ins, -ins * 1.75),
                              face))
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

    # ---- 胡须（D1 弧线 + D4 随呼吸/情绪摆动） ----
    if shape in ("cat", "rat", "rabbit", "tiger", "dragon"):
        hp = _line(QColor("#CFC9DC") if dark else QColor("#E0AC76"), lw * 0.78)
        p.setPen(hp)
        dys = (-0.03, 0.11) if lod == 0 else (-0.03, 0.04, 0.11)   # A7：小尺寸少一根
        mid = (len(dys) - 1) / 2.0
        # D4：呼吸微摆；摸猫/打喷嚏抖；开心时须根上扬、不开心时下垂
        br = math.sin(t * 1.15) * 0.010
        if pet_k is not None:
            br += math.sin(max(0.0, min(1.0, pet_k)) * math.pi * 6.0) * 0.045
        if action == "sneeze":
            br += math.sin(action_k * math.pi * 8.0) * 0.065
        if scared:
            br -= 0.030
        wl = 0.0
        if mouth == "smile":
            wl = -0.022
        elif mouth == "frown":
            wl = 0.030
        for sign in (-1, 1):
            for k, dy in enumerate(dys):
                y = cy + (dy + wl) * s
                x0 = cx + sign * 0.17 * s
                x1 = x0 + sign * 0.26 * s
                ye = y + (k - mid) * s * 0.055 + br * s
                # D1：二次贝塞尔微弧（上须上扬、下须下垂，中间近乎平直）
                arc = (k - mid) * s * 0.030 + br * s * 0.8
                wp = QPainterPath()
                wp.moveTo(x0, y)
                wp.quadTo(QPointF(x0 + sign * 0.14 * s, y - arc * 0.55),
                          QPointF(x1, ye))
                p.drawPath(wp)

    # ---- 眼睛（A2 眼型物种化；保留 v1.4 柔和虹膜 + A2 眼睑 + A6 眼神跟随） ----
    eye_dy, ewk, ehk, slit = _EYE.get(shape, _EYE_DEFAULT)
    eye_y = cy + (-0.02 + eye_dy) * s
    ew2, ehh = ewk * s, ehk * s
    # A2：按物种微调眼型
    eye_style = _EYE_STYLE.get(shape, "default")
    if eye_style == "red_big":          # 兔：更大更圆，虹膜偏红
        ew2, ehh = ew2 * 1.18, ehh * 1.15
    elif eye_style == "squint":         # 羊：眯缝眼
        ehh = ehh * 0.62
    elif eye_style == "bright":         # 鸡 / 鼠：小而亮
        ew2, ehh = ew2 * 0.92, ehh * 0.94
    eye_c = colors["eye"]
    if eye_style == "red_big":
        eye_c = _mix(colors["eye"], "#D9546E", 0.55)
    lid = max(0.0, min(1.0, float(eye_lid or 0.0)))
    # 兼容旧调用：没传 eye_lid 但传了 blink/sleepy 时，按全闭处理
    if lid < 0.02 and (blink or sleepy):
        lid = 1.0
    # A6：整只眼睛随 look 滑动（不是只有瞳孔动），眼神更自然
    lx = max(-1.0, min(1.0, look[0])) * s * 0.030
    ly = max(-1.0, min(1.0, look[1])) * s * 0.022
    for sign in (-1, 1):
        ex = cx + sign * 0.185 * s
        if excited and lid < 0.45:
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
            continue
        if lid >= 0.97:
            # 全闭：上弯的笑眼弧
            p.setPen(_line(QColor(colors["eye"]), lw * 1.85))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(ex - ew2 * 1.25, eye_y - ehh * 0.29,
                             ew2 * 2.50, ehh * 0.58), 180 * 16, 180 * 16)
            continue
        # 虹膜：上浅下深，保持原来可爱的柔和渐变
        p.setPen(Qt.PenStyle.NoPen)
        if colors.get("pupil"):            # 熊猫式：白眼 + 深色瞳孔
            p.setBrush(QColor(colors["eye"]))
        elif slit:                         # 龙 / 蛇：金色虹膜
            g = QLinearGradient(ex, eye_y - ehh / 2, ex, eye_y + ehh / 2)
            g.setColorAt(0, QColor("#F2C14E"))
            g.setColorAt(1, QColor("#C68E0F"))
            p.setBrush(g)
        else:
            g = QLinearGradient(ex, eye_y - ehh / 2, ex, eye_y + ehh / 2)
            g.setColorAt(0, QColor(eye_c))
            g.setColorAt(1, _mix(eye_c, "#14100E", 0.5))
            p.setBrush(g)
        p.drawEllipse(QRectF(ex - ew2 + lx, eye_y - ehh / 2 + ly, 2 * ew2, ehh))
        # 虹膜外圈细眼线
        p.setPen(_line(_mix(eye_c, "#14100E", 0.55), lw * 0.72, join=False))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(ex - ew2 + lx, eye_y - ehh / 2 + ly, 2 * ew2, ehh))
        p.setPen(Qt.PenStyle.NoPen)
        if colors.get("pupil"):            # 熊猫式：白眼 + 深色瞳孔
            pw, ph = ew2 * 0.44, ehh * 0.20
            p.setBrush(QColor(colors["pupil"]))
            p.drawEllipse(QRectF(ex - pw + lx, eye_y - ph + ly + ehh * 0.04,
                                 2 * pw, 2 * ph))
            p.setBrush(QColor("#FFFFFF"))
            p.drawEllipse(QRectF(ex + ew2 * 0.16 + lx, eye_y - ehh * 0.10 + ly,
                                 ew2 * 0.26, ew2 * 0.26))
        elif slit:                         # 龙 / 蛇：竖缝瞳 + 高光
            p.setBrush(QColor("#12100E"))
            pw, ph = ew2 * 0.30, ehh * 0.42
            p.drawEllipse(QRectF(ex - pw + lx, eye_y - ph + ly, 2 * pw, 2 * ph))
            p.setBrush(QColor(255, 255, 255, 200))
            p.drawEllipse(QRectF(ex + ew2 * 0.28 + lx, eye_y - ehh * 0.34 + ly,
                                 ew2 * 0.34, ehh * 0.24))
        else:
            # 原版高光：随眼球一起动，看起来光源在猫脸上而不是世界里
            p.setBrush(QColor("#FFFFFF"))
            p.drawEllipse(QRectF(ex + ew2 * 0.12 + lx, eye_y - ehh * 0.33 + ly,
                                 ew2 * 0.76, ehh * 0.29))
            if lod >= 1:
                p.drawEllipse(QRectF(ex - ew2 * 0.70 + lx, eye_y + ehh * 0.10 + ly,
                                     ew2 * 0.35, ehh * 0.13))
            if eye_style == "bright":     # 鸡 / 鼠：再点一颗亮斑，眼神更锐利
                p.setBrush(QColor(255, 255, 255, 220))
                p.drawEllipse(QRectF(ex - ew2 * 0.28 + lx, eye_y + ehh * 0.28 + ly,
                                     ew2 * 0.30, ehh * 0.16))
        # A2：droopy —— 下眼睑弧（外角下垂，看起来温柔没脾气）
        if eye_style == "droopy":
            p.setPen(_line(_mix(eye_c, "#14100E", 0.45), lw * 0.85))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(ex - ew2 * 1.12, eye_y + ehh * 0.06,
                             ew2 * 2.24, ehh * 1.05), 20 * 16, 140 * 16)
        # A2：上眼睑（柔和覆盖，laugh 弧形的闭合线）
        if lid > 0.02:
            cover = ehh * lid
            fur_up = QColor(colors.get("fur_l") or colors["fur"])
            lp = QPainterPath()
            lp.moveTo(ex - ew2 * 1.14, eye_y - ehh * 0.60)
            lp.quadTo(ex, eye_y - ehh * 0.78, ex + ew2 * 1.14, eye_y - ehh * 0.60)
            lp.lineTo(ex + ew2 * 1.14, eye_y - ehh * 0.52 + cover)
            lp.quadTo(ex, eye_y - ehh * 0.52 + cover + ehh * 0.12 * (1.0 - lid),
                      ex - ew2 * 1.14, eye_y - ehh * 0.52 + cover)
            lp.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fur_up)
            p.drawPath(lp)
            # 眼睑下缘细线
            p.setPen(_line(_mix(colors["eye"], "#14100E", 0.30), lw * 1.25))
            p.setBrush(Qt.BrushStyle.NoBrush)
            ep = QPainterPath()
            ep.moveTo(ex - ew2 * 1.10, eye_y - ehh * 0.52 + cover)
            ep.quadTo(ex, eye_y - ehh * 0.52 + cover + ehh * 0.12 * (1.0 - lid),
                      ex + ew2 * 1.10, eye_y - ehh * 0.52 + cover)
            p.drawPath(ep)

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
        # A3：鼻头湿润高光（左上受光，与角色统一）
        p.setBrush(QColor(255, 255, 255, 135))
        p.drawEllipse(QRectF(cx - 0.105 * s, cy + 0.100 * s, 0.080 * s, 0.045 * s))
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
        # A3：鼻头湿润高光
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 130))
        p.drawEllipse(QRectF(cx - 0.085 * s, cy + 0.200 * s, 0.070 * s, 0.038 * s))
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
        # A3：三瓣嘴 —— 鼻尖下方的 Y 形上唇分叉
        p.setPen(_line(line_c, lw * 1.05))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy + 0.158 * s), QPointF(cx, cy + 0.192 * s))
        p.drawArc(QRectF(cx - 0.070 * s, cy + 0.170 * s, 0.070 * s, 0.055 * s),
                  200 * 16, 140 * 16)
        p.drawArc(QRectF(cx, cy + 0.170 * s, 0.070 * s, 0.055 * s), 200 * 16, 140 * 16)
        p.setPen(Qt.PenStyle.NoPen)
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
    else:                                # 默认猫式：三角鼻 + 口型（C1/C2）
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
        mo = float(mouth_open or 0.0)
        if mo > 0.06:
            # C2：说话 / 喵叫 —— 张开的小嘴 + 舌头（开合由 mouth_open 驱动）
            mw = s * (0.030 + 0.052 * mo)
            mh = s * (0.018 + 0.070 * mo)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#7A4A3A"))
            p.drawEllipse(QRectF(cx - mw, cy + 0.148 * s, 2 * mw, 2 * mh))
            if mo > 0.35:                # 舌头
                p.setBrush(QColor("#F2909C"))
                p.drawEllipse(QRectF(cx - mw * 0.62, cy + (0.148 + 0.030) * s
                                     + mh * 0.55, mw * 1.24, mh * 0.62))
            p.setPen(_line(line_c, lw * 1.10))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(cx - mw, cy + 0.148 * s, 2 * mw, 2 * mh), 180 * 16, 180 * 16)
        elif mouth == "smile":           # C1：开心 —— 嘴角上扬，弧度更大
            p.drawArc(QRectF(cx - s * 0.098, cy + 0.108 * s, s * 0.098, s * 0.098),
                      195 * 16, 135 * 16)
            p.drawArc(QRectF(cx, cy + 0.108 * s, s * 0.098, s * 0.098),
                      210 * 16, 135 * 16)
        elif mouth == "flat":            # C1：平静 —— 一条短横线
            p.drawLine(QPointF(cx - s * 0.045, cy + 0.170 * s),
                       QPointF(cx + s * 0.045, cy + 0.170 * s))
        elif mouth == "frown":           # C1：累了 / 不开心 —— 嘴角下压
            p.drawArc(QRectF(cx - s * 0.090, cy + 0.152 * s, s * 0.090, s * 0.078),
                      20 * 16, 130 * 16)
            p.drawArc(QRectF(cx, cy + 0.152 * s, s * 0.090, s * 0.078),
                      30 * 16, 130 * 16)
        else:                            # 经典 W 嘴
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


# A2：图标类已拆到 icons.py，这里 re-export 保持 `from .draw import make_icon` 等旧写法可用
from .icons import (heart_path, draw_weather_icon, make_icon,
                    make_tray_icon, make_paw_cursor)
