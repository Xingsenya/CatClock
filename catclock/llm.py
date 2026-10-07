# -*- coding: utf-8 -*-
"""Qwen 个性化语录（可选功能，默认关闭）。

配置：%APPDATA%/CatClock/qwen.json
    {"enabled": false, "api_key": "", "model": "qwen-plus"}
也支持环境变量 DASHSCOPE_API_KEY / QWEN_API_KEY。

请求走 DashScope 的 OpenAI 兼容接口，只依赖标准库 urllib。
失败一律静默降级到内置语录池，绝不影响主界面。
"""
import json
import os
import re
import threading
import urllib.request

from .util import CONFIG_DIR

QWEN_PATH = os.path.join(CONFIG_DIR, "qwen.json")
CACHE_PATH = os.path.join(CONFIG_DIR, "qwen_cache.json")
ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DEFAULT_MODEL = "qwen-plus"

_pending = {"result": None, "done": True, "err": None}


def _cfg():
    c = {"enabled": False, "api_key": "", "model": DEFAULT_MODEL}
    try:
        if os.path.exists(QWEN_PATH):
            with open(QWEN_PATH, "r", encoding="utf-8") as f:
                c.update(json.load(f))
    except Exception:
        pass
    if not c.get("api_key"):
        c["api_key"] = os.environ.get("DASHSCOPE_API_KEY") or \
            os.environ.get("QWEN_API_KEY") or ""
    return c


def save_cfg(enabled, api_key, model=DEFAULT_MODEL):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(QWEN_PATH, "w", encoding="utf-8") as f:
            json.dump({"enabled": bool(enabled), "api_key": api_key or "",
                       "model": model or DEFAULT_MODEL},
                      f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def is_enabled():
    c = _cfg()
    return bool(c.get("enabled")) and bool(c.get("api_key"))


# ----------------------------------------------------------------------
# 缓存（每天一组）
# ----------------------------------------------------------------------
def _load_cache():
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(d):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def cached(day):
    d = _load_cache()
    if d.get("date") == day and isinstance(d.get("lines"), list) and d["lines"]:
        return d["lines"]
    return None


def _set_cache(day, lines):
    _save_cache({"date": day, "lines": lines})


# ----------------------------------------------------------------------
# 生成
# ----------------------------------------------------------------------
def _build_prompt(ctx):
    return (
        "你是桌面宠物猫时钟「CatClock」的文案助手，面向中国打工人。\n"
        "当前上下文：%s\n"
        "要求：输出 3 条中文短句，每条不超过 20 字，风格轻松可爱、会吐槽也会鼓励，"
        "不要 emoji，不要引号包裹整句，不要编号。\n"
        "重要：文案里不要出现猫的品种名（黑猫/橘猫/奶牛猫等一律不要写），"
        "自称用「我」或「本喵」；不要写具体时间、倒计时数字；三条句式不要雷同。\n"
        "只输出一个 JSON 数组，例如 [\"句子一\",\"句子二\",\"句子三\"]，不要任何解释。"
        % ctx.get("desc", "工作日白天")
    )


def _parse(text):
    """从返回文本里抠出 JSON 字符串数组"""
    if not text:
        return []
    m = re.search(r"\[.*?\]", text, re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except Exception:
        try:
            arr = json.loads(m.group(0).replace("'", '"'))
        except Exception:
            return []
    out = []
    for x in arr:
        if isinstance(x, str):
            s = x.strip().strip('"“”')
            if 0 < len(s) <= 26:
                out.append(s)
    return out[:3]


def generate(ctx, timeout=10.0):
    """同步生成（内部用）。返回 list[str]，失败返回 []。"""
    c = _cfg()
    key = c.get("api_key")
    if not key:
        return []
    body = json.dumps({
        "model": c.get("model") or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": "你是一只陪伴打工人的桌面猫，说话简短可爱。"},
            {"role": "user", "content": _build_prompt(ctx)},
        ],
        "temperature": 0.95,
        "max_tokens": 400,
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer %s" % key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        choices = data.get("choices") or []
        if not choices:
            return []
        return _parse(choices[0].get("message", {}).get("content", ""))
    except Exception:
        return []


def request_async(ctx, day, on_done=None):
    """后台线程生成；主界面用 poll() 取结果。已有缓存则直接回调。"""
    hit = cached(day)
    if hit:
        if on_done:
            on_done(hit)
        return False
    if not is_enabled():
        return False
    if not _pending["done"]:
        return False
    _pending.update({"result": None, "done": False, "err": None})

    def _run():
        lines = []
        try:
            lines = generate(ctx)
        except Exception as e:
            _pending["err"] = str(e)
        if lines:
            _set_cache(day, lines)
        _pending["result"] = lines
        _pending["done"] = True
        if on_done:
            try:
                on_done(lines)
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()
    return True


def poll():
    """主界面轮询：返回 (done, lines)"""
    return _pending["done"], (_pending["result"] or [])
