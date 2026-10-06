# -*- coding: utf-8 -*-
"""周报 + 成就徽章（基于 stats 的逐日数据）。"""
import os
from datetime import datetime, timedelta

from . import stats
from . import mood as M

WEEKDAY_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def _hhmm(mins):
    mins = int(mins)
    return "%02d:%02d" % (mins // 60 % 24, mins % 60)


def _week_days(now):
    mon = now - timedelta(days=now.weekday())
    return [(mon + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]


def week_report(now=None, plan_end="18:00", rest_days=(5, 6)):
    """本周数据概览。返回 dict，缺数据时字段为 None。"""
    now = now or datetime.now()
    days = _week_days(now)
    d = stats._load()
    offs = stats.off_marks(set(days))
    work = {}
    over = {}
    for day in days:
        rec = d.get(day)
        if isinstance(rec, dict):
            work[day] = int(rec.get("work", 0))
            over[day] = int(rec.get("over", 0))
    res = {"days": days, "work": work, "over": over, "offs": offs}
    res["total_work"] = sum(work.values())
    res["total_over"] = sum(over.values())
    res["days_worked"] = sum(1 for v in work.values() if v > 0)
    # 平均下班时间
    ms = [stats._minute(v) for v in offs.values()]
    ms = [m for m in ms if m is not None]
    res["avg_off"] = _hhmm(sum(ms) / len(ms)) if ms else None
    res["latest_off"] = _hhmm(max(ms)) if ms else None
    res["earliest_off"] = _hhmm(min(ms)) if ms else None
    # 最拼的一天（在岗最长）
    if work:
        best_day = max(work, key=lambda k: work[k])
        res["hardest"] = (best_day, work[best_day])
    else:
        res["hardest"] = None
    # 与计划下班时间比较
    pe = stats._minute(plan_end)
    res["plan_end"] = plan_end
    if pe is not None and ms:
        res["late_avg"] = int(sum(ms) / len(ms) - pe)
    else:
        res["late_avg"] = None
    return res


def _fmt_hm(sec):
    sec = int(sec or 0)
    h, m = divmod(sec // 60, 60)
    if h:
        return "%d 小时 %d 分" % (h, m)
    return "%d 分钟" % m


def week_text(now=None, plan_end="18:00"):
    r = week_report(now, plan_end)
    lines = ["📅 本周小结（%s ~ %s）" % (r["days"][0][5:], r["days"][-1][5:])]
    if r["days_worked"] == 0:
        lines.append("这周还没有在岗记录，猫等你开工～")
        return "\n".join(lines)
    lines.append("在岗 %s，加班 %s" % (_fmt_hm(r["total_work"]),
                                    _fmt_hm(r["total_over"])))
    if r["avg_off"]:
        lines.append("平均 %s 下班（计划 %s）" % (r["avg_off"], r["plan_end"]))
    if r["late_avg"] is not None:
        if r["late_avg"] <= 0:
            lines.append("平均比计划早 %d 分钟，优秀！" % -r["late_avg"])
        else:
            lines.append("平均比计划晚 %d 分钟" % r["late_avg"])
    if r["hardest"]:
        day, sec = r["hardest"]
        wd = WEEKDAY_CN[datetime.strptime(day, "%Y-%m-%d").weekday()]
        lines.append("最拼的是%s，在岗 %s" % (wd, _fmt_hm(sec)))
    if r["latest_off"] and r["earliest_off"] and r["latest_off"] != r["earliest_off"]:
        lines.append("最早 %s 走，最晚 %s 走" % (r["earliest_off"], r["latest_off"]))
    # 心情
    wk = M.week(now)
    scored = [x for x in wk if x["score"] is not None]
    if scored:
        avg = sum(x["score"] for x in scored) / float(len(scored))
        face = "累" if avg < 0.7 else ("开心" if avg > 1.6 else "还行")
        lines.append("心情平均偏「%s」（打卡 %d 天）" % (face, len(scored)))
        lines.append("曲线：" + M.curve_text(7, now))
        lines.append(M.insight(now))
    return "\n".join(lines)


# ----------------------------------------------------------------------
# 成就徽章
# ----------------------------------------------------------------------
def badges(now=None, plan_end="18:00"):
    """返回 [(名称, 说明, 是否达成), ...]"""
    now = now or datetime.now()
    r = week_report(now, plan_end)
    d = stats._load()
    out = []

    # 1 零加班周
    out.append(("零加班周", "本周加班少于 30 分钟",
                r["total_over"] < 1800 and r["days_worked"] > 0))
    # 2 准时下班
    ok = r["late_avg"] is not None and r["late_avg"] <= 0
    out.append(("准点达人", "本周平均不晚于计划下班时间", bool(ok)))
    # 3 早鸟（有某天早于计划 30 分钟走）
    ms = [stats._minute(v) for v in r["offs"].values()]
    ms = [m for m in ms if m is not None]
    pe = stats._minute(plan_end)
    out.append(("早鸟", "本周有一天提前 30 分钟以上走",
                bool(pe is not None and ms and min(ms) <= pe - 30)))
    # 4 全勤猫：本周工作日都有在岗记录
    rest = set()
    work_days = [day for i, day in enumerate(r["days"]) if i not in rest]
    got = all(int(r["work"].get(day, 0)) > 0 for day in work_days[:5])
    out.append(("全勤猫", "周一到周五都有在岗记录", bool(got)))
    # 5 连续 3 天不加班
    days = stats.all_days()
    streak = 0
    best = 0
    for day in days:
        rec = d.get(day) or {}
        if int(rec.get("over", 0)) < 600 and int(rec.get("work", 0)) > 0:
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    out.append(("克制之猫", "连续 3 天加班少于 10 分钟", best >= 3))
    # 6 百小时陪伴（累计）
    total = sum(int((v or {}).get("work", 0)) for v in d.values()
                if isinstance(v, dict))
    out.append(("百小时陪伴", "累计在岗 100 小时", total >= 360000))
    # 7 心情记录者
    mcount = sum(1 for _, s in M.recent(30, now) if s is not None)
    out.append(("心情观察家", "近 30 天打卡 10 次以上", mcount >= 10))
    # 8 好心情周
    scored = [x for x in M.week(now) if x["score"] is not None]
    out.append(("快乐打工人", "本周心情全是「开心」",
                bool(scored) and all(x["score"] == 2 for x in scored) and len(scored) >= 3))
    return out


def badges_text(now=None, plan_end="18:00"):
    lines = []
    for name, desc, got in badges(now, plan_end):
        lines.append("%s %s —— %s" % ("🏅" if got else "⚪", name, desc))
    return "\n".join(lines)
