# -*- coding: utf-8 -*-
import sys, json, os
p = os.path.join(os.environ["APPDATA"], "CatClock", "config.json")
cfg = json.load(open(p, encoding="utf-8"))
cfg["scale"] = 1.0
json.dump(cfg, open(p, "w", encoding="utf-8"), ensure_ascii=False)
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
server.newConnection.connect(lambda: (server.nextPendingConnection(), wgt.show_and_raise()))
wgt.show()
QTimer.singleShot(25000, app.quit)
rc = app.exec()
print("scale1.0 exec returned", rc, flush=True)
