# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"D:\CatClock")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QRect
from PyQt6.QtGui import QPixmap, QPainter, QColor
import cat_clock as cc
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
server = cc.acquire_single()
if server is None:
    sys.exit(0)
wgt = cc.CatClock()
server.newConnection.connect(lambda: (server.nextPendingConnection(), wgt.show_and_raise()))
# 预渲染整窗到缓存
cache = QPixmap(wgt.size())
wgt.render(cache)
def fast_paint(ev):
    p = QPainter(wgt)
    p.drawPixmap(0, 0, cache)
    p.fillRect(QRect(wgt.width() - 60, 10, 50, 20), QColor(255, 255, 255))
    p.end()
wgt.paintEvent = fast_paint
wgt.show()
QTimer.singleShot(20000, app.quit)
rc = app.exec()
print("cache-mode exec returned", rc, flush=True)
