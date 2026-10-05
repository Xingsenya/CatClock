"""把 cat_clock.py 拆成 catclock/ 包的一次性脚本。"""
import io, os

SRC = "D:/CatClock/_orig_cat_clock.py"
DST = "D:/CatClock/catclock"
os.makedirs(DST, exist_ok=True)

lines = io.open(SRC, encoding="utf-8").read().split("\n")  # 0-indexed


def seg(a, b):
    """取 1-indexed 行区间 [a, b]"""
    return "\n".join(lines[a - 1:b])


IMPORTS_UTIL = '''# -*- coding: utf-8 -*-
"""配置读写、开机自启、单实例、字体与颜色工具。"""
import json
import os
import sys
from datetime import datetime

try:
    import winreg
except Exception:
    winreg = None

from PyQt6.QtGui import QColor, QFont
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from . import data as _data

CHARACTERS = _data.CHARACTERS
STYLES = _data.STYLES
'''

IMPORTS_DATA = '''# -*- coding: utf-8 -*-
"""静态数据：角色配色、主题、语录、物种映射表。"""

'''

IMPORTS_DRAW = '''# -*- coding: utf-8 -*-
"""程序化矢量绘制：猫/动物、帽子、道具、天气图标、托盘图标。"""
import math

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QLinearGradient, QRadialGradient,
    QPixmap, QFont, QIcon,
)

from . import data as D
from .util import _mix, _q_luma
from .data import (_HEAD, _EYE, _EYE_DEFAULT, _TAIL, _HAND, _HAT, _HAT_EXT,
                   _BODY_SHAPE, _TOP_EXT)

CHARACTERS = D.CHARACTERS
STYLES = D.STYLES
'''

IMPORTS_WEATHER = '''# -*- coding: utf-8 -*-
"""天气获取（Open-Meteo）。"""
import json
import os
from urllib.parse import quote

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from . import data as D
from .util import CONFIG_DIR

'''

IMPORTS_UI = '''# -*- coding: utf-8 -*-
"""通用小弹窗。"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QLineEdit, QLabel,
)

'''

IMPORTS_APP = '''# -*- coding: utf-8 -*-
"""主窗口 CatClock。"""
import json
import os
import math
import random
import calendar
import sys
from datetime import datetime, timedelta

from PyQt6.QtCore import Qt, QPoint, QPointF, QTimer, QRectF, QUrl, QObject
from PyQt6.QtGui import (
    QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QLinearGradient,
    QRadialGradient, QPixmap, QAction, QActionGroup, QCursor,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QMenu, QSystemTrayIcon, QInputDialog, QMessageBox,
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QLineEdit, QLabel,
)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from . import data as D
from . import draw as G
from . import weather as W
from . import ui as U
from .util import (
    APP_NAME, CONFIG_DIR, CONFIG_PATH, DEFAULTS, load_cfg, save_cfg, app_path,
    autostart_enabled, set_autostart, _raise_existing, acquire_single, rr,
    _q_luma, _mix, user_idle_seconds, font,
)
from .draw import draw_cat, heart_path, draw_weather_icon, make_icon
from .data import (
    CHARACTERS, STYLES, QUOTES, QUOTES_FRIDAY, WEATHER_QUOTES, HYDRATE_MSGS,
    WMO_TEXT, wmo_kind, PROP_BY_WEATHER,
)
from .weather import WeatherFetcher
from .ui import CatInputDialog, RestDaysDialog

'''

files = {}

files["util.py"] = IMPORTS_UTIL + seg(40, 72) + "\n\n\n" + seg(322, 479)
files["data.py"] = (IMPORTS_DATA + seg(73, 112) + "\n\n\n" + seg(113, 321)
                    + "\n\n\n" + seg(2156, 2217))
files["draw.py"] = IMPORTS_DRAW + seg(480, 2018)
files["weather.py"] = IMPORTS_WEATHER + seg(2019, 2095)
files["ui.py"] = IMPORTS_UI + seg(2096, 2155)
files["app.py"] = IMPORTS_APP + seg(2218, len(lines))

for name, text in files.items():
    io.open(os.path.join(DST, name), "w", encoding="utf-8", newline="\n").write(text)
    print("wrote", name, len(text.split("\n")), "lines")

io.open(os.path.join(DST, "__init__.py"), "w", encoding="utf-8", newline="\n").write(
    "# -*- coding: utf-8 -*-\n"
    '"""CatClock 包。"""\n'
    '__version__ = "0.0.0"\n'
)
print("done")
