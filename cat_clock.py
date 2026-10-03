# -*- coding: utf-8 -*-
"""
CatClock —— 桌面可爱猫猫 · 下班倒计时挂件

类似 Catime 的桌面悬浮小窗：多只可选猫猫 + 多套界面主题。
支持拖动、右键菜单（角色 / 样式 / 上下班时间 / 迷你模式 / 开机自启 / 置顶）、托盘图标。
智能状态：上班前 / 工作中（含进度条）/ 下班后 / 休息日。
智能交互：离开打瞌睡（GetLastInputInfo）、回来打招呼、下班前 30/10 分钟预告、
上班前提醒、休息日前夜提示、天气联动语录、久坐文案轮换、整点报时防打扰。
"""

import json
import os
import re
import sys
import math
import random
import calendar
from datetime import datetime, timedelta
from urllib.parse import quote

try:
    import winreg
except Exception:
    winreg = None

from PyQt6.QtCore import Qt, QPoint, QPointF, QTimer, QRectF, QUrl, QObject, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QLinearGradient, QRadialGradient,
    QPixmap, QAction, QActionGroup, QCursor,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QMenu, QSystemTrayIcon, QInputDialog, QMessageBox,
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QLineEdit, QLabel,
)
from PyQt6.QtNetwork import (
    QLocalServer, QLocalSocket, QNetworkAccessManager, QNetworkRequest, QNetworkReply,
)

APP_NAME = "CatClock"
SINGLE_ID = "CatClockSingleInstance"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS = {
    "start": "09:00",     # 上班时间 HH:MM
    "end": "18:00",       # 下班时间 HH:MM
    "char": "橘猫",
    "style": "奶油",
    "pos": None,
    "top": True,
    "autostart": True,
    "show_sec": True,     # 双击窗口切换 秒 显示
    "mini": False,        # 迷你模式（只显示猫 + 时间）
    "rest_days": [5, 6],  # 每周休息日（0=周一 … 6=周日），单休/轮休可改
    "notify_off": True,   # 下班时通知
    "notify_work": True,  # 上班时提醒
    "sound": True,        # 提示音
    "city": "",           # 天气城市（留空不显示天气）
    "payday": 0,          # 每月发薪日（1-31，0=不显示）
    "hydrate": True,      # 每小时久坐提醒
    "notify_pre": True,   # 下班前 30/10 分钟预告
    "afk": True,          # 离开时猫打瞌睡
    "scale": 1.0,         # 整体缩放（0.6-1.6，滚轮调节）
}

# ======================================================================
# 打工人语录（按时段轮换）
# ======================================================================
QUOTES = [
    (9.0, 10.5, ["新的一天，搬砖愉快", "早！今天也要加油鸭", "咖啡续上了吗"]),
    (10.5, 11.5, ["坚持住，马上吃饭了", "上午的砖搬完一半了"]),
    (11.5, 13.5, ["干饭时间到！", "干饭不积极，思想有问题", "今天食堂还是外卖？"]),
    (13.5, 15.5, ["午困，撑住", "摸鱼五分钟，精神两小时"]),
    (15.5, 16.5, ["下午茶整一个？", "摸鱼也要讲基本法"]),
    (16.5, 17.5, ["开始收拾东西了", "键盘声都变响了"]),
]

QUOTES_FRIDAY = {
    (9.0, 10.5): ["周五！稳住，胜利在望", "今天是周五，懂的都懂"],
    (15.5, 16.5): ["周五下午，心在飞", "想想周末去哪玩"],
    (16.5, 17.5): ["周五！忍住，就快了", "周五的 4 点，你懂的"],
    (17.5, 24.0): ["周末启动！", "周五晚上，人间值得"],
}

# ======================================================================
# 天气联动语录（晴雨雪雷各有专属，与时段语录穿插出现）
# ======================================================================
WEATHER_QUOTES = {
    "rain": ["下雨了，出门记得带伞", "雨天适合摸鱼发呆"],
    "thunder": ["打雷了，猫有点怕怕", "雷雨天，早点回家"],
    "snow": ["下雪啦，注意保暖", "下雪天适合许愿哦"],
    "sun": ["今天阳光不错，晒晒心情", "大晴天，搬砖都有劲"],
    "cloud-sun": ["多云转晴，心情也是"],
    "cloud": ["阴天，适合闷头干活"],
    "fog": ["雾好大，路上慢点"],
}

