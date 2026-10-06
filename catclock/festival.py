# -*- coding: utf-8 -*-
"""全年节日皮肤表：日期 → 帽子 / 配饰 / 道具 / 问候 / 专属语录。

农历节日用内置公历对照表（2026-2030），超出范围自动不做农历节日，
只保留公历节日，绝不因为日期计算出错而崩。
"""
from datetime import date, timedelta

# 农历节日对照（公历）。超出范围则不过该农历节日。
CNY = {2026: (2, 17), 2027: (2, 6), 2028: (1, 26), 2029: (2, 13), 2030: (2, 3)}
DUANWU = {2026: (6, 19), 2027: (6, 9), 2028: (5, 28), 2029: (6, 16), 2030: (6, 5)}
ZHONGQIU = {2026: (9, 25), 2027: (9, 15), 2028: (10, 3), 2029: (9, 22), 2030: (9, 12)}


def _lunar(year, table, offset=0):
    """取农历节日公历日期；没有对照片则返回 None"""
    v = table.get(year)
    if not v:
        return None
    d = date(year, v[0], v[1]) + timedelta(days=offset)
    return (d.month, d.day)


def _span(center, before=0, after=0):
    """把 (月,日) 展开成 [(月,日)…] 便于快速匹配"""
    if not center:
        return []
    y, m, d = 2000, center[0], center[1]
    base = date(y, m, d)
    out = []
    for i in range(-before, after + 1):
        x = base + timedelta(days=i)
        out.append((x.month, x.day))
    return out


# ----------------------------------------------------------------------
# 节日定义
#   md  : 匹配的 (月,日) 列表
#   hat / acc / prop / greet / pool
#   pool 为该节日专属语录（工作时段随机穿插）
# ----------------------------------------------------------------------
def _table(year):
    cny = CNY.get(year)
    return [
        {
            "key": "newyear", "name": "元旦",
            "md": [(1, 1), (1, 2), (1, 3)],
            "hat": "party", "acc": "none", "prop": "coin",
            "greet": "新年快乐！今年也请多指教～",
            "pool": ["新的一年，也要准时下班哦", "2026 的第一天，猫陪你搬砖",
                     "新年新气象，先从喝水开始"],
        },
        {
            "key": "cny", "name": "春节",
            "md": _span(cny, 1, 7) if cny else [],
            "hat": "cny", "acc": "none", "prop": "coin",
            "greet": "过年好！猫给你拜年了～",
            "pool": ["年味还在，心已经飞走了", "春节还在搬砖，猫心疼你",
                     "恭喜发财，红包拿来（伸出爪）"],
        },
        {
            "key": "lantern", "name": "元宵节",
            "md": _span(_lunar(year, CNY, 14), 0, 1) if cny else [],
            "hat": "cny", "acc": "none", "prop": "coin",
            "greet": "元宵节快乐，吃汤圆了吗～",
            "pool": ["汤圆要趁热吃，班要慢慢上", "过了元宵，年才算过完"],
        },
        {
            "key": "valentine", "name": "情人节",
            "md": [(2, 14)],
            "hat": "none", "acc": "bowtie", "prop": "heart",
            "greet": "情人节快乐，今天猫是你的小情人～",
            "pool": ["有对象陪，也要记得陪猫", "今天是属于两个人的日子"],
        },
        {
            "key": "qingming", "name": "清明",
            "md": [(4, 4), (4, 5), (4, 6)],
            "hat": "none", "acc": "none", "prop": "umbrella",
            "greet": "清明时节雨纷纷，路上行人……在加班",
            "pool": ["清明宜休息，宜想念", "雨纷纷，猫陪你一起安静"],
        },
        {
            "key": "labour", "name": "劳动节",
            "md": [(5, 1), (5, 2), (5, 3)],
            "hat": "party", "acc": "none", "prop": "coffee",
            "greet": "劳动节快乐，劳动的人最帅！",
            "pool": ["劳动节还在劳动，致敬", "今天你值得一杯奶茶"],
        },
        {
            "key": "duanwu", "name": "端午节",
            "md": _span(_lunar(year, DUANWU), 0, 1) if year in DUANWU else [],
            "hat": "straw", "acc": "none", "prop": "coin",
            "greet": "端午安康，粽子吃甜的还是咸的？",
            "pool": ["粽子节快乐，猫想要肉粽", "甜咸之争，猫站肉粽"],
        },
        {
            "key": "zhongqiu", "name": "中秋节",
            "md": _span(_lunar(year, ZHONGQIU), 1, 1) if year in ZHONGQIU else [],
            "hat": "crown", "acc": "none", "prop": "coin",
            "greet": "中秋快乐，记得抬头看月亮～",
            "pool": ["月亮很圆，你也该回家了", "月饼吃了吗？猫分你一口"],
        },
        {
            "key": "national", "name": "国庆节",
            "md": [(10, 1), (10, 2), (10, 3), (10, 4), (10, 5), (10, 6), (10, 7)],
            "hat": "cny", "acc": "none", "prop": "coin",
            "greet": "国庆快乐！祖国生日，猫也放假～",
            "pool": ["长假快乐，班就先放一边", "国庆还在上班？猫给你敬礼"],
        },
        {
            "key": "halloween", "name": "万圣节",
            "md": [(10, 31), (11, 1)],
            "hat": "witch", "acc": "none", "prop": "coin",
            "greet": "不给糖就捣蛋！喵～",
            "pool": ["今晚的猫有点吓人（其实很可爱）", "南瓜灯亮了，别加班太晚"],
        },
        {
            "key": "christmas", "name": "圣诞节",
            "md": [(12, 24), (12, 25), (12, 26)],
            "hat": "santa", "acc": "none", "prop": "scarf",
            "greet": "圣诞快乐！猫的袜子已经挂好了～",
            "pool": ["圣诞快乐，礼物是……准时下班", "铃儿响叮当，猫也想要礼物"],
        },
        {
            "key": "newyear_eve", "name": "跨年夜",
            "md": [(12, 31)],
            "hat": "party", "acc": "none", "prop": "coin",
            "greet": "今晚跨年，早点回家倒数吧！",
            "pool": ["今年最后一天班了，撑住", "新年倒计时开始，猫先许愿"],
        },
    ]


def today_festival(d=None):
    """返回今天的节日 dict（含 key/name/hat/acc/prop/greet/pool），无节日返回 None。"""
    d = d or date.today()
    md = (d.month, d.day)
    try:
        for f in _table(d.year):
            if md in f["md"]:
                return f
    except Exception:
        return None
    return None


def festival_hat(d=None):
    f = today_festival(d)
    return f["hat"] if f and f.get("hat") not in (None, "none") else None


def all_festivals(year=None):
    """列出某年全部节日（设置窗口展示用）：[(月日, 名称, 帽)]"""
    year = year or date.today().year
    out = []
    for f in _table(year):
        for m, dd in f["md"]:
            out.append((m, dd, f["name"], f.get("hat") or "none"))
    return sorted(set(out))
