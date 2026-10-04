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
    "dim25": False,       # 2.5D 立体效果（投影/倾斜/挤压/耳抖）
    "body": True,         # 半身模式（圆身体 + 前爪 + 状态道具）
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
        fur="#4C4653", fur_d="#3A3542", fur_l="#7E7688", line="#2F2B36",
        ear_in="#C8B8CC", nose="#E88FA0", eye="#FDD45E",
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
        fur="#FFFFFF", fur_d="#F1ECE5", fur_l="#FFFFFF", line="#C4B4A2",
        ear_in="#FFC2CE", nose="#FF9FB0", eye="#4A342C",
        tabby=False, patches=(), ears=(None, None),
    ),
    "蓝猫": dict(
        fur="#AAB5C1", fur_d="#8F9BA9", fur_l="#C7CED7", line="#7D8997",
        ear_in="#DBA9B5", nose="#E89AA8", eye="#4E9E85",
        tabby=True, tabby_c="#93A0AE", patches=(), ears=(None, None),
    ),
    "暹罗猫": dict(
        fur="#F6EDE2", fur_d="#EADFD2", fur_l="#FBF6EE", line="#C9B8A8",
        ear_in="#D8B8AC", nose="#C9808A", eye="#7FB3D5",
        tabby=False, patches=(
            dict(x=-0.16, y=-0.44, w=0.34, h=0.38, c="#5C463A", feather=True),   # 面部重点色
        ), ears=("#5C463A", "#5C463A"),
    ),
    "虎斑猫": dict(
        fur="#C4B09A", fur_d="#A98F76", fur_l="#EFE3D2", line="#8A7258",
        ear_in="#D8A8A0", nose="#E8909C", eye="#3E3226",
        tabby=True, tabby_c="#7A6448", patches=(), ears=(None, None),
    ),
    "熊猫": dict(
        shape="panda",
        fur="#FFFFFF", fur_d="#EFEFEF", fur_l="#FFFFFF", line="#3A3A3A",
        ear_in="#3A3A3A", nose="#3A3A3A", eye="#F5F5F5", pupil="#2A2A2A",
        tabby=False, patches=(
            dict(x=-0.285, y=-0.14, w=0.20, h=0.22, c="#5C5C5C"),  # 左眼圈
            dict(x=0.085, y=-0.14, w=0.20, h=0.22, c="#5C5C5C"),   # 右眼圈
        ), ears=("#5C5C5C", "#5C5C5C"),
    ),
    # ==================== 十二生肖 ====================
    "鼠": dict(
        fur="#9AA3B2", fur_d="#7E8798", fur_l="#C9CFDA", line="#6A7284",
        ear_in="#F5B8C4", nose="#F08CA0", eye="#3A3230",
        tabby=False, patches=(), ears=(None, None), shape="rat",
    ),
    "牛": dict(
        fur="#E8DCC8", fur_d="#D4C4A8", fur_l="#F7F0E2", line="#B5A284",
        ear_in="#E8B8B0", nose="#C9908A", eye="#4A3B30",
        tabby=False, patches=(), ears=(None, None), shape="ox",
    ),
    "虎": dict(
        fur="#E87F3A", fur_d="#D06622", fur_l="#FFF3E2", line="#B55A1F",
        ear_in="#F9C6B0", nose="#E87F6E", eye="#4A342C",
        tabby=True, tabby_c="#7A4A28", patches=(), ears=(None, None), shape="tiger",
    ),
    "兔": dict(
        fur="#F2E3E6", fur_d="#E4CDD2", fur_l="#FFFFFF", line="#D3B7BE",
        ear_in="#F7B8C8", nose="#F28CA0", eye="#5A4440",
        tabby=False, patches=(), ears=(None, None), shape="rabbit",
    ),
    "龙": dict(
        fur="#7FC8B4", fur_d="#5FAE9A", fur_l="#BFE8DC", line="#4E9482",
        ear_in="#A8E0CE", nose="#E8A090", eye="#2E4A42",
        tabby=False, patches=(), ears=(None, None), shape="dragon",
    ),
    "蛇": dict(
        fur="#8FBF6A", fur_d="#75A855", fur_l="#B8DCA0", line="#648F48",
        ear_in="#B8DCA0", nose="#648F48", eye="#3E5A2E",
        tabby=False, patches=(), ears=(None, None), shape="snake",
    ),
    "马": dict(
        fur="#C9A27E", fur_d="#B08A64", fur_l="#E8D0B8", line="#96714E",
        ear_in="#DDB8A0", nose="#8A6A58", eye="#4A3628", mane="#6A4E38",
        tabby=False, patches=(), ears=(None, None), shape="horse",
    ),
    "羊": dict(
        fur="#FFFDF6", fur_d="#EFE8DA", fur_l="#FFFFFF", line="#CFC4B2",
        ear_in="#E8C8C0", nose="#C9908A", eye="#5A4A40", wool="#EFEDE4",
        tabby=False, patches=(), ears=(None, None), shape="sheep",
    ),
    "猴": dict(
        fur="#B08968", fur_d="#96714E", fur_l="#EED3B0", line="#7A5A3E",
        ear_in="#EED3B0", nose="#8A5A44", eye="#3E2E22",
        tabby=False, patches=(), ears=(None, None), shape="monkey",
    ),
    "鸡": dict(
        fur="#FFF4DC", fur_d="#F2E2BC", fur_l="#FFFDF4", line="#D8B878",
        ear_in="#F2A33C", nose="#F2A33C", eye="#4A3628", comb="#D66A6A",
        tabby=False, patches=(), ears=(None, None), shape="rooster",
    ),
    "狗": dict(
        fur="#E8C48F", fur_d="#D0A874", fur_l="#F5E3C8", line="#B08A5A",
        ear_in="#E8B8A8", nose="#4A3630", eye="#4A3628",
        tabby=False, patches=(), ears=(None, None), shape="dog",
    ),
    "猪": dict(
        fur="#F5C8D0", fur_d="#E8A8B4", fur_l="#FCE4E8", line="#D68E9C",
        ear_in="#F2B0BC", nose="#E87F92", eye="#5A3A40",
        tabby=False, patches=(), ears=(None, None), shape="pig",
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


def _q_luma(c):
    """颜色亮度 0-1（用于判断深/浅毛色，做自适应描边）"""
    col = QColor(c)
    return (0.299 * col.red() + 0.587 * col.green() + 0.114 * col.blue()) / 255.0


def _mix(c1, c2, f):
    """两色按比例混合，返回 QColor"""
    a, b = QColor(c1), QColor(c2)
    return QColor(int(a.red() + (b.red() - a.red()) * f),
                  int(a.green() + (b.green() - a.green()) * f),
                  int(a.blue() + (b.blue() - a.blue()) * f))


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
    base_col = _mix(colors["fur_l"], "#FFFFFF", 0.06)
    pad_col = colors.get("nose") or colors.get("ear_in") or "#E8A3A3"
    detail = 0 if s < 120 else (1 if s < 200 else 2)

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
            p.setPen(QPen(_mix(hc, "#000000", 0.30), max(1.0, s * 0.012),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
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
            p.setPen(QPen(_mix(pc, "#6B4A33", 0.45), max(1.0, s * 0.013),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
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
            p.setPen(QPen(QColor(wc), max(1.0, s * 0.012),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
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
            p.setPen(QPen(outline.color(), max(1.2, s * 0.015),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
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
    """头顶帽子：cap（棒球帽）/ beanie（毛线帽）。这种 Q 版风格不画头发。"""
    if style == "none":
        return
    top = head_top
    line_c = outline.color()
    if style == "cap":
        # 帽身：圆顶盖在头顶上半，颜色明快
        cap_c = "#E8734A"
        dome = QPainterPath()
        dome.moveTo(cx - 0.40 * s, top + 0.16 * s)
        dome.cubicTo(cx - 0.42 * s, top - 0.06 * s,
                     cx + 0.42 * s, top - 0.06 * s,
                     cx + 0.40 * s, top + 0.16 * s)
        dome.quadTo(cx, top + 0.26 * s, cx - 0.40 * s, top + 0.16 * s)
        dome.closeSubpath()
        p.setPen(outline)
        p.setBrush(QColor(cap_c))
        p.drawPath(dome)
        # 帽檐：向右前方挑出
        brim = QPainterPath()
        brim.moveTo(cx + 0.02 * s, top + 0.13 * s)
        brim.quadTo(cx + 0.36 * s, top + 0.06 * s, cx + 0.52 * s, top + 0.16 * s)
        brim.quadTo(cx + 0.36 * s, top + 0.22 * s, cx + 0.02 * s, top + 0.21 * s)
        brim.closeSubpath()
        p.setBrush(QColor(_mix(cap_c, "#000000", 0.18)))
        p.drawPath(brim)
        # 顶部小圆纽
        p.setBrush(QColor(cap_c))
        p.drawEllipse(QRectF(cx - 0.045 * s, top - 0.075 * s, 0.09 * s, 0.075 * s))
    elif style == "beanie":
        # 毛线帽：圆顶 + 翻边 + 绒球
        bean_c = "#7FA8D9" if colors.get("shape") != "rat" else "#B48ACB"
        dome = QPainterPath()
        dome.moveTo(cx - 0.40 * s, top + 0.14 * s)
        dome.cubicTo(cx - 0.42 * s, top - 0.12 * s,
                     cx + 0.42 * s, top - 0.12 * s,
                     cx + 0.40 * s, top + 0.14 * s)
        dome.closeSubpath()
        p.setPen(outline)
        p.setBrush(QColor(bean_c))
        p.drawPath(dome)
        # 翻边（横向罗纹带）
        p.setBrush(QColor(_mix(bean_c, "#FFFFFF", 0.25)))
        p.drawRoundedRect(QRectF(cx - 0.41 * s, top + 0.07 * s,
                                 0.82 * s, 0.13 * s), 0.05 * s, 0.05 * s)
        # 绒球
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(cx - 0.085 * s, top - 0.23 * s, 0.17 * s, 0.15 * s))



def _draw_prop(p, prop, cx, cy, s, colors, side=None, wx=None, wy=None):
    """画半身状态道具。双手道具用 cx,cy；单手道具用 wx,wy 并参考 side('L'/'R')。"""
    line_c = colors.get("line", "#4A3B33")
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
        p.setPen(QPen(QColor("#D4CFC7"), max(1.5, s * 0.018),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(bx + bw - s * 0.03, by + s * 0.04,
                         s * 0.10, s * 0.14), 0, 180 * 16)
        # 热气
        steam = QColor("#FFFFFF")
        steam.setAlpha(120)
        p.setPen(QPen(steam, max(1.0, s * 0.012),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for dx in (-s * 0.06, 0, s * 0.06):
            p.drawArc(QRectF(cx + dx - s * 0.03, by - s * 0.14,
                             s * 0.06, s * 0.10), 0, 180 * 16)
    elif prop == "coin":
        r = s * 0.14
        x, y = cx, cy + s * 0.76
        p.setPen(QPen(QColor("#B8860B"), max(1.2, s * 0.014)))
        p.setBrush(QColor("#FFD700"))
        p.drawEllipse(QRectF(x - r, y - r, r * 2, r * 2))
        p.setBrush(QColor("#F4C430"))
        p.drawEllipse(QRectF(x - r * 0.78, y - r * 0.78,
                             r * 1.56, r * 1.56))
        p.setPen(QPen(QColor("#B8860B"), max(1.0, s * 0.012)))
        p.setFont(QFont("Segoe UI", int(s * 0.14), QFont.Weight.Bold))
        p.drawText(QRectF(x - r, y - r, r * 2, r * 2),
                   Qt.AlignmentFlag.AlignCenter, "¥")
    elif prop == "bag":
        if wx is None or wy is None:
            return
        bw, bh = s * 0.22, s * 0.26
        bx = wx - bw * (0.2 if side == "R" else 0.8)
        by = wy + s * 0.06
        bag_c = colors.get("bag", "#C49A6C")
        p.setPen(QPen(QColor(line_c), max(1.0, s * 0.014)))
        p.setBrush(QColor(bag_c))
        body = QPainterPath()
        body.moveTo(bx + bw * 0.15, by)
        body.lineTo(bx + bw * 0.85, by)
        body.lineTo(bx + bw, by + bh)
        body.lineTo(bx, by + bh)
        body.closeSubpath()
        p.drawPath(body)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(line_c), max(1.2, s * 0.016),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(bx + bw * 0.25, by - s * 0.08,
                         bw * 0.50, s * 0.12), 0, 180 * 16)
    elif prop == "fan":
        if wx is None or wy is None:
            return
        fx = wx + (s * 0.08 if side == "R" else -s * 0.08)
        fy = wy - s * 0.12
        r = s * 0.18
        p.setPen(QPen(QColor(line_c), max(1.0, s * 0.014)))
        p.setBrush(QColor("#F8C3CD"))
        # 扇面：半扇形
        start = -150 * 16 if side == "R" else -30 * 16
        span = 120 * 16 if side == "R" else -120 * 16
        p.drawPie(QRectF(fx - r, fy - r * 0.55, r * 2, r * 1.45), start, span)
        # 扇骨
        p.setPen(QPen(_mix(line_c, "#FFFFFF", 0.35), max(0.8, s * 0.010),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        base_angs = (-160, -130, -100) if side == "R" else (-80, -50, -20)
        for ang in base_angs:
            rad = math.radians(ang)
            p.drawLine(QPointF(fx, fy),
                       QPointF(fx + math.cos(rad) * r * 0.9,
                               fy + math.sin(rad) * r * 0.9))
        # 柄
        p.setPen(QPen(QColor(line_c), max(1.5, s * 0.018),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(fx, fy), QPointF(wx, wy))
    elif prop == "umbrella":
        if wx is None or wy is None:
            return
        ux, uy = cx, cy - s * 0.38
        r = s * 0.32
        p.setPen(QPen(QColor(line_c), max(1.0, s * 0.014)))
        p.setBrush(QColor("#F8C3CD"))
        p.drawEllipse(QRectF(ux - r, uy - r * 0.40, r * 2, r * 1.20))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#E89AAA"), max(1.2, s * 0.016),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(ux - r * 0.92, uy + r * 0.12,
                         r * 1.84, r * 0.50), 0, 180 * 16)
        p.setPen(QPen(QColor(line_c), max(1.5, s * 0.018),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
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
             scared=False, look=(0.0, 0.0), mood=None, tail_phase=None, t=0.0,
             dim25=False, pet_k=None, ear_tw=None, body=False, prop=None):
    """画一只可爱的猫脑袋。s 为整体直径；look 为瞳孔偏移(-1..1)；mood 待机动作；tail_phase 摇尾
    dim25=2.5D 模式（投影/倾斜/挤压）；pet_k 摸猫进度 0..1；ear_tw=(方向±1, 进度0..1) 耳抖
    body=半身模式（圆身体+前爪）；prop=手上的道具（coffee/umbrella/fan/scarf/coin/bag）"""
    if colors is None:
        colors = CHARACTERS["橘猫"]
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    cy += math.sin(t) * s * 0.018          # 呼吸浮动
    if mood == "stretch":                  # 伸懒腰：整体放大一点 + 眯眼
        s *= 1.05
        blink = True

    lw = max(1.0, s * 0.016)
    dark = _q_luma(colors["fur"]) < 0.42      # 深毛色：描边向浅色靠拢，避免糊成一团
    line_c = _mix(colors["line"], colors["fur_l"], 0.72) if dark else QColor(colors["line"])
    outline = QPen(line_c, lw)
    outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    outline.setCapStyle(Qt.PenCapStyle.RoundCap)

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
            for i in range(7):
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
            p.setPen(QPen(QColor("#C43C38"), max(1.0, s * 0.020)))
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
            p.setPen(QPen(QColor(colors["wool"] if colors.get("wool") else colors["fur_l"]),
                          max(1.0, s * 0.014), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
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
        if shape in ("snake", "dragon"):
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
        p.setPen(QPen(_mix(colors["mane"], "#000000", 0.25), max(1.0, s * 0.015),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
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
        p.setPen(QPen(QColor(tc), max(2.2, s * 0.038),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
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

    # ---- 顶部受光（体积感）：小而柔的斜上光斑，不是脑门大补丁 ----
    head_clip = QPainterPath()
    head_clip.addEllipse(head_rect)
    p.setClipPath(head_clip)
    g = QRadialGradient(QPointF(cx - 0.12 * s, cy - 0.34 * s), 0.34 * s)
    g.setColorAt(0, _mix(colors["fur_l"], "#FFFFFF", 0.26))
    g.setColorAt(0.6, _mix(colors["fur_l"], "#FFFFFF", 0.10))
    g.setColorAt(1, QColor(0, 0, 0, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(g)
    p.drawEllipse(QRectF(cx - 0.48 * s, cy - 0.70 * s, 0.72 * s, 0.72 * s))
    p.setClipping(False)

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
    p.setClipPath(head_clip)
    chin = QColor(colors["fur_d"])
    chin.setAlpha(130)
    p.setBrush(chin)
    p.drawEllipse(QRectF(cx - 0.32 * s, cy + 0.24 * s, 0.64 * s, 0.30 * s))
    p.setClipping(False)

    # ---- 腮红 ----
    p.setBrush(QColor(255, 150, 170, 105))
    for sign in (-1, 1):
        p.drawEllipse(QRectF(cx + sign * 0.30 * s - 0.085 * s, cy + 0.04 * s, 0.17 * s, 0.105 * s))

    # ---- 头顶帽子（物种差异化；这种 Q 版风格不画头发） ----
    _draw_hat(p, cx, cy, s, colors, outline, _HAT.get(shape, "none"),
              head_top, hw, t)

    # ---- 胡须（猫/鼠/兔/虎/龙；深毛色用浅须，浅毛色用经典橘须） ----
    if shape in ("cat", "rat", "rabbit", "tiger", "dragon"):
        hp = QPen(QColor("#CFC9DC") if dark else QColor("#E0AC76"), max(1.0, s * 0.012))
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
            p.setPen(QPen(QColor("#E8930C"), max(1.0, s * 0.014)))
            p.setBrush(QColor("#FFD34D"))
            p.drawPath(star)
        elif blink or sleepy:
            p.setPen(QPen(QColor(colors["eye"]), max(1.6, s * 0.030), Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
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
            p.setPen(QPen(_mix(colors["eye"], "#14100E", 0.55), max(1.0, s * 0.012)))
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
                p.drawEllipse(QRectF(ex - ew2 * 0.70 + lx, eye_y + ehh * 0.10 + ly,
                                     ew2 * 0.35, ehh * 0.13))

    # ---- 鼻子 & 嘴（按物种分形状；打哈欠统一 O 形嘴） ----
    mouth_pen = QPen(line_c, max(1.3, s * 0.022), Qt.PenStyle.SolidLine,
                     Qt.PenCapStyle.RoundCap)
    if mood == "yawn":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#7A4A3A"))
        p.drawEllipse(QRectF(cx - s * 0.040, cy + 0.125 * s, s * 0.080, s * 0.095))
        p.setPen(Qt.PenStyle.NoPen)      # 打哈欠的泪珠
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
        p.setPen(QPen(QColor("#D86A7A"), max(1.0, s * 0.012)))
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
        p.setPen(QPen(line_c, max(1.2, s * 0.020)))
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
        p.setPen(QPen(line_c, max(1.0, s * 0.014)))
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
            p.setPen(QPen(QColor("#E85A6A"), max(1.2, s * 0.016),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
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


# 各物种"头顶以上"的延伸系数（耳朵/角/鸡冠/帽子），半身模式用来自动定尺寸防出界
_TOP_EXT = {"rabbit": 0.86, "ox": 0.76, "dragon": 0.78,
           "sheep": 0.72, "rooster": 0.64, "horse": 0.84,
           "monkey": 0.80, "dog": 0.72, "rat": 0.80}

# 各物种身体形态（默认 round = 圆润标准）
_BODY_SHAPE = {"horse": "long", "snake": "long", "ox": "wide", "pig": "wide",
               "dog": "slim", "monkey": "slim"}

# 各物种头型：(宽, 高, 中心纵向偏移)，默认 (0.88, 0.86, 0)
# 马/蛇修长，牛/猪/虎宽扁，鼠/兔小巧，猴心形略高
_HEAD = {
    "horse":  (0.80, 0.98, -0.03),
    "snake":  (0.78, 0.88, 0.00),
    "ox":     (0.94, 0.84, 0.02),
    "pig":    (0.92, 0.82, 0.02),
    "tiger":  (0.94, 0.84, 0.00),
    "rat":    (0.82, 0.84, 0.01),
    "rabbit": (0.86, 0.88, 0.00),
    "monkey": (0.86, 0.90, -0.01),
    "dog":    (0.88, 0.86, 0.00),
    "dragon": (0.86, 0.88, 0.00),
    "panda":  (0.88, 0.86, 0.00),
}

# 各物种帽子（这种 Q 版风格不画头发，改用可爱小帽做差异化）
_HAT = {
    "dog": "cap", "monkey": "beanie", "rat": "beanie",
}

# 各物种眼睛形态：(纵向偏移, 半宽, 全高, 是否竖瞳)
# 牛/马 → 小横椭圆、位置偏高；猪/猴 → 大而圆（猴位置偏低）；
# 龙/蛇 → 细长竖瞳；鸡 → 小而锐利；虎 → 横置带凶感
_EYE = {
    "ox":     (-0.055, 0.060, 0.125, False),
    "horse":  (-0.055, 0.062, 0.130, False),
    "tiger":  (-0.010, 0.082, 0.150, False),
    "pig":    (0.015,  0.078, 0.215, False),
    "monkey": (0.030,  0.076, 0.210, False),
    "dragon": (-0.010, 0.070, 0.145, True),
    "snake":  (0.000,  0.066, 0.120, True),
    "rooster": (-0.020, 0.055, 0.140, False),
}
_EYE_DEFAULT = (0.0, 0.068, 0.190, False)

# 各物种的尾巴样式（默认 cat = 细长弯钩猫尾）
_TAIL = {"rabbit": "puff", "sheep": "puff", "dog": "curl_up", "pig": "curl",
         "horse": "brush", "ox": "brush", "dragon": "fin", "snake": "coil",
         "rooster": "feather", "rat": "whip", "monkey": "long"}

# 各物种的手型（默认 paw = 猫爪；snake 无手，连手臂一起省略）
_HAND = {"rat": "fingers", "ox": "hoof", "tiger": "paw", "rabbit": "puff_paw",
         "dragon": "claw", "snake": "none", "horse": "hoof", "sheep": "hoof",
         "monkey": "monkey", "rooster": "wing", "dog": "dog_paw", "pig": "cloven"}

# 状态 → 手上的道具
PROP_BY_WEATHER = {"rain": "umbrella", "thunder": "umbrella", "snow": "scarf"}


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
        self.act_25d = QAction("2.5D 立体效果", self, checkable=True)
        self.act_25d.setChecked(bool(self.cfg.get("dim25", False)))
        self.act_25d.triggered.connect(lambda on: self.toggle_cfg("dim25", on))
        self.act_body = QAction("半身小猫（身体+道具）", self, checkable=True)
        self.act_body.setChecked(bool(self.cfg.get("body", True)))
        self.act_body.triggered.connect(lambda on: self.toggle_cfg("body", on))

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
        self.menu.addAction(self.act_25d)
        self.menu.addAction(self.act_body)
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
        # 摇尾：平时慢摆，摸猫时快摆
        tail_phase = (self.t0 * (7.0 if meowing else 1.8)) + (2.0 if meowing else 0.0)
        dim25 = bool(self.cfg.get("dim25", False))
        ear_tw = None
        if dim25 and self.ear_tw:
            ear_tw = (self.ear_tw[0], (self.t0 - self.ear_tw[1]) / 0.6)
        # 半身模式：按状态决定手上的道具
        body = bool(self.cfg.get("body", True))
        prop = self._prop_now()
        draw_cat(p, ccx + shake, ccy, cs, self.char_colors(),
                 blink=self.blink_t < 0.18 or meowing, excited=excited, sleepy=sleepy,
                 scared=thunder or too_hot, look=look, mood=mood,
                 tail_phase=tail_phase, t=self.t0, dim25=dim25,
                 pet_k=self.meow_t if self.meow_t < 1.0 else None, ear_tw=ear_tw,
                 body=body, prop=prop)

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
