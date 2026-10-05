# -*- coding: utf-8 -*-
"""主窗口 CatClock。"""
import json
import os
import math
import random
import calendar
import sys
from datetime import datetime, timedelta

from PyQt6.QtCore import Qt, QPoint, QPointF, QTimer, QRectF, QUrl, QObject
from PyQt6.QtGui import (
    QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QLinearGradient,
    QRadialGradient, QPixmap, QAction, QActionGroup, QCursor,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QMenu, QSystemTrayIcon, QInputDialog, QMessageBox,
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QLineEdit, QLabel,
)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from . import data as D
from . import draw as G
from . import weather as W
from . import ui as U
from . import update as UPD
from . import stats
from . import quotes as Q
from . import settings as S
from . import __version__
from .util import (
    APP_NAME, CONFIG_DIR, CONFIG_PATH, DEFAULTS, load_cfg, save_cfg, app_path,
    autostart_enabled, set_autostart, _raise_existing, acquire_single, rr,
    _q_luma, _mix, user_idle_seconds, font,
)
from .draw import draw_cat, heart_path, draw_weather_icon, make_icon
from .data import (
    CHARACTERS, STYLES, WMO_TEXT, wmo_kind, PROP_BY_WEATHER,
)
from .weather import WeatherFetcher
from .ui import CatInputDialog, RestDaysDialog

