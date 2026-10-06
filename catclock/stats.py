# -*- coding: utf-8 -*-
"""工作时长统计：按日累计在岗 / 加班时长。

数据文件：%APPDATA%/CatClock/work_stats.json
结构：{"2026-10-05": {"work": 28800, "over": 1800}, ...}
"""
import csv
import json
import os
from datetime import datetime, timedelta

from .util import CONFIG_DIR

STATS_PATH = os.path.join(CONFIG_DIR, "work_stats.json")


def _load():
    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(d):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(STATS_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def add(day, work_sec=0, over_sec=0):
    """累加某天的在岗/加班秒数。"""
    if work_sec <= 0 and over_sec <= 0:
        return
    d = _load()
    rec = d.get(day) or {"work": 0, "over": 0}
    rec["work"] = int(rec.get("work", 0)) + int(work_sec)
    rec["over"] = int(rec.get("over", 0)) + int(over_sec)
    d[day] = rec
    _save(d)


def mark_off(day, hhmm):
    """记录某天真正下班的时刻（HH:MM），用于周报算平均下班时间。"""
    d = _load()
    rec = d.get(day) or {"work": 0, "over": 0}
    rec["off"] = hhmm
    d[day] = rec
    _save(d)


def _minute(hhmm):
    try:
        h, m = str(hhmm).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def off_marks(days=None):
    """返回 {日期: "HH:MM"}，只含有下班时刻记录的日子。"""
    d = _load()
    out = {}
    for day, rec in d.items():
        if not isinstance(rec, dict):
            continue
        v = rec.get("off")
        if v and (days is None or day in days):
            out[day] = v
    return out


def all_days():
    return sorted(_load().keys())


def _fmt(sec):
    sec = int(sec or 0)
    h, m = divmod(sec // 60, 60)
    return "%dh%02dm" % (h, m)


def summary(now=None):
    """返回 (今日, 本周, 本月) 的 (在岗秒, 加班秒)。"""
    now = now or datetime.now()
    d = _load()
    today = now.strftime("%Y-%m-%d")
    wk_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    mon_prefix = now.strftime("%Y-%m")
    tw = to = ww = wo = mw = mo = 0
    for day, rec in d.items():
        if not isinstance(rec, dict):
            continue
        w, o = int(rec.get("work", 0)), int(rec.get("over", 0))
        if day == today:
            tw += w
            to += o
        if day >= wk_start:
            ww += w
            wo += o
        if day.startswith(mon_prefix):
            mw += w
            mo += o
    return {"today": (tw, to), "week": (ww, wo), "month": (mw, mo)}


def report_text(now=None):
    s = summary(now)
    lines = ["今日在岗 %s（加班 %s）" % (_fmt(s["today"][0]), _fmt(s["today"][1])),
             "本周在岗 %s（加班 %s）" % (_fmt(s["week"][0]), _fmt(s["week"][1])),
             "本月在岗 %s（加班 %s）" % (_fmt(s["month"][0]), _fmt(s["month"][1]))]
    return "\n".join(lines)


def export_csv(path):
    """导出逐日明细 CSV。返回写入行数。"""
    d = _load()
    rows = sorted(d.items())
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["日期", "在岗时长", "加班时长"])
        for day, rec in rows:
            if not isinstance(rec, dict):
                continue
            w.writerow([day, _fmt(rec.get("work", 0)), _fmt(rec.get("over", 0))])
    return len(rows)
