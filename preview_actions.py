# 渲染动作 / 配饰 / 节日道具预览
import sys
sys.path.insert(0, "D:/CatClock")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPainter, QColor, QPixmap, QFont
from PyQt6.QtCore import QRectF
from catclock.data import CHARACTERS
from catclock.draw import draw_cat

app = QApplication(sys.argv)
CELL = 190
ROWS = [
    ("动作", [(dict(action=a, action_k=0.6), a) for a in
             ("stretch", "yawn", "wave", "tail_wag", "sneeze", "spin")]),
    ("配饰", [(dict(acc=a), a) for a in ("none", "glasses", "sunglasses", "headphones", "bowtie")]),
    ("道具", [(dict(prop=a), a) for a in ("coffee", "coin", "heart", "bag", "umbrella")]),
]
W = CELL * 6
H = CELL * len(ROWS) + 40
img = QPixmap(W, H)
img.fill(QColor("#E8EAF2"))
p = QPainter(img)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
p.setFont(QFont("Microsoft YaHei", 11))
colors = CHARACTERS["橘猫"]
y0 = 20
for r, (title, items) in enumerate(ROWS):
    p.setPen(QColor("#666666"))
    p.drawText(QRectF(6, y0 + r * CELL + 12, 120, 24), 0x0004, title)
    for i, (kw, label) in enumerate(items):
        cx = i * CELL + CELL // 2
        draw_cat(p, cx, y0 + r * CELL + CELL // 2 + 6, 105, colors,
                 body=True, hat="none", t=0.0, **kw)
        p.setPen(QColor("#333333"))
        p.drawText(QRectF(i * CELL, y0 + r * CELL + CELL - 26, CELL, 22), 0x0004, label)
p.end()
img.save("D:/CatClock/preview_actions.png")
print("saved", img.width(), img.height())
