# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"D:\CatClock")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import cat_clock as cc
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
server = cc.acquire_single()
if server is None:
    sys.exit(0)
wgt = cc.CatClock()
wgt.setMouseTracking(False)
wgt.enterEvent = lambda e: None
wgt.leaveEvent = lambda e: None
wgt.mouseMoveEvent = lambda e: None
server.newConnection.connect(lambda: (server.nextPendingConnection(), wgt.show_and_raise()))
wgt.show()
QTimer.singleShot(25000, app.quit)
rc = app.exec()
print("no-mouse exec returned", rc, flush=True)
