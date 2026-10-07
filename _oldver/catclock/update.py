# -*- coding: utf-8 -*-
"""版本更新检查（GitHub Release）。

设计原则：任何异常都静默吞掉——没网、仓库不存在、返回格式异常，都不能影响挂件本身。
"""
import json
import urllib.request

from . import __version__, UPDATE_API, GITHUB_REPO


def _vtuple(v):
    """'v1.2.3' / '1.2.3' → (1, 2, 3)；解析失败返回 (0,)。"""
    try:
        s = str(v).lstrip("vV").strip()
        parts = []
        for seg in s.split(".")[:3]:
            num = ""
            for ch in seg:
                if ch.isdigit():
                    num += ch
                else:
                    break
            parts.append(int(num) if num else 0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts)
    except Exception:
        return (0,)


def is_newer(remote):
    return _vtuple(remote) > _vtuple(__version__)


def check_update(timeout=6.0):
    """查询最新 Release。

    返回 dict(version=, url=, notes=) 表示有新版；None 表示无新版或查询失败。
    """
    try:
        req = urllib.request.Request(
            UPDATE_API, headers={"User-Agent": "CatClock", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        tag = data.get("tag_name") or data.get("name") or ""
        if not tag or not is_newer(tag):
            return None
        return {
            "version": str(tag).lstrip("vV"),
            "url": data.get("html_url") or ("https://github.com/%s/releases" % GITHUB_REPO),
            "notes": (data.get("body") or "")[:400],
        }
    except Exception:
        return None
