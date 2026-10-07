# -*- coding: utf-8 -*-
"""新旧并排对比图：把 _old.png 与 _fixed.png 左右拼起来"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt

app = QApplication([])

old = QPixmap(sys.argv[1])
new = QPixmap(sys.argv[2])
out = sys.argv[3]

W = old.width() + new.width() + 80
H = max(old.height(), new.height()) + 60
pm = QPixmap(W, H)
pm.fill(QColor(250, 250, 250))
p = QPainter(pm)
p.setFont(QFont("Microsoft YaHei", 20))
p.setPen(QColor(80, 80, 80))
p.drawText(20, 40, "旧版 (v1.4)")
p.drawText(60 + old.width(), 40, "修复后 (v1.5.1)")
p.drawPixmap(20, 60, old)
p.drawPixmap(60 + old.width(), 60, new)
p.end()
pm.save(out)
print("saved", out)
