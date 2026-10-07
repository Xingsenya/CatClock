# -*- coding: utf-8 -*-
"""F1：全角色 × 多状态对照图。

改五官（眼睛 / 鼻子 / 嘴 / 胡须 / 尾巴）时，12 生肖 + 8 种猫 + 熊猫共 21 个角色
很容易只顾着改好橘猫、把别的物种改歪。这个脚本把全部角色按状态铺成一张大图，
一眼就能比对。

用法：
    python tools/characters.py                 # 输出到项目根 characters.png
    python tools/characters.py --cols 5        # 每行 5 个角色
    python tools/characters.py --out shots/a.png

状态（列）：睁眼 / 半闭(犯困) / 闭眼(眨眼) / 开心(星星眼) / 说话(张嘴) / 笑 / 不开心
"""
import argparse
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from catclock.data import CHARACTERS
from catclock.draw import draw_cat
from catclock.util import font

# (列名, draw_cat 的额外参数)
STATES = (
    ("睁眼",   dict()),
    ("犯困",   dict(eye_lid=0.48)),
    ("眨眼",   dict(eye_lid=1.0)),
    ("开心",   dict(excited=True)),
    ("说话",   dict(mouth_open=0.8)),
    ("笑",     dict(mouth="smile")),
    ("不开心", dict(mouth="frown")),
)


def render(out_path, cols=4, cell=150, chars=None):
    names = chars or list(CHARACTERS.keys())
    rows = (len(names) + cols - 1) // cols
    nst = len(STATES)

    cw = cell * nst
    ch = cell + 22                       # 顶部留出角色名
    W = cols * cw + 8
    H = rows * ch + 8

    pm = QPixmap(W, H)
    pm.fill(QColor("#F6F2EA"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setFont(font("Microsoft YaHei", 11))

    for i, name in enumerate(names):
        gx = 4 + (i % cols) * cw
        gy = 4 + (i // cols) * ch
        p.setPen(QColor("#4A4038"))
        p.drawText(QRectF(gx + 4, gy + 2, cw - 8, 18), Qt.AlignmentFlag.AlignLeft, name)
        for j, (label, kw) in enumerate(STATES):
            x = gx + j * cell + cell / 2.0
            y = gy + 22 + cell * 0.52
            p.save()
            draw_cat(p, x, y, cell * 0.62, CHARACTERS[name],
                     tail_phase=0.6, t=0.0, body=True, **kw)
            p.restore()
            p.setPen(QColor("#9A9088"))
            p.setFont(font("Microsoft YaHei", 9))
            p.drawText(QRectF(gx + j * cell, gy + ch - 14, cell, 13),
                       Qt.AlignmentFlag.AlignCenter, label)
            p.setFont(font("Microsoft YaHei", 11))
    p.end()
    pm.save(out_path)
    return out_path, (W, H)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--cell", type=int, default=150)
    ap.add_argument("--only", default=None, help="只画指定角色，逗号分隔，如 橘猫,黑猫")
    a = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = a.out or os.path.join(root, "characters.png")
    chars = [x.strip() for x in a.only.split(",")] if a.only else None

    app = QApplication([])
    path, (w, h) = render(out, a.cols, a.cell, chars)
    print("[characters] %d 角色 x %d 状态 -> %s (%dx%d)"
          % (len(chars or CHARACTERS), len(STATES), path, w, h))


if __name__ == "__main__":
    main()
