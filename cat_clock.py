# -*- coding: utf-8 -*-
"""
CatClock —— 桌面可爱猫猫 · 下班倒计时挂件（入口）

实际实现已拆分到 catclock/ 包：
    catclock/data.py     角色配色 / 主题 / 语录 / 物种映射表
    catclock/util.py     配置读写 / 开机自启 / 单实例 / 字体颜色工具
    catclock/draw.py     程序化矢量绘制（角色 / 帽子 / 道具 / 图标）
    catclock/weather.py  天气获取（Open-Meteo）
    catclock/ui.py       通用小弹窗
    catclock/app.py      主窗口与 main()
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catclock.app import main          # noqa: E402

if __name__ == "__main__":
    main()
