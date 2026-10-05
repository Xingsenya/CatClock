# -*- coding: utf-8 -*-
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt
from catclock.draw import draw_cat
from catclock.data import CHARACTERS

app = QApplication(sys.argv)
keys = [("yawn", 0.5), ("yawn", 1.0), ("stretch", 0.6), ("wave", 0.5), ("tail_wag", 0.6)]
size = 170
pm = QPixmap(len(keys) * size, size)
pm.fill(Qt.GlobalColor.transparent)
p = QPainter(pm)
p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
for i, (act, ak) in enumerate(keys):
    draw_cat(p, size * i + size // 2, size // 2 + 10, 80, CHARACTERS["橘猫"],
             action=act, action_k=ak, body=True, t=0.0)
p.end()
pm.save("_preview_actions.png")
print("saved _preview_actions.png")
