# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"D:\CatClock")
CNT = open(r"D:\CatClock\patch_count.txt", "w", encoding="utf-8")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QPainter
import cat_clock as cc
n = [0]
orig = QPainter.drawText
def fake(self, *a, **k):
    n[0] += 1
    return orig(self, *a, **k)
QPainter.drawText = fake
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
CNT.write("drawText calls: %d, exec returned %s\n" % (n[0], rc))
CNT.close()
