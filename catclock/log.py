# -*- coding: utf-8 -*-
"""A3：轻量日志。

设计原则（和 update.py 一样）：**任何异常都不能影响挂件本身**。
日志写不进去、磁盘满、目录没权限 —— 全部静默吞掉。

日志位置：%APPDATA%\\CatClock\\catclock.log
- 单文件滚动：超过 _MAX_BYTES 就把旧的改名成 catclock.log.1，只留一份备份
- 默认只记录 WARNING 及以上 + 关键生命周期事件；DEBUG 需要设置环境变量 CATCLOCK_DEBUG=1
"""
import os
import sys
import time
import threading

from .util import CONFIG_DIR

_LOCK = threading.Lock()
_PATH = os.path.join(CONFIG_DIR, "catclock.log")
_MAX_BYTES = 512 * 1024          # 超过 512K 滚动一次
_KEEP = 1                        # 只保留一份 .1 备份
_ENABLED = True

# 启动就置位：让各模块可以无成本地判断「要不要拼字符串」
DEBUG = os.environ.get("CATCLOCK_DEBUG", "") == "1"


def _roll_if_needed():
    """超过阈值就把当前日志滚成 .1（只留一份）。失败一律忽略。"""
    try:
        if not os.path.exists(_PATH) or os.path.getsize(_PATH) < _MAX_BYTES:
            return
        old = _PATH + ".1"
        if os.path.exists(old):
            os.remove(old)
        os.rename(_PATH, old)
    except Exception:
        pass


def _write(level, msg):
    global _ENABLED
    if not _ENABLED:
        return
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with _LOCK:
            _roll_if_needed()
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(_PATH, "a", encoding="utf-8", errors="replace") as f:
                f.write("%s [%s] %s\n" % (ts, level, msg))
    except Exception:
        # 日志本身不能成为崩溃源：写一次失败就永久关掉，避免每帧都重试
        _ENABLED = False


def debug(msg):
    if DEBUG:
        _write("DEBUG", msg)


def info(msg):
    _write("INFO", msg)


def warn(msg):
    _write("WARN", msg)


def error(msg):
    _write("ERROR", msg)


def exception(where, exc=None):
    """记录异常（含 traceback）。`where` 用于定位，例如 "paintEvent"。"""
    import traceback
    if exc is None:
        txt = traceback.format_exc()
    else:
        txt = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    _write("ERROR", "%s: %s\n%s" % (where, exc, txt))


def startup(version):
    """进程启动写一行，方便回溯「哪次运行出的错」。"""
    try:
        _write("INFO", "---- CatClock %s start (py=%s, frozen=%s) ----" % (
            version, sys.version.split()[0], bool(getattr(sys, "frozen", False))))
    except Exception:
        pass


def tail(n=60):
    """返回最后 n 行日志（设置窗口 / 排障用）。"""
    try:
        with open(_PATH, "r", encoding="utf-8", errors="replace") as f:
            return f.readlines()[-n:]
    except Exception:
        return []


def open_log():
    """用系统默认程序打开日志文件。失败静默。"""
    try:
        os.startfile(_PATH)  # noqa: S606 - 仅 Windows
        return True
    except Exception:
        return False
