# -*- coding: utf-8 -*-
"""通用小弹窗。"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QLineEdit, QLabel,
)

class CatInputDialog(QDialog):
    """统一风格的中文输入对话框（替换系统 QInputDialog 的英文按钮）"""

    def __init__(self, title, label, text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(340)
        layout = QVBoxLayout(self)
        lab = QLabel(label)
        lab.setWordWrap(True)
        layout.addWidget(lab)
        self.edit = QLineEdit(text)
        self.edit.selectAll()
        layout.addWidget(self.edit)
        btns = QHBoxLayout()
        ok = QPushButton("确定")
        cancel = QPushButton("取消")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def value(self):
        return self.edit.text().strip()


class RestDaysDialog(QDialog):
    """每周休息日多选（单休/轮休适用）"""

    NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    def __init__(self, days, parent=None):
        super().__init__(parent)
        self.setWindowTitle("休息日设置")
        self.setFixedWidth(220)
        self.boxes = []
        layout = QVBoxLayout(self)
        for i, n in enumerate(self.NAMES):
            b = QCheckBox(n)
            b.setChecked(i in days)
            self.boxes.append(b)
            layout.addWidget(b)
        btns = QHBoxLayout()
        ok = QPushButton("确定")
        cancel = QPushButton("取消")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def days(self):
        return [i for i, b in enumerate(self.boxes) if b.isChecked()]


# 各物种"头顶以上"的延伸系数（耳朵/角/鸡冠/帽子），半身模式用来自动定尺寸防出界