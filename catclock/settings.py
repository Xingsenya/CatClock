# -*- coding: utf-8 -*-
"""分组设置窗口：外观 / 时间 / 通知 / 天气 / 智能 / 高级 六个标签页。

用法：
    dlg = SettingsDialog(cfg, app)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        cfg.update(dlg.result())
"""
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QComboBox, QCheckBox, QLineEdit, QSpinBox, QLabel, QPushButton,
    QMessageBox, QFileDialog, QScrollArea, QFrame, QApplication,
)

from . import data as D
from .util import CONFIG_DIR, CONFIG_PATH, autostart_enabled
from . import stats
from . import quotes as Q
from . import sense as SENSE
from . import festival as F
from . import mood as M
from . import report
from . import llm


def _row(*widgets):
    """一行布局：自动加 stretch"""
    h = QHBoxLayout()
    for w in widgets:
        if w is None:
            h.addStretch(1)
        elif isinstance(w, int):
            h.addSpacing(w)
        else:
            h.addWidget(w)
    h.addStretch(1)
    return h


class SettingsDialog(QDialog):
    """统一的设置窗口，替代越来越长的右键菜单。"""

    WEEK = ["一", "二", "三", "四", "五", "六", "日"]

    def __init__(self, cfg, app=None, parent=None, on_preview=None, on_cancel=None):
        super().__init__(parent or app)
        self.cfg = dict(cfg)
        self.app = app
        self._preview_fn = on_preview
        self._cancel_fn = on_cancel
        self._snap = None
        self.setWindowTitle("CatClock 设置")
        self.setMinimumWidth(430)
        # B1：设置窗口限制高度，小屏下自动出现滚动条
        scr = QApplication.primaryScreen()
        sh = scr.availableGeometry().height() if scr else 768
        self.setMaximumHeight(int(sh * 0.88))
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._scroll(self._tab_look()), "外观")
        self.tabs.addTab(self._scroll(self._tab_time()), "时间")
        self.tabs.addTab(self._scroll(self._tab_notify()), "通知")
        self.tabs.addTab(self._scroll(self._tab_weather()), "天气")
        self.tabs.addTab(self._scroll(self._tab_smart()), "智能")
        self.tabs.addTab(self._scroll(self._tab_adv()), "高级")

        btns = QHBoxLayout()
        ok = QPushButton("确定")
        cancel = QPushButton("取消")
        ok.setDefault(True)
        ok.clicked.connect(self._on_ok)
        cancel.clicked.connect(self.reject)
        self._connect_preview()
        btns.addStretch(1)
        btns.addWidget(ok)
        btns.addWidget(cancel)

        root = QVBoxLayout(self)
        root.addWidget(self.tabs)
        root.addLayout(btns)

    def _scroll(self, widget):
        """B1：把标签页内容包在滚动区域里，避免 768 屏装不下智能页。"""
        sa = QScrollArea(self)
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setWidget(widget)
        return sa

    # ---------------------------------------------------------------- 外观
    def _tab_look(self):
        w = QWidget()
        v = QVBoxLayout(w)

        g1 = QGroupBox("角色")
        f = QFormLayout(g1)
        self.c_char = QComboBox()
        self.c_char.addItems(list(D.CHARACTERS))
        self.c_char.setCurrentText(str(self.cfg.get("char", "橘猫")))
        f.addRow("角色：", self.c_char)

        self.c_style = QComboBox()
        self.c_style.addItems(list(D.STYLES))
        self.c_style.setCurrentText(str(self.cfg.get("style", "奶油")))
        f.addRow("配色：", self.c_style)

        self.c_hat = QComboBox()
        for key, name in D.HATS:
            self.c_hat.addItem(name, key)
        idx = self.c_hat.findData(str(self.cfg.get("hat", "auto")))
        self.c_hat.setCurrentIndex(max(0, idx))
        f.addRow("帽子：", self.c_hat)

        self.c_acc = QComboBox()
        for key, name in D.ACCS:
            self.c_acc.addItem(name, key)
        idx = self.c_acc.findData(str(self.cfg.get("acc", "auto")))
        self.c_acc.setCurrentIndex(max(0, idx))
        f.addRow("配饰：", self.c_acc)

        self.c_size = QComboBox()
        for pct in D.SIZES:
            self.c_size.addItem("%d%%" % pct, pct / 100.0)
        cur = float(self.cfg.get("scale", 1.0))
        best, bd = 0, 9e9
        for i in range(self.c_size.count()):
            d = abs(self.c_size.itemData(i) - cur)
            if d < bd:
                best, bd = i, d
        self.c_size.setCurrentIndex(best)
        f.addRow("大小：", self.c_size)
        v.addWidget(g1)

        g2 = QGroupBox("显示")
        v2 = QVBoxLayout(g2)
        self.k_body = self._chk("半身小猫（身体 + 状态道具）", "body", True)
        self.k_25d = self._chk("2.5D 立体效果", "dim25", False)
        self.k_mini = self._chk("迷你模式（只显示猫和时间）", "mini", False)
        self.k_sec = self._chk("显示秒", "show_sec", True)
        self.k_top = self._chk("始终显示在最前", "top", True)
        for b in (self.k_body, self.k_25d, self.k_mini, self.k_sec, self.k_top):
            v2.addWidget(b)
        v.addWidget(g2)

        tip = QLabel("提示：在窗口上滚轮可直接缩放，双击可切换秒显示。")
        tip.setStyleSheet("color:#9A8B80; font: 9pt 'Microsoft YaHei';")
        v.addWidget(tip)
        v.addStretch(1)
        return w

    # ---------------------------------------------------------------- 时间
    def _tab_time(self):
        w = QWidget()
        v = QVBoxLayout(w)

        g = QGroupBox("工作时间")
        f = QFormLayout(g)
        self.e_start = QLineEdit(str(self.cfg.get("start", "09:00")))
        self.e_end = QLineEdit(str(self.cfg.get("end", "18:00")))
        self.e_start.setPlaceholderText("09:00")
        self.e_end.setPlaceholderText("18:00")
        self.e_start.setFixedWidth(90)
        self.e_end.setFixedWidth(90)
        f.addRow("上班时间：", self.e_start)
        f.addRow("下班时间：", self.e_end)
        v.addWidget(g)

        g2 = QGroupBox("每周休息日（休息日不倒计时，猫猫陪你摆烂）")
        h = QHBoxLayout(g2)
        self.rest_boxes = []
        days = self.cfg.get("rest_days", [5, 6]) or []
        for i, n in enumerate(self.WEEK):
            b = QCheckBox("周" + n)
            b.setChecked(i in days)
            self.rest_boxes.append(b)
            h.addWidget(b)
        h.addStretch(1)
        v.addWidget(g2)

        g3 = QGroupBox("发薪日")
        f3 = QFormLayout(g3)
        self.s_pay = QSpinBox()
        self.s_pay.setRange(0, 31)
        self.s_pay.setSpecialValueText("不显示")
        self.s_pay.setValue(int(self.cfg.get("payday", 0) or 0))
        self.s_pay.setFixedWidth(90)
        f3.addRow("每月几号发工资：", self.s_pay)
        v.addWidget(g3)
        v.addStretch(1)
        return w

    # ---------------------------------------------------------------- 通知
    def _tab_notify(self):
        w = QWidget()
        v = QVBoxLayout(w)

        g = QGroupBox("提醒")
        vv = QVBoxLayout(g)
        self.k_noff = self._chk("下班时通知", "notify_off", True)
        self.k_nwork = self._chk("上班时提醒", "notify_work", True)
        self.k_pre = self._chk("下班前预告（30 / 10 分钟）", "notify_pre", True)
        self.k_hyd = self._chk("每小时久坐提醒", "hydrate", True)
        self.k_sound = self._chk("提示音", "sound", True)
        for b in (self.k_noff, self.k_nwork, self.k_pre, self.k_hyd, self.k_sound):
            vv.addWidget(b)
        v.addWidget(g)

        g2 = QGroupBox("摸鱼")
        v2 = QVBoxLayout(g2)
        self.k_afk = self._chk("离开电脑时猫猫打瞌睡", "afk", True)
        v2.addWidget(self.k_afk)
        v.addWidget(g2)
        v.addStretch(1)
        return w

    # ---------------------------------------------------------------- 天气
    def _tab_weather(self):
        w = QWidget()
        v = QVBoxLayout(w)

        g = QGroupBox("天气城市")
        f = QFormLayout(g)
        self.e_city = QLineEdit(str(self.cfg.get("city", "")))
        self.e_city.setPlaceholderText("留空则不显示天气，如：上海闵行区")
        btn_r = QPushButton("立即刷新")
        btn_r.setFixedWidth(90)
        btn_r.clicked.connect(self._refresh_weather)
        row = QHBoxLayout()
        row.addWidget(self.e_city, 1)
        row.addWidget(btn_r)
        fw = QWidget()
        fw.setLayout(row)
        f.addRow("城市：", fw)
        v.addWidget(g)

        self.lab_wx = QLabel(self._wx_text())
        self.lab_wx.setWordWrap(True)
        self.lab_wx.setStyleSheet("color:#9A8B80; font: 9pt 'Microsoft YaHei';")
        v.addWidget(self.lab_wx)
        v.addStretch(1)
        return w

    def _wx_text(self):
        w = getattr(self.app, "weather", None) if self.app else None
        if not w:
            return "当前天气：暂无数据（设置城市后会自动拉取，也可点「立即刷新」）"
        txt = "当前天气：%s %s %s°C" % (w.get("city", ""), w.get("text", ""), w.get("temp", ""))
        if w.get("aqi_text"):
            txt += " · %s" % w["aqi_text"]
        if w.get("dress"):
            txt += "\n穿衣建议：%s" % w["dress"]
        return txt

    def _refresh_weather(self):
        self.cfg["city"] = self.e_city.text().strip()
        if self.app:
            try:
                self.app.cfg["city"] = self.cfg["city"]
                from .util import save_cfg
                save_cfg(self.app.cfg)
                self.app.weather = None
                self.app.refresh_weather()
            except Exception:
                pass
        self.lab_wx.setText(self._wx_text())

    # ---------------------------------------------------------------- 智能
    def _tab_smart(self):
        w = QWidget()
        v = QVBoxLayout(w)

        # 1 情境感知
        g = QGroupBox("情境感知（应用 / 会议 / 忙碌度 / 电量 / CPU）")
        vv = QVBoxLayout(g)
        self.k_ctx = self._chk("开启情境感知（猫会根据你在干什么换台词）",
                               "context_aware", True)
        vv.addWidget(self.k_ctx)
        self.lab_sense = QLabel("")
        self.lab_sense.setWordWrap(True)
        self.lab_sense.setStyleSheet("color:#9A8B80; font: 9pt 'Microsoft YaHei';")
        vv.addWidget(self.lab_sense)
        b_now = QPushButton("刷新")
        b_now.clicked.connect(self._refresh_sense)
        vv.addWidget(b_now)
        v.addWidget(g)

        # 4 交互增强
        g2 = QGroupBox("交互")
        v2 = QVBoxLayout(g2)
        self.k_dock = self._chk("拖到屏幕边缘自动吸附（悬停滑出）", "edge_dock", True)
        self.k_boss = self._chk("老板键 Ctrl+Alt+H 一键隐身", "boss_key", True)
        self.k_surp = self._chk("随机小惊喜（打喷嚏 / 追尾巴 / 掉金币）",
                                "surprise", True)
        for b in (self.k_dock, self.k_boss, self.k_surp):
            v2.addWidget(b)
        v.addWidget(g2)

        # 3 心情打卡
        g3 = QGroupBox("心情打卡")
        v3 = QVBoxLayout(g3)
        self.k_mood = self._chk("每天工作时段提醒一次打卡", "mood_daily", True)
        v3.addWidget(self.k_mood)
        hm = QHBoxLayout()
        for sc in (2, 1, 0):
            b = QPushButton("%s %s" % (M.SCORE_FACE[sc], M.SCORE_TEXT[sc]))
            b.clicked.connect(lambda _, v=sc: self._pick_mood(v))
            hm.addWidget(b)
        hm.addStretch(1)
        v3.addLayout(hm)
        self.lab_mood = QLabel(self._mood_text())
        self.lab_mood.setWordWrap(True)
        self.lab_mood.setStyleSheet("color:#9A8B80; font: 9pt 'Microsoft YaHei';")
        v3.addWidget(self.lab_mood)
        v.addWidget(g3)

        # 6 节日皮肤
        g4 = QGroupBox("节日皮肤（自动生效，无需设置）")
        v4 = QVBoxLayout(g4)
        f = F.today_festival()
        v4.addWidget(QLabel("今天：%s" % (f["name"] if f else "不是节日")))
        lab_f = QLabel("、".join("%d/%d %s" % (m, d, n)
                                for m, d, n, _ in F.all_festivals()))
        lab_f.setWordWrap(True)
        lab_f.setStyleSheet("color:#9A8B80; font: 9pt 'Microsoft YaHei';")
        v4.addWidget(lab_f)
        v.addWidget(g4)

        # 12 Qwen 个性化语录
        g5 = QGroupBox("Qwen 个性化语录（可选，需要 API Key）")
        v5 = QVBoxLayout(g5)
        self.k_llm = QCheckBox("启用 AI 生成每日语录（离线自动回退内置语录）")
        self.e_key = QLineEdit()
        self.e_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.e_key.setPlaceholderText("sk-…（只保存在本机 %APPDATA%）")
        self.e_model = QLineEdit()
        self.e_model.setPlaceholderText("qwen-plus")
        _c = llm._cfg()
        self.k_llm.setChecked(bool(_c.get("enabled")))
        self.e_key.setText(_c.get("api_key", ""))
        self.e_model.setText(_c.get("model", "qwen-plus"))
        f5 = QFormLayout()
        f5.addRow("", self.k_llm)
        f5.addRow("API Key：", self.e_key)
        f5.addRow("模型：", self.e_model)
        v5.addLayout(f5)
        h5 = QHBoxLayout()
        b_test = QPushButton("保存并试生成")
        b_test.clicked.connect(self._test_llm)
        h5.addWidget(b_test)
        h5.addStretch(1)
        v5.addLayout(h5)
        self.lab_llm = QLabel("")
        self.lab_llm.setWordWrap(True)
        self.lab_llm.setStyleSheet("color:#9A8B80; font: 9pt 'Microsoft YaHei';")
        v5.addWidget(self.lab_llm)
        v.addWidget(g5)

        v.addStretch(1)
        self._refresh_sense()
        return w

    # ---------------------------------------------------------------- 实时预览（B2）
    def _connect_preview(self):
        """外观相关改动实时同步到挂件，取消时回滚。"""
        if not self._preview_fn:
            return
        self.c_char.currentTextChanged.connect(self._emit_preview)
        self.c_style.currentTextChanged.connect(self._emit_preview)
        for w in (self.c_hat, self.c_acc, self.c_size):
            w.currentIndexChanged.connect(self._emit_preview)
        for w in (self.k_body, self.k_25d, self.k_mini, self.k_sec, self.k_top):
            w.stateChanged.connect(self._emit_preview)

    def _snapshot(self):
        if self._snap is None:
            self._snap = dict(self.cfg)

    def _emit_preview(self):
        if not self._preview_fn:
            return
        self._snapshot()
        self._preview_fn(self._preview_delta())

    def _preview_delta(self):
        """只返回可安全实时预览的键（避免触发天气/注册表/位置重置）。"""
        return {
            "char": self.c_char.currentText(),
            "style": self.c_style.currentText(),
            "hat": self.c_hat.currentData(),
            "acc": self.c_acc.currentData(),
            "scale": float(self.c_size.currentData()),
            "body": self.k_body.isChecked(),
            "dim25": self.k_25d.isChecked(),
            "mini": self.k_mini.isChecked(),
            "show_sec": self.k_sec.isChecked(),
            "top": self.k_top.isChecked(),
        }

    def reject(self):
        """取消 / 点 × 时回滚已预览的改动。"""
        if self._cancel_fn:
            self._cancel_fn()
        super().reject()

    def _refresh_sense(self):
        try:
            s = SENSE.sample(force=True)
            label = SENSE.scene_label(s.get("scene", "other")) or "（普通使用）"
            bits = ["当前：%s（%s）" % (label, s.get("app") or "未知程序")]
            if s.get("fullscreen"):
                bits.append("全屏中")
            bits.append("忙碌度 %d%%" % int(s.get("busy", 0) * 100))
            bits.append("CPU %d%%" % int(s.get("cpu", 0)))
            if s.get("battery", 255) <= 100:
                bits.append("电量 %d%%%s" % (s["battery"],
                                             "" if s.get("ac") else "（未插电）"))
            self.lab_sense.setText("，".join(bits))
        except Exception as e:
            self.lab_sense.setText("读取失败：%s" % e)

    def _mood_text(self):
        try:
            t = M.today()
            head = "今天：%s" % (M.SCORE_TEXT.get(t, "还没打卡") if t is not None
                                else "还没打卡")
            return head + "\n近 14 天：" + M.curve_text(14) + "\n" + M.insight()
        except Exception as e:
            return "读取失败：%s" % e

    def _pick_mood(self, score):
        try:
            M.set_today(score)
            self.lab_mood.setText(self._mood_text())
        except Exception:
            pass

    def _test_llm(self):
        key = self.e_key.text().strip()
        model = self.e_model.text().strip() or "qwen-plus"
        enable = self.k_llm.isChecked()
        if not llm.save_cfg(enable, key, model):
            self.lab_llm.setText("保存失败，检查配置目录权限")
            return
        if not enable or not key:
            self.lab_llm.setText("已保存（未启用）")
            return
        self.lab_llm.setText("正在生成…")
        from datetime import datetime
        ctx = {"desc": datetime.now().strftime("%m月%d日 %H:%M 工作日")}
        lines = llm.generate(ctx)
        self.lab_llm.setText("示例：" + " / ".join(lines) if lines
                             else "生成失败：检查 API Key、模型名或网络")

    # ---------------------------------------------------------------- 高级
    def _tab_adv(self):
        w = QWidget()
        v = QVBoxLayout(w)

        g = QGroupBox("启动与更新")
        vv = QVBoxLayout(g)
        self.k_auto = QCheckBox("开机自动启动")
        self.k_auto.setChecked(autostart_enabled())
        self.k_upd = self._chk("启动时检查新版本", "check_update", True)
        vv.addWidget(self.k_auto)
        vv.addWidget(self.k_upd)
        v.addWidget(g)

        g2 = QGroupBox("工作统计")
        v2 = QVBoxLayout(g2)
        self.k_over = self._chk("把下班后的时间计入加班", "count_over", True)
        v2.addWidget(self.k_over)
        h = QHBoxLayout()
        b1 = QPushButton("查看统计…")
        b2 = QPushButton("导出 CSV…")
        b1.clicked.connect(self._show_stats)
        b2.clicked.connect(self._export_csv)
        h.addWidget(b1)
        h.addWidget(b2)
        h.addStretch(1)
        v2.addLayout(h)
        v.addWidget(g2)

        g3 = QGroupBox("其他")
        h3 = QHBoxLayout(g3)
        b_pos = QPushButton("回到默认位置")
        b_dir = QPushButton("打开配置目录")
        b_cfg = QPushButton("查看配置文件")
        b_pos.clicked.connect(self._reset_pos)
        b_dir.clicked.connect(lambda: self._open_path(CONFIG_DIR))
        b_cfg.clicked.connect(lambda: self._open_path(CONFIG_PATH))
        for b in (b_pos, b_dir, b_cfg):
            h3.addWidget(b)
        h3.addStretch(1)
        v.addWidget(g3)

        g4 = QGroupBox("语录（可编辑 JSON，支持天气/周五/久坐文案）")
        v4 = QVBoxLayout(g4)
        self.lab_quotes = QLabel("语录文件：" + Q.QUOTE_PATH)
        self.lab_quotes.setWordWrap(True)
        self.lab_quotes.setStyleSheet("color:#9A8B80; font: 9pt 'Microsoft YaHei';")
        v4.addWidget(self.lab_quotes)
        h4 = QHBoxLayout()
        b_open = QPushButton("打开语录文件")
        b_rel = QPushButton("重新加载")
        b_def = QPushButton("恢复默认")
        b_open.clicked.connect(self._open_quotes)
        b_rel.clicked.connect(self._reload_quotes)
        b_def.clicked.connect(self._reset_quotes)
        for b in (b_open, b_rel, b_def):
            h4.addWidget(b)
        h4.addStretch(1)
        v4.addLayout(h4)
        v.addWidget(g4)

        v.addStretch(1)
        return w

    # ---------------------------------------------------------------- 工具
    def _chk(self, text, key, default=False):
        b = QCheckBox(text)
        b.setChecked(bool(self.cfg.get(key, default)))
        return b

    def _open_path(self, path):
        try:
            if os.path.isdir(path):
                os.startfile(path)                      # noqa: S606
            elif os.path.exists(path):
                os.startfile(path)                      # noqa: S606
        except Exception:
            QMessageBox.information(self, "路径", path)

    def _reset_pos(self):
        self._want_reset_pos = True
        QMessageBox.information(self, "已安排", "点「确定」后窗口会回到屏幕右下角。")

    def _open_quotes(self):
        Q.ensure_default_file()
        self._open_path(Q.QUOTE_PATH)

    def _reload_quotes(self):
        QMessageBox.information(self, "已重新加载", "语录会在下一条轮换时读取最新文件。")

    def _reset_quotes(self):
        btn = QMessageBox.question(self, "恢复默认语录",
                                   "确定把语录文件恢复为内置默认吗？")
        if btn != QMessageBox.StandardButton.Yes:
            return
        Q.reset_quotes_file()
        QMessageBox.information(self, "已恢复", "语录文件已重置为内置默认。")

    def _show_stats(self):
        QMessageBox.information(self, "工作统计", stats.report_text())

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出工作统计",
            os.path.join(os.path.expanduser("~"), "work_stats.csv"), "CSV 文件 (*.csv)")
        if not path:
            return
        try:
            n = stats.export_csv(path)
            QMessageBox.information(self, "导出完成", "已导出 %d 天记录到\n%s" % (n, path))
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    # ---------------------------------------------------------------- 收集
    def _time_val(self, edit, fallback):
        txt = edit.text().strip()
        try:
            hh, mm = txt.split(":")
            hh, mm = int(hh), int(mm)
            assert 0 <= hh <= 23 and 0 <= mm <= 59
            return "%02d:%02d" % (hh, mm)
        except Exception:
            return fallback

    def _on_ok(self):
        fb_start = str(self.cfg.get("start", "09:00"))
        fb_end = str(self.cfg.get("end", "18:00"))
        start = self._time_val(self.e_start, fb_start)
        end = self._time_val(self.e_end, fb_end)
        if self.e_start.text().strip() and self.e_start.text().strip() != fb_start \
                and start == fb_start:
            QMessageBox.warning(self, "时间格式不对", "上班时间请写成 HH:MM，例如 09:00")
            return
        if self.e_end.text().strip() and self.e_end.text().strip() != fb_end \
                and end == fb_end:
            QMessageBox.warning(self, "时间格式不对", "下班时间请写成 HH:MM，例如 18:00")
            return
        # Qwen 配置单独存 qwen.json（不要把 key 混进主配置）
        try:
            llm.save_cfg(self.k_llm.isChecked(), self.e_key.text().strip(),
                         self.e_model.text().strip() or "qwen-plus")
        except Exception:
            pass
        self.accept()

    def result(self):
        """返回与 DEFAULTS 同键的配置增量（只含本窗口能改的项）。"""
        out = {
            "char": self.c_char.currentText(),
            "style": self.c_style.currentText(),
            "hat": self.c_hat.currentData(),
            "acc": self.c_acc.currentData(),
            "scale": float(self.c_size.currentData()),
            "body": self.k_body.isChecked(),
            "dim25": self.k_25d.isChecked(),
            "mini": self.k_mini.isChecked(),
            "show_sec": self.k_sec.isChecked(),
            "top": self.k_top.isChecked(),
            "start": self._time_val(self.e_start, "09:00"),
            "end": self._time_val(self.e_end, "18:00"),
            "rest_days": [i for i, b in enumerate(self.rest_boxes) if b.isChecked()],
            "payday": int(self.s_pay.value()),
            "notify_off": self.k_noff.isChecked(),
            "notify_work": self.k_nwork.isChecked(),
            "notify_pre": self.k_pre.isChecked(),
            "hydrate": self.k_hyd.isChecked(),
            "sound": self.k_sound.isChecked(),
            "afk": self.k_afk.isChecked(),
            "city": self.e_city.text().strip(),
            "check_update": self.k_upd.isChecked(),
            "count_over": self.k_over.isChecked(),
            "context_aware": self.k_ctx.isChecked(),
            "edge_dock": self.k_dock.isChecked(),
            "boss_key": self.k_boss.isChecked(),
            "surprise": self.k_surp.isChecked(),
            "mood_daily": self.k_mood.isChecked(),
        }
        out["_autostart"] = self.k_auto.isChecked()
        out["_reset_pos"] = bool(getattr(self, "_want_reset_pos", False))
        return out
