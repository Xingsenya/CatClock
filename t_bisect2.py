# -*- coding: utf-8 -*-
import sys, traceback
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
    interval = int(sys.argv[1])
    server = cc.acquire_single()
    if server is None:
        w("blocked"); sys.exit(0)
    wgt = cc.CatClock()
    wgt.timer.stop()
    wgt.timer.start(interval)
    server.newConnection.connect(lambda: (server.nextPendingConnection(), wgt.show_and_raise()))
    wgt.show()
    w("shown, tick=%dms" % interval)
    QTimer.singleShot(18000, app.quit)
    rc = app.exec()
    w("exec returned %s" % rc)
except BaseException:
    w("EXC: " + traceback.format_exc())
finally:
    w("end"); LOG.close()
