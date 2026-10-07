# -*- coding: utf-8 -*-
"""自定义语录：内置兜底 + 可编辑 JSON 文件。

语录文件位置：%APPDATA%\\CatClock\\quotes.json
支持自定义：
  - quotes：工作日时段语录池
  - friday：周五专属语录池
  - pre：上班前语录池（以前这个阶段挂件一句话都不说）
  - off：下班后语录池（同样，现在猫也会陪你聊两句）
  - weather：天气联动语录（rain/thunder/snow/sun/cloud-sun/cloud/fog）
  - hydrate：久坐提醒文案池
  - context：情境感知语录（开会 / 写代码 / 电量低 ……）

升级：内置语录扩充时 SCHEMA 会 +1，load_custom_quotes() 会把新增的句子
**追加**进用户已有的 quotes.json（用户自己写的永远保留在前），不会因为
升级而被覆盖掉。
"""
import json
import os
from datetime import date

from . import data as D
from .util import CONFIG_DIR

QUOTE_PATH = os.path.join(CONFIG_DIR, "quotes.json")

# 语录表结构版本：内置语录有增删时 +1，触发一次「合并式升级」
SCHEMA = 2


def _default_data():
    return {
        "version": SCHEMA,
        "quotes": [{"start": a, "end": b, "pool": list(pool)}
                   for a, b, pool in D.QUOTES],
        "friday": [{"start": a, "end": b, "pool": list(pool)}
                   for (a, b), pool in D.QUOTES_FRIDAY.items()],
        "pre": [{"start": a, "end": b, "pool": list(pool)}
                for a, b, pool in D.QUOTES_PRE],
        "off": [{"start": a, "end": b, "pool": list(pool)}
                for a, b, pool in D.QUOTES_OFF],
        "weather": {k: list(v) for k, v in D.WEATHER_QUOTES.items()},
        "hydrate": list(D.HYDRATE_MSGS),
        "context": {k: list(v) for k, v in D.CONTEXT_QUOTES.items()},
    }


_DEFAULT = _default_data()


def _merge_list(dst, src):
    """把 src 里 dst 没有的句子追加到 dst 后面（用户内容保持在前）。"""
    seen = set(dst)
    return list(dst) + [x for x in src if x not in seen]


def _merge_slots(out_slots, user_slots):
    """按时段合并：用户时段优先，内置新增时段/句子追加在后。"""
    by_key = {(it["start"], it["end"]): dict(it) for it in out_slots}
    order = [(it["start"], it["end"]) for it in out_slots]
    for it in user_slots:
        if not (isinstance(it, dict) and isinstance(it.get("pool"), list)):
            continue
        t = (it.get("start", 9.0), it.get("end", 18.0))
        if t in by_key:
            by_key[t]["pool"] = _merge_list(by_key[t]["pool"], it["pool"])
        else:
            by_key[t] = {"start": t[0], "end": t[1], "pool": list(it["pool"])}
            order.append(t)
    return [by_key[t] for t in order]


