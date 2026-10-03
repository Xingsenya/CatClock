# -*- coding: utf-8 -*-
import sys
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QColor
mode = sys.argv[1]
app = QApplication(sys.argv)
w = QWidget()
w.setWindowTitle("CatClock")
flags = Qt.WindowType.FramelessWindowHint
if mode in ("tool", "full"):
    flags |= Qt.WindowType.Tool
if mode in ("top", "full"):
    flags |= Qt.WindowType.WindowStaysOnTopHint
w.setWindowFlags(flags)
if mode in ("trans", "full"):
    w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
w.resize(300, 120)
def paint(ev):
    p = QPainter(w)
    p.fillRect(w.rect(), QColor(255, 250, 245, 250))
    p.setPen(QColor(200, 100, 100))
    p.drawText(w.rect(), 0, "tick")
    p.end()
w.paintEvent = paint
def tick():
    w.update()
QTimer.singleShot(100, lambda: None)
t = QTimer(); t.timeout.connect(tick); t.start(100)
w.show()
QTimer.singleShot(15000, app.quit)
rc = app.exec()
print("survived", mode, flush=True)
