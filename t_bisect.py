# -*- coding: utf-8 -*-
import sys, os, traceback
sys.path.insert(0, r"D:\CatClock")
LOG = open(r"D:\CatClock\bisect_log.txt", "w", encoding="utf-8")
def w(m):
    LOG.write(m + "\n"); LOG.flush()
try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    import cat_clock as cc
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    w("mode=" + mode)
    server = cc.acquire_single()
    if server is None:
        w("blocked"); sys.exit(0)
    wgt = cc.CatClock()
    if mode == "notick":
        wgt.timer.stop()
    if mode == "nopaint":
        wgt.timer.stop()
        wgt.update = lambda *a, **k: None
    if mode == "nowx":
        wgt.wx_timer.stop()
    server.newConnection.connect(lambda: (server.nextPendingConnection(), wgt.show_and_raise()))
    wgt.show()
    w("shown, exec")
    QTimer.singleShot(15000, app.quit)
    rc = app.exec()
    w("exec returned %s" % rc)
except BaseException:
    w("EXC: " + traceback.format_exc())
finally:
    w("end")
    LOG.close()