def _upgrade_user_file(data):
    """把内置新增语录合并进用户文件（只补不删），并写回抬高 version。"""
    builtin = _default_data()
    out = {
        "version": SCHEMA,
        "quotes": _merge_slots(builtin["quotes"], data.get("quotes") or []),
        "friday": _merge_slots(builtin["friday"], data.get("friday") or []),
        "pre": _merge_slots(builtin["pre"], data.get("pre") or []),
        "off": _merge_slots(builtin["off"], data.get("off") or []),
        "weather": dict(builtin["weather"]),
        "hydrate": _merge_list(builtin["hydrate"], data.get("hydrate") or []),
        "context": dict(builtin["context"]),
    }
    for k, v in (data.get("weather") or {}).items():
        if isinstance(v, list):
            out["weather"][k] = _merge_list(builtin["weather"].get(k, []), v)
    for k, v in (data.get("context") or {}).items():
        if isinstance(v, list):
            out["context"][k] = _merge_list(builtin["context"].get(k, []), v)
    try:
        with open(QUOTE_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return out


def ensure_default_file():
    """首次使用时把默认语录写进用户目录，方便后续编辑。"""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if not os.path.exists(QUOTE_PATH):
            with open(QUOTE_PATH, "w", encoding="utf-8") as f:
                json.dump(_default_data(), f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_custom_quotes():
    """读取用户语录；文件缺失/损坏时回退到内置并尝试重建。

    内置语录扩充后（SCHEMA 变大）会自动做一次「只补不删」的合并升级，
    用户自己加的句子始终保留。
    """
    try:
        ensure_default_file()
        with open(QUOTE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return _default_data()

    if int(data.get("version", 1)) < SCHEMA:
        return _upgrade_user_file(data)

    out = _default_data()
    for key in ("quotes", "friday", "pre", "off"):
        if isinstance(data.get(key), list):
            out[key] = _merge_slots(out[key], data[key])
    if isinstance(data.get("weather"), dict):
        out["weather"].update({k: list(v) for k, v in data["weather"].items()
                               if isinstance(v, list)})
    if isinstance(data.get("hydrate"), list) and data["hydrate"]:
        out["hydrate"] = list(data["hydrate"])
    if isinstance(data.get("context"), dict):
        out["context"].update({k: list(v) for k, v in data["context"].items()
                               if isinstance(v, list)})
    return out


def reset_quotes_file():
    """一键恢复出厂语录。"""
    ensure_default_file()
    try:
        with open(QUOTE_PATH, "w", encoding="utf-8") as f:
            json.dump(_default_data(), f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_quote(phase, hour, is_friday, weather_kind, idx, custom=None):
    """根据时段/天气/周五/轮询索引挑一条语录。

    参数：
      phase   : 'work' 工作 / 'pre' 上班前 / 'off' 下班后；'rest' 直接 None
      hour    : 当前小时带小数，如 9.5
      is_friday: 是否周五
      weather_kind: rain/thunder/snow/sun/cloud-sun/cloud/fog 或 None
      idx     : self.quote_i，用于轮询同一句池
      custom  : load_custom_quotes() 的结果，None 则用内置默认
    """
    if phase not in ("work", "pre", "off"):
        return None
    data = custom if custom is not None else _DEFAULT

    # 上班前 / 下班后：直接走各自的时段池，不掺天气和周五
    if phase in ("pre", "off"):
        for it in data.get(phase, []):
            if it["start"] <= hour < it["end"]:
                pool = it["pool"]
                return pool[idx % len(pool)]
        # 时段没覆盖（比如凌晨）：把该阶段所有句子摊平后轮询，保证有话说
        pool = [s for it in data.get(phase, []) for s in it["pool"]]
        return pool[idx % len(pool)] if pool else None

    # 天气联动：每 3 条语录穿插一次天气语录
    if weather_kind and idx % 3 == 0:
        pool = data["weather"].get(weather_kind)
        if pool:
            msg = pool[(idx // 3) % len(pool)]
            if weather_kind == "sun":
                # 温度补充放到 app.py 里做，这里保持纯文本
                pass
            return msg

    # 周五专属
    if is_friday:
        for it in data.get("friday", []):
            if it["start"] <= hour < it["end"]:
                pool = it["pool"]
                return pool[idx % len(pool)]

    # 工作日时段
    for it in data.get("quotes", []):
        if it["start"] <= hour < it["end"]:
            pool = it["pool"]
            return pool[idx % len(pool)]
    # 超出时段（比如下班时间早于 9 点 / 晚于 18.6）：摊平兜底
    pool = [s for it in data.get("quotes", []) for s in it["pool"]]
    return pool[idx % len(pool)] if pool else None


def hydrate_msg(idx, custom=None):
    """久坐提醒文案轮询。"""
    data = custom if custom is not None else _DEFAULT
    pool = data.get("hydrate") or D.HYDRATE_MSGS
    if not pool:
        return "起来活动一下吧"
    return pool[idx % len(pool)]


def context_msg(key, idx, custom=None):
    """按感知场景取语录；未配置返回 None。"""
    if not key:
        return None
    data = custom if custom is not None else _DEFAULT
    pool = data.get("context", {}).get(key)
    if not pool:
        pool = D.CONTEXT_QUOTES.get(key)
    if not pool:
        return None
    return pool[idx % len(pool)]


def festive_hat_now():
    """返回当前节日专属帽，无节日返回 None。（委托给 festival 表）"""
    try:
        from .festival import festival_hat
        return festival_hat()
    except Exception:
        return None
