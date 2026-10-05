# -*- coding: utf-8 -*-
"""美术评审用渲染：21 角色大图（透明底）+ 缩略图测试 + 灰度明度测试 + 剪影测试"""
import sys
sys.path.insert(0, r"D:\CatClock")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QRectF
from PIL import Image
from cat_clock import CHARACTERS, draw_cat, _TOP_EXT

app = QApplication([])

# ---- 1. 角色大图（透明底，半身 + 无道具，纯看造型）----
CELL = 240
cols = 7
rows = (len(CHARACTERS) + cols - 1) // cols
W, H = CELL * cols, CELL * rows
pm = QPixmap(W, H)
pm.fill(Qt.GlobalColor.transparent)
p = QPainter(pm)
p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
names = list(CHARACTERS.keys())
for i, name in enumerate(names):
    ox, oy = (i % cols) * CELL, (i // cols) * CELL
    shape = CHARACTERS[name].get("shape", "cat")
    top = _TOP_EXT.get(shape, 0.64)
    cs = int((CELL - 16) / (top + 1.02))
    ccy = 8 + top * cs
    draw_cat(p, ox + CELL / 2, oy + ccy, cs, CHARACTERS[name], body=True, t=1.2)
    p.setPen(QColor("#666666"))
    p.setFont(QFont("Microsoft YaHei", 11))
    p.drawText(QRectF(ox, oy + CELL - 22, CELL, 18),
               Qt.AlignmentFlag.AlignCenter, name)
p.end()
pm.save(r"D:\CatClock\review_chars.png", "PNG")
print("review_chars.png", W, H)

# ---- 2. 缩略图测试（10%）----
img = Image.open(r"D:\CatClock\review_chars.png")
tw, th = max(1, W // 10), max(1, H // 10)
thumb = img.resize((tw, th), Image.LANCZOS)
# 放大回原尺寸方便查看（保持像素感用 NEAREST）
big = thumb.resize((W // 2, H // 2), Image.NEAREST)
bg = Image.new("RGB", (W // 2, H // 2), (255, 255, 255))
bg.paste(big, (0, 0), big)
bg.save(r"D:\CatClock\review_thumb.png")
print("review_thumb.png", W // 2, H // 2)

# ---- 3. 灰度明度测试 ----
rgba = img.convert("RGBA")
flat = Image.new("RGB", rgba.size, (255, 255, 255))
flat.paste(rgba, (0, 0), rgba)
gray = flat.convert("L")
gray.save(r"D:\CatClock\review_gray.png")
print("review_gray.png ok")

# ---- 4. 剪影测试 ----
a = rgba.split()[3]
sil = Image.new("RGB", rgba.size, (255, 255, 255))
sil.paste((20, 20, 20), (0, 0), a)
sil.save(r"D:\CatClock\review_silhouette.png")
print("review_silhouette.png ok")
