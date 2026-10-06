# -*- coding: utf-8 -*-
"""配置读写、开机自启、单实例、字体与颜色工具。"""
import json
import os
import sys
from datetime import datetime

try:
    import winreg
except Exception:
    winreg = None

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QFont, QPainterPath
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from . import data as _data

CHARACTERS = _data.CHARACTERS
STYLES = _data.STYLES
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
    "hat": "auto",        # 帽子：auto/none/cap/beanie/beret/straw/party/crown/santa/cny
    "acc": "auto",        # 配饰：auto/none/glasses/sunglasses/headphones/bowtie
    "check_update": True, # 启动时静默检查 GitHub Release
    "count_over": True,   # 工作统计是否把下班后的时间计入加班
    "context_aware": True,  # 情境感知（应用/会议/忙碌度/电量）
    "edge_dock": True,      # 拖到屏幕边缘自动吸附（悬停时滑出）
    "surprise": True,       # 随机小惊喜（打喷嚏/追尾巴/掉金币）
    "boss_key": True,       # 老板键 Ctrl+Alt+H 一键隐身
    "mood_daily": True,     # 每天工作时段提醒一次心情打卡
}

# ======================================================================
# 打工人语录（按时段轮换）
# ======================================================================


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