# -*- coding: utf-8 -*-
"""上下文感知：前台应用 / 全屏 / 忙碌度 / 电量 / CPU / 锁屏。

所有 Win32 调用都做了节流与异常兜底，采样失败一律返回保守值，
绝不让主界面因为感知模块崩掉。

对外只有一个入口 sample()，返回 dict：
    app        : 前台进程名（小写，无 .exe）
    title      : 窗口标题
    scene      : meeting/code/sheet/doc/deck/browser/chat/design/video/game/other
    fullscreen : 是否全屏（会议投屏、视频全屏等）
    busy       : 0..1 忙碌度（近 60s 有输入的比例）
    cpu        : 0..100 CPU 总占用
    battery    : 0..100 电量（255 = 无电池）
    ac         : 是否插电
    locked     : 是否锁屏
"""
import ctypes
import os
import time
from ctypes import wintypes

_u = None
_k = None
try:
    _u = ctypes.windll.user32
    _k = ctypes.windll.kernel32
except Exception:
    pass

# ----------------------------------------------------------------------
# 场景分类：进程名关键词 → 场景
# ----------------------------------------------------------------------
APP_RULES = (
    # 会议 / 远程协作（最优先：在开会时不该被打扰）
    (("ms-teams", "teams", "zoom", "tencentmeeting", "wemeetapp", "welink",
      "dingtalk", "lark", "feishu", "anydesk", "todesk", "sunloginclient"), "meeting"),
    # 写代码
    (("code.exe", "devenv", "idea64", "pycharm64", "webstorm64", "goland64",
      "rider64", "clion64", "cursor", "notepad++", "sublime_text", "gvim",
      "windowsterminal", "powershell", "cmd.exe", "wt.exe", "hyper"), "code"),
    # 表格 / 文档 / 演示
    (("excel", "et.exe", "wps.exe", "libreoffice"), "sheet"),
    (("winword", "notepad", "obsidian", "typora"), "doc"),
    (("powerpnt", "wpp.exe"), "deck"),
    # 浏览器
    (("chrome", "msedge", "firefox", "360se", "360chrome", "iexplore",
      "opera", "brave", "sogouexplorer"), "browser"),
    # 聊天
    (("wechat", "weixin", "wxwork", "qq.exe", "telegram", "discord",
      "slack", "skype"), "chat"),
    # 设计 / 剪辑
    (("photoshop", "illustrator", "figma", "sketch", "canva", "blender",
      "premiere", "afterfx", "davinci"), "design"),
    (("obs64", "obs32", "potplayer", "vlc", "kwailive", "douyin",
      "bilibili", "iqiyi", "youku"), "video"),
    # 游戏
    (("steam", "valorant", "league of legends", "epicgames", "origin",
      "battle.net", "bg3", "bg3_dx11", "cyberpunk2077"), "game"),
)

# 标题关键词 → 场景（比进程名更准，优先匹配）
TITLE_RULES = (
    (("腾讯会议", "视频会议", "正在会议", "会议中", "zoom meeting",
      "microsoft teams", "共享屏幕", "screen share"), "meeting"),
    ((".xls", "xlsx", "excel", "表格", "sheet"), "sheet"),
    ((".doc", "docx", "word", "文档"), "doc"),
    ((".ppt", "pptx", "幻灯片", "powerpoint"), "deck"),
    (("stack overflow", "github", "gitlab", "jira", "vscode", "terminal"), "code"),
)

SCENE_LABEL = {
    "meeting": "在开会",
    "code": "在写代码",
    "sheet": "在做表格",
    "doc": "在写文档",
    "deck": "在做 PPT",
    "browser": "在冲浪",
    "chat": "在聊天",
    "design": "在做设计",
    "video": "在看视频",
    "game": "在摸鱼打游戏",
    "other": None,
}

# ----------------------------------------------------------------------
# 采样状态
# ----------------------------------------------------------------------
_state = {
    "t": 0.0,          # 上次采样时间
    "data": {},        # 上次结果
    "last_input": 0,   # 上次 GetLastInputInfo 的 dwTime
    "hits": 0,         # 近窗口期内的"有输入"次数
    "samples": 0,      # 近窗口期内的采样次数
    "win_t": [],       # (时间戳, 是否活跃)
    "prev_sys": None,  # 上次 GetSystemTimes (idle, kernel, user)
    "cpu": 0.0,
}

SAMPLE_INTERVAL = 1.5      # 前台/电量/CPU 采样间隔（秒）
BUSY_WINDOW = 60.0         # 忙碌度统计窗口（秒）


# ----------------------------------------------------------------------
# Win32 原语
# ----------------------------------------------------------------------
def _foreground():
    """返回 (进程名, 窗口标题, hwnd)"""
    if not _u:
        return "", "", 0
    try:
        hwnd = _u.GetForegroundWindow()
        if not hwnd:
            return "", "", 0
        n = _u.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(max(1, n) + 1)
        _u.GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value or ""
        pid = wintypes.DWORD()
        _u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return _exe_of(pid.value), title, hwnd
    except Exception:
        return "", "", 0


