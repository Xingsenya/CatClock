# -*- coding: utf-8 -*-
"""A1：鼠标 / 键盘 / 拖拽惯性 / 边缘吸附 / 全局热键（CatClock 的 _InteractMixin）。

从 app.py 拆出：所有和用户手指相关的交互集中在这里。

注意：`_WinMSG` 必须在模块顶层定义 —— 在窗口回调里再 import ctypes 会触发
Windows loader lock，进程会被 fail-fast 杀掉（0xC000041D）。
"""
import ctypes
import math
from ctypes import wintypes
from datetime import datetime

from PyQt6.QtCore import Qt, QPoint, QPointF, QTimer, QRect, QRectF
from PyQt6.QtGui import QCursor, QColor
from PyQt6.QtWidgets import QApplication, QWidget, QMenu

from . import data as D
from .draw import make_paw_cursor
from .util import save_cfg, font

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 1, 2, 4, 8, 0x4000

_VK_EXTRA = {
    "ESC": 0x1B, "SPACE": 0x20, "TAB": 0x09, "ENTER": 0x0D, "RETURN": 0x0D,
    "BACKSPACE": 0x08, "INS": 0x2D, "DEL": 0x2E, "HOME": 0x24, "END": 0x23,
    "PGUP": 0x21, "PGDOWN": 0x22, "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27,
    "DOWN": 0x28, "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD,
    "\\": 0xDC, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
}


class _WinMSG(ctypes.Structure):
    """Windows MSG（只取前 6 个字段足够判断消息号）"""
    _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD), ("pt", wintypes.POINT)]


def _parse_hotkey(seq):
    """F1：把 'Ctrl+Alt+H' 解析成 (mods, vk)；留空/无法识别返回 None。"""
    if not seq:
        return None
    parts = [x.strip() for x in str(seq).split("+") if x.strip()]
    mods, key = 0, None
    for p in parts:
        u = p.upper()
        if u in ("CTRL", "CONTROL", "STRG"):
            mods |= MOD_CONTROL
        elif u == "ALT":
            mods |= MOD_ALT
        elif u == "SHIFT":
            mods |= MOD_SHIFT
        elif u in ("WIN", "SUPER", "META"):
            mods |= MOD_WIN
        else:
            key = p
    if not key:
        return None
    u = key.upper()
    if u.startswith("F") and u[1:].isdigit() and 1 <= int(u[1:]) <= 24:
        return mods, 0x6F + int(u[1:])
    if u in _VK_EXTRA:
        return mods, _VK_EXTRA[u]
    if len(key) == 1:
        return mods, ord(u)
    return None


