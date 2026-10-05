# -*- coding: utf-8 -*-
import os, sys, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtWidgets import QApplication
from catclock.app import CatClock

app = QApplication(sys.argv)
w = CatClock()
w.show()
app.processEvents()
pm1 = w.grab()
pm1.save("_b5_a.png")
print("grab size:", pm1.width(), pm1.height(), "bg cache:", w._bg_pm is not None,
      "bg size:", w._bg_pm.width(), w._bg_pm.height() if w._bg_pm else None)
# 缓存命中：key 不变应复用同一对象
a = w._bg_pixmap(); b = w._bg_pixmap()
print("cache reused:", a is b)
# hover 变化应失效
w.hover = True; w._bg_invalidate()
c = w._bg_pixmap()
print("hover invalidated:", c is not a)
w.hover = False; w._bg_invalidate()

# 帧率档位
w.cfg["show_sec"] = True
print("work+sec:", w._want_interval("work", False), "rest+sec:", w._want_interval("rest", False))
w.cfg["show_sec"] = False
print("work-nosec:", w._want_interval("work", False), "rest-nosec:", w._want_interval("rest", False),
      "anim:", w._want_interval("rest", True))
print("anim_active default:", w._anim_active())

# 计时：连续 30 次绘制
w.cfg["show_sec"] = True
t = time.perf_counter()
for _ in range(30):
    w.render(app.primaryScreen()) if False else w.update(); app.processEvents()
print("30 frames:", round(time.perf_counter() - t, 3), "s")
w.grab().save("_b5_b.png")
print("OK")