def _exe_of(pid):
    try:
        h = _k.OpenProcess(0x1000, False, pid)      # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if _k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return os.path.splitext(os.path.basename(buf.value))[0].lower()
        finally:
            _k.CloseHandle(h)
    except Exception:
        pass
    return ""


def _is_fullscreen(hwnd):
    """前台窗口铺满整个主屏视为全屏（会议共享、视频全屏、游戏）"""
    if not _u or not hwnd:
        return False
    try:
        r = wintypes.RECT()
        if not _u.GetWindowRect(hwnd, ctypes.byref(r)):
            return False
        sw = _u.GetSystemMetrics(0)
        sh = _u.GetSystemMetrics(1)
        return (r.right - r.left) >= sw - 2 and (r.bottom - r.top) >= sh - 2
    except Exception:
        return False


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]


def _input_tick():
    """返回本次采样期间是否有键鼠输入"""
    if not _u:
        return False
    try:
        li = _LASTINPUTINFO()
        li.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not _u.GetLastInputInfo(ctypes.byref(li)):
            return False
        prev = _state["last_input"]
        _state["last_input"] = li.dwTime
        return prev != 0 and li.dwTime != prev
    except Exception:
        return False


def _cpu_percent():
    """系统总 CPU 占用（与上次采样的差值）"""
    if not _k:
        return 0.0
    try:
        idle, kernel, user = (ctypes.c_ulonglong() for _ in range(3))
        if not _k.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel),
                                 ctypes.byref(user)):
            return _state["cpu"]
        cur = (idle.value, kernel.value, user.value)
        prev = _state["prev_sys"]
        _state["prev_sys"] = cur
        if not prev:
            return _state["cpu"]
        d_idle = cur[0] - prev[0]
        d_total = (cur[1] - prev[1]) + (cur[2] - prev[2])
        if d_total <= 0:
            return _state["cpu"]
        v = 100.0 * (1.0 - d_idle / float(d_total))
        # 平滑，避免抖动
        _state["cpu"] = _state["cpu"] * 0.5 + v * 0.5
        return _state["cpu"]
    except Exception:
        return _state["cpu"]


class _POWER_STATUS(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_byte),
                ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte),
                ("Reserved1", ctypes.c_byte),
                ("BatteryLifeTime", wintypes.DWORD),
                ("BatteryFullLifeTime", wintypes.DWORD)]


def _power():
    """返回 (电量百分比, 是否插电)；无电池时电量为 255"""
    if not _k:
        return 255, True
    try:
        ps = _POWER_STATUS()
        if not _k.GetSystemPowerStatus(ctypes.byref(ps)):
            return 255, True
        pct = int(ps.BatteryLifePercent)
        if pct > 100:          # 127/255 表示未知
            pct = 255
        return pct, ps.ACLineStatus == 1
    except Exception:
        return 255, True


def _is_locked(exe, title):
    if exe in ("lockapp", "logonui") or "lockapp" in exe:
        return True
    return False


# ----------------------------------------------------------------------
# 分类
# ----------------------------------------------------------------------
def classify(exe, title):
    t = (title or "").lower()
    for keys, scene in TITLE_RULES:
        for k in keys:
            if k in t:
                return scene
    e = (exe or "").lower()
    for keys, scene in APP_RULES:
        for k in keys:
            if e == k or e.startswith(k) or k in e:
                return scene
    return "other"


def _busy(active):
    """维护 60s 滑动窗口，返回活跃比例 0..1"""
    now = time.time()
    w = _state["win_t"]
    w.append((now, active))
    while w and now - w[0][0] > BUSY_WINDOW:
        w.pop(0)
    if not w:
        return 0.0
    # 时间加权：越近的采样权重越高
    tot = 0.0
    hit = 0.0
    for ts, a in w:
        wt = 1.0 - 0.7 * ((now - ts) / BUSY_WINDOW)
        tot += wt
        if a:
            hit += wt
    return hit / tot if tot > 0 else 0.0


# ----------------------------------------------------------------------
# 对外入口
# ----------------------------------------------------------------------
_EMPTY = {"app": "", "title": "", "scene": "other", "fullscreen": False,
          "busy": 0.0, "cpu": 0.0, "battery": 255, "ac": True, "locked": False}


def sample(force=False):
    """采样一次（内部节流 1.5s，返回上一次的结果）。"""
    now = time.time()
    if not force and now - _state["t"] < SAMPLE_INTERVAL and _state["data"]:
        return _state["data"]
    _state["t"] = now

    active = _input_tick()
    busy = _busy(active)
    exe, title, hwnd = _foreground()
    scene = classify(exe, title)
    data = {
        "app": exe,
        "title": title,
        "scene": scene,
        "fullscreen": _is_fullscreen(hwnd),
        "busy": busy,
        "cpu": round(_cpu_percent(), 1),
        "locked": _is_locked(exe, title),
    }
    pct, ac = _power()
    data["battery"] = pct
    data["ac"] = ac
    _state["data"] = data
    return data


def scene_label(scene):
    return SCENE_LABEL.get(scene)
