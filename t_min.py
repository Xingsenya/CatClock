# -*- coding: utf-8 -*-
import sys
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import QTimer
print("start", flush=True)
app = QApplication(sys.argv)
w = QWidget(); w.setWindowTitle("CatClock"); w.resize(300, 100); w.show()
QTimer.singleShot(10000, app.quit)
rc = app.exec()
print("exec returned", rc, flush=True)