class CatClock(QWidget):
    W = 272
    H_FULL = 122
    H_MINI = 76

    def __init__(self):
        super().__init__()
        self.cfg = load_cfg()
        self.drag_off = None
        self.t0 = 0.0
        self.blink_t = 0.0
        self.blink_until = 2.5
        self.hover = False
        self.meow_t = 1.0          # >=1 表示不在播放摸猫动画
        self.last_phase = None
        self.weather = None        # dict(city, code, kind, temp, text)
        self.idle = None           # 待机小动作 (name, start_t)
        self.idle_next = 15.0      # 距下次小动作的秒数
        self.action = None         # 当前待机动作（stretch/yawn/wave/tail_wag）
        self.action_start = 0.0
        self.action_dur = 3.0
        self.quote_i = 0
        self.quote_t = 0.0         # 语录轮播计时
        self.hydrate_t = 99.0      # 久坐提醒气泡（>=5 不显示）
        self.last_hydrate = 0.0
        self.hourly_t = 99.0       # 整点报时气泡
        self.last_hour_mark = -1
        self.hover_cat_t = 0.0     # 悬停猫头计时
        self.meow_bubble_t = 99.0  # 摸猫呼噜气泡
        self.bubble_text = None    # 通用气泡文案
        self.bubble_t = 99.0       # 通用气泡计时
        self.afk = False           # 用户离开（猫打瞌睡）
        self._press_pos = None     # 按下时的全局坐标（区分点击/拖动）
        self._press_on_cat = False
        self._prev_secs = None     # 上一帧剩余秒（跨点检测用）
        self._fired_marks = set()  # 本阶段已发过的预告（1800/600）
        self._rest_eve_day = None  # 已提示过的"明天休息"日期
        self.ear_tw = None         # 2.5D 耳抖 (方向, 起始 t0)
        self.next_ear_tw = 12.0    # 下次耳抖的 t0

        self.setWindowTitle(APP_NAME)
        self.set_window_flags()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setWindowIcon(make_icon(64, self.cfg["char"]))
        self.apply_size()

        if self.cfg.get("autostart", True):
            set_autostart(True)

        self._place()
        self._clamp()
        self._build_menu()
        self._build_tray()
        self.apply_app_style()
        self.last_phase = self._status()[0]

        # 天气：启动 1.5s 后首拉，之后每 30 分钟刷新
        self.wx = WeatherFetcher(self)
        self.wx.got.connect(self._wx_got)
        self.wx.failed.connect(self._wx_retry)
        self.weather = None
        try:                                  # 先用上次缓存，联网后再覆盖
            self.weather = W.load_cache()
        except Exception:
            pass
        QTimer.singleShot(1500, self.refresh_weather)
        self.wx_timer = QTimer(self)
        self.wx_timer.timeout.connect(self.refresh_weather)
        self.wx_timer.start(30 * 60 * 1000)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(100)
        self.step = 0.1            # 当前帧间隔（秒），自适应帧率时会变
        self.lowfps = False        # 静止降频模式（冻结尾巴/眨眼，保证画面不跳）
        self._bg_key = None        # 背景面板缓存 key
        self._bg_pm = None         # 背景面板缓存 QPixmap

        # 版本更新：启动 6s 后静默检查一次
        self._update_url = None
        self.auto_check_update()

    # ---------- 窗口 ----------
    def set_window_flags(self):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.cfg.get("top", True):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def apply_size(self):
        s = float(self.cfg.get("scale", 1.0))
        h = self.H_MINI if self.cfg.get("mini") else self.H_FULL
        self.setFixedSize(int(self.W * s), int(int(h) * s))
        self._bg_invalidate()
        self._clamp()
        self.update()

    def set_scale(self, s):
        s = max(0.6, min(1.6, round(float(s), 2)))
        if abs(s - float(self.cfg.get("scale", 1.0))) < 0.001:
            return
        self.cfg["scale"] = s
        save_cfg(self.cfg)
        # 同步「大小」菜单勾选态（滚轮缩放后保持一致）
        try:
            for a in self.size_menu.actions():
                pct = int(a.text().rstrip("%"))
                a.setChecked(abs(pct / 100.0 - s) < 0.001)
        except Exception:
            pass
        old = self.frameGeometry()
        self.apply_size()
        # 缩放时以窗口中心为锚点，避免跳动
        new = self.frameGeometry()
        self.move(old.x() + (old.width() - new.width()) // 2,
                  old.y() + (old.height() - new.height()) // 2)
        self._clamp()

    # ---------- 角色 / 主题 ----------
    def char_colors(self):
        return CHARACTERS[self.cfg["char"]]

    def _prop_now(self):
        """当前手上该拿的道具（半身模式）：发薪金币 / 雨伞 / 扇子 / 围巾 / 拎包 / 咖啡"""
        if not bool(self.cfg.get("body", True)):
            return None
        now = datetime.now()
        pday = int(self.cfg.get("payday", 0) or 0)
        if pday and now.day == min(pday, calendar.monthrange(now.year, now.month)[1]):
            return "coin"
        if self.afk:
            return None                                    # 打瞌睡：不拿东西
        wtemp = self.weather["temp"] if self.weather else None
        wkind = self.weather["kind"] if self.weather else None
        if wkind in ("rain", "thunder"):
            return "umbrella"
        if wtemp is not None and wtemp >= 32:
            return "fan"
        if wtemp is not None and wtemp <= 2:
            return "scarf"
        phase = self._status()[0]
        if phase == "off":
            return "bag"
        if phase == "work":
            return "coffee"
        return None

    def _cat_geo(self, prop="__auto__"):
        """猫(动物)的绘制几何：直径 cs、中心 (ccx, ccy)。
        半身模式按物种头顶延伸系数自动定尺寸，保证「头 + 身体 + 道具」都在画布内。"""
        mini = bool(self.cfg.get("mini", False))
        H = self.H_MINI if mini else self.H_FULL
        ccx = 54 if mini else 58
        if not bool(self.cfg.get("body", True)):
            cs, dy = (60, 0) if mini else (84, 0)
            if self.char_colors().get("shape") == "rabbit":
                cs, dy = (56, 12) if mini else (84, 10)
            return cs, ccx, H / 2 + dy
        shape = self.char_colors().get("shape", "cat")
        top = _TOP_EXT.get(shape, 0.64)
        # 帽子占的头顶空间（auto = 物种默认帽 / 节日自动帽）
        hat = self._effective_hat()
        top = max(top, D._HAT_EXT.get(hat, 0.0))
        if prop == "__auto__":
            prop = self._prop_now()
        if prop == "umbrella":
            top = max(top, 0.88)                    # 伞要撑在头顶，多留空间
        cs = int((H - 8) / (top + 1.02))
        cs = max(30, min(96, cs))
        return cs, ccx, 4 + top * cs

    def style(self):
        return STYLES[self.cfg["style"]]

    def apply_app_style(self):
        st = self.style()
        QApplication.instance().setStyleSheet("""
        QMenu {{ background:{bg}; border:1px solid {bd}; border-radius:10px; padding:6px; }}
        QMenu::item {{ padding:6px 24px; border-radius:6px; color:{tx}; font: 10pt "Microsoft YaHei"; }}
        QMenu::item:selected {{ background:{sel}; }}
        QMenu::separator {{ height:1px; background:{sep}; margin:4px 10px; }}
        QDialog {{ background:{bg}; }}
        QLabel {{ color:{tx}; font: 10pt "Microsoft YaHei"; }}
        QCheckBox {{ color:{tx}; font: 10pt "Microsoft YaHei"; padding:3px; }}
        QLineEdit {{ background:#FFFFFF; color:#4A3B33; border:1px solid {bd};
                     border-radius:6px; padding:5px 8px; font: 10pt "Microsoft YaHei"; }}
        QPushButton {{ background:{sel}; color:{tx}; border:1px solid {bd};
                       border-radius:6px; padding:5px 18px; font: 10pt "Microsoft YaHei"; }}
        QPushButton:hover {{ background:{bd}; }}
        """.format(bg=st["menu_bg"], bd=st["menu_border"], tx=st["menu_text"],
                   sel=st["menu_sel"], sep=st["menu_sep"]))

    def set_char(self, name):
        self.cfg["char"] = name
        save_cfg(self.cfg)
        self.tray.setIcon(make_icon(64, name))
        self.setWindowIcon(make_icon(64, name))
        self.update()

    def set_style(self, name):
        self.cfg["style"] = name
        save_cfg(self.cfg)
        self.apply_app_style()
        self._bg_invalidate()
        self.update()

    # ---------- 位置（支持多屏） ----------
    def _screen(self):
        return QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()

    def _place(self):
        pos = self.cfg.get("pos")
        screen = QApplication.primaryScreen().availableGeometry()
        if pos and isinstance(pos, list) and len(pos) == 2:
            self.move(int(pos[0]), int(pos[1]))
        else:
            self.move(screen.right() - self.width() - 28,
                      screen.bottom() - self.height() - 60)

    def _clamp(self):
        g = self._screen().availableGeometry()
        x = min(max(self.x(), g.left()), g.right() - self.width())
        y = min(max(self.y(), g.top()), g.bottom() - self.height())
        self.move(x, y)

    # ---------- 菜单 ----------
    def _build_menu(self):
        self.menu = QMenu(self)

        self.char_menu = QMenu("角色", self)
        self.char_actions = {}
        grp = QActionGroup(self)
        for name in CHARACTERS:
            a = QAction(name, self, checkable=True)
            a.setChecked(name == self.cfg["char"])
            a.triggered.connect(lambda _, n=name: self.set_char(n))
            grp.addAction(a)
            self.char_menu.addAction(a)
            self.char_actions[name] = a

        self.style_menu = QMenu("样式", self)
        self.style_actions = {}
        grp2 = QActionGroup(self)
        for name in STYLES:
            a = QAction(name, self, checkable=True)
            a.setChecked(name == self.cfg["style"])
            a.triggered.connect(lambda _, n=name: self.set_style(n))
            grp2.addAction(a)
            self.style_menu.addAction(a)
            self.style_actions[name] = a

        self.act_start = QAction("设置上班时间…", self)
        self.act_start.triggered.connect(lambda: self.set_time("start", "上班"))
        self.act_end = QAction("设置下班时间…", self)
        self.act_end.triggered.connect(lambda: self.set_time("end", "下班"))
        self.act_rest = QAction("设置休息日…", self)
        self.act_rest.triggered.connect(self.set_rest_days)
        self.act_city = QAction("设置城市（天气）…", self)
        self.act_city.triggered.connect(self.set_city)
        self.act_payday = QAction("设置发薪日…", self)
        self.act_payday.triggered.connect(self.set_payday)
        self.act_hydrate = QAction("每小时久坐提醒", self, checkable=True)
        self.act_hydrate.setChecked(bool(self.cfg.get("hydrate", True)))
        self.act_hydrate.triggered.connect(lambda on: self.toggle_cfg("hydrate", on))
        self.act_npre = QAction("下班前预告（30/10 分钟）", self, checkable=True)
        self.act_npre.setChecked(bool(self.cfg.get("notify_pre", True)))
        self.act_npre.triggered.connect(lambda on: self.toggle_cfg("notify_pre", on))
        self.act_afk = QAction("离开时猫打瞌睡", self, checkable=True)
        self.act_afk.setChecked(bool(self.cfg.get("afk", True)))
        self.act_afk.triggered.connect(lambda on: self.toggle_cfg("afk", on))
        self.act_25d = QAction("2.5D 立体效果", self, checkable=True)
        self.act_25d.setChecked(bool(self.cfg.get("dim25", False)))
        self.act_25d.triggered.connect(lambda on: self.toggle_cfg("dim25", on))
        self.act_body = QAction("半身小猫（身体+道具）", self, checkable=True)
        self.act_body.setChecked(bool(self.cfg.get("body", True)))
        self.act_body.triggered.connect(lambda on: self.toggle_cfg("body", on))

        # 帽子子菜单
        self.hat_menu = QMenu("帽子", self)
        self.hat_actions = {}
        grp_h = QActionGroup(self)
        cur_hat = str(self.cfg.get("hat", "auto"))
        for key, name in D.HATS:
            a = QAction(name, self, checkable=True)
            a.setChecked(cur_hat == key)
            a.triggered.connect(lambda _, v=key: self.set_hat(v))
            grp_h.addAction(a)
            self.hat_menu.addAction(a)
            self.hat_actions[key] = a

        # 大小子菜单
        self.size_menu = QMenu("大小（也可在窗口上滚轮）", self)
        self.size_actions = {}
        grp_s = QActionGroup(self)
        for pct in D.SIZES:
            a = QAction("%d%%" % pct, self, checkable=True)
            a.setChecked(abs(float(self.cfg.get("scale", 1.0)) - pct / 100.0) < 0.001)
            a.triggered.connect(lambda _, v=pct / 100.0: self.set_scale(v))
            grp_s.addAction(a)
            self.size_menu.addAction(a)
            self.size_actions[pct] = a
        self.act_noff = QAction("下班时通知", self, checkable=True)
        self.act_noff.setChecked(bool(self.cfg.get("notify_off", True)))
        self.act_noff.triggered.connect(lambda on: self.toggle_cfg("notify_off", on))
        self.act_nwork = QAction("上班时提醒", self, checkable=True)
        self.act_nwork.setChecked(bool(self.cfg.get("notify_work", True)))
        self.act_nwork.triggered.connect(lambda on: self.toggle_cfg("notify_work", on))
        self.act_sound = QAction("提示音", self, checkable=True)
        self.act_sound.setChecked(bool(self.cfg.get("sound", True)))
        self.act_sound.triggered.connect(lambda on: self.toggle_cfg("sound", on))
        self.act_mini = QAction("迷你模式", self, checkable=True)
        self.act_mini.setChecked(bool(self.cfg.get("mini")))
        self.act_mini.triggered.connect(self.toggle_mini)
        self.act_sec = QAction("显示秒", self, checkable=True)
        self.act_sec.setChecked(bool(self.cfg.get("show_sec", True)))
        self.act_sec.triggered.connect(self.toggle_sec)
        self.act_top = QAction("始终显示在最前", self, checkable=True)
        self.act_top.setChecked(bool(self.cfg.get("top", True)))
        self.act_top.triggered.connect(self.toggle_top)
        self.act_auto = QAction("开机自动启动", self, checkable=True)
        self.act_auto.setChecked(autostart_enabled())
        self.act_auto.triggered.connect(self.toggle_autostart)
        self.act_settings = QAction("设置…", self)
        self.act_settings.triggered.connect(self.open_settings)
        self.act_stats = QAction("工作统计…", self)
        self.act_stats.triggered.connect(self.show_stats)
        self.act_reset = QAction("回到默认位置", self)
        self.act_reset.triggered.connect(self.reset_pos)
        self.act_update = QAction("检查更新…", self)
        self.act_update.triggered.connect(self.check_update_manual)
        self.act_about = QAction("关于 CatClock", self)
        self.act_about.triggered.connect(self.show_about)
        self.act_quit = QAction("退出", self)
        self.act_quit.triggered.connect(self.quit)

        # 菜单只留高频快捷项，完整设置走「设置…」分组窗口
        self.menu.addAction(self.act_settings)
        self.menu.addSeparator()
        self.menu.addMenu(self.char_menu)
        self.menu.addMenu(self.style_menu)
        self.menu.addMenu(self.hat_menu)
        self.menu.addSeparator()
        self.menu.addAction(self.act_mini)
        self.menu.addAction(self.act_sec)
        self.menu.addAction(self.act_top)
        self.menu.addAction(self.act_auto)
        self.menu.addSeparator()
        self.menu.addMenu(self.size_menu)
        self.menu.addAction(self.act_stats)
        self.menu.addSeparator()
        self.menu.addAction(self.act_update)
        self.menu.addAction(self.act_about)
        self.menu.addSeparator()
        self.menu.addAction(self.act_quit)

        # 需要在设置窗口改动后同步勾选态的动作
        self._check_actions = [
            (self.act_mini, "mini"), (self.act_sec, "show_sec"),
            (self.act_top, "top"), (self.act_hydrate, "hydrate"),
            (self.act_npre, "notify_pre"), (self.act_afk, "afk"),
            (self.act_25d, "dim25"), (self.act_body, "body"),
            (self.act_noff, "notify_off"), (self.act_nwork, "notify_work"),
            (self.act_sound, "sound"),
        ]

    def _build_tray(self):
        self.tray = QSystemTrayIcon(make_icon(64, self.cfg["char"]), self)
        self.tray.setToolTip("%s · %s" % (APP_NAME, self.cfg["char"]))
        tray_menu = QMenu()
        tray_menu.addAction(self.char_menu.menuAction())
        tray_menu.addAction(self.style_menu.menuAction())
        tray_menu.addSeparator()
        tray_menu.addAction(self.act_settings)
        tray_menu.addAction(self.act_mini)
        tray_menu.addAction(self.size_menu.menuAction())
        tray_menu.addAction(self.act_end)
        tray_menu.addSeparator()
        tray_menu.addAction(self.act_top)
        tray_menu.addAction(self.act_auto)
        tray_menu.addSeparator()
        tray_menu.addAction(self.act_quit)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(lambda r: self.show_and_raise()
                                    if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    # ---------- 菜单动作 ----------
    def warn(self, text):
        box = QMessageBox(self)
        box.setWindowTitle("提示")
        box.setText(text)
        box.addButton("确定", QMessageBox.ButtonRole.AcceptRole)
        box.exec()

    def set_time(self, key, label):
        cur = self.cfg.get(key, "18:00" if key == "end" else "09:00")
        dlg = CatInputDialog("%s时间" % label, "设置%s时间（24 小时制 HH:MM）：" % label, cur, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        txt = dlg.value()
        try:
            hh, mm = txt.split(":")
            hh, mm = int(hh), int(mm)
            assert 0 <= hh <= 23 and 0 <= mm <= 59
        except Exception:
            self.warn("请输入类似 18:00 的时间")
            return
        self.cfg[key] = "%02d:%02d" % (hh, mm)
        save_cfg(self.cfg)
        self.update()

    def set_rest_days(self):
        dlg = RestDaysDialog(self.cfg.get("rest_days", [5, 6]), self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.cfg["rest_days"] = dlg.days()
            save_cfg(self.cfg)
            self.update()

    # ---------- 天气 ----------
    def set_city(self):
        dlg = CatInputDialog("城市",
                             "输入城市名用于天气，可精确到区县（如：上海闵行区）。\n"
                             "查不到会自动匹配到上级城市，留空则不显示天气。",
                             self.cfg.get("city", ""), self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.cfg["city"] = dlg.value()
        save_cfg(self.cfg)
        self.weather = None
        self.refresh_weather()
        self.update()

    def refresh_weather(self):
        """拉取天气；失败时按 2min → 10min 退避重试（最多 3 次）。"""
        city = self.cfg.get("city", "")
        if not city:
            return
        try:
            self.wx.start(city)
        except Exception:
            self._wx_retry()

    def _wx_retry(self):
        self._wx_fail_n = getattr(self, "_wx_fail_n", 0) + 1
        if self._wx_fail_n > 3:
            return
        delay = 120000 if self._wx_fail_n < 3 else 600000
        QTimer.singleShot(delay, self.refresh_weather)

    def _wx_got(self, w):
        self.weather = w
        self._wx_fail_n = 0
        try:
            tip = "%s · %s %s %d°C" % (APP_NAME, w["city"], w["text"], w["temp"])
            if w.get("aqi_text"):
                tip += " · %s" % w["aqi_text"]
            self.tray.setToolTip(tip)
        except Exception:
            pass
        self.update()

    def toggle_cfg(self, key, on):
        self.cfg[key] = bool(on)
        save_cfg(self.cfg)

    def set_hat(self, style):
        self.cfg["hat"] = style
        save_cfg(self.cfg)
        self.update()

    def set_payday(self):
        cur = str(self.cfg.get("payday", 0) or "")
        dlg = CatInputDialog("发薪日", "每月几号发工资？输入 1-31，留空或 0 表示不显示。",
                             cur, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        txt = dlg.value()
        try:
            pd = int(txt) if txt else 0
            assert 0 <= pd <= 31
        except Exception:
            self.warn("请输入 1-31 的数字，或留空")
            return
        self.cfg["payday"] = pd
        save_cfg(self.cfg)
        self.update()

    def notify(self, title, msg, celebrate):
        try:
            self.tray.showMessage(title, msg, self.tray.icon(), 8000)
        except Exception:
            pass
        if self.cfg.get("sound", True):
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_OK if celebrate else winsound.MB_ICONASTERISK)
            except Exception:
                pass

    def toggle_mini(self, on):
        self.cfg["mini"] = bool(on)
        save_cfg(self.cfg)
        self.apply_size()
        self.act_mini.setChecked(bool(on))

    def toggle_sec(self, on):
        self.cfg["show_sec"] = bool(on)
        save_cfg(self.cfg)
        self.act_sec.setChecked(bool(on))
        self.update()

    def toggle_top(self, on):
        self.cfg["top"] = bool(on)
        save_cfg(self.cfg)
        was = self.isVisible()
        self.set_window_flags()
        if was:
            self.show()
        self.act_top.setChecked(bool(on))

    def toggle_autostart(self, on):
        ok = set_autostart(bool(on))
        self.cfg["autostart"] = bool(on)
        save_cfg(self.cfg)
        self.act_auto.setChecked(autostart_enabled())
        if on and not ok:
            QMessageBox.warning(self, "设置失败", "写入注册表失败，可能需要管理员权限")

    def check_update_manual(self):
        info = UPD.check_update()
        if not info:
            QMessageBox.information(self, "检查更新", "当前已是最新版本（v%s）" % __version__)
            return
        txt = "发现新版本 v%s\n\n%s\n\n是否打开下载页？" % (info["version"], info["notes"] or "（无更新说明）")
        if QMessageBox.question(self, "检查更新", txt) == QMessageBox.StandardButton.Yes:
            import webbrowser
            try:
                webbrowser.open(info["url"])
            except Exception:
                pass

    def auto_check_update(self):
        """启动后延迟检查一次，有新版本只走托盘提示，不打断使用。"""
        if not self.cfg.get("check_update", True):
            return

        def _run():
            info = UPD.check_update()
            if not info:
                return
            try:
                self.tray.showMessage("CatClock 有新版本 v%s" % info["version"],
                                      "点此打开下载页（或在右键菜单「检查更新」查看）",
                                      self.tray.icon(), 10000)
                self._update_url = info["url"]
                self.tray.messageClicked.connect(self._open_update_url)
            except Exception:
                pass

        QTimer.singleShot(6000, _run)

    def _open_update_url(self):
        import webbrowser
        try:
            webbrowser.open(getattr(self, "_update_url", UPD.UPDATE_API))
        except Exception:
            pass

    # ---------- 分组设置窗口 ----------
    def open_settings(self):
        dlg = S.SettingsDialog(self.cfg, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new = dlg.result()
        autostart = new.pop("_autostart", None)
        reset_pos = new.pop("_reset_pos", False)
        old = dict(self.cfg)
        self.cfg.update(new)
        save_cfg(self.cfg)
        if autostart is not None and autostart != autostart_enabled():
            ok = set_autostart(bool(autostart))
            self.cfg["autostart"] = bool(autostart)
            save_cfg(self.cfg)
            if autostart and not ok:
                QMessageBox.warning(self, "设置失败", "写入注册表失败，可能需要管理员权限")
        self._apply_cfg(old)
        if reset_pos:
            self.reset_pos()

    def _apply_cfg(self, old):
        """设置窗口改完后的统一落地：图标 / 尺寸 / 置顶 / 天气 / 菜单勾选"""
        if self.cfg.get("char") != old.get("char"):
            self.set_char(self.cfg["char"])
        if self.cfg.get("style") != old.get("style"):
            self.set_style(self.cfg["style"])
        if (abs(float(self.cfg.get("scale", 1.0)) - float(old.get("scale", 1.0))) > 0.001
                or bool(self.cfg.get("mini")) != bool(old.get("mini"))):
            self.apply_size()
        if bool(self.cfg.get("top", True)) != bool(old.get("top", True)):
            was = self.isVisible()
            self.set_window_flags()
            if was:
                self.show()
        if self.cfg.get("city", "") != old.get("city", ""):
            self.weather = None
            self.refresh_weather()
        self._sync_menu()
        self.update()

    def _sync_menu(self):
        """把右键菜单 / 托盘菜单的勾选态同步到当前 cfg"""
        for act, key in getattr(self, "_check_actions", []):
            try:
                act.setChecked(bool(self.cfg.get(key, False)))
            except Exception:
                pass
        try:
            for name, a in self.char_actions.items():
                a.setChecked(name == self.cfg.get("char"))
            for name, a in self.style_actions.items():
                a.setChecked(name == self.cfg.get("style"))
            for key, a in self.hat_actions.items():
                a.setChecked(key == str(self.cfg.get("hat", "auto")))
            for pct, a in self.size_actions.items():
                a.setChecked(abs(pct / 100.0 - float(self.cfg.get("scale", 1.0))) < 0.001)
            self.act_auto.setChecked(autostart_enabled())
        except Exception:
            pass

    def show_stats(self):
        """工作时长统计：今日 / 本周 / 本月，并可导出 CSV。"""
        from PyQt6.QtWidgets import QFileDialog
        txt = stats.report_text()
        box = QMessageBox(self)
        box.setWindowTitle("工作统计")
        box.setText(txt + "\n\n（在岗=工作时间内的时长，加班=下班后仍在的时长）")
        box.addButton("导出 CSV", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
        if box.exec() != 0:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出工作统计", os.path.join(os.path.expanduser("~"), "work_stats.csv"),
            "CSV 文件 (*.csv)")
        if not path:
            return
        try:
            n = stats.export_csv(path)
            QMessageBox.information(self, "导出完成", "已导出 %d 天记录到\n%s" % (n, path))
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def show_about(self):
        QMessageBox.information(
            self, "关于 CatClock",
            "CatClock v%s\n\n桌面可爱猫猫 · 下班倒计时挂件\n"
            "21 个角色 / 6 款帽子 / 半身道具 / 2.5D\n\n"
            "右键菜单可切换角色、帽子与时间设置。" % __version__)

    def reset_pos(self):
        self.cfg["pos"] = None
        save_cfg(self.cfg)
        self._place()

    def show_and_raise(self):
        self.show()
        self.raise_()
        self._clamp()

    def quit(self):
        self.cfg["pos"] = [self.x(), self.y()]
        save_cfg(self.cfg)
        self.tray.hide()
        QApplication.quit()

    # ---------- 交互 ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            pos = e.position()
            s = float(self.cfg.get("scale", 1.0))
            lx, ly = pos.x() / s, pos.y() / s      # 换算到逻辑坐标
            cs, ccx, ccy = self._cat_geo()
            self._press_on_cat = (lx - ccx) ** 2 + (ly - ccy) ** 2 < (cs * 0.52) ** 2
            self._press_pos = e.globalPosition().toPoint()
            self.drag_off = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def wheelEvent(self, e):
        step = e.angleDelta().y() / 120 * 0.1     # 每格 10%
        self.set_scale(float(self.cfg.get("scale", 1.0)) + step)
        e.accept()

    def mouseMoveEvent(self, e):
        if self.drag_off is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self.drag_off)
            e.accept()
        else:
            # 悬停猫头检测
            pos = e.position()
            s = float(self.cfg.get("scale", 1.0))
            lx, ly = pos.x() / s, pos.y() / s
            cs, ccx, ccy = self._cat_geo()
            if (lx - ccx) ** 2 + (ly - ccy) ** 2 < (cs * 0.55) ** 2:
                if self.hover_cat_t == 0.0 and self.meow_bubble_t >= 2.5 \
                        and random.random() < 0.15:
                    self.meow_bubble_t = 0.0
                self.hover_cat_t += 0.1
            else:
                self.hover_cat_t = 0.0

    def mouseReleaseEvent(self, e):
        if self.drag_off is not None:
            self.drag_off = None
            self._clamp()
            self.cfg["pos"] = [self.x(), self.y()]
            save_cfg(self.cfg)
        # 点击（非拖动）且按在猫头上才算摸到猫
        if (self._press_pos is not None and self._press_on_cat
                and (e.globalPosition().toPoint() - self._press_pos).manhattanLength() < 10):
            self.meow_t = 0.0
            self.meow_bubble_t = 0.0
        self._press_pos = None
        self._press_on_cat = False

    def mouseDoubleClickEvent(self, e):
        pass

    def contextMenuEvent(self, e):
        self.act_auto.setChecked(autostart_enabled())
        self.menu.exec(e.globalPos())

    def enterEvent(self, e):
        self.hover = True
        self._bg_invalidate()
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self._bg_invalidate()
        self.update()

    def closeEvent(self, e):
        self.cfg["pos"] = [self.x(), self.y()]
        save_cfg(self.cfg)
        e.accept()

    # ---------- 计时 ----------
    def _tick(self):
        dt = getattr(self, "step", 0.1)      # 自适应帧率下的真实帧间隔
        self.t0 += dt
        self.blink_t += dt
        self.quote_t += dt
        if self.blink_t > self.blink_until:
            self.blink_t = 0.0
            self.blink_until = 2.2 + (os.getpid() % 7) * 0.4
        if self.meow_t < 1.0:
            self.meow_t += 0.8 * dt
        if self.quote_t >= 25.0:        # 每 25 秒换下一条语录
            self.quote_t = 0.0
            self.quote_i += 1
        if self.hydrate_t < 5.0:
            self.hydrate_t += dt
        if self.hourly_t < 3.0:
            self.hourly_t += dt
        if self.meow_bubble_t < 2.5:
            self.meow_bubble_t += dt
        if self.bubble_t < 3.5:
            self.bubble_t += dt
        # 悬停猫头计时会衰减：鼠标不动约 0.8s 后视为静止，允许降频
        if self.hover_cat_t > 0.0:
            self.hover_cat_t = max(0.0, self.hover_cat_t - dt)
        # 整点报时：7-22 点且非休息日（深夜和休息不打扰）
        now = datetime.now()
        phase, start, end, secs, pct = self._status()
        # 工作时长统计：工作中记在岗；过了下班时间还在，记加班
        try:
            last = getattr(self, "_stat_ts", None)
            if last is not None:
                dt = (now - last).total_seconds()
                if 0 < dt < 120:
                    day = now.strftime("%Y-%m-%d")
                    if phase == "work":
                        stats.add(day, work_sec=dt)
                    elif phase == "off" and self.cfg.get("count_over", True):
                        over = min(dt, (now - end).total_seconds() if now > end else dt)
                        if over > 0:
                            stats.add(day, over_sec=over)
            self._stat_ts = now
        except Exception:
            pass
        if (now.minute == 0 and now.second < 3 and self.last_hour_mark != now.hour
                and 7 <= now.hour <= 22 and phase != "rest"):
            self.last_hour_mark = now.hour
            self.hourly_t = 0.0
        # 用户离开检测：走开 3 分钟猫打瞌睡，回来后打招呼并重新计久坐
        was_afk = self.afk
        self.afk = bool(self.cfg.get("afk", True)) and user_idle_seconds() > 180
        if was_afk and not self.afk:
            self._say("你回来啦，猫想你啦～")
            self.last_hydrate = self.t0
        # 待机小动作状态机（午后 13-14 点更容易打哈欠；打瞌睡时不抢戏）
        if self.idle is None and self.t0 >= self.idle_next and not self.afk:
            hour = now.hour + now.minute / 60.0
            if 13.0 <= hour < 14.0:
                name = "yawn" if random.random() < 0.7 else "stretch"
            else:
                name = random.choice(["stretch", "yawn", "wave", "tail_wag"])
            self.idle = (name, self.t0)
            self.action = name
            self.action_start = self.t0
        if self.idle and self.t0 - self.idle[1] > 3.0:
            self.idle = None
            self.action = None
            self.idle_next = self.t0 + random.uniform(20, 45)
        # 2.5D：随机耳抖（每 25-60 秒一次，每次 0.6 秒）
        if self.ear_tw and self.t0 - self.ear_tw[1] > 0.6:
            self.ear_tw = None
        if self.cfg.get("dim25") and self.ear_tw is None and self.t0 >= self.next_ear_tw:
            self.ear_tw = (random.choice((-1, 1)), self.t0)
            self.next_ear_tw = self.t0 + random.uniform(25, 60)
        # 阶段切换：发通知
        prev_phase = self.last_phase
        if prev_phase and phase != prev_phase:
            self._fired_marks.clear()
            if phase == "off" and self.cfg.get("notify_off", True):
                self.notify("下班啦～", "辛苦了，快去享受生活！", True)
            elif phase == "work" and prev_phase in ("pre", "rest") \
                    and self.cfg.get("notify_work", True):
                self.notify("该上班啦", "新的一天，加油～", False)
        self.last_phase = phase
        # 下班前 30 / 10 分钟预告（跨点检测，每阶段各发一次）
        if phase == "work" and self.cfg.get("notify_pre", True) \
                and self._prev_secs is not None:
            for mark in (1800, 600):
                if self._prev_secs > mark >= secs and mark not in self._fired_marks:
                    self._fired_marks.add(mark)
                    self.notify("还有 %d 分钟就下班啦" % (mark // 60),
                                "坚持住，猫陪你一起冲～", False)
        # 上班前 10 分钟提醒
        if phase == "pre" and self.cfg.get("notify_work", True) \
                and self._prev_secs is not None \
                and self._prev_secs > 600 >= secs and 600 not in self._fired_marks:
            self._fired_marks.add(600)
            self.notify("10 分钟后上班", "准备好了吗，搬砖人～", False)
        # 休息日前夜提示（21 点后，每天一次）
        if now.hour >= 21 and phase != "rest":
            tomorrow = (now + timedelta(days=1)).date()
            if tomorrow.weekday() in self.cfg.get("rest_days", [5, 6]) \
                    and self._rest_eve_day != tomorrow:
                self._rest_eve_day = tomorrow
                self._say("明天就休息了，别熬太晚～")
        # 久坐提醒：仅工作中计数，用户不在座位时不打扰（回来后重新计时）
        if phase == "work":
            if prev_phase != "work":
                self.last_hydrate = self.t0
            if self.cfg.get("hydrate", True) and not self.afk \
                    and self.t0 - self.last_hydrate >= 3600:
                self.last_hydrate = self.t0
                self.hydrate_t = 0.0
                self.notify("该活动一下啦", Q.hydrate_msg(self.quote_i), False)
        else:
            self.last_hydrate = self.t0
        self._prev_secs = secs

        # ---- 自适应帧率：静止时降频，有动画时立刻回到 10fps ----
        try:
            anim = self._anim_active()
            want = self._want_interval(phase, anim)
            was_low = self.lowfps
            self.lowfps = want >= 250 and not anim
            if want != getattr(self, "_timer_ms", 100):
                self._timer_ms = want
                self.step = want / 1000.0
                self.timer.setInterval(want)
            elif was_low != self.lowfps:
                self.update()          # 刚进入/退出静止态，补一帧
        except Exception:
            pass
        self.update()

    def _say(self, text, dur=3.5):
        """让猫说话（通用气泡）"""
        self.bubble_text = text
        self.bubble_t = 0.0

    def _quote(self):
        """挑一条当前时段/天气/周五的自定义语录。"""
        now = datetime.now()
        w = self.weather
        kind = w.get("kind") if w else None
        msg = Q.get_quote("work", now.hour + now.minute / 60.0,
                          now.weekday() == 4, kind, self.quote_i)
        if msg and kind == "sun" and w.get("temp", 0) >= 34:
            msg += "，多喝水"
        return msg

    def _effective_hat(self):
        """当前实际佩戴的帽子：用户选择 > 节日自动 > 角色默认。"""
        hat = str(self.cfg.get("hat", "auto"))
        if hat != "auto":
            return hat
        fest = Q.festive_hat_now()
        if fest:
            return fest
        return D._HAT.get(self.char_colors().get("shape", "cat"), "none")

    def _effective_acc(self):
        """当前实际佩戴的配饰：用户选择 > none。"""
        acc = str(self.cfg.get("acc", "auto"))
        if acc != "auto":
            return acc
        return "none"

    def _bubble_active(self):
        """是否有气泡在展示（猫需要下移让位）"""
        return self.hydrate_t < 5.0 or self.hourly_t < 3.0 or self.meow_bubble_t < 2.5

    def payday_info(self):
        """距发薪日信息（payday=0 返回 None）"""
        pd = self.cfg.get("payday", 0)
        if not pd:
            return None
        today = datetime.now()
        y, m = today.year, today.month

        def build(yy, mm):
            last = calendar.monthrange(yy, mm)[1]
            return datetime(yy, mm, min(pd, last))

        nxt = build(y, m)
        if today.date() > nxt.date() or (today.date() == nxt.date() and today.hour >= 12):
            m += 1
            if m > 12:
                m, y = 1, y + 1
            nxt = build(y, m)
        days = (nxt.date() - today.date()).days
        if days == 0:
            return "今天发工资！"
        return "距发工资还有 %d 天" % days

    def _status(self):
        """返回 (阶段, start, end, secs, pct)
        阶段: pre 上班前 / work 工作中 / off 下班后 / rest 休息日
        secs: pre/work 为距节点剩余秒; off 为已下班秒数
        """
        now = datetime.now()

        def mk(v):
            hh, mm = (v.split(":") + ["0"])[:2]
            return now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)

        start = mk(self.cfg.get("start", "09:00"))
        end = mk(self.cfg.get("end", "18:00"))
        if end <= start:
            end += timedelta(days=1)

        if now.weekday() in self.cfg.get("rest_days", [5, 6]):
            return "rest", start, end, 0, 1.0
        if now < start:
            return "pre", start, end, max(int((start - now).total_seconds()) + 1, 0), 0.0
        if now >= end:
            return "off", start, end, int((now - end).total_seconds()), 1.0
        pct = (now - start).total_seconds() / (end - start).total_seconds()
        return "work", start, end, int((end - now).total_seconds()) + 1, pct

    # ---------- 绘制缓存 ----------
    def _bg_invalidate(self):
        """面板外观变了就丢弃缓存（配色 / 悬停 / 尺寸 / 迷你模式）"""
        self._bg_key = None
        self._bg_pm = None

    def _bg_pixmap(self):
        """带阴影的圆角面板：内容只在外观变化时重绘，平时直接贴图。"""
        key = (self.cfg.get("style"), bool(self.hover), bool(self.cfg.get("mini")),
               round(float(self.cfg.get("scale", 1.0)), 2), self.width(), self.height())
        if self._bg_key == key and self._bg_pm is not None:
            return self._bg_pm
        st = self.style()
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
        # 柔和阴影
        for i in range(6):
            k = 5 - i
            inset = pad + k * 1.2 - 1.2
            q.setPen(Qt.PenStyle.NoPen)
            q.setBrush(QColor(st["shadow"][0], st["shadow"][1], st["shadow"][2], 8 + k * 4))
            q.drawPath(rr(inset, inset + 1.6, W - 2 * inset, H - 2 * inset, 25))
        # 面板
        g = QLinearGradient(0, pad, 0, H - pad)
        g.setColorAt(0, QColor(*st["panel0"]))
        g.setColorAt(1, QColor(*st["panel1"]))
        q.setBrush(g)
        ba = 235 if self.hover else 190
        bcol = st["border_h"] if self.hover else st["border"]
        q.setPen(QPen(QColor(bcol[0], bcol[1], bcol[2], ba), 1.3))
        q.drawPath(rr(pad, pad, W - 2 * pad, H - 2 * pad, 24))
        q.end()
        self._bg_key = key
        self._bg_pm = pm
        return pm

    # ---------- 自适应帧率 ----------
    def _anim_active(self):
        """当前是否有正在播放的动画（决定要不要高频刷新）"""
        return (self.meow_t < 1.0 or self.idle is not None
                or self.hydrate_t < 5.0 or self.hourly_t < 3.0
                or self.meow_bubble_t < 2.5 or self.bubble_t < 3.5
                or self.hover or 0.0 < getattr(self, "hover_cat_t", 0.0) < 0.8
                or self.ear_tw is not None)

    def _want_interval(self, phase, anim):
        """返回期望的定时器间隔（毫秒）"""
        show_sec = bool(self.cfg.get("show_sec", True))
        if anim:
            return 100
        if phase == "rest":
            return 1000 if not show_sec else 500
        if show_sec:
            return 100
        return 250                      # 只剩冒号闪烁，250ms 足够

    # ---------- 绘制 ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.drawPixmap(0, 0, self._bg_pixmap())     # 面板走缓存，不再每帧重画阴影
        s = float(self.cfg.get("scale", 1.0))
        p.scale(s, s)                       # 全局等比缩放，后续全部用逻辑坐标
        W = self.W
        mini = self.cfg.get("mini", False)
        H = self.H_MINI if mini else self.H_FULL
        pad = 5
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
        draw_cat(p, ccx + shake, ccy, cs, self.char_colors(),
                 blink=(self.blink_t < 0.18 or meowing) and not still,
                 excited=excited, sleepy=sleepy,
                 scared=thunder or too_hot, look=look, action=action,
                 action_k=action_k, tail_phase=tail_phase, t=self.t0, dim25=dim25,
                 pet_k=self.meow_t if self.meow_t < 1.0 else None, ear_tw=ear_tw,
                 body=body, prop=prop, hat=self._effective_hat(), acc=self._effective_acc())

        # 天气小图标（右上角）
        if self.weather and not mini:
            draw_weather_icon(p, W - 36, 14, 22, self.weather["kind"], self.t0)

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

        # ---- 主文字区 ----
        if phase == "rest":
            p.setPen(QColor(st["pink"]))
            p.setFont(font("Microsoft YaHei", 20, QFont.Weight.Bold))
            p.drawText(QRectF(x, H / 2 - 34, tw, 36),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "今天休息～")
            p.setPen(QColor(st["sub"]))
            p.setFont(font("Microsoft YaHei", 9))
            now = datetime.now()
            p.drawText(QRectF(x, H / 2 + 2, tw, 18),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       "%d月%d日 · 好好放松" % (now.month, now.day))
            pay = self.payday_info()
            if pay:
                p.setPen(QColor(st["pink"]))
                p.drawText(QRectF(x, H / 2 + 22, tw, 16),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "¥ %s" % pay)
        else:
            # 倒计时数字
            if phase == "off":
                p.setPen(QColor(st["pink"]))
                p.setFont(font("Microsoft YaHei", 20 if not mini else 18, QFont.Weight.Bold))
                p.drawText(QRectF(x, 14, tw, 36),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "下班啦～")
            else:
                fcol = QColor(st["pink"] if excited else st["text"])
                size = 24 if mini else (26 if show_sec else 30)
                p.setFont(font("Segoe UI", size, QFont.Weight.Bold, QFont.StyleHint.SansSerif))
                cy0 = (H / 2 - 38) if mini else 12
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
                p.drawText(QRectF(x, 50, tw, 16),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, line1)

                # 行2：气泡消息（猫说的话，尾巴指向猫）优先于语录
                msg = None
                if self.hydrate_t < 5.0:
                    k = self.hydrate_t
                    msg = ("喝口水，动一动～", 255 if k < 4.0 else max(0, int(255 * (5.0 - k))))
                elif self.hourly_t < 3.0:
                    k = self.hourly_t
                    msg = ("%d 点啦" % datetime.now().hour, 255 if k < 2.2 else max(0, int(255 * (3.0 - k) / 0.8)))
                elif self.meow_bubble_t < 2.5:
                    k = self.meow_bubble_t
                    msg = ("呼噜噜～" if self.meow_t < 1.0 else "喵～",
                           255 if k < 1.8 else max(0, int(255 * (2.5 - k) / 0.7)))
                elif self.bubble_t < 3.5:
                    k = self.bubble_t
                    msg = (self.bubble_text or "",
                           255 if k < 2.6 else max(0, int(255 * (3.5 - k) / 0.9)))
                if msg:
                    text, alpha = msg
                    p.setFont(font("Microsoft YaHei", 9))
                    fm = p.fontMetrics()
                    bw3 = fm.horizontalAdvance(text) + 26
                    bh3 = 18
                    bx3, by3 = float(x), 64.0
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(255, 255, 255, min(235, alpha)))
                    p.drawEllipse(QRectF(bx3 - 5, by3 + bh3 - 7, 8, 8))   # 指向猫的小尾巴
                    p.drawPath(rr(bx3, by3, bw3, bh3, 9))
                    p.setPen(QColor(st["pink"]))
                    p.setOpacity(alpha / 255.0)
                    p.drawText(QRectF(bx3, by3 - 1, bw3, bh3 + 2),
                               Qt.AlignmentFlag.AlignCenter, text)
                    p.setOpacity(1.0)
                elif phase == "work" and not excited and not self.afk:
                    q = self._quote()
                    if q:
                        p.setPen(QColor(st["text"]))
                        p.drawText(QRectF(x, 66, tw, 15),
                                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                                   "“%s”" % q)

                # 行3：发薪日
                pay = self.payday_info()
                if pay and phase != "pre":
                    p.setPen(QColor(st["pink"]))
                    p.drawText(QRectF(x, 83, tw, 15),
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                               "¥ %s" % pay)

        # ---- 进度条（非迷你、非休息日） ----
        if not mini and phase != "rest":
            bx, by, bw, bh = x, 102, tw, 6
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
                    gg.setColorAt(0, QColor(*st["bar0"]))
                    gg.setColorAt(1, QColor(*st["bar1"]))
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


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    server = acquire_single()
    if server is None:
        sys.exit(0)

    w = CatClock()
    app.setWindowIcon(make_icon(64, w.cfg["char"]))

    def on_conn():
        c = server.nextPendingConnection()
        if c:
            c.close()
        w.show_and_raise()

    server.newConnection.connect(on_conn)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
