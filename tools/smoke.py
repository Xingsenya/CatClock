# -*- coding: utf-8 -*-
"""D2：CatClock 一键冒烟。

    python tools/smoke.py              # 编译检查 + 渲染 preview_states.png
    python tools/smoke.py --exe        # 额外跑 dist/CatClock.exe 15 秒
    python tools/smoke.py --out x.png  # 指定预览图输出路径
"""
import os
import sys
import subprocess
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PY = sys.executable
OUT = os.path.join(ROOT, "preview_states.png")

CASES = [
    ("none", "无语录"),
    ("quote", "语录-单行"),
    ("quote2", "语录-两行"),
    ("hydrate", "喝水提醒"),
    ("meow", "摸猫"),
    ("rush", "下班前冲刺"),
]


def compile_all():
    mods = ["app", "draw", "data", "util", "settings", "quotes", "sense",
            "festival", "mood", "report", "stats", "update", "llm", "weather"]
    r = subprocess.run([PY, "-m", "py_compile"] +
                       [os.path.join(ROOT, "catclock", m + ".py") for m in mods],
                       capture_output=True, text=True)
    print("[compile]", "OK" if r.returncode == 0 else "FAIL")
    if r.returncode:
        print(r.stderr[-2000:])
    return r.returncode == 0


def render(out):
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QPainter, QPixmap, QColor
    from PyQt6.QtCore import QPoint
    from catclock.app import CatClock

    app = QApplication([])

    def mk(kind):
        w = CatClock()
        w.cfg["mini"] = False
        w.cfg["scale"] = 1.0
        w.apply_size()
        n = datetime.now()
        w._status = lambda: ("work", n.replace(hour=9, minute=0),
                             n.replace(hour=18, minute=0), 3600, 0.5)
        w.hydrate_t = w.hourly_t = w.meow_bubble_t = w.bubble_t = 9.0
        w.meow_t, w.afk, w.bubble_text = 0.0, False, ""
        if kind == "none":
            w._quote = lambda: None
        elif kind == "quote":
            w._quote = lambda: "加油，快下班了"
        elif kind == "quote2":
            w._quote = lambda: "再坚持一下，马上就能下班回家摸鱼啦"
        elif kind == "hydrate":
            w.hydrate_t = 1.0
        elif kind == "meow":
            w.meow_bubble_t = 1.0
        elif kind == "rush":
            w._quote = lambda: "要下班啦，收东西咯～"
            w._start_action("pack", 3.0)
            w.action_k = 0.4
        return w

    ws = [mk(k) for k, _ in CASES]
    W, H = ws[0].width(), ws[0].height()
    canvas = QPixmap(W * len(ws), H)
    canvas.fill(QColor(60, 70, 90))
    p = QPainter(canvas)
    for i, w in enumerate(ws):
        w.render(p, QPoint(i * W, 0))
    p.end()
    canvas.save(out)
    print("[render] %dx%d -> %s" % (W * len(ws), H, out))
    print("[states] " + " | ".join(n for _, n in CASES))


def smoke_exe(secs=15):
    exe = os.path.join(ROOT, "dist", "CatClock.exe")
    if not os.path.exists(exe):
        print("[exe] 未找到 %s（先打包）" % exe)
        return False
    proc = subprocess.Popen([exe], cwd=ROOT)
    try:
        code = proc.wait(timeout=secs)
        print("[exe] 提前退出 code=%s" % code)
        return code == 0
    except subprocess.TimeoutExpired:
        proc.kill()
        print("[exe] 运行 %ds 正常，已结束" % secs)
        return True


def main():
    ok = compile_all()
    try:
        render(sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else OUT)
    except Exception as e:
        print("[render] FAIL", e)
        ok = False
    if "--exe" in sys.argv:
        ok = smoke_exe() and ok
    print("[result]", "ALL OK" if ok else "HAS FAILURE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
