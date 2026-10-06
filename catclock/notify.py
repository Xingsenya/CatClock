# -*- coding: utf-8 -*-
"""A1：通知 / 提醒 / 天气刷新 / 统计与周报（CatClock 的 _NotifyMixin）。

从 app.py 拆出：所有「对外发消息」和「拉外部数据」的入口都在这里。
"""
import os
import webbrowser
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCursor, QAction
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QFileDialog

from . import __version__
from . import stats
from . import report
from . import mood
from . import update as UPD
from . import festival as F
from .weather import WeatherFetcher
from .util import APP_NAME, save_cfg, font


class _NotifyMixin:

    def notify(self, title, msg, celebrate):
        try:
            self.tray.showMessage(title, msg, self.tray.icon(), 8000)
        except Exception:
            pass
        if self.cfg.get("sound", True):
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_OK if celebrate else winsound.MB_ICONASTERISK)
            except Exception:
                pass


    def refresh_weather(self):
        """拉取天气；失败时按 2min → 10min 退避重试（最多 3 次）。"""
        city = self.cfg.get("city", "")
        if not city:
            return
        try:
            self.wx.start(city)
        except Exception:
            self._wx_retry()


    def _wx_retry(self):
        self._wx_fail_n = getattr(self, "_wx_fail_n", 0) + 1
        if self._wx_fail_n > 3:
            return
        delay = 120000 if self._wx_fail_n < 3 else 600000
        QTimer.singleShot(delay, self.refresh_weather)


    def _wx_got(self, w):
        self.weather = w
        self._wx_fail_n = 0
        try:
            tip = "%s · %s %s %d°C" % (APP_NAME, w["city"], w["text"], w["temp"])
            if w.get("aqi_text"):
                tip += " · %s" % w["aqi_text"]
            self.tray.setToolTip(tip)
        except Exception:
            pass
        self.update()


    def check_update_manual(self):
        info = UPD.check_update()
        if not info:
            QMessageBox.information(self, "检查更新", "当前已是最新版本（v%s）" % __version__)
            return
        txt = "发现新版本 v%s\n\n%s\n\n是否打开下载页？" % (info["version"], info["notes"] or "（无更新说明）")
        if QMessageBox.question(self, "检查更新", txt) == QMessageBox.StandardButton.Yes:
            import webbrowser
            try:
                webbrowser.open(info["url"])
            except Exception:
                pass


    def auto_check_update(self):
        """启动后延迟检查一次，有新版本只走托盘提示，不打断使用。"""
        if not self.cfg.get("check_update", True):
            return

        def _run():
            info = UPD.check_update()
            if not info:
                return
            try:
                self.tray.showMessage("CatClock 有新版本 v%s" % info["version"],
                                      "点此打开下载页（或在右键菜单「检查更新」查看）",
                                      self.tray.icon(), 10000)
                self._update_url = info["url"]
                self.tray.messageClicked.connect(self._open_update_url)
            except Exception:
                pass

        QTimer.singleShot(6000, _run)


    def _open_update_url(self):
        import webbrowser
        try:
            webbrowser.open(getattr(self, "_update_url", UPD.UPDATE_API))
        except Exception:
            pass


    def show_stats(self):
        """工作时长统计：今日 / 本周 / 本月，并可导出 CSV。"""
        from PyQt6.QtWidgets import QFileDialog
        txt = stats.report_text()
        box = QMessageBox(self)
        box.setWindowTitle("工作统计")
        box.setText(txt + "\n\n（在岗=工作时间内的时长，加班=下班后仍在的时长）")
        box.addButton("导出 CSV", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
        if box.exec() != 0:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出工作统计", os.path.join(os.path.expanduser("~"), "work_stats.csv"),
            "CSV 文件 (*.csv)")
        if not path:
            return
        try:
            n = stats.export_csv(path)
            QMessageBox.information(self, "导出完成", "已导出 %d 天记录到\n%s" % (n, path))
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def show_week(self):
        from PyQt6.QtWidgets import QFileDialog
        plan_end = str(self.cfg.get("end", "18:00"))
        txt = report.week_text(None, plan_end)
        box = QMessageBox(self)
        box.setWindowTitle("本周小结与成就")
        box.setText(txt)
        box.setInformativeText("成就徽章：\n" + report.badges_text(None, plan_end))
        box.addButton("导出心情 CSV", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
        if box.exec() != 0:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出心情记录", os.path.join(os.path.expanduser("~"), "mood.csv"),
            "CSV 文件 (*.csv)")
        if not path:
            return
        try:
            n = mood.export_csv(path)
            QMessageBox.information(self, "导出完成", "已导出 %d 天心情记录" % n)
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def ask_mood(self):
        """三选一心情打卡；双击猫头也会走到这里。"""
        menu = QMenu(self)
        acts = {}
        for sc, label in ((2, "开心"), (1, "还行"), (0, "累")):
            a = QAction("%s %s" % (mood.SCORE_FACE[sc], label), self)
            a.triggered.connect(lambda _, v=sc: self._set_mood(v))
            menu.addAction(a)
            acts[sc] = a
        menu.exec(QCursor.pos())


    def _set_mood(self, score):
        reply = mood.set_today(score)
        self._say(reply)
        self.tray.setToolTip("%s · 今天：%s" % (APP_NAME, mood.SCORE_TEXT[score]))


    def show_about(self):
        QMessageBox.information(
            self, "关于 CatClock",
            "CatClock v%s\n\n桌面可爱猫猫 · 下班倒计时挂件\n"
            "21 个角色 / 6 款帽子 / 半身道具 / 2.5D\n\n"
            "右键菜单可切换角色、帽子与时间设置。" % __version__)


    def _say(self, text, dur=3.5):
        """让猫说话（通用气泡）"""
        self.bubble_text = text
        self.bubble_t = 0.0

    def _fire_surprise(self):
        """低概率触发一个小惊喜：动作 / 临时道具 / 气泡"""
        pool = [
            ("sneeze", 1.2, "阿嚏！猫感冒了（并没有）"),
            ("sneeze", 1.2, "阿嚏——吓到你了吧"),
            ("spin", 1.8, "追尾巴中……转晕了"),
            ("spin", 1.8, "猫在转圈圈，别管我"),
        ]
        if bool(self.cfg.get("body", True)):
            pool += [("coin", 4.0, "哇，掉了一枚金币！"),
                     ("heart", 4.0, "送你一颗爱心，收好～"),
                     ("wave", 2.0, " hi～猫跟你打招呼")]
        name, dur, text = random.choice(pool)
        if name in ("coin", "heart"):
            self._surprise_prop = (name, self.t0 + dur)
        else:
            self.action = name
            self.action_start = self.t0
            self.action_dur = dur
            self.idle = (name, self.t0)
        self._say(text, 3.0)
