# -*- coding: utf-8 -*-
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from catclock.app import CatClock

app = QApplication(sys.argv)
w = CatClock()
w.cfg["show_sec"] = False
w.cfg["start"] = "23:00"
w.cfg["end"] = "23:01"
# simulate rest phase
w.cfg["rest_days"] = [0,1,2,3,4,5,6]
w.show()
w._tick()
print("interval after tick:", w.timer.interval(), "ms", "lowfps:", w.lowfps)
# force anim
w.idle = ("yawn", w.t0)
w._tick()
print("with idle interval:", w.timer.interval(), "lowfps:", w.lowfps)
w.idle = None
w.hover = True
w._tick()
print("with hover interval:", w.timer.interval(), "lowfps:", w.lowfps)
print("OK")
