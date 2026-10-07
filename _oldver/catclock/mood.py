# -*- coding: utf-8 -*-
"""心情打卡 + 情绪曲线。

数据文件：%APPDATA%/CatClock/mood.json
结构：{"2026-10-06": {"score": 1, "ts": "10:24"}, ...}

score: 0=累  1=还行  2=开心
"""
import json
import os
from datetime import datetime, timedelta

from .util import CONFIG_DIR

MOOD_PATH = os.path.join(CONFIG_DIR, "mood.json")
SCORE_TEXT = {0: "累", 1: "还行", 2: "开心"}
SCORE_FACE = {0: "(´；ω；｀)", 1: "(・_・)", 2: "(≧▽≦)"}
WEEKDAY_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

REPLY = {
    0: ("辛苦了，先喝口水，猫给你揉揉", "累了就靠一会儿，猫在",
        "今天先放过自己，明天再战", "抱抱，猫把尾巴借你握着"),
    1: ("平平淡淡也是福，猫陪你", "还行就好，稳住",
        "这种状态刚刚好，继续", "猫也今天一般般，一起摸鱼"),
    2: ("开心会传染的，猫也笑了", "好状态！趁热把事办了",
        "看你开心猫也开心", "今天一定是有什么好事"),
}


def _load():
    try:
        with open(MOOD_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(d):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(MOOD_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def set_today(score, now=None):
    """记录今天的心情；同一天覆盖。"""
    now = now or datetime.now()
    d = _load()
    d[now.strftime("%Y-%m-%d")] = {
        "score": int(score),
        "ts": now.strftime("%H:%M"),
    }
    _save(d)
    return reply_for(int(score), now)


def today(now=None):
    now = now or datetime.now()
    r = _load().get(now.strftime("%Y-%m-%d"))
    return r.get("score") if isinstance(r, dict) else None


def reply_for(score, now=None):
    """打卡后猫的回应（按时段微调）"""
    import random
    now = now or datetime.now()
    pool = list(REPLY.get(int(score), REPLY[1]))
    if now.hour >= 20:
        pool.append("这么晚了，打完卡就回家吧")
    return random.choice(pool)


def week(now=None):
    """本周（周一起）每天的心情：[{"day","wd","score"}...]，未打卡 score=None"""
    now = now or datetime.now()
    d = _load()
    mon = now - timedelta(days=now.weekday())
    out = []
    for i in range(7):
        day = (mon + timedelta(days=i)).strftime("%Y-%m-%d")
        r = d.get(day)
        out.append({
            "day": day,
            "wd": WEEKDAY_CN[i],
            "score": r.get("score") if isinstance(r, dict) else None,
        })
    return out


def recent(days=14, now=None):
    now = now or datetime.now()
    d = _load()
    out = []
    for i in range(days - 1, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        r = d.get(day)
        out.append((day, r.get("score") if isinstance(r, dict) else None))
    return out


def curve_text(days=14, now=None):
    """用字符画出近 N 天情绪曲线"""
    rows = recent(days, now)
    bar = "▁▂▃▄▅▆▇"
    s = ""
    for _, sc in rows:
        s += "·" if sc is None else bar[max(0, min(2, int(sc))) * 3]
    return s


def insight(now=None):
    """近 30 天洞察：哪天最累 / 开心率 / 连续记录"""
    now = now or datetime.now()
    d = _load()
    from collections import defaultdict
    by_wd = defaultdict(list)
    cnt = {0: 0, 1: 0, 2: 0}
    for i in range(30):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        r = d.get(day)
        if not isinstance(r, dict):
            continue
        sc = r.get("score")
        if sc is None:
            continue
        cnt[int(sc)] += 1
        try:
            wd = datetime.strptime(day, "%Y-%m-%d").weekday()
            by_wd[wd].append(int(sc))
        except Exception:
            pass
    total = sum(cnt.values())
    if total < 3:
        return "打卡还不够多，再多几天猫就能看出规律啦"
    parts = []
    avg = {k: sum(v) / len(v) for k, v in by_wd.items() if len(v) >= 2}
    if avg:
        worst = min(avg, key=lambda k: avg[k])
        best = max(avg, key=lambda k: avg[k])
        if avg[worst] < 1.2:
            parts.append("%s你最容易累" % WEEKDAY_CN[worst])
        if avg[best] > 1.6 and best != worst:
            parts.append("%s心情最好" % WEEKDAY_CN[best])
    happy = cnt[2] / float(total)
    if happy >= 0.5:
        parts.append("最近有一半以上的日子是开心的")
    elif cnt[0] / float(total) >= 0.4:
        parts.append("最近累的日子有点多，注意休息")
    return "；".join(parts) if parts else "情绪还挺稳的，继续保持"


def export_csv(path):
    import csv
    d = _load()
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["日期", "心情", "时间"])
        for day in sorted(d):
            r = d[day]
            if not isinstance(r, dict):
                continue
            w.writerow([day, SCORE_TEXT.get(r.get("score"), ""), r.get("ts", "")])
    return len(d)
