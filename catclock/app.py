# -*- coding: utf-8 -*-
"""主窗口 CatClock。"""
import json
import os
import math
import random
import calendar
import sys
import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta

from PyQt6.QtCore import Qt, QPoint, QPointF, QTimer, QRect, QRectF, QUrl, QObject
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
from . import sense as SENSE
from . import festival as F
from . import mood
from . import report
from . import llm
from . import __version__
from .util import (
    APP_NAME, CONFIG_DIR, CONFIG_PATH, DEFAULTS, load_cfg, save_cfg, app_path,
    autostart_enabled, set_autostart,     _raise_existing, acquire_single, rr,
    _q_luma, _mix, user_idle_seconds, font, auto_scale,
)
from .draw import (draw_cat, heart_path, draw_weather_icon, make_icon,
                   make_tray_icon, make_paw_cursor)
from .data import (
    CHARACTERS, STYLES, WMO_TEXT, wmo_kind, PROP_BY_WEATHER,
)
from .weather import WeatherFetcher
from .ui import CatInputDialog, RestDaysDialog


# A1：以下能力已拆到独立模块，通过 mixin 组合回 CatClock
from .paint import _PaintMixin
from .menu import _MenuMixin
from .notify import _NotifyMixin
from .interact import _InteractMixin



class CatClock(_PaintMixin, _MenuMixin, _NotifyMixin, _InteractMixin, QWidget):
    W = 272
    BUB_TOP = 0           # 0 = 语录文字回到右侧文字区（v39 布局）；>0 = 飘在猫头顶上方
    BUBBLE_STYLE = "none"  # none=无框纯文字 / auto=按情绪切形状 / capsule、round、heart、drop、burst
    H_FULL = 134          # 无框语录（最多两行）+ 发薪日 + 进度条都能落在面板内
    H_MINI = 76           # 迷你模式不显示气泡

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
        self._fired_marks = set()  # 本阶段已发过的预告（3600/1800/600/300）
        self._over_marks = set()   # C1：今日已劝过的加班档位（30/60/120 分钟）
        self.pomo = None           # C2：番茄钟 {"mode": "focus"/"break", "left": 剩余秒}
        self._rest_eve_day = None  # 已提示过的"明天休息"日期
        self.ear_tw = None         # 2.5D 耳抖 (方向, 起始 t0)
        self.next_ear_tw = 12.0    # 下次耳抖的 t0
        self.hover_cat = False     # E3：鼠标是否停在猫身上
        self._paw_cursor = None    # E3：爪型光标（懒加载）
        self._tray_min_mark = None  # F4：托盘图标上已渲染的分钟数

        # ---- 情境感知 / 节日 / 心情 / 智能语录 ----
        self.sense = {}            # sense.sample() 结果（每 tick 刷新，内部节流）
        self.quotes = None         # 用户自定义语录（quotes.json）
        try:
            self.quotes = Q.load_custom_quotes()
        except Exception:
            self.quotes = None
        self.fest = F.today_festival()   # 今日节日 dict 或 None
        self.llm_lines = None      # Qwen 生成的今日个性化语录
        self._llm_day = None
        self._mood_asked_day = None
        self.surprise_next = 40.0  # 下次"随机小惊喜"的 t0
        self.surprise = None       # (name, start_t, dur)
        self._surprise_prop = None # (道具名, 到期 t0)

        # ---- 老板键 / 边缘吸附 ----
        self._hidden = False       # 老板键隐身中
        self._hotkey_ok = False
        self._hotkey_err = []
        self._dock_edge = None     # left/right/top/None
        self._dock_off = None      # 完整可见位置（贴边但未藏）
        self._dock_pos = None      # 吸附后的藏身位置
        self._dock_out = True      # 当前是否在"完整可见"位置
        self._dock_last = 0.0      # 上次滑出/收回的时间戳（防抖冷却）
        self._dock_leave = None    # 鼠标离开滑出区的时间戳（延迟收回）
        self._dock_timer = QTimer(self)   # 只在吸附状态下跑的迟滞监听
        self._dock_timer.setInterval(80)
        self._dock_timer.timeout.connect(self._dock_watch)
        self._dock_slide_timer = QTimer(self)   # 滑出/收回的缓动动画
        self._dock_slide_timer.setInterval(16)
        self._dock_slide_timer.timeout.connect(self._dock_slide_step)
        self._dock_slide = None        # (起点, 终点, 已走步数)

        # A5：松手惯性滑行（撞到屏幕边缘会轻弹回来）
        self._fling_timer = QTimer(self)
        self._fling_timer.timeout.connect(self._fling_step)
        self._drag_vel = [0.0, 0.0]
        self._drag_last = None
        # B1：完整 / 迷你模式切换的高度渐变
        self._h_anim = None            # 动画中的插值高度；None = 用当前模式固定高度
        self._h_anim_timer = QTimer(self)
        self._h_anim_timer.timeout.connect(self._h_anim_step)
        self._h_from = self._h_to = 0
        self._h_k = 0.0

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
        # B4：监听屏幕/DPI变化，避免拔插显示器后窗口丢失
        try:
            self.windowHandle().screenChanged.connect(self._on_screen_changed)
            QApplication.screenAdded.connect(self._on_screen_added)
            QApplication.screenRemoved.connect(self._on_screen_removed)
        except Exception:
            pass
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
        self._cat_key = None       # C1：猫身绘制缓存 key
        self._cat_pm = None        # C1：猫身绘制缓存 QPixmap

        # 版本更新：启动 6s 后静默检查一次
        self._update_url = None
        self.auto_check_update()

        # 老板键（全局热键 Ctrl+Alt+H）
        self._register_hotkey()
        # Qwen 个性化语录（可选，配置关闭则完全静默）
        self._init_llm()
        # 节日问候（启动 3 秒后说一次）
        if self.fest:
            QTimer.singleShot(3000, lambda: self._say(self.fest["greet"]))

    # ---------- 窗口 ----------
    def set_window_flags(self):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.cfg.get("top", True):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def apply_size(self):
        # 尺寸变了：先滑回完整位置，避免"半个窗口在屏幕外"时算出错误的吸附参数
        redock = bool(self._dock_edge)
        was_out = self._dock_out
        if redock and not was_out:
            self._dock_set(True, instant=True)
        s = float(self.cfg.get("scale", 1.0))
        h = self.H_MINI if self.cfg.get("mini") else self.H_FULL
        self.setFixedSize(int(self.W * s), int(int(h) * s))
        self._bg_invalidate()
        self._clamp()
        if redock:
            base = self._dock_off
            self._dock_timer.stop()
            self._dock_edge = None
            self._dock_off = None
            self._dock_pos = None
            self._dock_out = True
            if base:
                self.move(*base)
            self._apply_dock()      # 用新尺寸重算吸附位置
            if was_out:
                self._dock_set(True, instant=True)
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
        # 随机小惊喜的临时道具优先（掉金币 / 送爱心）
        sp = getattr(self, "_surprise_prop", None)
        if sp:
            name, until = sp
            if self.t0 < until:
                return name
            self._surprise_prop = None
        # 节日道具
        if self.fest and self.fest.get("prop"):
            return self.fest["prop"]
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

    def _cur_h(self):
        """当前面板逻辑高度（B1 动画期间取插值，避免布局跳变）。"""
        if self._h_anim is not None:
            return self._h_anim
        return self.H_MINI if self.cfg.get("mini") else self.H_FULL

    def _anim_h_to(self, target):
        """B1：完整↔迷你切换时高度渐变，而不是瞬间跳变。"""
        if abs(target - self._cur_h()) < 0.5:
            return
        self._h_from, self._h_to, self._h_k = self._cur_h(), target, 0.0
        self._h_anim = self._h_from
        self._h_anim_timer.start(16)

    def _h_anim_step(self):
        self._h_k = min(1.0, self._h_k + 0.13)
        e = 1.0 - (1.0 - self._h_k) ** 3          # ease-out：起步快、收尾稳
        self._h_anim = self._h_from + (self._h_to - self._h_from) * e
        s = float(self.cfg.get("scale", 1.0))
        self.setFixedSize(int(self.W * s), int(self._h_anim * s))
        self._bg_invalidate()
        if self._h_k >= 1.0:
            self._h_anim_timer.stop()
            self._h_anim = None
            self.apply_size()                      # 收尾：走正常流程（clamp / 吸附重算）
            return
        self.update()


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



    # ---------- 位置（支持多屏） ----------



    # B4：多屏 / DPI 变化时防止窗口飘到不可见区域




    # ---------- 菜单 ----------







    # ---------- 菜单动作 ----------



    # ---------- 天气 ----------















    # ---------- 分组设置窗口 ----------




    # ---------- 心情打卡（3） ----------


    # ---------- 周报与成就（5） ----------

    # ---------- 老板键（4） ----------




    # ---------- 边缘吸附（4） ----------






    # ---------- Qwen 个性化语录（12） ----------
    def _init_llm(self):
        try:
            if not llm.is_enabled():
                return
            self._llm_day = datetime.now().strftime("%Y-%m-%d")
            hit = llm.cached(self._llm_day)
            if hit:
                self.llm_lines = hit
                return
            ctx = {"desc": self._llm_context()}
            llm.request_async(ctx, self._llm_day, self._on_llm)
        except Exception:
            pass

    def _llm_context(self):
        now = datetime.now()
        w = self.weather
        wx = "%s %s℃" % (w.get("text", ""), w.get("temp", "")) if w else "未知"
        return "%s %s，天气%s，计划 %s 下班，猫叫%s" % (
            now.strftime("%m月%d日 %H:%M"), mood.WEEKDAY_CN[now.weekday()],
            wx, self.cfg.get("end", "18:00"), self.cfg.get("char", "橘猫"))

    def _on_llm(self, lines):
        if lines:
            self.llm_lines = list(lines)

    # ---------- 随机小惊喜（10） ----------





    # ---------- 交互 ----------





    # ---- A5：拖放惯性 ----







    # ---------- 计时 ----------
    def _tick_impl(self):
        dt = getattr(self, "step", 0.1)      # 自适应帧率下的真实帧间隔
        self.t0 += dt
        self._update_tray_icon()             # F4：托盘图标上的剩余时间
        # C2：番茄钟倒计时（用 step 计时，避免被后面的 dt 覆盖）
        if self.pomo:
            self.pomo["left"] -= getattr(self, "step", 0.1)
            if self.pomo["left"] <= 0:
                mode = self.pomo["mode"]
                self.pomo = None
                if mode == "focus":
                    self.notify("番茄结束啦", "起身活动一下，喝口水～", False)
                    self._pomo_start("break")
                else:
                    self._say("休息结束，继续冲～", 3.0)
                self._sync_pomo_action()
        self.blink_t += dt
        self.quote_t += dt
        if self.blink_t > self.blink_until:
            self.blink_t = 0.0
            self.blink_until = 2.2 + (os.getpid() % 7) * 0.4
            # A1：偶尔来一次「双眨」，比机械单眨更像活物
            if random.random() < 0.28:
                self.blink_until = 0.42
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
        # ---- 情境感知：前台应用 / 忙碌度 / 电量 / CPU（内部节流 1.5s） ----
        if self.cfg.get("context_aware", True):
            try:
                self.sense = SENSE.sample()
            except Exception:
                self.sense = {}
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
        if self.cfg.get("ear_tw", True) and self.ear_tw is None and self.t0 >= self.next_ear_tw:
            self.ear_tw = (random.choice((-1, 1)), self.t0)
            self.next_ear_tw = self.t0 + random.uniform(18, 45)
        # 阶段切换：发通知
        prev_phase = self.last_phase
        if prev_phase and phase != prev_phase:
            self._fired_marks.clear()
            if phase == "off":
                self._over_marks.clear()      # C1：新的一段加班，重新计劝走档位
            if phase == "off":
                # 记录真正的下班时刻（周报用）
                try:
                    stats.mark_off(now.strftime("%Y-%m-%d"), now.strftime("%H:%M"))
                except Exception:
                    pass
            if phase == "off" and self.cfg.get("notify_off", True):
                self.notify("下班啦～", "辛苦了，快去享受生活！", True)
            elif phase == "work" and prev_phase in ("pre", "rest") \
                    and self.cfg.get("notify_work", True):
                self.notify("该上班啦", "新的一天，加油～", False)
        self.last_phase = phase
        # 心情打卡提醒：工作时段每天问一次（已打卡或已问过就不再打扰）
        if self.cfg.get("mood_daily", True) and phase == "work" and not self.afk:
            day = now.strftime("%Y-%m-%d")
            if self._mood_asked_day != day and now.hour >= 10 and self.t0 > 15.0:
                try:
                    already = mood.today() is not None
                except Exception:
                    already = True
                self._mood_asked_day = day
                if not already:
                    self._say("今天心情怎么样？双击猫头就能打卡～", 4.0)
        # 随机小惊喜：约每 3-7 分钟判定一次，35% 概率触发
        if self.cfg.get("surprise", True) and not self.afk \
                and not self.cfg.get("mini", False):
            if self.t0 >= self.surprise_next:
                self.surprise_next = self.t0 + random.uniform(180, 420)
                if random.random() < 0.35:
                    self._fire_surprise()
        # A2：下班临近分级递进 60/30/10/5 分钟（跨点检测，每级各触发一次）
        if phase == "work" and self.cfg.get("notify_pre", True) \
                and self._prev_secs is not None:
            for mark, title in ((3600, "还有 1 小时下班"),
                                (1800, "还有 30 分钟下班"),
                                (600, "还有 10 分钟下班"),
                                (300, "还有 5 分钟！")):
                if self._prev_secs > mark >= secs and mark not in self._fired_marks:
                    self._fired_marks.add(mark)
                    if mark == 300:                       # 最后 5 分钟：猫开始收拾包
                        self._start_action("pack", 3.0)
                        self._say("要下班啦，收东西咯～", 3.0)
                        if self.cfg.get("notify_pre", True) and not self.afk:
                            self.notify(title, "收好东西，准点冲！", False)
                    else:
                        self.notify(title, "坚持住，猫陪你一起冲～", False)
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
                self.notify("该活动一下啦", Q.hydrate_msg(self.quote_i, self.quotes), False)
        else:
            self.last_hydrate = self.t0
        # C1：加班关怀——下班后还在忙，到点劝你走（30/60/120 分钟各劝一次）
        if phase == "off" and self.cfg.get("over_care", True) and not self.afk:
            try:
                over_min = stats.summary(now)["today"][1] / 60.0
            except Exception:
                over_min = 0.0
            for mark, txt in ((30, "已经加班半小时啦，差不多就走吧～"),
                              (60, "加班 1 小时了，身体要紧，收工！"),
                              (120, "两小时了……猫要睡了，你也快回家吧")):
                if over_min >= mark and mark not in self._over_marks:
                    self._over_marks.add(mark)
                    self._say(txt, 4.0)
                    break
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


    def _tick(self):
        """A4：tick 里任何异常都不能让计时循环死掉（否则挂件静止不动）。"""
        try:
            self._tick_impl()
        except Exception:
            from . import log
            log.exception("_tick")

    # ---------- C2：番茄钟 ----------
    def _pomo_minutes(self, mode):
        key = "pomo_focus" if mode == "focus" else "pomo_break"
        return max(1, int(self.cfg.get(key, 25 if mode == "focus" else 5)))

    def _pomo_start(self, mode):
        mins = self._pomo_minutes(mode)
        self.pomo = {"mode": mode, "left": float(mins * 60)}
        self._say("专注 %d 分钟，猫陪你一起～" % mins if mode == "focus"
                  else "休息 %d 分钟，起来动一动～" % mins, 3.0)

    def _sync_pomo_action(self):
        try:
            if self.pomo:
                self.act_pomo.setText("结束番茄（%s中）"
                                      % ("专注" if self.pomo["mode"] == "focus" else "休息"))
            else:
                self.act_pomo.setText("番茄钟 · 专注 %d 分钟" % self._pomo_minutes("focus"))
        except Exception:
            pass

    def toggle_pomo(self):
        if self.pomo:
            self.pomo = None
            self._say("番茄取消啦～", 2.5)
        else:
            self._pomo_start("focus")
        self._sync_pomo_action()

    def _start_action(self, name, dur=2.0):
        """A2：播放一个指定动作（覆盖当前待机动作）。"""
        self.action = name
        self.action_start = self.t0
        self.action_dur = dur
        self.idle = (name, self.t0)


    # ---- 圆角气泡排版辅助 ----


    # ---- 气泡形状 ----



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
        """当前实际佩戴的配饰：用户选择 > 节日 > none。"""
        acc = str(self.cfg.get("acc", "auto"))
        if acc != "auto":
            return acc
        if self.fest and self.fest.get("acc"):
            return self.fest["acc"]
        return "none"

    def _quote(self):
        """挑一条语录。优先级：
        Qwen 个性化 > 节日 > 设备告警 > 应用/会议场景 > 忙碌度 > 天气/周五/时段"""
        phase = self._status()[0]
        # 上班前 / 下班后也会说两句话（休息日不打扰）
        if phase not in ("work", "pre", "off"):
            return None
        now = datetime.now()
        hour = now.hour + now.minute / 60.0
        i = self.quote_i
        custom = self.quotes

        # 1) Qwen 个性化语录（配置开启时每 3 条插 1 条）
        if self.llm_lines and i % 3 == 1:
            return self.llm_lines[(i // 3) % len(self.llm_lines)]

        # 2) 节日专属
        if self.fest and i % 4 == 0:
            pool = self.fest.get("pool") or []
            if pool:
                return pool[(i // 4) % len(pool)]

        # 3) 情境感知（应用 / 会议 / 忙碌度 / 电量 / CPU / 全屏）——只在工作时段
        if self.cfg.get("context_aware", True) and self.sense and phase == "work":
            s = self.sense
            key = None
            if s.get("battery", 255) <= 20 and not s.get("ac", True):
                key = "low_battery"
            elif s.get("cpu", 0) >= 88:
                key = "high_cpu"
            elif s.get("scene") == "meeting":
                key = "meeting"
            elif s.get("fullscreen") and i % 2 == 0:
                key = "fullscreen"
            elif s.get("scene", "other") != "other":
                key = s["scene"]
            elif s.get("busy", 0.0) >= 0.65:
                key = "busy_high"
            elif s.get("busy", 1.0) <= 0.15:
                key = "busy_low"
            if key:
                msg = Q.context_msg(key, i // 2, custom)
                if msg:
                    return msg

        # 4) 原有：天气 / 周五 / 时段
        w = self.weather
        kind = w.get("kind") if w else None
        msg = Q.get_quote(phase, hour, now.weekday() == 4, kind, i, custom)
        if msg and kind == "sun" and w.get("temp", 0) >= 34:
            msg += "，多喝水"
        return msg

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



    # ---------- E1：面板天气氛围 ----------


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


def _excepthook(exc_type, exc_value, exc_tb):
    """A4/B3：未捕获异常统一走 log 模块（%APPDATA%\\CatClock\\catclock.log）。"""
    try:
        import traceback
        from . import log as LOG
        LOG.exception("excepthook")
        # 兼容旧习惯：同时写一份 crash.log
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(os.path.join(CONFIG_DIR, "crash.log"), "a", encoding="utf-8") as f:
            f.write("%s %s: %s\n" % (datetime.now().isoformat(),
                                     exc_type.__name__, exc_value))
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
            f.write("\n")
    except Exception:
        pass


def main():
    sys.excepthook = _excepthook
    from . import log as LOG
    LOG.startup(__version__)          # A3：每次启动写一行，便于回溯
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
