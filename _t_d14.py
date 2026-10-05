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
keys = ["none", "glasses", "sunglasses", "headphones", "bowtie"]
size = 130
pm = QPixmap(len(keys) * size, size)
pm.fill(Qt.GlobalColor.transparent)
p = QPainter(pm)
p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
for i, k in enumerate(keys):
    draw_cat(p, size * i + size // 2, size // 2 + 10, 80, CHARACTERS["橘猫"], acc=k)
p.end()
pm.save("_preview_acc.png")
print("saved _preview_acc.png")
