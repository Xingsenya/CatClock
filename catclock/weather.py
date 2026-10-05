# -*- coding: utf-8 -*-
"""天气获取（Open-Meteo）。"""
import json
import os
from urllib.parse import quote

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from . import data as D
from .util import CONFIG_DIR

class WeatherFetcher(QObject):
    """Open-Meteo 天气拉取：地理编码（逐级降级）→ 实时天气，got 信号发 dict"""
    got = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nam = QNetworkAccessManager(self)
        self._candidates = []

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

    def _try_next(self):
        if not self._candidates:
            return
        name = self._candidates.pop(0)
        url = ("https://geocoding-api.open-meteo.com/v1/search?name=%s"
               "&count=1&language=zh&format=json" % quote(name))
        req = QNetworkRequest(QUrl(url))
        req.setTransferTimeout(15000)
        reply = self.nam.get(req)
        reply.finished.connect(lambda r=reply: self._geo_done(r))

    def _geo_done(self, reply):
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            results = data.get("results") or []
            if not results:
                self._try_next()          # 查不到则降级到上级地名
                reply.deleteLater()
                return
            loc = results[0]
            lat, lon = loc["latitude"], loc["longitude"]
            name = loc.get("name", "")
            url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
                   "&current_weather=true&timezone=Asia%%2FShanghai" % (lat, lon))
            req = QNetworkRequest(QUrl(url))
            req.setTransferTimeout(15000)
            r2 = self.nam.get(req)
            r2.finished.connect(lambda rr=r2, n=name: self._wx_done(rr, n))
        except Exception:
            pass
        reply.deleteLater()

    def _wx_done(self, reply, name):
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            cw = data["current_weather"]
            code = int(cw["weathercode"])
            self.got.emit(dict(
                city=name, code=code, kind=wmo_kind(code),
                temp=round(cw["temperature"]),
                text=WMO_TEXT.get(code, "多云"),
            ))
        except Exception:
            pass
        reply.deleteLater()