class _InteractMixin:
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            gpt = e.globalPosition().toPoint()
            # 惯性滑行中按下：立刻接管，停下滑行
            if self._fling_timer.isActive():
                self._fling_timer.stop()
                self._after_drag()
            # 吸附状态下按下先把窗口滑出来，保证拖动起点正确
            self._dock_slide_finish()
            if self._dock_edge and not self._dock_out:
                self._dock_set(True, instant=True)
            pos = self.mapFromGlobal(gpt)      # 滑出后重新换算局部坐标
            s = float(self.cfg.get("scale", 1.0))
            lx, ly = pos.x() / s, pos.y() / s      # 换算到逻辑坐标
            cs, ccx, ccy = self._cat_geo()
            self._press_on_cat = (lx - ccx) ** 2 + (ly - ccy) ** 2 < (cs * 0.52) ** 2
            self._press_pos = gpt
            self.drag_off = gpt - self.frameGeometry().topLeft()
            self._drag_vel = [0.0, 0.0]           # A5：重新累计拖动速度
            self._drag_last = (gpt.x(), gpt.y())
            e.accept()


    def wheelEvent(self, e):
        step = e.angleDelta().y() / 120 * 0.1     # 每格 10%
        self.set_scale(float(self.cfg.get("scale", 1.0)) + step)
        e.accept()


    def mouseMoveEvent(self, e):
        if self.drag_off is not None and e.buttons() & Qt.MouseButton.LeftButton:
            gpt = e.globalPosition().toPoint()
            if self._drag_last is not None:        # A5：指数平滑累计速度
                dx = gpt.x() - self._drag_last[0]
                dy = gpt.y() - self._drag_last[1]
                self._drag_vel[0] = self._drag_vel[0] * 0.6 + dx * 0.4
                self._drag_vel[1] = self._drag_vel[1] * 0.6 + dy * 0.4
            self._drag_last = (gpt.x(), gpt.y())
            self.move(gpt - self.drag_off)
            e.accept()
        else:
            # E3：悬停猫身上 —— 抬头看你 + 爪型光标 + 偶尔抖一下耳朵
            pos = e.position()
            s = float(self.cfg.get("scale", 1.0))
            lx, ly = pos.x() / s, pos.y() / s
            cs, ccx, ccy = self._cat_geo()
            on_cat = (lx - ccx) ** 2 + (ly - ccy) ** 2 < (cs * 0.55) ** 2
            if on_cat:
                if not self.hover_cat:
                    self.hover_cat = True
                    self._set_paw_cursor(True)
                    if self.cfg.get("dim25") and self.ear_tw is None:
                        self.ear_tw = (random.choice((-1, 1)), self.t0)
                if self.hover_cat_t == 0.0 and self.meow_bubble_t >= 2.5 \
                        and random.random() < 0.15:
                    self.meow_bubble_t = 0.0
                self.hover_cat_t += 0.1
            else:
                if self.hover_cat:
                    self.hover_cat = False
                    self._set_paw_cursor(False)
                self.hover_cat_t = 0.0


    def mouseReleaseEvent(self, e):
        if self.drag_off is not None:
            self.drag_off = None
            self._drag_last = None
            # A5：甩手后惯性滑行一段；速度太小就直接落位
            vx = max(-26.0, min(26.0, self._drag_vel[0]))
            vy = max(-26.0, min(26.0, self._drag_vel[1]))
            if self.cfg.get("fling", True) and (abs(vx) + abs(vy)) >= 2.5:
                self._drag_vel = [vx, vy]
                self._fling_timer.start(16)
            else:
                self._after_drag()
        # 点击（非拖动）且按在猫头上才算摸到猫
        if (self._press_pos is not None and self._press_on_cat
                and (e.globalPosition().toPoint() - self._press_pos).manhattanLength() < 10):
            self.meow_t = 0.0
            self.meow_bubble_t = 0.0
        self._press_pos = None
        self._press_on_cat = False


    def mouseDoubleClickEvent(self, e):
        # 双击猫头 = 心情打卡；双击其它地方 = 切换秒显示
        pos = e.position()
        s = float(self.cfg.get("scale", 1.0))
        lx, ly = pos.x() / s, pos.y() / s
        cs, ccx, ccy = self._cat_geo()
        if (lx - ccx) ** 2 + (ly - ccy) ** 2 < (cs * 0.55) ** 2:
            self.ask_mood()
        else:
            self.toggle_sec(not bool(self.cfg.get("show_sec", True)))


    def contextMenuEvent(self, e):
        self.act_auto.setChecked(autostart_enabled())
        self.menu.exec(e.globalPos())


    def enterEvent(self, e):
        self.hover = True
        self._bg_invalidate()
        self.update()


    def leaveEvent(self, e):
        self.hover = False
        self.hover_cat = False
        self._set_paw_cursor(False)
        self._bg_invalidate()
        self.update()


    def closeEvent(self, e):
        self.cfg["pos"] = list(self._dock_off or (self.x(), self.y()))
        save_cfg(self.cfg)
        e.accept()


    def _set_paw_cursor(self, on):
        """E3：猫身上换爪型光标（程序绘制，懒加载一次）。"""
        if not on:
            self.unsetCursor()
            return
        if self._paw_cursor is None:
            try:
                self._paw_cursor = make_paw_cursor(32)
            except Exception:
                self._paw_cursor = False
        if self._paw_cursor:
            self.setCursor(self._paw_cursor)
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _after_drag(self):
        """拖动/滑行结束：收边、吸附、记位置。"""
        self._clamp()
        self._apply_dock()                 # 边缘吸附（悬停会临时滑出）
        px, py = self._dock_off or (self.x(), self.y())
        self.cfg["pos"] = [px, py]         # 存"完整可见"位置，便于下次恢复
        save_cfg(self.cfg)


    def _fling_step(self):
        vx, vy = self._drag_vel
        x, y = self.x() + int(round(vx)), self.y() + int(round(vy))
        g = self._screen().availableGeometry()
        w, h = self.width(), self.height()
        bounced = False
        if x < g.left():                   # 撞边：反向并大幅衰减，形成轻弹
            x, vx, bounced = g.left(), -vx * 0.38, True
        elif x > g.right() - w:
            x, vx, bounced = g.right() - w, -vx * 0.38, True
        if y < g.top():
            y, vy, bounced = g.top(), -vy * 0.38, True
        elif y > g.bottom() - h:
            y, vy, bounced = g.bottom() - h, -vy * 0.38, True
        self.move(x, y)
        if not bounced:
            vx, vy = vx * 0.90, vy * 0.90
        self._drag_vel = [vx, vy]
        if abs(vx) + abs(vy) < 0.6:
            self._fling_timer.stop()
            self._after_drag()

    def _unregister_hotkey(self):
        try:
            hwnd = int(self.winId())
            for hid in (1, 2, 3):
                ctypes.windll.user32.UnregisterHotKey(hwnd, hid)
        except Exception:
            pass


    def _register_hotkey(self):
        """F1：注册全局热键（1=老板键 / 2=显示隐藏 / 3=番茄钟）。

        组合键可在设置 → 高级里自定义；留空表示不注册。注册失败（被其它程序
        占用）静默跳过，菜单里仍然能用。"""
        self._unregister_hotkey()
        self._hotkey_ok = False
        jobs = ((1, "hotkey_boss" if self.cfg.get("boss_key", True) else None),
                (2, "hotkey_show"), (3, "hotkey_pomo"))
        try:
            hwnd = int(self.winId())
        except Exception:
            return
        self._hotkey_err = []
        for hid, ckey in jobs:
            if not ckey:
                continue
            seq = str(self.cfg.get(ckey, "") or "").strip()
            if not seq:
                continue
            parsed = _parse_hotkey(seq)
            if parsed is None:
                self._hotkey_err.append("%s：无法识别" % seq)
                continue
            mods, vk = parsed
            try:
                ok = ctypes.windll.user32.RegisterHotKey(
                    hwnd, hid, mods | MOD_NOREPEAT, vk)
            except Exception:
                ok = False
            if ok:
                self._hotkey_ok = True
            else:
                self._hotkey_err.append("%s：被占用或无效" % seq)


    def nativeEvent(self, eventType, message):
        """接收 WM_HOTKEY（老板键）。

        坑：PyQt6 要求返回 (bool, int)，而基类实现会返回 (False, None)，
        直接透传会让 sip 转换失败并导致进程被 fail-fast 杀掉，
        所以这里一定规范化成 (bool, int) 再返回。"""
        handled, result = False, 0
        try:
            if not isinstance(eventType, str):
                eventType = bytes(eventType).decode("utf-8", "ignore")
            if eventType in ("windows_generic_MSG", "windows_dispatcher_MSG"):
                msg = _WinMSG.from_address(int(message))
                if msg.message == WM_HOTKEY:
                    wid = int(msg.wParam)
                    if wid == 1:
                        self.toggle_boss()
                    elif wid == 2:
                        self._show_or_hide()
                    elif wid == 3:
                        self.toggle_pomo()
                    handled = True
        except Exception:
            pass
        try:
            base = super().nativeEvent(eventType, message)
            if isinstance(base, tuple) and len(base) == 2:
                handled = handled or bool(base[0])
                result = int(base[1]) if base[1] is not None else 0
        except Exception:
            pass
        return handled, result


    def toggle_boss(self):
        """一键隐身 / 恢复（老板来了）"""
        if self._hidden:
            self._hidden = False
            self.show()
            self.raise_()
            if self._dock_edge:
                self._dock_set(False)
                self._dock_timer.start()
        else:
            self._hidden = True
            self._dock_slide_finish()
            self._dock_timer.stop()
            self.hide()
            self.tray.showMessage(
                APP_NAME, "猫先躲起来了（Ctrl+Alt+H 唤回）",
                QSystemTrayIcon.MessageIcon.Information, 2000)

    def _apply_dock(self):
        """拖放结束 / 配置变更后重新判断吸附。会先复位再计算，可重复调用。"""
        self._dock_timer.stop()
        self._dock_edge = None
        self._dock_off = None
        self._dock_pos = None
        self._dock_out = True
        self._dock_leave = None
        if not self.cfg.get("edge_dock", True):
            return
        try:
            ag = self._screen().availableGeometry()
        except Exception:
            return
        w, h = self.width(), self.height()
        x, y = self.x(), self.y()
        TH = 70
        edge = None
        if x - ag.left() < TH:
            edge = "left"
        elif ag.right() - (x + w) < TH:
            edge = "right"
        elif y - ag.top() < TH:
            edge = "top"
        if edge is None:
            return
        off = int(w * 0.58)
        if edge == "left":
            px, py = ag.left() - off, y
        elif edge == "right":
            px, py = ag.right() - w + off, y
        else:
            px, py = x, ag.top() - int(h * 0.55)
        self._dock_edge = edge
        self._dock_off = (x, y)
        self._dock_pos = (px, py)
        self._dock_last = self.t0
        self._dock_set(False, instant=True)   # 先收起来
        self._dock_timer.start()


    def _dock_set(self, out, instant=False):
        """在"贴边完整可见"与"藏到边缘外"之间切换；幂等 + 冷却由调用方保证。"""
        if out == self._dock_out:
            return
        self._dock_out = out
        self._dock_last = self.t0
        self._dock_leave = None
        tgt = self._dock_off if out else self._dock_pos
        if tgt:
            if instant:
                self._dock_slide_timer.stop()
                self._dock_slide = None
                self.move(*tgt)
            else:
                self._dock_slide_to(QPoint(*tgt))
        if out:
            self.raise_()


    def _dock_slide_to(self, target):
        """约 130ms 的缓动滑动（只是视觉过渡，判定仍用逻辑目标位置）"""
        start = QPoint(self.x(), self.y())
        if start == target:
            return
        self._dock_slide = (start, target, 0)
        self._dock_slide_timer.start()


    def _dock_slide_step(self):
        if not self._dock_slide:
            self._dock_slide_timer.stop()
            return
        st, tg, i = self._dock_slide
        i += 1
        n = 8
        k = min(1.0, i / n)
        e = 1 - (1 - k) ** 3                  # ease-out cubic
        self.move(int(st.x() + (tg.x() - st.x()) * e),
                  int(st.y() + (tg.y() - st.y()) * e))
        if k >= 1.0:
            self._dock_slide = None
            self._dock_slide_timer.stop()
        else:
            self._dock_slide = (st, tg, i)


    def _dock_slide_finish(self):
        """拖动 / 隐藏前调用：立刻结束动画并落到终点，避免和拖动打架"""
        self._dock_slide_timer.stop()
        if self._dock_slide:
            self.move(self._dock_slide[1])
            self._dock_slide = None


    def _dock_watch(self):
        """80ms 轮询鼠标全局位置做迟滞判断。
        不用 enter/leave 事件直接移动窗口——窗口一动就会重新触发
        enter/leave，形成「滑出→离开→收回→又滑出」的高频抖动（抽搐）。
        这里改为：鼠标进触发带才滑出；鼠标离开完整窗口且持续 0.45s 才收回。
        """
        if self._hidden or self.drag_off is not None:
            return
        if not (self._dock_edge and self._dock_off and self._dock_pos):
            self._dock_timer.stop()
            return
        try:
            cur = QCursor.pos()
        except Exception:
            return
        w, h = self.width(), self.height()
        ox, oy = self._dock_off
        px, py = self._dock_pos
        now = self.t0
        # 收起时露出的那一小块（+8px 容差）→ 进入即滑出
        hid = QRect(px, py, w, h).adjusted(-8, -8, 8, 8)
        # 滑出后的完整窗口（+18px 迟滞带）→ 离开这么宽才算真的走了
        full = QRect(ox, oy, w, h).adjusted(-18, -18, 18, 18)
        if self._dock_out:
            if full.contains(cur):
                self._dock_leave = None
            else:
                if self._dock_leave is None:
                    self._dock_leave = now
                if now - self._dock_leave > 0.45 and now - self._dock_last > 0.25:
                    self._dock_set(False)
        else:
            if hid.contains(cur) and now - self._dock_last > 0.12:
                self._dock_set(True)

    def _screen(self):
        return QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()


    def _place(self):
        pos = self.cfg.get("pos")
        screen = QApplication.primaryScreen().availableGeometry()
        if pos and isinstance(pos, list) and len(pos) == 2:
            self.move(int(pos[0]), int(pos[1]))
            # 上次是靠边收起的，启动后恢复吸附；首次启动（无记录）保持完整可见
            self._apply_dock()
        else:
            self.move(screen.right() - self.width() - 28,
                      screen.bottom() - self.height() - 60)


    def _clamp(self):
        g = self._screen().availableGeometry()
        x = min(max(self.x(), g.left()), g.right() - self.width())
        y = min(max(self.y(), g.top()), g.bottom() - self.height())
        self.move(x, y)

    def _on_screen_changed(self, screen):
        if screen:
            self._guard_visible()


    def _on_screen_added(self, _=None):
        self._guard_visible()


    def _on_screen_removed(self, _=None):
        self._guard_visible()


    def _guard_visible(self):
        try:
            g = self._screen().availableGeometry()
            if not g.intersects(self.frameGeometry()):
                screen = QApplication.primaryScreen().availableGeometry()
                self.move(screen.right() - self.width() - 28,
                          screen.bottom() - self.height() - 60)
        except Exception:
            pass


    def reset_pos(self):
        self.cfg["pos"] = None
        save_cfg(self.cfg)
        self._place()


    def show_and_raise(self):
        self.show()
        self.raise_()
        self._clamp()


    def quit(self):
        self.cfg["pos"] = list(self._dock_off or (self.x(), self.y()))
        save_cfg(self.cfg)
        self.tray.hide()
        QApplication.quit()
