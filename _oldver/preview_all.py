# -*- coding: utf-8 -*-
"""渲染 6 角色 x 5 样式 预览图 preview.png"""
import sys
sys.path.insert(0, r"D:\CatClock")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient, QPen, QPainterPath
from PyQt6.QtCore import Qt, QRectF
from catclock.data import CHARACTERS, STYLES, _TOP_EXT
from catclock.draw import draw_cat
from catclock.util import rr

app = QApplication([])
CELL_W, CELL_H = 300, 140
cols = list(STYLES.keys())
rows = list(CHARACTERS.keys())
W, H = CELL_W * len(cols), CELL_H * len(rows)
pm = QPixmap(W, H)
pm.fill(QColor("#E8E4E0"))
p = QPainter(pm)
p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

for r, cname in enumerate(rows):
    for c, sname in enumerate(cols):
        ox, oy = c * CELL_W, r * CELL_H
        st = STYLES[sname]
        # 面板
        g = QLinearGradient(0, oy + 12, 0, oy + CELL_H - 12)
        g.setColorAt(0, QColor(*st["panel0"]))
        g.setColorAt(1, QColor(*st["panel1"]))
        p.setBrush(g)
        p.setPen(QPen(QColor(*st["border"], 200), 1.2))
        p.drawPath(rr(ox + 10, oy + 12, CELL_W - 20, CELL_H - 24, 20))
        # 猫（半身模式）
        shape = CHARACTERS[cname].get("shape", "cat")
        top = _TOP_EXT.get(shape, 0.64)
        cs = int((CELL_H - 14) / (top + 1.02))
        ccy = 7 + top * cs
        draw_cat(p, ox + 58, oy + ccy, cs, CHARACTERS[cname],
                 body=True, prop="coffee", t=1.2, dim25=True)
        # 文字示例
        p.setPen(QColor(st["text"]))
        p.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        p.drawText(QRectF(ox + 105, oy + 30, 180, 30), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "02:10:37")
        p.setPen(QColor(st["sub"]))
        p.setFont(QFont("Microsoft YaHei", 8))
        p.drawText(QRectF(ox + 105, oy + 62, 180, 18), Qt.AlignmentFlag.AlignLeft, "%s / %s" % (cname, sname))
        # 进度条
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(*st["bar_bg"]))
        p.drawPath(rr(ox + 105, oy + 92, 130, 6, 3))
        gg = QLinearGradient(ox + 105, 0, ox + 235, 0)
        gg.setColorAt(0, QColor(*st["bar0"]))
        gg.setColorAt(1, QColor(*st["bar1"]))
        p.setBrush(gg)
        p.drawPath(rr(ox + 105, oy + 92, 96, 6, 3))

p.end()
pm.save(r"D:\CatClock\preview.png", "PNG")
print("preview saved", W, H)
