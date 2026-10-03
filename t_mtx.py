# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"D:\CatClock")
from PyQt6.QtWidgets import QApplication
import cat_clock as cc
app = QApplication([])
print("calling acquire_single...", flush=True)
s = cc.acquire_single()
print("acquire result:", "None" if s is None else "server OK", flush=True)
print("second call:", "None" if cc.acquire_single() is None else "server OK", flush=True)