# 久坐提醒文案轮换
HYDRATE_MSGS = [
    "喝口水，起来走走～",
    "活动一下，看看远处～",
    "肩颈放松 30 秒，继续战斗",
    "站起来倒杯水，猫替你盯着进度",
]

# ======================================================================
# 角色表
# ======================================================================
CHARACTERS = {
    "橘猫": dict(
        fur="#FBBF77", fur_d="#F3A65A", fur_l="#FFEACF", line="#E89B52",
        ear_in="#FFB9C6", nose="#FF8FA3", eye="#4A342C",
        tabby=True, tabby_c="#F0A052", patches=(), ears=(None, None),
    ),
    "奶牛猫": dict(
        fur="#FFFFFF", fur_d="#F3EDE4", fur_l="#FFF9F2", line="#D8C8B8",
        ear_in="#FFC9D4", nose="#FF8FA3", eye="#4A342C",
        tabby=False, patches=(
            dict(x=-0.46, y=-0.46, w=0.50, h=0.44, c="#3B3733"),
            dict(x=0.08, y=-0.47, w=0.36, h=0.30, c="#3B3733"),
            dict(x=-0.48, y=0.12, w=0.30, h=0.30, c="#3B3733"),
        ), ears=("#3B3733", None),
    ),
    "黑猫": dict(
        fur="#4C4653", fur_d="#3A3542", fur_l="#5E5866", line="#2F2B36",
        ear_in="#9A8BA0", nose="#E88FA0", eye="#F2C14E",
        tabby=False, patches=(), ears=(None, None),
    ),
    "三花猫": dict(
        fur="#FFF7EE", fur_d="#F5E9DA", fur_l="#FFFCF6", line="#DCC3AA",
        ear_in="#FFB9C6", nose="#FF8FA3", eye="#4A342C",
        tabby=False, patches=(
            dict(x=-0.44, y=-0.44, w=0.42, h=0.38, c="#F3A65A"),
            dict(x=0.12, y=-0.46, w=0.34, h=0.32, c="#3B3733"),
            dict(x=0.28, y=0.10, w=0.28, h=0.24, c="#F3A65A"),
            dict(x=-0.46, y=0.12, w=0.26, h=0.22, c="#3B3733"),
        ), ears=("#F3A65A", "#3B3733"),
    ),
    "白猫": dict(
        fur="#FFFFFF", fur_d="#F1ECE5", fur_l="#FFFFFF", line="#DACFC4",
        ear_in="#FFC9D4", nose="#FF9FB0", eye="#4A342C",
        tabby=False, patches=(), ears=(None, None),
    ),
    "蓝猫": dict(
        fur="#AAB5C1", fur_d="#8F9BA9", fur_l="#C7CED7", line="#7D8997",
        ear_in="#DBA9B5", nose="#E89AA8", eye="#3A4754",
        tabby=True, tabby_c="#93A0AE", patches=(), ears=(None, None),
    ),
    "暹罗猫": dict(
        fur="#F6EDE2", fur_d="#EADFD2", fur_l="#FBF6EE", line="#C9B8A8",
        ear_in="#D8B8AC", nose="#C9808A", eye="#7FB3D5",
        tabby=False, patches=(
            dict(x=-0.20, y=-0.46, w=0.42, h=0.42, c="#5C463A"),   # 面部重点色
        ), ears=("#5C463A", "#5C463A"),
    ),
    "虎斑猫": dict(
        fur="#C4B09A", fur_d="#A98F76", fur_l="#EFE3D2", line="#8A7258",
        ear_in="#D8A8A0", nose="#E8909C", eye="#3E3226",
        tabby=True, tabby_c="#7A6448", patches=(), ears=(None, None),
    ),
    "熊猫": dict(
        fur="#FFFFFF", fur_d="#EFEFEF", fur_l="#FFFFFF", line="#3A3A3A",
        ear_in="#3A3A3A", nose="#3A3A3A", eye="#F5F5F5", pupil="#2A2A2A",
        tabby=False, patches=(
            dict(x=-0.285, y=-0.14, w=0.20, h=0.22, c="#3A3A3A"),  # 左眼圈
            dict(x=0.085, y=-0.14, w=0.20, h=0.22, c="#3A3A3A"),   # 右眼圈
        ), ears=("#3A3A3A", "#3A3A3A"),
    ),
}

