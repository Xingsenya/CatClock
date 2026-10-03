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
server.newConnection.connect(lambda: (server.nextPendingConnection(), wgt.show_and_raise()))
wgt.timer.stop()
state = {"last": -1}
orig_update = wgt.update
def slow_tick():
    sec = int(wgt.t0)
    do_paint = (sec != state["last"]) or (wgt.blink_t < 0.25)
    state["last"] = sec
    wgt.update = orig_update if do_paint else (lambda *a, **k: None)
    wgt._tick()
t = QTimer(); t.timeout.connect(slow_tick); t.start(100)
wgt.show()
QTimer.singleShot(25000, app.quit)
rc = app.exec()
print("throttled exec returned", rc, flush=True)
