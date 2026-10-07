# -*- coding: utf-8 -*-
"""把某个版本的猫渲染成大图，用于新旧对比。用法：python tools/_cmp_render.py <root> <out.png>"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
root = sys.argv[1]
out = sys.argv[2]
sys.path.insert(0, root)

from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtGui import QPainter, QPixmap, QColor, QFont  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402

app = QApplication([])

import catclock.data as D  # noqa: E402
from catclock.draw import draw_cat  # noqa: E402
from catclock.util import font  # noqa: E402

S = 150
COLS = ["橘猫", "黑猫", "熊猫"]
ROWS = [
    ("正常", dict()),
    ("眨眼", dict(eye_lid=1.0)),
    ("半闭眼", dict(eye_lid=0.48)),
    ("开心", dict(excited=True)),
]
PAD = 20
LAB = 26
CW = int(S * 2.4)
CH = int(S * 2.4)
W = PAD + len(COLS) * (CW + PAD)
H = LAB + len(ROWS) * (CH + LAB)

pm = QPixmap(W, H)
pm.fill(QColor(246, 244, 240))
p = QPainter(pm)
p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
p.setFont(QFont(font("Microsoft YaHei", 12)))
p.setPen(QColor(120, 120, 120))
for j, c in enumerate(COLS):
    p.drawText(PAD + j * (CW + PAD), 6, CW, LAB, Qt.AlignmentFlag.AlignLeft, c)
for i, (name, kw) in enumerate(ROWS):
    y0 = LAB + i * (CH + LAB)
    p.drawText(4, y0, PAD, CH, Qt.AlignmentFlag.AlignLeft, name)
    for j, c in enumerate(COLS):
        x = PAD + j * (CW + PAD) + CW // 2
        y = y0 + int(CH * 0.52)
        draw_cat(p, x, y, S, D.CHARACTERS[c], body=True, prop="none", hat="none", t=0.0, **kw)
p.end()
pm.save(out)
print("saved", out, W, "x", H)
