# -*- coding: utf-8 -*-
"""A1：所有绘制相关（CatClock 的 _PaintMixin）。

从 app.py 拆出：面板背景缓存、猫的几何、语录气泡、天气氛围、主 paintEvent。
"""
import math
from datetime import datetime, timedelta

from PyQt6.QtCore import Qt, QPointF, QRect, QRectF, QTimer
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPainterPath, QPen, QLinearGradient,
    QRadialGradient, QPixmap, QCursor,
)
from PyQt6.QtWidgets import QApplication

from . import data as D
from . import ui as U
from .draw import draw_cat, heart_path, draw_weather_icon
from .util import font, rr, _mix, _q_luma
from . import log


def _mix_rgb(c, q, k):
    """A2：把 RGB 元组 c 向 QColor q 混合 k 比例（0..1），返回新元组。"""
    t = (q.red(), q.green(), q.blue())
    return tuple(int(round(c[i] + (t[i] - c[i]) * k)) for i in range(3))


class _PaintMixin:
    def _paint_impl(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.drawPixmap(0, 0, self._bg_pixmap())     # 面板走缓存，不再每帧重画阴影
        s = float(self.cfg.get("scale", 1.0))
        p.scale(s, s)                       # 全局等比缩放，后续全部用逻辑坐标
        W = self.W
        mini = self.cfg.get("mini", False)
        H = self._cur_h()
        pad = 5
        yo = 0 if mini else self.BUB_TOP      # 非迷你：内容整体下移，给头顶气泡让位
        st = self.style()

        phase, start, end, secs, pct = self._status()
        excited = phase == "work" and secs <= 1800 and not self.afk
        sleepy = phase == "off" or self.afk
        show_sec = self.cfg.get("show_sec", True)
        if show_sec:
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
        else:
            # 时分模式：分钟向上取整（"还有 X 分钟"的语义，和手机一致）
            total_min = (secs + 59) // 60
            h, m = divmod(total_min, 60)
            s = 0

        # 猫（雷暴/严寒发抖；高温冒汗；瞳孔跟随鼠标；待机小动作；摇尾巴）
        cs, ccx, ccy = self._cat_geo()
        meowing = self.meow_t < 0.7
        thunder = bool(self.weather) and self.weather["kind"] == "thunder"
        wtemp = self.weather["temp"] if self.weather else None
        too_hot = wtemp is not None and wtemp >= 34 and phase == "work"
        too_cold = wtemp is not None and wtemp <= 0
        shake = math.sin(self.t0 * 42) * 1.6 if (thunder or too_cold) else 0
        cur = QCursor.pos()
        s_f = float(self.cfg.get("scale", 1.0))
        look = ((cur.x() - (self.x() + ccx * s_f)) / (160.0 * s_f),
                (cur.y() - (self.y() + ccy * s_f)) / (160.0 * s_f))
        mood = None if mini else (self.idle[0] if self.idle else None)
        action = self.action if not mini else None
        action_k = 0.0
        if action and self.action_dur:
            action_k = max(0.0, min(1.0, (self.t0 - self.action_start) / self.action_dur))
        # 静止降频：冻结尾摆与眨眼，避免低帧率下画面一跳一跳
        still = self.lowfps and not self._anim_active()
        # 摇尾：平时慢摆，摸猫时快摆
        tail_phase = 0.6 if still else \
            (self.t0 * (7.0 if meowing else 1.8)) + (2.0 if meowing else 0.0)
        dim25 = bool(self.cfg.get("dim25", False))
        ear_tw = None
        if dim25 and self.ear_tw:
            ear_tw = (self.ear_tw[0], (self.t0 - self.ear_tw[1]) / 0.6)
        # 半身模式：按状态决定手上的道具
        body = bool(self.cfg.get("body", True))
        prop = self._prop_now()
        # E3：鼠标停在猫身上时轻微抬头（配合爪型光标，像在看你）
        lift = -cs * 0.025 if self.hover_cat else 0.0
        # C1：静止时走缓存（见 _draw_cat_cached），动画期间照常逐帧画
        cat_kw = dict(
            blink=(self.blink_t < 0.18 or meowing) and not still,
            excited=excited, sleepy=sleepy,
            scared=thunder or too_hot, look=look, action=action,
            action_k=action_k, tail_phase=tail_phase, t=self.t0, dim25=dim25,
            pet_k=self.meow_t if self.meow_t < 1.0 else None, ear_tw=ear_tw,
            body=body, prop=prop, hat=self._effective_hat(), acc=self._effective_acc())
        self._draw_cat_cached(p, ccx + shake, ccy + lift, cs,
                              self.char_colors(), **cat_kw)

        # E1：面板天气氛围（雨雪落在面板上，盖住猫但压在文字之下）
        self._draw_weather_fx(p, W, H, st)

        # 天气小图标（右上角）
        if self.weather and not mini:
            draw_weather_icon(p, W - 36, 14 + yo, 22, self.weather["kind"], self.t0)

        # 摸猫爱心
        if self.meow_t < 1.0:
            k = self.meow_t
            hx = ccx + cs * 0.40
            hy = ccy - cs * 0.62 - k * 16
            size = cs * (0.28 + 0.10 * k)
            p.save()
            p.setOpacity(max(0.0, 1.0 - k * k))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(st["pink"]))
            p.drawPath(heart_path(hx, hy, size))
            p.restore()

        x = 98 if mini else 112
        tw = W - x - 14
        yc = (H + yo) / 2.0                   # 视觉中心（含气泡区后的等效中心）
        quote_h = 0                           # 语录气泡占高，用于下推发薪日/进度条

        # ---- 主文字区 ----
        if phase == "rest":
            p.setPen(QColor(st["pink"]))
            p.setFont(font("Microsoft YaHei", 20, QFont.Weight.Bold))
            p.drawText(QRectF(x, yc - 34, tw, 36),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "今天休息～")
            p.setPen(QColor(st["sub"]))
            p.setFont(font("Microsoft YaHei", 9))
            now = datetime.now()
            p.drawText(QRectF(x, yc + 2, tw, 18),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       "%d月%d日 · 好好放松" % (now.month, now.day))
            pay = self.payday_info()
            if pay:
                p.setPen(QColor(st["pink"]))
                p.drawText(QRectF(x, yc + 22, tw, 16),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "¥ %s" % pay)
        else:
            # 倒计时数字
            if phase == "off":
                p.setPen(QColor(st["pink"]))
                p.setFont(font("Microsoft YaHei", 20 if not mini else 18, QFont.Weight.Bold))
                p.drawText(QRectF(x, 14 + yo, tw, 36),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "下班啦～")
            else:
                fcol = QColor(st["pink"] if excited else st["text"])
                size = 24 if mini else (26 if show_sec else 30)
                p.setFont(font("Segoe UI", size, QFont.Weight.Bold, QFont.StyleHint.SansSerif))
                cy0 = (H / 2 - 38) if mini else 12 + yo
                if show_sec:
                    txt = "%02d:%02d:%02d" % (h, m, s)
                    p.setPen(fcol)
                    p.drawText(QRectF(x, cy0, tw, 38),
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, txt)
                else:
                    # 时分模式：冒号每秒闪烁，表示时间在走
                    p.setPen(fcol)
                    p.drawText(QRectF(x, cy0, tw, 38),
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "%02d" % h)
                    fw = p.fontMetrics().horizontalAdvance("%02d" % h)
                    ccol = QColor(fcol)
                    if int(self.t0 * 2) % 2 == 0:
                        ccol.setAlpha(90)
                    p.setPen(ccol)
                    p.drawText(QRectF(x + fw, cy0, tw, 38),
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, ":")
                    fw += p.fontMetrics().horizontalAdvance(":")
                    p.setPen(fcol)
                    p.drawText(QRectF(x + fw, cy0, tw, 38),
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "%02d" % m)

            # 行1：天气 + 距下班（按可用宽度自适应精简，防右侧裁切）
            p.setPen(QColor(st["sub"]))
            p.setFont(font("Microsoft YaHei", 9))
            wt = self.weather["text"] if self.weather else ""
            tp = self.weather["temp"] if self.weather else None
            wx_full = "%s %d°C · " % (wt, tp) if tp is not None else ""
            wx_cmp = "%s·" % wt if wt else ""
            if mini:
                sub = {"pre": "%s 开工" % start.strftime("%H:%M"),
                       "work": "距 %s" % end.strftime("%H:%M"),
                       "off": "已下班"}.get(phase, "")
                p.drawText(QRectF(x, H / 2 - 2, tw, 18),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sub)
            else:
                fm = p.fontMetrics()

                def pick(cands):
                    for t in cands:
                        if fm.horizontalAdvance(t) <= tw:
                            return t
                    return cands[-1]

                if phase == "pre":
                    line1 = pick([wx_full + "%s 开工 · 还没上班呢" % start.strftime("%H:%M"),
                                  wx_cmp + "%s 开工" % start.strftime("%H:%M"),
                                  "%s 开工" % start.strftime("%H:%M")])
                elif phase == "work":
                    if excited:
                        line1 = "快下班了，冲！"
                    else:
                        hm = end.strftime("%H:%M")
                        line1 = pick([wx_full + "距 %s 下班" % hm,
                                      wx_cmp + "距%s下班" % hm,
                                      "距 %s 下班" % hm])
                else:
                    if datetime.now().hour >= 22:
                        line1 = pick([wx_full + "夜深了，早点休息", "夜深了，早点休息"])
                    else:
                        line1 = pick([wx_full + "已下班 %d 小时 %02d 分" % (h, m),
                                      "已下班 %d 小时 %02d 分" % (h, m),
                                      "已下班 %dh%02d" % (h, m)])
                # C2：番茄钟运行时，副行改显示番茄倒计时（不跟天气抢宽度）
                if self.pomo:
                    mm, ss = divmod(max(0, int(self.pomo["left"])), 60)
                    if self.pomo["mode"] == "focus":
                        line1 = "专注 %02d:%02d · 别摸鱼～" % (mm, ss)
                    else:
                        line1 = "休息 %02d:%02d · 动一动" % (mm, ss)
                p.drawText(QRectF(x, 50 + yo, tw, 16),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, line1)

                # 猫头顶气泡：临时消息优先，其次是语录（形状随情绪自动切换）
                msg = None
                kind = "say"
                if self.hydrate_t < 5.0:
                    k = self.hydrate_t
                    kind = "hydrate"
                    msg = ("喝口水，动一动～", 255 if k < 4.0 else max(0, int(255 * (5.0 - k))))
                elif self.hourly_t < 3.0:
                    k = self.hourly_t
                    kind = "hourly"
                    msg = ("%d 点啦" % datetime.now().hour, 255 if k < 2.2 else max(0, int(255 * (3.0 - k) / 0.8)))
                elif self.meow_bubble_t < 2.5:
                    k = self.meow_bubble_t
                    kind = "meow"
                    msg = ("呼噜噜～" if self.meow_t < 1.0 else "喵～",
                           255 if k < 1.8 else max(0, int(255 * (2.5 - k) / 0.7)))
                elif self.bubble_t < 3.5:
                    k = self.bubble_t
                    msg = (self.bubble_text or "",
                           255 if k < 2.6 else max(0, int(255 * (3.5 - k) / 0.9)))
                else:
                    if phase == "work" and not self.afk:
                        q = self._quote()
                        if q:
                            kind = "quote"
                            msg = (q, 255)

                if msg:
                    text, alpha = msg
                    # 右侧文字区：气泡在时间/副行下方，尾巴朝左指向猫
                    _, bh = self._draw_bubble(p, x, 66 + yo, tw, text, st, alpha=alpha,
                                              shape=self._bubble_shape(kind, excited))
                    # 气泡高过预留的 14px 才把下方内容整体下移，减少跳动
                    quote_h = max(0, bh - 14)

                # 行3：发薪日
                pay = self.payday_info()
                if pay and phase != "pre":
                    p.setPen(QColor(st["pink"]))
                    p.drawText(QRectF(x, 83 + yo + quote_h, tw, 15),
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                               "¥ %s" % pay)

        # ---- 进度条（非迷你、非休息日） ----
        if not mini and phase != "rest":
            bx, by, bw, bh = x, 102 + yo + quote_h, tw, 6
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(*st["bar_bg"]))
            p.drawPath(rr(bx, by, bw, bh, bh / 2))
            fillw = bw * pct
            if fillw > 0.5:
                if phase == "off":
                    gg = QLinearGradient(bx, 0, bx + bw, 0)
                    gg.setColorAt(0, QColor(*st["bar0_off"]))
                    gg.setColorAt(1, QColor(*st["bar1_off"]))
                else:
                    gg = QLinearGradient(bx, 0, bx + bw, 0)
                    c0, c1 = st["bar0"], st["bar1"]
                    # A2：越接近下班，进度条越向主题粉靠拢（暖度递进）
                    if phase == "work" and pct > 0.80:
                        k = min(1.0, (pct - 0.80) / 0.20) * 0.55
                        pk = QColor(st["pink"])
                        c0, c1 = _mix_rgb(c0, pk, k), _mix_rgb(c1, pk, k)
                    gg.setColorAt(0, QColor(*c0))
                    gg.setColorAt(1, QColor(*c1))
                p.setBrush(gg)
                p.drawPath(rr(bx, by, max(fillw, bh), bh, bh / 2))

            # 进度条末端猫爪
            if phase == "work" and pct > 0.02:
                px, py = bx + fillw, by + bh / 2
                r = 5.2
                p.setBrush(QColor(st["pink"]))
                p.drawEllipse(QRectF(px - r * 0.85, py - r * 0.45, r * 1.7, r * 1.5))
                for a in (-0.85, 0.0, 0.85):
                    tx = px + math.sin(a) * r * 1.45
                    ty = py - r * 1.45 - abs(math.cos(a)) * r * 0.25
                    p.drawEllipse(QRectF(tx - r * 0.40, ty - r * 0.40, r * 0.80, r * 0.80))

        p.end()

    # ---------------- C1：猫身绘制缓存 ----------------
    # 猫是逐帧矢量绘制（几十个 path + 渐变），秒显模式下每秒要重画 10 次。
    # 静止时外观几乎不变，把它缓存成 pixmap 直接贴图；只有动画期间才逐帧画。
    CAT_W, CAT_H, CAT_OY = 2.0, 2.4, 0.9      # 缓存画布相对 cs 的宽/高/中心纵向偏移

    def _cat_cache_key(self, cs, colors, kw):
        """影响猫外观的全部参数；只要有一项变了就得重画。"""
        look = kw.get("look") or (0.0, 0.0)
        ear = kw.get("ear_tw")
        pk = kw.get("pet_k")
        return (
            self.cfg.get("char"), int(cs), colors.get("shape", "cat"),
            bool(kw.get("body")), kw.get("prop"), kw.get("hat"), kw.get("acc"),
            bool(kw.get("blink")), bool(kw.get("excited")), bool(kw.get("sleepy")),
            bool(kw.get("scared")), kw.get("action"),
            round(float(kw.get("action_k") or 0.0), 2),
            round(float(kw.get("tail_phase") or 0.0), 1),
            round(float(kw.get("t") or 0.0) / 0.5) * 0.5,      # 呼吸量化到 0.5s
            bool(kw.get("dim25")),
            None if pk is None else round(float(pk), 2),
            None if ear is None else (ear[0], round(float(ear[1]), 2)),
            round(float(look[0]), 1), round(float(look[1]), 1),   # 瞳孔跟随量化
            round(float(self.cfg.get("scale", 1.0)), 2),
            round(float(self.devicePixelRatioF() or 1.0), 2),
        )

    def _draw_cat_cached(self, p, cx, cy, cs, colors, **kw):
        """画猫：动画期间直接画，静止时复用上一帧的 pixmap。"""
        # 有动画在跑 → 必须逐帧画，同时让缓存失效，动画结束后重新建立
        try:
            animating = self._anim_active()
        except Exception:
            animating = True
        if animating:
            self._cat_key = None
            draw_cat(p, cx, cy, cs, colors, **kw)
            return

        key = self._cat_cache_key(cs, colors, kw)
        # PyQt6 drawPixmap 不支持 QRectF 目标，用 QPointF 定位 + pixmap 逻辑尺寸
        pos = QPointF(cx - cs, cy - self.CAT_OY * cs)
        if self._cat_key == key and self._cat_pm is not None:
            p.drawPixmap(pos, self._cat_pm)
            return

        K = min(3.0, max(1.0, (self.devicePixelRatioF() or 1.0)
                         * float(self.cfg.get("scale", 1.0))))
        pm = QPixmap(int(self.CAT_W * cs * K), int(self.CAT_H * cs * K))
        pm.fill(Qt.GlobalColor.transparent)
        qp = QPainter(pm)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        qp.scale(K, K)
        draw_cat(qp, cs, self.CAT_OY * cs, cs, colors, **kw)
        qp.end()
        pm.setDevicePixelRatio(K)          # 逻辑尺寸 = 像素 / K，正好等于 CAT_W*cs x CAT_H*cs
        self._cat_pm, self._cat_key = pm, key
        p.drawPixmap(pos, pm)

    # ---------------- A4：异常兜底 ----------------
    def paintEvent(self, e):
        """绘制出错时降级到「面板 + 一行字」，绝不白屏、绝不崩溃。"""
        try:
            self._paint_impl(e)
        except Exception:
            from . import log
            log.exception("paintEvent")
            try:
                self._paint_fallback()
            except Exception:
                pass

    def _paint_fallback(self):
        """降级画面：只画面板和一个提示，保证挂件仍然可见、可右键退出。"""
        from . import log
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            st = self.style()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(*st["panel0"]))
            p.drawRoundedRect(QRectF(4, 4, self.width() - 8, self.height() - 8), 20, 20)
            p.setPen(QColor(*st["text"]))
            p.setFont(font("Microsoft YaHei", 10))
            p.drawText(QRectF(10, 10, self.width() - 20, self.height() - 20),
                       Qt.AlignmentFlag.AlignCenter,
                       "CatClock 绘制异常\n已降级显示（详见日志）")
        except Exception:
            log.exception("paint_fallback")
        finally:
            p.end()



    def _bg_pixmap(self):
        """带阴影的圆角面板：内容只在外观变化时重绘，平时直接贴图。"""
        key = (self.cfg.get("style"), bool(self.hover), bool(self.cfg.get("mini")),
               round(float(self.cfg.get("scale", 1.0)), 2), self.width(), self.height(),
               self._is_night(), int(self.cfg.get("panel_alpha", 255)),
               bool(self.cfg.get("panel_shadow", True)))
        if self._bg_key == key and self._bg_pm is not None:
            return self._bg_pm
        st = self.style()
        night = self._is_night()
        # E4：面板不透明度（半透明玻璃感）；夜间再向深色压一档
        alpha = max(120, min(255, int(self.cfg.get("panel_alpha", 255) or 255)))

        def _pc(rgb):
            c = QColor(*rgb)
            if night:
                c = _mix(c, QColor(26, 24, 34), 0.18)
            c.setAlpha(alpha)
            return c

        s = float(self.cfg.get("scale", 1.0))
        mini = bool(self.cfg.get("mini", False))
        W = self.W
        H = self.H_MINI if mini else self.H_FULL
        pad = 5
        dpr = self.devicePixelRatioF() or 1.0
        pm = QPixmap(int(self.width() * dpr), int(self.height() * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        q = QPainter(pm)
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        q.scale(s, s)
        # E4：柔和阴影（可关）
        if self.cfg.get("panel_shadow", True):
            for i in range(6):
                k = 5 - i
                inset = pad + k * 1.2 - 1.2
                q.setPen(Qt.PenStyle.NoPen)
                q.setBrush(QColor(st["shadow"][0], st["shadow"][1], st["shadow"][2], 8 + k * 4))
                q.drawPath(rr(inset, inset + 1.6, W - 2 * inset, H - 2 * inset, 25))
        # 面板
        g = QLinearGradient(0, pad, 0, H - pad)
        g.setColorAt(0, _pc(st["panel0"]))
        g.setColorAt(1, _pc(st["panel1"]))
        q.setBrush(g)
        ba = 235 if self.hover else 190
        bcol = st["border_h"] if self.hover else st["border"]
        q.setPen(QPen(QColor(bcol[0], bcol[1], bcol[2], int(ba * alpha / 255.0)), 1.3))
        q.drawPath(rr(pad, pad, W - 2 * pad, H - 2 * pad, 24))
        q.end()
        self._bg_key = key
        self._bg_pm = pm
        return pm

    def _bg_invalidate(self):
        """面板外观变了就丢弃缓存（配色 / 悬停 / 尺寸 / 迷你模式）"""
        self._bg_key = None
        self._bg_pm = None


    def _draw_weather_fx(self, p, W, H, st):
        """雨滴沿面板滑落 / 雪花飘落 / 雷暴闪光。粒子位置由 t0 推导，无需保存状态。"""
        kind = self._weather_fx_kind()
        if kind is None:
            return
        pad = 5
        p.save()
        p.setClipPath(rr(pad, pad, W - 2 * pad, H - 2 * pad, 24))   # 只在面板圆角内画
        if kind == "snow":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 190))
            for i in range(22):
                r = (i * 37) % 100 / 100.0
                x = pad + 6 + ((i * 53) % int(W - 2 * pad - 12))
                span = H - 2 * pad
                y = pad + ((self.t0 * (14 + (i % 5) * 5) + r * span * 3) % span)
                x += math.sin(self.t0 * 0.9 + i) * 5.0              # 左右轻摆
                d = 1.6 + (i % 3) * 0.7
                p.drawEllipse(QRectF(x, y, d, d))
        else:
            # 雨：斜线；thunder 时偶尔整块提亮（闪光）
            if kind == "thunder":
                fl = (self.t0 % 7.0)
                if fl < 0.14:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(255, 255, 255, 70))
                    p.drawPath(rr(pad, pad, W - 2 * pad, H - 2 * pad, 24))
            pen = QPen(QColor(255, 255, 255, 150), 1.3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            span = H - 2 * pad
            for i in range(26):
                r = (i * 41) % 100 / 100.0
                x = pad + 4 + ((i * 61) % int(W - 2 * pad - 8))
                y = pad + ((self.t0 * (300 + (i % 4) * 90) + r * span * 4) % (span + 30)) - 30
                ln = 12 + (i % 3) * 5
                p.drawLine(QPointF(x, y), QPointF(x - 2.8, y + ln))
        p.restore()

    def _weather_fx_kind(self):
        """当前该画哪种氛围：rain / snow / thunder / None。"""
        if not self.cfg.get("weather_fx", True):
            return None
        if not self.weather:
            return None
        k = self.weather.get("kind")
        if k in ("rain", "thunder"):
            return k
        if k in ("snow", "sleet"):
            return "snow"
        return None


    def _draw_bubble(self, p, x, y, max_w, text, st, alpha=255, shape="round",
                     bottom=None, tail_x=None):
        """漫画气泡：形状随情绪切换，飘在猫头顶上方（bottom=气泡底边 y）。
        尾巴朝下指向猫头；自动换行，返回实际 (宽, 高)。"""
        if not text:
            return 0, 0
        p.save()
        p.setFont(font("Microsoft YaHei", 9))
        fm = p.fontMetrics()
        lh = fm.height()
        if shape in ("heart", "drop"):
            pad_x, pad_y, max_lines = 15, 9, 1       # 异形泡只放一行，放不下自动降级
        elif shape == "burst":
            pad_x, pad_y, max_lines = 15, 9, 2
        elif shape in ("cloud", "think"):
            pad_x, pad_y, max_lines = 13, 5, 2
        elif shape == "none":
            pad_x, pad_y, max_lines = 0, 0, 2       # 无框：只画文字，不带背景
        else:
            pad_x, pad_y, max_lines = 10, 4, 2
        max_line_w = max(28, int(max_w) - pad_x * 2)
        lines = self._fit_bubble_lines(fm, text, max_line_w, max_lines)
        if not lines:
            p.restore()
            return 0, 0
        if shape in ("heart", "drop") and len(lines) > 1:
            shape, pad_x, pad_y = "round", 10, 4     # 撑不下的异形泡退回圆角
            lines = self._fit_bubble_lines(fm, text, max_line_w, 2)
        t_w = max(fm.horizontalAdvance(l) for l in lines)
        bw = min(int(max_w), max(46, int(t_w + pad_x * 2)))
        bh = lh * len(lines) + pad_y * 2
        if shape == "heart":
            bw = min(int(max_w), max(52, int(t_w + 28)))
            bh = max(26, lh * len(lines) + 14)
        elif shape == "drop":
            bw = min(int(max_w), max(50, int(t_w + 24)))
            bh = max(24, lh * len(lines) + 12)
        if bottom is not None:
            y = max(1.0, bottom - bh)       # 气泡区压窄后，超高气泡贴顶而不越界
        p.setOpacity(max(0.0, min(1.0, alpha / 255.0)))

        if shape == "none":                 # 无气泡：文字直接落在面板上，最不抢戏
            p.setPen(QColor(st["sub"]))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for i, ln in enumerate(lines):
                p.drawText(QRectF(x, y + i * lh, bw, lh),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, ln)
            p.restore()
            return bw, bh

        # 配色随主题走：浅色面板 → 奶白底 + 主题粉细边；深色面板 → 半透明白
        dark = sum(st["panel0"][:3]) / 3.0 < 128
        if dark:
            bg = QColor(255, 255, 255, 34)
            bd = QColor(255, 255, 255, 66)
        else:
            acc = QColor(st["pink"])
            bg = QColor(255, 255, 255, 246)
            bd = QColor(acc.red(), acc.green(), acc.blue(), 96)
        pen = QPen(bd, 1.1)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        # 尾巴：右侧文字区时朝左指向猫；头顶模式(bottom 给定)时朝下指向猫头
        tx = tail_x if tail_x is not None else x + bw / 2.0
        tx = max(x + 10, min(x + bw - 10, tx))
        if bottom is None:
            if shape in ("round", "capsule", "cloud", "burst"):
                tp = QPainterPath()
                ty0 = y + bh * 0.30
                tp.moveTo(QPointF(x + 1.5, ty0))
                tp.lineTo(QPointF(x - 7.0, ty0 + bh * 0.36))
                tp.lineTo(QPointF(x + 1.5, ty0 + bh * 0.72))
                tp.closeSubpath()
                p.setPen(pen)
                p.setBrush(bg)
                p.drawPath(tp)
        elif shape == "think":
            for i, k in enumerate((1.0, 0.62)):
                r = 3.8 * k
                cy_d = y + bh + 2.5 + i * 5.2
                p.setPen(pen)
                p.setBrush(bg)
                p.drawEllipse(QRectF(tx - r, cy_d - r, r * 2, r * 2))
        elif shape in ("round", "capsule", "cloud", "burst"):
            tp = QPainterPath()
            tp.moveTo(QPointF(tx - 6.0, y + bh - 1.5))
            tp.lineTo(QPointF(tx + 6.0, y + bh - 1.5))
            tp.lineTo(QPointF(tx, y + bh + 7.5))
            tp.closeSubpath()
            p.setPen(pen)
            p.setBrush(bg)
            p.drawPath(tp)

        # 气泡本体
        p.setPen(pen)
        p.setBrush(bg)
        p.drawPath(self._bubble_path(shape, x, y, bw, bh))

        # 文字（异形泡视觉重心略偏下，做一点补偿）
        dy = 0.0
        if shape == "heart":
            dy = bh * 0.06
        elif shape == "drop":
            dy = bh * 0.09
        elif shape == "burst":
            dy = 0.0
        p.setPen(QColor(st["text"]))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i, ln in enumerate(lines):
            p.drawText(QRectF(x + pad_x, y + pad_y + i * lh + dy, bw - pad_x * 2, lh),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, ln)
        p.restore()
        return bw, bh


    def _bubble_path(self, shape, x, y, w, h):
        """生成气泡轮廓（文字内边距由 _draw_bubble 负责）。"""
        pp = QPainterPath()
        if shape == "cloud" or shape == "think":
            r = h / 2.0
            n = max(3, min(6, int(w / (r * 1.1))))
            step = (w - 2 * r) / (n - 1) if n > 1 else 0.0
            for i in range(n):                      # 底部一排圆 → 云朵轮廓
                cx = x + r + i * step
                ri = r * (0.84 if 0 < i < n - 1 else 1.0)
                pp.addEllipse(QRectF(cx - ri, y + h / 2 - ri, ri * 2, ri * 2))
            pp.addEllipse(QRectF(x + r * 0.55, y + h * 0.10, r * 1.5, r * 1.5))
            pp.addEllipse(QRectF(x + w - r * 2.05, y + h * 0.16, r * 1.4, r * 1.4))
            pp.setFillRule(Qt.FillRule.WindingFill)
        elif shape == "burst":
            amp = min(6.0, h * 0.22)
            pts = []

            def edge(x0, y0, x1, y1, m, nx, ny):
                for k in range(m):
                    t = k / float(m)
                    off = amp if k % 2 == 0 else -amp * 0.34
                    pts.append((x0 + (x1 - x0) * t + nx * off,
                                y0 + (y1 - y0) * t + ny * off))

            mh = max(4, int(w / 13))
            mv = max(2, int(h / 13))
            edge(x, y, x + w, y, mh, 0, -1)
            edge(x + w, y, x + w, y + h, mv, 1, 0)
            edge(x + w, y + h, x, y + h, mh, 0, 1)
            edge(x, y + h, x, y, mv, -1, 0)
            pp.moveTo(QPointF(pts[0][0], pts[0][1]))
            for qx, qy in pts[1:]:
                pp.lineTo(QPointF(qx, qy))
            pp.closeSubpath()
        elif shape == "heart":
            pts = []
            for i in range(73):
                t = 2 * math.pi * i / 72
                hx = 16 * math.sin(t) ** 3
                hy = -(13 * math.cos(t) - 5 * math.cos(2 * t)
                       - 2 * math.cos(3 * t) - math.cos(4 * t))
                pts.append((hx, hy))
            xs = [q[0] for q in pts]
            ys = [q[1] for q in pts]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            for i, (hx, hy) in enumerate(pts):
                px = x + (hx - x0) / max(1e-6, x1 - x0) * w
                py = y + (hy - y0) / max(1e-6, y1 - y0) * h
                if i == 0:
                    pp.moveTo(QPointF(px, py))
                else:
                    pp.lineTo(QPointF(px, py))
            pp.closeSubpath()
        elif shape == "drop":
            cx = x + w / 2.0
            pp.moveTo(QPointF(cx, y))
            pp.cubicTo(QPointF(x + w * 0.90, y + h * 0.40), QPointF(x + w, y + h * 0.62),
                       QPointF(x + w * 0.86, y + h * 0.84))
            pp.cubicTo(QPointF(x + w * 0.70, y + h), QPointF(x + w * 0.30, y + h),
                       QPointF(x + w * 0.14, y + h * 0.84))
            pp.cubicTo(QPointF(x, y + h * 0.62), QPointF(x + w * 0.10, y + h * 0.40),
                       QPointF(cx, y))
            pp.closeSubpath()
        elif shape == "capsule":
            pp.addRoundedRect(QRectF(x, y, w, h), h / 2.0, h / 2.0)
        else:                                        # round
            pp.addRoundedRect(QRectF(x, y, w, h), min(h * 0.46, 12.0), min(h * 0.46, 12.0))
        return pp

    def _bubble_shape(self, kind, excited=False):
        """B1：按消息类型自动选形状。喝水(水滴) / 摸猫(心形) / 快下班(爆炸框)。
        BUBBLE_STYLE 设为其它值（如 none）时该项全局覆盖。"""
        if self.BUBBLE_STYLE != "auto":
            return self.BUBBLE_STYLE
        if kind == "hydrate":
            return "drop"
        if kind == "meow":
            return "heart"
        if kind == "quote" and excited:
            return "burst"
        return "capsule"          # 默认用胶囊，单行更圆润、不呆板


    def _fit_bubble_lines(self, fm, text, max_w, max_lines=2):
        """断行 + 限行 + 末行孤字回移（避免「敬礼」被单独甩到第二行）。"""
        lines = self._wrap_lines(fm, text, max_w)
        if len(lines) > max_lines:
            rest = "".join(lines[max_lines - 1:])
            head = lines[:max_lines - 1]
            s = ""
            for ch in rest:
                if fm.horizontalAdvance(s + ch + "…") > max_w:
                    break
                s += ch
            lines = head + [s.rstrip() + "…"]
        if len(lines) >= 2 and len(lines[-1]) <= 1 and len(lines[-2]) >= 3:
            lines[-1] = lines[-2][-1] + lines[-1]
            lines[-2] = lines[-2][:-1]
        return lines

    def _wrap_lines(self, fm, text, max_w):
        """按可用宽度贪心断行（逐字符，中英混排都安全）。"""
        lines, cur = [], ""
        for ch in (text or "").replace("\r", "").replace("\n", " "):
            if cur and fm.horizontalAdvance(cur + ch) > max_w:
                lines.append(cur)
                cur = ""
            cur += ch
        if cur:
            lines.append(cur)
        return lines


    def _cat_geo(self, prop="__auto__"):
        """猫(动物)的绘制几何：直径 cs、中心 (ccx, ccy)。
        半身模式按物种头顶延伸系数自动定尺寸，保证「头 + 身体 + 道具」都在画布内。"""
        mini = bool(self.cfg.get("mini", False))
        H = self._cur_h()
        ccx = 54 if mini else 58
        bub = 0 if mini else self.BUB_TOP      # 迷你模式不留气泡区
        if not bool(self.cfg.get("body", True)):
            cs, dy = (60, 0) if mini else (84, 0)
            if self.char_colors().get("shape") == "rabbit":
                cs, dy = (56, 12) if mini else (84, 10)
            return cs, ccx, bub / 2 + H / 2 + dy
        shape = self.char_colors().get("shape", "cat")
        top = D._TOP_EXT.get(shape, 0.64)
        # 帽子占的头顶空间（auto = 物种默认帽 / 节日自动帽）
        hat = self._effective_hat()
        top = max(top, D._HAT_EXT.get(hat, 0.0))
        if prop == "__auto__":
            prop = self._prop_now()
        if prop == "umbrella":
            top = max(top, 0.88)                    # 伞要撑在头顶，多留空间
        # 1.10 给 slim/long 身体、爪子与道具留安全边距，避免半身被裁出画面
        cs = int((H - 10 - bub) / (top + 1.10))
        cs = max(36, min(80, cs))
        return cs, ccx, 6 + bub + top * cs


    def _is_night(self):
        """E1：日落后（20:00–06:00）面板自动压暗一档，夜里不刺眼。"""
        if not self.cfg.get("night_dim", True):
            return False
        h = datetime.now().hour
        return h >= 20 or h < 6
