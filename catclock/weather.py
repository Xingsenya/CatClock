# -*- coding: utf-8 -*-
"""天气获取（Open-Meteo 实时天气 + 空气质量）。

特性：
- 地理编码逐级降级（上海闵行区 → 上海闵行 → 上海闵 → 上海）
- 附带 AQI（欧洲标准 European AQI）与穿衣建议
- 本地缓存：断网或请求失败时启动先用上次结果
"""
import json
import os
import re
import time
from urllib.parse import quote

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from . import data as D
from .util import CONFIG_DIR

CACHE_PATH = os.path.join(CONFIG_DIR, "weather_cache.json")


def dress_advice(temp, kind):
    """按温度 + 天气给一句穿衣/出行建议。"""
    if temp is None:
        return ""
    if temp >= 33:
        return "高温，短袖 + 防晒，多喝水"
    if temp >= 28:
        return "短袖就行，注意防晒"
    if temp >= 23:
        return "单衣舒适，早晚可加薄外套"
    if temp >= 17:
        return "长袖 + 薄外套"
    if temp >= 11:
        return "外套 + 长裤，风大加件风衣"
    if temp >= 4:
        return "毛衣 / 卫衣 + 厚外套"
    return "羽绒服 + 保暖，注意防冻"


def aqi_text(aqi):
    if aqi is None:
        return ""
    try:
        aqi = int(aqi)
    except Exception:
        return ""
    if aqi <= 20:
        return "空气优"
    if aqi <= 40:
        return "空气良"
    if aqi <= 60:
        return "空气一般"
    if aqi <= 80:
        return "空气较差"
    if aqi <= 100:
        return "空气差"
    return "空气很差，减少外出"


def load_cache(max_age=6 * 3600):
    """读取上次天气（超过 6 小时视为过期，仍返回但带 stale 标记）。"""
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict) or "temp" not in d:
            return None
        d["stale"] = (time.time() - float(d.get("_ts", 0))) > max_age
        return d
    except Exception:
        return None


def save_cache(w):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        d = dict(w)
        d["_ts"] = time.time()
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass


class WeatherFetcher(QObject):
    """Open-Meteo 天气拉取。got 信号发 dict；全部候选失败发 failed。"""
    got = pyqtSignal(dict)
    failed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nam = QNetworkAccessManager(self)
        self._candidates = []
        self._pending = None

    # ---------- 入口 ----------
    def start(self, city):
        self._candidates = self._fallback_names(city)
        self._try_next()

    @staticmethod
    def _fallback_names(city):
        """上海闵行区 → 上海闵行区 / 上海闵行 / 上海闵 / 上海"""
        names = [city]
        base = re.sub(r"(省|市|区|县)$", "", city)
        if base != city:
            names.append(base)
        while len(base) > 2:
            base = base[:-1]
            names.append(base)
        seen, out = set(), []
        for n in names:
            if n and n not in seen:
                seen.add(n)
                out.append(n)
        return out

    # ---------- 地理编码 ----------
    def _try_next(self):
        if not self._candidates:
            self.failed.emit()
            return
        name = self._candidates.pop(0)
        url = ("https://geocoding-api.open-meteo.com/v1/search?name=%s"
               "&count=1&language=zh&format=json" % quote(str(name)))
        req = QNetworkRequest(QUrl(url))
        req.setTransferTimeout(15000)
        reply = self.nam.get(req)
        reply.finished.connect(lambda r=reply: self._geo_done(r))

    def _geo_done(self, reply):
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            results = data.get("results") or []
            if not results:
                reply.deleteLater()
                self._try_next()          # 查不到则降级到上级地名
                return
            loc = results[0]
            lat, lon = loc["latitude"], loc["longitude"]
            name = loc.get("name", "")
            url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
                   "&current_weather=true&timezone=Asia%%2FShanghai" % (lat, lon))
            req = QNetworkRequest(QUrl(url))
            req.setTransferTimeout(15000)
            r2 = self.nam.get(req)
            r2.finished.connect(lambda rr=r2, n=name, la=lat, lo=lon: self._wx_done(rr, n, la, lo))
        except Exception:
            self._try_next()
        reply.deleteLater()

    # ---------- 实时天气 ----------
    def _wx_done(self, reply, name, lat, lon):
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            cw = data["current_weather"]
            code = int(cw["weathercode"])
            temp = round(cw["temperature"])
            self._pending = dict(
                city=name, code=code, kind=D.wmo_kind(code),
                temp=temp, text=D.WMO_TEXT.get(code, "多云"),
                advice=dress_advice(temp, D.wmo_kind(code)),
            )
            self._fetch_aqi(lat, lon)
        except Exception:
            self._emit()
        reply.deleteLater()

    # ---------- 空气质量 ----------
    def _fetch_aqi(self, lat, lon):
        try:
            url = ("https://air-quality-api.open-meteo.com/v1/air-quality"
                   "?latitude=%s&longitude=%s&current=european_aqi,pm2_5" % (lat, lon))
            req = QNetworkRequest(QUrl(url))
            req.setTransferTimeout(12000)
            r3 = self.nam.get(req)
            r3.finished.connect(lambda rr=r3: self._aqi_done(rr))
        except Exception:
            self._emit()

    def _aqi_done(self, reply):
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            cur = data.get("current") or {}
            aqi = cur.get("european_aqi")
            if self._pending is not None and aqi is not None:
                self._pending["aqi"] = int(aqi)
                self._pending["aqi_text"] = aqi_text(aqi)
        except Exception:
            pass
        self._emit()
        reply.deleteLater()

    def _emit(self):
        if not self._pending:
            return
        w = self._pending
        self._pending = None
        save_cache(w)
        self.got.emit(w)
