# -*- coding: utf-8 -*-
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtWidgets import QApplication
from catclock.util import load_cfg
from catclock.settings import SettingsDialog

app = QApplication(sys.argv)
cfg = load_cfg()
cfg.update({"char": "奶牛猫", "hat": "crown", "scale": 1.4, "city": "上海闵行区",
            "payday": 15, "rest_days": [5, 6], "mini": False, "top": True})
dlg = SettingsDialog(cfg, None)
print("tabs:", dlg.tabs.count(), [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())])
r = dlg.result()
for k in ("char", "style", "hat", "scale", "start", "end", "rest_days", "payday", "city", "check_update", "count_over"):
    print(" ", k, "=", r[k])
# 改几个值再取一次
dlg.c_hat.setCurrentIndex(dlg.c_hat.findData("straw"))
dlg.k_25d.setChecked(True)
dlg.e_start.setText("10:30")
dlg.e_end.setText("19:00")
dlg.rest_boxes[4].setChecked(False)
r2 = dlg.result()
print("changed ->", r2["hat"], r2["dim25"], r2["start"], r2["end"], r2["rest_days"])
# 非法时间回退
dlg.e_start.setText("99:99")
print("bad time fallback ->", dlg.result()["start"])