# ======================================================================
# 主题表
# ======================================================================
STYLES = {
    "奶油": dict(
        panel0=(255, 255, 255, 252), panel1=(255, 247, 240, 248),
        border=(255, 216, 192), border_h=(255, 198, 168), shadow=(70, 45, 35),
        bar_bg=(246, 233, 221), bar0=(255, 210, 157), bar1=(255, 158, 110),
        bar0_off=(255, 170, 190), bar1_off=(255, 122, 156),
        text="#4A3B33", sub="#B09A8C", pink="#FF7A9C",
        menu_bg="#FFFDFA", menu_border="#F2D9C6", menu_sel="#FFE9D6",
        menu_text="#5A4A42", menu_sep="#F0E3DA",
    ),
    "草莓": dict(
        panel0=(255, 252, 253, 252), panel1=(255, 240, 245, 248),
        border=(255, 205, 218), border_h=(255, 183, 205), shadow=(95, 40, 62),
        bar_bg=(249, 229, 236), bar0=(255, 183, 205), bar1=(255, 145, 180),
        bar0_off=(255, 170, 190), bar1_off=(255, 122, 156),
        text="#5A3A46", sub="#C096A4", pink="#FF6B95",
        menu_bg="#FFF9FB", menu_border="#F6D3DE", menu_sel="#FFE3EC",
        menu_text="#5A3A46", menu_sep="#F5DEE6",
    ),
    "薄荷": dict(
        panel0=(253, 255, 254, 252), panel1=(240, 250, 246, 248),
        border=(196, 232, 218), border_h=(168, 224, 200), shadow=(35, 70, 55),
        bar_bg=(226, 241, 234), bar0=(159, 222, 190), bar1=(96, 199, 150),
        bar0_off=(255, 170, 190), bar1_off=(255, 122, 156),
        text="#2E443C", sub="#8FA89E", pink="#F27A9C",
        menu_bg="#FAFEFC", menu_border="#CBE8DC", menu_sel="#DDF3E9",
        menu_text="#2E443C", menu_sep="#D8EDE3",
    ),
    "夜幕": dict(
        panel0=(54, 49, 67, 250), panel1=(36, 32, 46, 248),
        border=(99, 90, 125), border_h=(134, 123, 165), shadow=(0, 0, 0),
        bar_bg=(67, 61, 82), bar0=(152, 131, 224), bar1=(202, 141, 232),
        bar0_off=(255, 150, 180), bar1_off=(255, 110, 150),
        text="#F2ECE4", sub="#9C93AC", pink="#FF8FB0",
        menu_bg="#2F2B39", menu_border="#575168", menu_sel="#4C465B",
        menu_text="#EDE8F2", menu_sep="#474153",
    ),
    "柠檬": dict(
        panel0=(255, 254, 250, 252), panel1=(255, 248, 228, 248),
        border=(244, 228, 170), border_h=(238, 213, 138), shadow=(92, 76, 30),
        bar_bg=(246, 238, 208), bar0=(255, 224, 140), bar1=(250, 196, 90),
        bar0_off=(255, 170, 190), bar1_off=(255, 122, 156),
        text="#54452A", sub="#B5A273", pink="#F2839C",
        menu_bg="#FFFEF7", menu_border="#EFE3B8", menu_sel="#FBF0C9",
        menu_text="#54452A", menu_sep="#F0E7C8",
    ),
}


# ======================================================================
# 天气（Open-Meteo，免 key）
# ======================================================================
WMO_TEXT = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴",
    45: "雾", 48: "雾",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨", 56: "冻雨", 57: "冻雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪",
    80: "阵雨", 81: "阵雨", 82: "强阵雨",
    85: "阵雪", 86: "阵雪",
    95: "雷暴", 96: "雷暴冰雹", 99: "雷暴冰雹",
}


def wmo_kind(code):
    if code == 0:
        return "sun"
    if code in (1, 2):
        return "cloud-sun"
    if code == 3:
        return "cloud"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "thunder"
    return "cloud"


def load_cfg():
    cfg = dict(DEFAULTS)
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
    except Exception:
        pass
    if cfg["char"] not in CHARACTERS:
        cfg["char"] = "橘猫"
    if cfg["style"] not in STYLES:
        cfg["style"] = "奶油"
    return cfg


def save_cfg(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def app_path():
    return os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)


def autostart_enabled():
    if not winreg:
        return False
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY)
        val, _ = winreg.QueryValueEx(k, APP_NAME)
        winreg.CloseKey(k)
        return bool(val)
    except Exception:
        return False


def set_autostart(enable):
    if not winreg:
        return False
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_WRITE)
        if enable:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, '"%s"' % app_path())
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(k)
        return True
    except Exception:
        return False


