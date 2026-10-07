# -*- coding: utf-8 -*-
"""A1：菜单 / 托盘 / 设置对话框（CatClock 的 _MenuMixin）。

从 app.py 拆出：这里只管「用户点了什么 → 改配置 → 同步菜单勾选」，
不管计时逻辑（core）也不管怎么画（paint）。
"""
import os
import json
from datetime import datetime

from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QColor, QIcon, QFont, QCursor, QAction, QActionGroup
from PyQt6.QtWidgets import (
    QApplication, QWidget, QMenu, QSystemTrayIcon, QInputDialog, QMessageBox,
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QLineEdit, QLabel,
)

from . import data as D
from . import __version__
from . import quotes as Q
from . import settings as S
from . import stats
from . import report
from . import mood
from . import update as UPD
from . import festival as F
from .draw import make_icon, make_tray_icon, make_paw_cursor
from .weather import WeatherFetcher
from .ui import CatInputDialog, RestDaysDialog
from .util import (
    APP_NAME, DEFAULTS, save_cfg, app_path, autostart_enabled, set_autostart, font,
)
from .data import CHARACTERS, STYLES


class _MenuMixin:
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
        self.act_pomo = QAction("番茄钟 · 专注 25 分钟", self)
        self.act_pomo.triggered.connect(self.toggle_pomo)
        self.act_mood = QAction("心情打卡…（也可双击猫）", self)
        self.act_mood.triggered.connect(self.ask_mood)
        self.act_week = QAction("本周小结与成就…", self)
        self.act_week.triggered.connect(self.show_week)
        self.act_boss = QAction("老板键（隐身）\tCtrl+Alt+H", self)
        self.act_boss.triggered.connect(self.toggle_boss)
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
        self.menu.addAction(self.act_mood)
        self.menu.addAction(self.act_pomo)
        self.menu.addAction(self.act_week)
        self.menu.addAction(self.act_boss)
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
        self._sync_pomo_action()


    def _build_tray(self):
        self.tray = QSystemTrayIcon(make_icon(64, self.cfg["char"]), self)
        self._update_tray_tooltip()
        tray_menu = QMenu()
        self.act_show = QAction("显示 / 隐藏", self)
        self.act_show.triggered.connect(self._show_or_hide)
        tray_menu.addAction(self.act_show)
        tray_menu.addSeparator()
        tray_menu.addAction(self.char_menu.menuAction())
        tray_menu.addAction(self.style_menu.menuAction())
        tray_menu.addAction(self.hat_menu.menuAction())
        tray_menu.addSeparator()
        tray_menu.addAction(self.act_settings)
        tray_menu.addAction(self.act_mini)
        tray_menu.addAction(self.act_boss)
        tray_menu.addAction(self.act_mood)
        tray_menu.addAction(self.act_pomo)
        tray_menu.addAction(self.act_stats)
        tray_menu.addAction(self.size_menu.menuAction())
        tray_menu.addSeparator()
        tray_menu.addAction(self.act_auto)
        tray_menu.addAction(self.act_update)
        tray_menu.addAction(self.act_about)
        tray_menu.addSeparator()
        tray_menu.addAction(self.act_quit)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._tray_activated)
        self._update_tray_icon(True)
        self.tray.show()


    def _update_tray_tooltip(self):
        self.tray.setToolTip("%s v%s · %s" % (APP_NAME, __version__, self.cfg["char"]))


    def _tray_time_text(self):
        """F4：托盘图标上叠的剩余时间文案（尽量 2–4 个字符，小尺寸也认得出）。"""
        try:
            phase, _s, _e, secs, _p = self._status()
        except Exception:
            return ""
        if phase == "rest":
            return "休"
        if phase == "pre":
            h, rem = divmod(int(secs), 3600)
            m = rem // 60
            return ("%dh" % h) if h >= 1 else ("%dm" % max(1, m))
        if phase == "off":
            return "下班"
        h, rem = divmod(int(max(0, secs)), 3600)
        m = rem // 60
        if h >= 1:
            return "%dh%d" % (h, m) if m else "%dh" % h
        return str(max(0, m))


    def _update_tray_icon(self, force=False):
        """F4：托盘图标叠加剩余时间，分钟变化时刷新。"""
        if not hasattr(self, "tray"):
            return
        show = bool(self.cfg.get("tray_time", True))
        mark = int(self.t0 // 60) if show else -1
        if not force and mark == self._tray_min_mark:
            return
        self._tray_min_mark = mark
        try:
            self.tray.setIcon(make_tray_icon(64, self.cfg["char"],
                                             self._tray_time_text() if show else ""))
        except Exception:
            pass


    def _tray_activated(self, reason):
        if reason != QSystemTrayIcon.ActivationReason.Trigger:
            return
        act = str(self.cfg.get("tray_click", "toggle") or "toggle")
        if act == "menu":
            self.menu.exec(QCursor.pos())
        elif act == "mood":
            self.ask_mood()
        else:
            self._show_or_hide()


    def _show_or_hide(self):
        if self.isVisible():
            self.hide()
        else:
            self.show_and_raise()


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


    def set_hat(self, style):
        self.cfg["hat"] = style
        save_cfg(self.cfg)
        self.update()


    def set_char(self, name):
        self.cfg["char"] = name
        save_cfg(self.cfg)
        self.tray.setIcon(make_icon(64, name))
        self.setWindowIcon(make_icon(64, name))
        self._update_tray_tooltip()
        self._update_tray_icon(True)      # F4：换角色后重画带时间的托盘图标
        self.update()


    def set_style(self, name):
        self.cfg["style"] = name
        save_cfg(self.cfg)
        self.apply_app_style()
        self._bg_invalidate()
        self.update()


    def toggle_cfg(self, key, on):
        self.cfg[key] = bool(on)
        save_cfg(self.cfg)
        self.update()


    def toggle_mini(self, on):
        on = bool(on)
        self.cfg["mini"] = on
        save_cfg(self.cfg)
        self.act_mini.setChecked(on)
        # B1：高度渐变切换，不再瞬间跳变
        self._anim_h_to(self.H_MINI if on else self.H_FULL)


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

    def open_settings(self):
        snap = dict(self.cfg)

        def preview(patch):
            old = dict(self.cfg)
            self.cfg.update(patch)
            save_cfg(self.cfg)
            self._apply_cfg(old)

        def cancel():
            old = dict(self.cfg)
            self.cfg.update(snap)
            save_cfg(self.cfg)
            self._apply_cfg(old)

        dlg = S.SettingsDialog(self.cfg, self, on_preview=preview, on_cancel=cancel)
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
        # 语录文件可能刚被编辑过，重新加载
        try:
            self.quotes = Q.load_custom_quotes()
        except Exception:
            pass
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
        # F1：老板键开关 / 任意热键组合变化 → 重新注册
        if (bool(self.cfg.get("boss_key", True)) != bool(old.get("boss_key", True))
                or self.cfg.get("hotkey_boss", "") != old.get("hotkey_boss", "")
                or self.cfg.get("hotkey_show", "") != old.get("hotkey_show", "")
                or self.cfg.get("hotkey_pomo", "") != old.get("hotkey_pomo", "")):
            self._unregister_hotkey()
            self._register_hotkey()
        # F4：托盘图标 / 左键行为
        self._update_tray_icon(True)
        if bool(self.cfg.get("edge_dock", True)) != bool(old.get("edge_dock", True)):
            self._apply_dock()             # 开→重新吸附，关→恢复原位并停掉监听
        self._sync_menu()
        self.update()
