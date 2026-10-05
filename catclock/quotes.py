# -*- coding: utf-8 -*-
"""自定义语录：内置兜底 + 可编辑 JSON 文件。

语录文件位置：%APPDATA%\\CatClock\\quotes.json
支持自定义：
  - quotes：工作日时段语录池
  - friday：周五专属语录池
  - weather：天气联动语录（rain/thunder/snow/sun/cloud-sun/cloud/fog）
  - hydrate：久坐提醒文案池
"""
import json
import os
from datetime import date

from . import data as D
from .util import CONFIG_DIR

QUOTE_PATH = os.path.join(CONFIG_DIR, "quotes.json")


def _default_data():
    return {
        "version": 1,
        "quotes": [{"start": a, "end": b, "pool": list(pool)}
                   for a, b, pool in D.QUOTES],
        "friday": [{"start": a, "end": b, "pool": list(pool)}
                   for (a, b), pool in D.QUOTES_FRIDAY.items()],
        "weather": {k: list(v) for k, v in D.WEATHER_QUOTES.items()},
        "hydrate": list(D.HYDRATE_MSGS),
    }


_DEFAULT = _default_data()


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
    """读取用户语录；文件缺失/损坏时回退到内置并尝试重建。"""
    try:
        ensure_default_file()
        with open(QUOTE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return _default_data()
    out = _default_data()
    for key in ("quotes", "friday"):
        if isinstance(data.get(key), list):
            merged = []
            seen = set()
            for it in out[key]:
                merged.append(it)
                seen.add((it["start"], it["end"]))
            for it in data[key]:
                if isinstance(it, dict) and isinstance(it.get("pool"), list):
                    it.setdefault("start", 9.0)
                    it.setdefault("end", 18.0)
                    t = (it["start"], it["end"])
                    if t in seen:
                        # 用户覆盖该时段
                        merged = [m for m in merged if (m["start"], m["end"]) != t]
                    merged.append(it)
                    seen.add(t)
            out[key] = merged
    if isinstance(data.get("weather"), dict):
        out["weather"].update({k: list(v) for k, v in data["weather"].items()
                               if isinstance(v, list)})
    if isinstance(data.get("hydrate"), list) and data["hydrate"]:
        out["hydrate"] = list(data["hydrate"])
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
      phase   : 'work' 才返回；其它直接 None
      hour    : 当前小时带小数，如 9.5
      is_friday: 是否周五
      weather_kind: rain/thunder/snow/sun/cloud-sun/cloud/fog 或 None
      idx     : self.quote_i，用于轮询同一句池
      custom  : load_custom_quotes() 的结果，None 则用内置默认
    """
    if phase != "work":
        return None
    data = custom if custom is not None else _DEFAULT

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
    return None


def hydrate_msg(idx, custom=None):
    """久坐提醒文案轮询。"""
    data = custom if custom is not None else _DEFAULT
    pool = data.get("hydrate") or D.HYDRATE_MSGS
    if not pool:
        return "起来活动一下吧"
    return pool[idx % len(pool)]


def festive_hat_now():
    """返回当前节日专属帽，无节日返回 None。
    目前支持：12/20-12/26 圣诞帽，春节（1/1-1/7）福帽。"""
    today = date.today()
    if today.month == 12 and 20 <= today.day <= 26:
        return "santa"
    if today.month == 1 and 1 <= today.day <= 7:
        return "cny"
    return None
