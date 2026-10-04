# 渲染所有帽型预览：橘猫戴 6 款帽子
import sys
sys.path.insert(0, "D:/CatClock")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPainter, QColor, QPixmap, QFont
from PyQt6.QtCore import QRectF
from cat_clock import draw_cat, CHARACTERS

HATS = [("auto", "auto"), ("none", "none"), ("cap", "cap"), ("beanie", "beanie"),
        ("beret", "beret"), ("straw", "straw"), ("party", "party"), ("crown", "crown")]

app = QApplication(sys.argv)
W, H = 200 * len(HATS), 250
img = QPixmap(W, H)
img.fill(QColor("#E8EAF2"))
p = QPainter(img)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
p.setFont(QFont("Microsoft YaHei", 11))
colors = CHARACTERS["橘猫"]
for i, (key, style) in enumerate(HATS):
    cx = i * 200 + 100
    draw_cat(p, cx, 135, 120, colors, hat=key, body=True)
    p.setPen(QColor("#333333"))
    p.drawText(QRectF(i * 200, 220, 200, 26), 0x0004, style)
p.end()
img.save("D:/CatClock/preview_hats.png")
print("saved", img.width(), img.height())
