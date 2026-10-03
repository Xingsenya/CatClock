# -*- coding: utf-8 -*-
import sys, traceback
sys.path.insert(0, r"D:\CatClock")
LOG = open(r"D:\CatClock\bisect_log.txt", "w", encoding="utf-8")
def w(m):
    LOG.write(m + "\n"); LOG.flush()
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import cat_clock as cc
mode = sys.argv[1]
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
server = cc.acquire_single()
if server is None:
    sys.exit(0)
wgt = cc.CatClock()
if mode == "nocat":
    cc.draw_cat_orig = cc.draw_cat
    import types
    cc.draw_cat = lambda *a, **k: None
if mode == "nocursor":
    from PyQt6.QtGui import QCursor
    cc.QCursor_orig = cc.QCursor
    class FakeCursor:
        @staticmethod
        def pos():
            return cc.QCursor_orig.pos()
    # 直接改类属性不可行，改 paintEvent 用的全局名
    cc.QCursor = FakeCursor
if mode == "nofont":
    wgt._orig_paint = wgt.paintEvent
    def paint_no_font(ev):
        pass
    wgt.paintEvent = paint_no_font
server.newConnection.connect(lambda: (server.nextPendingConnection(), wgt.show_and_raise()))
wgt.show()
w("mode=%s shown" % mode)
QTimer.singleShot(15000, app.quit)
rc = app.exec()
w("exec returned %s" % rc)
LOG.close()