def _raise_existing():
    """尽力唤起已运行的实例（旧版兼容）"""
    try:
        sock = QLocalSocket()
        sock.connectToServer(SINGLE_ID)
        if sock.waitForConnected(300):
            sock.write(b"raise")
            sock.waitForBytesWritten(300)
            sock.close()
    except Exception:
        pass


def acquire_single():
    """单实例锁：Windows 命名互斥体为准（进程被杀内核也自动释放，不会残留），
    QLocalServer 仅用于唤起已运行实例。即使管道残留导致 listen 失败也照常运行，
    绝不静默退出。"""
    import ctypes
    k = ctypes.windll.kernel32
    mutex = k.CreateMutexW(None, False, "CatClockSingleInstance")
    last_err = k.GetLastError()
    if mutex and last_err == 183:                  # ERROR_ALREADY_EXISTS
        k.CloseHandle(mutex)
        _raise_existing()
        return None

    QLocalServer.removeServer(SINGLE_ID)
    server = QLocalServer()
    import time
    for attempt in range(5):                       # 管道名残留时重试清理
        if server.listen(SINGLE_ID):
            break
        QLocalServer.removeServer(SINGLE_ID)
        if attempt < 4:
            time.sleep(0.4)
    server._catclock_mutex = mutex                 # 保持引用，进程退出时内核释放
    return server


def rr(x, y, w, h, r):
    p = QPainterPath()
    p.addRoundedRect(QRectF(x, y, w, h), r, r)
    return p


# 字体全局缓存：每帧新建 QFont 会反复触发字体引擎查询，
# 在某些装了桌面水印/EDR  hooks 的机器上会导致 native fail-fast
_FONT_CACHE = {}


