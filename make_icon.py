# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap
from PIL import Image
from cat_clock import make_icon

app = QApplication([])
icon = make_icon(128)
pm = icon.pixmap(128, 128)
pm.save(r"D:\CatClock\cat.png", "PNG")
img = Image.open(r"D:\CatClock\cat.png")
img.save(r"D:\CatClock\cat.ico", format="ICO", sizes=[(16,16),(32,32),(48,48),(64,64),(128,128)])
print("ico created", img.size)
