# -*- coding: utf-8 -*-
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtWidgets import QApplication
from catclock.app import CatClock

app = QApplication(sys.argv)
w = CatClock()
print("menu items:", [a.text() for a in w.menu.actions() if not a.menu() and not a.isSeparator()])
print("menu submenus:", [a.text() for a in w.menu.actions() if a.menu()])
old = dict(w.cfg)
w.cfg.update({"char": "三花猫", "hat": "straw", "scale": 1.2, "dim25": True,
              "mini": False, "top": True, "city": ""})
w._apply_cfg(old)
print("char act checked:", w.char_actions["三花猫"].isChecked(),
      "| 橘猫:", w.char_actions["橘猫"].isChecked())
print("hat straw:", w.hat_actions["straw"].isChecked(), "| auto:", w.hat_actions["auto"].isChecked())
print("size 120%:", w.size_actions[120].isChecked(), "| 100%:", w.size_actions[100].isChecked())
print("dim25 act:", w.act_25d.isChecked(), "| body act:", w.act_body.isChecked())
print("size now:", w.width(), "x", w.height())
print("OK")
