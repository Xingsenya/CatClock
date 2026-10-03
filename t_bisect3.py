# -*- coding: utf-8 -*-
import sys, traceback, faulthandler
sys.path.insert(0, r"D:\CatClock")
fh = open(r"D:\CatClock\fh_dump.txt", "w", encoding="utf-8")
faulthandler.enable(fh)
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import cat_clock as cc
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
server = cc.acquire_single()
if server is None:
    sys.exit(0)
wgt = cc.CatClock()
server.newConnection.connect(lambda: (server.nextPendingConnection(), wgt.show_and_raise()))
wgt.show()
QTimer.singleShot(18000, app.quit)
rc = app.exec()
fh.write("exec returned %s\n" % rc)
fh.close()