def user_idle_seconds():
    """用户无键盘/鼠标输入的时长（秒），读取失败返回 0"""
    try:
        import ctypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]

        li = LASTINPUTINFO()
        li.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
            return 0.0
        diff = (ctypes.windll.kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF
        if diff > 0x7FFFFFFF:      # 异常值兜底
            return 0.0
        return diff / 1000.0
    except Exception:
        return 0.0


def font(name, size, weight=None, style_hint=None):
    key = (name, size, weight, style_hint)
    f = _FONT_CACHE.get(key)
    if f is None:
        f = QFont(name, size)
        if weight is not None:
            f.setWeight(weight)
        if style_hint is not None:
            f.setStyleHint(style_hint)
        _FONT_CACHE[key] = f
    return f


# ======================================================================
# 猫猫绘制
# ======================================================================
def draw_cat(p, cx, cy, s, colors=None, blink=False, excited=False, sleepy=False,
             scared=False, look=(0.0, 0.0), mood=None, tail_phase=None, t=0.0):
    """画一只可爱的猫脑袋。s 为整体直径；look 为瞳孔偏移(-1..1)；mood 待机动作；tail_phase 摇尾"""
    if colors is None:
        colors = CHARACTERS["橘猫"]
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    cy += math.sin(t) * s * 0.018          # 呼吸浮动
    if mood == "stretch":                  # 伸懒腰：整体放大一点 + 眯眼
        s *= 1.05
        blink = True

    lw = max(1.0, s * 0.016)
    outline = QPen(QColor(colors["line"]), lw)
    outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    outline.setCapStyle(Qt.PenCapStyle.RoundCap)

    head_rect = QRectF(cx - 0.44 * s, cy - 0.42 * s, 0.88 * s, 0.86 * s)

    # ---- 尾巴（最底层，从头侧伸出摆动） ----
    if tail_phase is not None:
        bx, by = cx - 0.38 * s, cy + 0.32 * s
        sw = math.sin(tail_phase) * 0.18 * s
        tail = QPainterPath()
        tail.moveTo(bx, by)
        tail.cubicTo(bx - 0.18 * s, by + 0.08 * s,
                     bx - 0.16 * s + sw, by - 0.14 * s,
                     bx - 0.04 * s + sw * 1.7, by - 0.24 * s)
        p.setPen(QPen(QColor(colors["fur_d"]), max(2.0, s * 0.055), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(tail)
        p.setPen(QPen(QColor(colors["fur_l"]), max(1.0, s * 0.020), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        tail2 = QPainterPath()
        tail2.moveTo(bx - 0.02 * s, by - 0.015 * s)
        tail2.cubicTo(bx - 0.17 * s, by + 0.05 * s,
                      bx - 0.15 * s + sw, by - 0.13 * s,
                      bx - 0.05 * s + sw * 1.6, by - 0.21 * s)
        p.drawPath(tail2)

    # ---- 耳朵 ----
    for idx, sign in enumerate((-1, 1)):
        ear_c = colors["ears"][idx] or colors["fur"]
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
            p.setBrush(QColor(pt["c"]))
            p.drawEllipse(QRectF(cx + pt["x"] * s, cy + pt["y"] * s,
                                 pt["w"] * s, pt["h"] * s))
        p.setClipping(False)

    # ---- 虎斑 ----
    if colors.get("tabby"):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(colors["tabby_c"]))
        for off, hh, ww in ((-0.15, 0.10, 0.026), (0.0, 0.13, 0.030), (0.15, 0.10, 0.026)):
            p.drawRoundedRect(QRectF(cx + off * s - ww * s / 2, cy - 0.40 * s, ww * s, hh * s),
                              ww * s / 2, ww * s / 2)

    # ---- 脸颊浅色 ----
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(colors["fur_l"]))
    p.drawEllipse(QRectF(cx - 0.24 * s, cy + 0.08 * s, 0.48 * s, 0.26 * s))

    # ---- 腮红 ----
    p.setBrush(QColor(255, 150, 170, 105))
    for sign in (-1, 1):
        p.drawEllipse(QRectF(cx + sign * 0.30 * s - 0.085 * s, cy + 0.04 * s, 0.17 * s, 0.105 * s))

    # ---- 胡须 ----
    hp = QPen(QColor("#E0AC76"), max(1.0, s * 0.012))
    hp.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(hp)
    for sign in (-1, 1):
        for k, dy in enumerate((-0.03, 0.04, 0.11)):
            y = cy + dy * s
            x0 = cx + sign * 0.17 * s
            p.drawLine(
                QPointF(x0, y),
                QPointF(x0 + sign * 0.26 * s, y + (k - 1) * s * 0.030),
            )

    # ---- 眼睛 ----
    eye_y = cy - 0.02 * s
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
            p.setPen(QPen(QColor("#E8930C"), max(1.0, s * 0.014)))
            p.setBrush(QColor("#FFD34D"))
            p.drawPath(star)
        elif blink or sleepy:
            p.setPen(QPen(QColor(colors["eye"]), max(1.6, s * 0.030), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(ex - s * 0.085, eye_y - s * 0.055, s * 0.17, s * 0.11),
                      180 * 16, 180 * 16)
        else:                             # 大眼 + 双高光（瞳孔跟随 look 偏移）
            lx = max(-1.0, min(1.0, look[0])) * s * 0.030
            ly = max(-1.0, min(1.0, look[1])) * s * 0.022
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(colors["eye"]))
            p.drawEllipse(QRectF(ex - s * 0.068, eye_y - s * 0.095, s * 0.136, s * 0.19))
            if colors.get("pupil"):            # 熊猫式：白眼 + 深色瞳孔
                p.setBrush(QColor(colors["pupil"]))
                p.drawEllipse(QRectF(ex - s * 0.030 + lx, eye_y - s * 0.030 + ly, s * 0.060, s * 0.075))
                p.setBrush(QColor("#FFFFFF"))
                p.drawEllipse(QRectF(ex + s * 0.010 + lx, eye_y - s * 0.022 + ly, s * 0.022, s * 0.022))
            else:
                p.setBrush(QColor("#FFFFFF"))
                p.drawEllipse(QRectF(ex + s * 0.008 + lx, eye_y - s * 0.062 + ly, s * 0.052, s * 0.055))
                p.drawEllipse(QRectF(ex - s * 0.048 + lx, eye_y + s * 0.018 + ly, s * 0.024, s * 0.024))

    # ---- 鼻子 ----
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(colors["nose"]))
    nose = QPainterPath()
    nose.moveTo(cx - s * 0.045, cy + 0.115 * s)
    nose.lineTo(cx + s * 0.045, cy + 0.115 * s)
    nose.lineTo(cx, cy + 0.170 * s)
    nose.closeSubpath()
    p.drawPath(nose)

    # ---- 嘴（打哈欠为 O 形，否则 W 形） ----
    p.setPen(QPen(QColor(colors["line"]), max(1.3, s * 0.022), Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    if mood == "yawn":
        p.setBrush(QColor("#7A4A3A"))
        p.drawEllipse(QRectF(cx - s * 0.040, cy + 0.125 * s, s * 0.080, s * 0.095))
        p.setPen(Qt.PenStyle.NoPen)      # 打哈欠的泪珠
        p.setBrush(QColor("#8EC9E8"))
        p.drawEllipse(QRectF(cx + 0.20 * s, cy - 0.10 * s, s * 0.045, s * 0.06))
    else:
        p.drawArc(QRectF(cx - s * 0.090, cy + 0.125 * s, s * 0.090, s * 0.090), 200 * 16, 120 * 16)
        p.drawArc(QRectF(cx, cy + 0.125 * s, s * 0.090, s * 0.090), 220 * 16, 120 * 16)

    # ---- 害怕汗滴（雷暴） ----
    if scared:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#8EC9E8"))
        p.drawEllipse(QRectF(cx + 0.24 * s, cy - 0.42 * s, 0.10 * s, 0.14 * s))

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


class WeatherFetcher(QObject):
    """Open-Meteo 天气拉取：地理编码（逐级降级）→ 实时天气，got 信号发 dict"""
    got = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nam = QNetworkAccessManager(self)
        self._candidates = []

    def start(self, city):
        self._candidates = self._fallback_names(city)
        self._try_next()

    @staticmethod
    def _fallback_names(city):
        """上海闵行区 → 上海闵行区 / 上海闵行 / 上海闵 / 上海"""
        names = [city]
        base = re.sub(r"(省|市|区|县)$", "", city)
        if base != city:
            names.append(base)
        while len(base) > 2:
            base = base[:-1]
            names.append(base)
        seen, out = set(), []
        for n in names:
            if n and n not in seen:
                seen.add(n)
                out.append(n)
        return out

    def _try_next(self):
        if not self._candidates:
            return
        name = self._candidates.pop(0)
        url = ("https://geocoding-api.open-meteo.com/v1/search?name=%s"
               "&count=1&language=zh&format=json" % quote(name))
        req = QNetworkRequest(QUrl(url))
        req.setTransferTimeout(15000)
        reply = self.nam.get(req)
        reply.finished.connect(lambda r=reply: self._geo_done(r))

    def _geo_done(self, reply):
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            results = data.get("results") or []
            if not results:
                self._try_next()          # 查不到则降级到上级地名
                reply.deleteLater()
                return
            loc = results[0]
            lat, lon = loc["latitude"], loc["longitude"]
            name = loc.get("name", "")
            url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
                   "&current_weather=true&timezone=Asia%%2FShanghai" % (lat, lon))
            req = QNetworkRequest(QUrl(url))
            req.setTransferTimeout(15000)
            r2 = self.nam.get(req)
            r2.finished.connect(lambda rr=r2, n=name: self._wx_done(rr, n))
        except Exception:
            pass
        reply.deleteLater()

    def _wx_done(self, reply, name):
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            cw = data["current_weather"]
            code = int(cw["weathercode"])
            self.got.emit(dict(
                city=name, code=code, kind=wmo_kind(code),
                temp=round(cw["temperature"]),
                text=WMO_TEXT.get(code, "多云"),
            ))
        except Exception:
            pass
        reply.deleteLater()


class CatInputDialog(QDialog):
    """统一风格的中文输入对话框（替换系统 QInputDialog 的英文按钮）"""

    def __init__(self, title, label, text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(340)
        layout = QVBoxLayout(self)
        lab = QLabel(label)
        lab.setWordWrap(True)
        layout.addWidget(lab)
        self.edit = QLineEdit(text)
        self.edit.selectAll()
        layout.addWidget(self.edit)
        btns = QHBoxLayout()
        ok = QPushButton("确定")
        cancel = QPushButton("取消")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def value(self):
        return self.edit.text().strip()


class RestDaysDialog(QDialog):
    """每周休息日多选（单休/轮休适用）"""

    NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    def __init__(self, days, parent=None):
        super().__init__(parent)
        self.setWindowTitle("休息日设置")
        self.setFixedWidth(220)
        self.boxes = []
        layout = QVBoxLayout(self)
        for i, n in enumerate(self.NAMES):
            b = QCheckBox(n)
            b.setChecked(i in days)
            self.boxes.append(b)
            layout.addWidget(b)
        btns = QHBoxLayout()
        ok = QPushButton("确定")
        cancel = QPushButton("取消")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def days(self):
        return [i for i, b in enumerate(self.boxes) if b.isChecked()]


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
        QTimer.singleShot(1500, self.refresh_weather)
        self.wx_timer = QTimer(self)
        self.wx_timer.timeout.connect(self.refresh_weather)
        self.wx_timer.start(30 * 60 * 1000)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(100)

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
        grp = QActionGroup(self)
        for name in CHARACTERS:
            a = QAction(name, self, checkable=True)
            a.setChecked(name == self.cfg["char"])
            a.triggered.connect(lambda _, n=name: self.set_char(n))
            grp.addAction(a)
            self.char_menu.addAction(a)

        self.style_menu = QMenu("样式", self)
        grp2 = QActionGroup(self)
        for name in STYLES:
            a = QAction(name, self, checkable=True)
            a.setChecked(name == self.cfg["style"])
            a.triggered.connect(lambda _, n=name: self.set_style(n))
            grp2.addAction(a)
            self.style_menu.addAction(a)

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

        # 大小子菜单
        self.size_menu = QMenu("大小（也可在窗口上滚轮）", self)
        grp_s = QActionGroup(self)
        for pct in (60, 80, 100, 120, 140, 160):
            a = QAction("%d%%" % pct, self, checkable=True)
            a.setChecked(abs(float(self.cfg.get("scale", 1.0)) - pct / 100.0) < 0.001)
            a.triggered.connect(lambda _, v=pct / 100.0: self.set_scale(v))
            grp_s.addAction(a)
            self.size_menu.addAction(a)
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
        self.act_reset = QAction("回到默认位置", self)
        self.act_reset.triggered.connect(self.reset_pos)
        self.act_quit = QAction("退出", self)
        self.act_quit.triggered.connect(self.quit)

        self.menu.addMenu(self.char_menu)
        self.menu.addMenu(self.style_menu)
        self.menu.addSeparator()
        self.menu.addAction(self.act_start)
        self.menu.addAction(self.act_end)
        self.menu.addAction(self.act_rest)
        self.menu.addAction(self.act_city)
        self.menu.addAction(self.act_payday)
        self.menu.addSeparator()
        self.menu.addAction(self.act_noff)
        self.menu.addAction(self.act_nwork)
        self.menu.addAction(self.act_sound)
        self.menu.addAction(self.act_hydrate)
        self.menu.addAction(self.act_npre)
        self.menu.addAction(self.act_afk)
        self.menu.addSeparator()
        self.menu.addMenu(self.size_menu)
        self.menu.addSeparator()
        self.menu.addAction(self.act_mini)
        self.menu.addAction(self.act_sec)
        self.menu.addAction(self.act_top)
        self.menu.addAction(self.act_auto)
        self.menu.addSeparator()
        self.menu.addAction(self.act_reset)
        self.menu.addAction(self.act_quit)

    def _build_tray(self):
        self.tray = QSystemTrayIcon(make_icon(64, self.cfg["char"]), self)
        self.tray.setToolTip("%s · %s" % (APP_NAME, self.cfg["char"]))
        tray_menu = QMenu()
        tray_menu.addAction(self.char_menu.menuAction())
        tray_menu.addAction(self.style_menu.menuAction())
        tray_menu.addSeparator()
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
        city = self.cfg.get("city", "")
        if city:
            try:
                self.wx.start(city)
            except Exception:
                pass

    def _wx_got(self, w):
        self.weather = w
        try:
            self.tray.setToolTip("%s · %s %s %d°C" % (APP_NAME, w["city"], w["text"], w["temp"]))
        except Exception:
            pass
        self.update()

    def toggle_cfg(self, key, on):
        self.cfg[key] = bool(on)
        save_cfg(self.cfg)

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
            mini = self.cfg.get("mini", False)
            cs = 60 if mini else 84
            ccx = 54 if mini else 58
            ccy = (self.H_MINI if mini else self.H_FULL) / 2
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
            mini = self.cfg.get("mini", False)
            cs = 60 if mini else 84
            ccx = 54 if mini else 58
            ccy = (self.H_MINI if mini else self.H_FULL) / 2
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
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def closeEvent(self, e):
        self.cfg["pos"] = [self.x(), self.y()]
        save_cfg(self.cfg)
        e.accept()

    # ---------- 计时 ----------
    def _tick(self):
        self.t0 += 0.1
        self.blink_t += 0.1
        self.quote_t += 0.1
        if self.blink_t > self.blink_until:
            self.blink_t = 0.0
            self.blink_until = 2.2 + (os.getpid() % 7) * 0.4
        if self.meow_t < 1.0:
            self.meow_t += 0.08
        if self.quote_t >= 25.0:        # 每 25 秒换下一条语录
            self.quote_t = 0.0
            self.quote_i += 1
        if self.hydrate_t < 5.0:
            self.hydrate_t += 0.1
        if self.hourly_t < 3.0:
            self.hourly_t += 0.1
        if self.meow_bubble_t < 2.5:
            self.meow_bubble_t += 0.1
        if self.bubble_t < 3.5:
            self.bubble_t += 0.1
        # 整点报时：7-22 点且非休息日（深夜和休息不打扰）
        now = datetime.now()
        phase, start, end, secs, pct = self._status()
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
                name = random.choice(["stretch", "yawn", "yawn"])
            self.idle = (name, self.t0)
        if self.idle and self.t0 - self.idle[1] > 3.0:
            self.idle = None
            self.idle_next = self.t0 + random.uniform(20, 45)
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
                self.notify("该活动一下啦", random.choice(HYDRATE_MSGS), False)
        else:
            self.last_hydrate = self.t0
        self._prev_secs = secs
        self.update()

    def _say(self, text, dur=3.5):
        """让猫说话（通用气泡）"""
        self.bubble_text = text
        self.bubble_t = 0.0

    def _quote(self):
        """当前时段的打工人语录（周五专属池 + 天气联动穿插）"""
        now = datetime.now()
        h = now.hour + now.minute / 60.0
        if now.weekday() == 4:                       # 周五专属
            for (a, b), pool in QUOTES_FRIDAY.items():
                if a <= h < b:
                    return pool[self.quote_i % len(pool)]
        w = self.weather
        if w and w.get("kind") in WEATHER_QUOTES and self.quote_i % 3 == 0:
            pool = WEATHER_QUOTES[w["kind"]]
            msg = pool[(self.quote_i // 3) % len(pool)]
            if w.get("temp", 0) >= 34:
                msg += "，多喝水"
            return msg
        for a, b, pool in QUOTES:
            if a <= h < b:
                return pool[self.quote_i % len(pool)]
        return None

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

    # ---------- 绘制 ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        s = float(self.cfg.get("scale", 1.0))
        p.scale(s, s)                       # 全局等比缩放，后续全部用逻辑坐标
        W = self.W
        mini = self.cfg.get("mini", False)
        H = self.H_MINI if mini else self.H_FULL
        pad = 5
        st = self.style()

        # 柔和阴影
        for i in range(6):
            k = 5 - i
            inset = pad + k * 1.2 - 1.2
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(st["shadow"][0], st["shadow"][1], st["shadow"][2], 8 + k * 4))
            p.drawPath(rr(inset, inset + 1.6, W - 2 * inset, H - 2 * inset, 25))

        # 面板
        g = QLinearGradient(0, pad, 0, H - pad)
        g.setColorAt(0, QColor(*st["panel0"]))
        g.setColorAt(1, QColor(*st["panel1"]))
        p.setBrush(g)
        ba = 235 if self.hover else 190
        bcol = st["border_h"] if self.hover else st["border"]
        p.setPen(QPen(QColor(bcol[0], bcol[1], bcol[2], ba), 1.3))
        p.drawPath(rr(pad, pad, W - 2 * pad, H - 2 * pad, 24))

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
        cs = 60 if mini else 84
        ccx = 54 if mini else 58
        ccy = H / 2
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
        # 摇尾：平时慢摆，摸猫时快摆
        tail_phase = (self.t0 * (7.0 if meowing else 1.8)) + (2.0 if meowing else 0.0)
        draw_cat(p, ccx + shake, ccy, cs, self.char_colors(),
                 blink=self.blink_t < 0.18 or meowing, excited=excited, sleepy=sleepy,
                 scared=thunder or too_hot, look=look, mood=mood,
                 tail_phase=tail_phase, t=self.t0)

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

            # 行1：天气 + 距下班
            p.setPen(QColor(st["sub"]))
            p.setFont(font("Microsoft YaHei", 9))
            wx = ""
            if self.weather and not mini:
                wx = "%s %d°C · " % (self.weather["text"], self.weather["temp"])
            if mini:
                sub = {"pre": "%s 开工" % start.strftime("%H:%M"),
                       "work": "距 %s" % end.strftime("%H:%M"),
                       "off": "已下班"}.get(phase, "")
                p.drawText(QRectF(x, H / 2 - 2, tw, 18),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sub)
            else:
                if phase == "pre":
                    line1 = wx + "%s 开工 · 还没上班呢" % start.strftime("%H:%M")
                elif phase == "work":
                    line1 = "快下班了，冲！" if excited else wx + "距 %s 下班" % end.strftime("%H:%M")
                else:
                    if datetime.now().hour >= 22:
                        line1 = wx + "夜深了，早点休息"
                    else:
                        line1 = wx + "已下班 %d 小时 %02d 分 · 辛苦啦" % (h, m)
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
