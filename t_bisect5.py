# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, r"D:\CatClock")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QPainter, QFont, QFontMetrics
import cat_clock as cc
mode = sys.argv[1]
if mode == "notext":
    QPainter.drawText = lambda self, *a, **k: None
    QPainter.fontMetrics = lambda self: type("FM", (), {"horizontalAdvance": lambda self, s: 10})()
    QPainter.setFont = lambda self, *a, **k: None
if mode == "noshape":
    QPainter.drawPath = lambda self, *a, **k: None
    QPainter.setClipPath = lambda self, *a, **k: None
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
server = cc.acquire_single()
if server is None:
    sys.exit(0)
wgt = cc.CatClock()
server.newConnection.connect(lambda: (server.nextPendingConnection(), wgt.show_and_raise()))
wgt.show()
QTimer.singleShot(15000, app.quit)
rc = app.exec()
print("exec returned", rc, flush=True)
