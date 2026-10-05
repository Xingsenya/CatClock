# -*- coding: utf-8 -*-
"""静态数据：角色配色、主题、语录、物种映射表。"""

QUOTES = [
    (9.0, 10.5, ["新的一天，搬砖愉快", "早！今天也要加油鸭", "咖啡续上了吗"]),
    (10.5, 11.5, ["坚持住，马上吃饭了", "上午的砖搬完一半了"]),
    (11.5, 13.5, ["干饭时间到！", "干饭不积极，思想有问题", "今天食堂还是外卖？"]),
    (13.5, 15.5, ["午困，撑住", "摸鱼五分钟，精神两小时"]),
    (15.5, 16.5, ["下午茶整一个？", "摸鱼也要讲基本法"]),
    (16.5, 17.5, ["开始收拾东西了", "键盘声都变响了"]),
]

QUOTES_FRIDAY = {
    (9.0, 10.5): ["周五！稳住，胜利在望", "今天是周五，懂的都懂"],
    (15.5, 16.5): ["周五下午，心在飞", "想想周末去哪玩"],
    (16.5, 17.5): ["周五！忍住，就快了", "周五的 4 点，你懂的"],
    (17.5, 24.0): ["周末启动！", "周五晚上，人间值得"],
}

# ======================================================================
# 天气联动语录（晴雨雪雷各有专属，与时段语录穿插出现）
# ======================================================================
WEATHER_QUOTES = {
    "rain": ["下雨了，出门记得带伞", "雨天适合摸鱼发呆"],
    "thunder": ["打雷了，猫有点怕怕", "雷雨天，早点回家"],
    "snow": ["下雪啦，注意保暖", "下雪天适合许愿哦"],
    "sun": ["今天阳光不错，晒晒心情", "大晴天，搬砖都有劲"],
    "cloud-sun": ["多云转晴，心情也是"],
    "cloud": ["阴天，适合闷头干活"],
    "fog": ["雾好大，路上慢点"],
}

# 久坐提醒文案轮换
HYDRATE_MSGS = [
    "喝口水，起来走走～",
    "活动一下，看看远处～",
    "肩颈放松 30 秒，继续战斗",
    "站起来倒杯水，猫替你盯着进度",
]

# ======================================================================
# 角色表
# ======================================================================


CHARACTERS = {
    "橘猫": dict(
        fur="#FBBF77", fur_d="#F3A65A", fur_l="#FFEACF", line="#E89B52",
        ear_in="#FFB9C6", nose="#FF8FA3", eye="#4A342C",
        tabby=True, tabby_c="#F0A052", patches=(), ears=(None, None),
    ),
    "奶牛猫": dict(
        fur="#FFFFFF", fur_d="#F3EDE4", fur_l="#FFF9F2", line="#D8C8B8",
        ear_in="#FFC9D4", nose="#FF8FA3", eye="#4A342C",
        tabby=False, patches=(
            dict(x=-0.46, y=-0.46, w=0.50, h=0.44, c="#3B3733"),
            dict(x=0.08, y=-0.47, w=0.36, h=0.30, c="#3B3733"),
            dict(x=-0.48, y=0.12, w=0.30, h=0.30, c="#3B3733"),
        ), ears=("#3B3733", None),
    ),
    "黑猫": dict(
        fur="#4C4653", fur_d="#3A3542", fur_l="#7E7688", line="#2F2B36",
        ear_in="#C8B8CC", nose="#E88FA0", eye="#FDD45E",
        tabby=False, patches=(), ears=(None, None),
    ),
    "三花猫": dict(
        fur="#FFF7EE", fur_d="#F5E9DA", fur_l="#FFFCF6", line="#DCC3AA",
        ear_in="#FFB9C6", nose="#FF8FA3", eye="#4A342C",
        tabby=False, patches=(
            dict(x=-0.44, y=-0.44, w=0.42, h=0.38, c="#F3A65A"),
            dict(x=0.12, y=-0.46, w=0.34, h=0.32, c="#3B3733"),
            dict(x=0.28, y=0.10, w=0.28, h=0.24, c="#F3A65A"),
            dict(x=-0.46, y=0.12, w=0.26, h=0.22, c="#3B3733"),
        ), ears=("#F3A65A", "#3B3733"),
    ),
    "白猫": dict(
        fur="#FFFFFF", fur_d="#F1ECE5", fur_l="#FFFFFF", line="#C4B4A2",
        ear_in="#FFC2CE", nose="#FF9FB0", eye="#4A342C",
        tabby=False, patches=(), ears=(None, None),
    ),
    "蓝猫": dict(
        fur="#AAB5C1", fur_d="#8F9BA9", fur_l="#C7CED7", line="#7D8997",
        ear_in="#DBA9B5", nose="#E89AA8", eye="#4E9E85",
        tabby=True, tabby_c="#93A0AE", patches=(), ears=(None, None),
    ),
    "暹罗猫": dict(
        fur="#F6EDE2", fur_d="#EADFD2", fur_l="#FBF6EE", line="#C9B8A8",
        ear_in="#D8B8AC", nose="#C9808A", eye="#7FB3D5",
        tabby=False, patches=(
            dict(x=-0.16, y=-0.44, w=0.34, h=0.38, c="#5C463A", feather=True),   # 面部重点色
        ), ears=("#5C463A", "#5C463A"),
    ),
    "虎斑猫": dict(
        fur="#C4B09A", fur_d="#A98F76", fur_l="#EFE3D2", line="#8A7258",
        ear_in="#D8A8A0", nose="#E8909C", eye="#3E3226",
        tabby=True, tabby_c="#7A6448", patches=(), ears=(None, None),
    ),
    "熊猫": dict(
        shape="panda",
        fur="#FFFFFF", fur_d="#EFEFEF", fur_l="#FFFFFF", line="#3A3A3A",
        ear_in="#3A3A3A", nose="#3A3A3A", eye="#F5F5F5", pupil="#2A2A2A",
        tabby=False, patches=(
            dict(x=-0.285, y=-0.14, w=0.20, h=0.22, c="#5C5C5C"),  # 左眼圈
            dict(x=0.085, y=-0.14, w=0.20, h=0.22, c="#5C5C5C"),   # 右眼圈
        ), ears=("#5C5C5C", "#5C5C5C"),
    ),
    # ==================== 十二生肖 ====================
    "鼠": dict(
        fur="#9AA3B2", fur_d="#7E8798", fur_l="#C9CFDA", line="#6A7284",
        ear_in="#F5B8C4", nose="#F08CA0", eye="#3A3230",
        tabby=False, patches=(), ears=(None, None), shape="rat",
    ),
    "牛": dict(
        fur="#E8DCC8", fur_d="#D4C4A8", fur_l="#F7F0E2", line="#B5A284",
        ear_in="#E8B8B0", nose="#C9908A", eye="#4A3B30",
        tabby=False, patches=(), ears=(None, None), shape="ox",
    ),
    "虎": dict(
        fur="#E87F3A", fur_d="#D06622", fur_l="#FFF3E2", line="#B55A1F",
        ear_in="#F9C6B0", nose="#E87F6E", eye="#4A342C",
        tabby=True, tabby_c="#7A4A28", patches=(), ears=(None, None), shape="tiger",
    ),
    "兔": dict(
        fur="#F2E3E6", fur_d="#E4CDD2", fur_l="#FFFFFF", line="#D3B7BE",
        ear_in="#F7B8C8", nose="#F28CA0", eye="#5A4440",
        tabby=False, patches=(), ears=(None, None), shape="rabbit",
    ),
    "龙": dict(
        fur="#7FC8B4", fur_d="#5FAE9A", fur_l="#BFE8DC", line="#4E9482",
        ear_in="#A8E0CE", nose="#E8A090", eye="#2E4A42",
        tabby=False, patches=(), ears=(None, None), shape="dragon",
    ),
    "蛇": dict(
        fur="#8FBF6A", fur_d="#75A855", fur_l="#B8DCA0", line="#648F48",
        ear_in="#B8DCA0", nose="#648F48", eye="#3E5A2E",
        tabby=False, patches=(), ears=(None, None), shape="snake",
    ),
    "马": dict(
        fur="#C9A27E", fur_d="#B08A64", fur_l="#E8D0B8", line="#96714E",
        ear_in="#DDB8A0", nose="#8A6A58", eye="#4A3628", mane="#6A4E38",
        tabby=False, patches=(), ears=(None, None), shape="horse",
    ),
    "羊": dict(
        fur="#FFFDF6", fur_d="#EFE8DA", fur_l="#FFFFFF", line="#CFC4B2",
        ear_in="#E8C8C0", nose="#C9908A", eye="#5A4A40", wool="#EFEDE4",
        tabby=False, patches=(), ears=(None, None), shape="sheep",
    ),
    "猴": dict(
        fur="#B08968", fur_d="#96714E", fur_l="#EED3B0", line="#7A5A3E",
        ear_in="#EED3B0", nose="#8A5A44", eye="#3E2E22",
        tabby=False, patches=(), ears=(None, None), shape="monkey",
    ),
    "鸡": dict(
        fur="#FFF4DC", fur_d="#F2E2BC", fur_l="#FFFDF4", line="#D8B878",
        ear_in="#F2A33C", nose="#F2A33C", eye="#4A3628", comb="#D66A6A",
        tabby=False, patches=(), ears=(None, None), shape="rooster",
    ),
    "狗": dict(
        fur="#E8C48F", fur_d="#D0A874", fur_l="#F5E3C8", line="#B08A5A",
        ear_in="#E8B8A8", nose="#4A3630", eye="#4A3628",
        tabby=False, patches=(), ears=(None, None), shape="dog",
    ),
    "猪": dict(
        fur="#F5C8D0", fur_d="#E8A8B4", fur_l="#FCE4E8", line="#D68E9C",
        ear_in="#F2B0BC", nose="#E87F92", eye="#5A3A40",
        tabby=False, patches=(), ears=(None, None), shape="pig",
    ),
}

# ======================================================================
# 主题表
# ======================================================================
STYLES = {
    "奶油": dict(
        panel0=(255, 255, 255, 252), panel1=(255, 247, 240, 248),
        border=(255, 216, 192), border_h=(255, 198, 168), shadow=(70, 45, 35),
        bar_bg=(246, 233, 221), bar0=(255, 210, 157), bar1=(255, 158, 110),
        bar0_off=(255, 170, 190), bar1_off=(255, 122, 156),
        text="#4A3B33", sub="#B09A8C", pink="#FF7A9C",
        menu_bg="#FFFDFA", menu_border="#F2D9C6", menu_sel="#FFE9D6",
        menu_text="#5A4A42", menu_sep="#F0E3DA",
    ),
    "草莓": dict(
        panel0=(255, 252, 253, 252), panel1=(255, 240, 245, 248),
        border=(255, 205, 218), border_h=(255, 183, 205), shadow=(95, 40, 62),
        bar_bg=(249, 229, 236), bar0=(255, 183, 205), bar1=(255, 145, 180),
        bar0_off=(255, 170, 190), bar1_off=(255, 122, 156),
        text="#5A3A46", sub="#C096A4", pink="#FF6B95",
        menu_bg="#FFF9FB", menu_border="#F6D3DE", menu_sel="#FFE3EC",
        menu_text="#5A3A46", menu_sep="#F5DEE6",
    ),
    "薄荷": dict(
        panel0=(253, 255, 254, 252), panel1=(240, 250, 246, 248),
        border=(196, 232, 218), border_h=(168, 224, 200), shadow=(35, 70, 55),
        bar_bg=(226, 241, 234), bar0=(159, 222, 190), bar1=(96, 199, 150),
        bar0_off=(255, 170, 190), bar1_off=(255, 122, 156),
        text="#2E443C", sub="#8FA89E", pink="#F27A9C",
        menu_bg="#FAFEFC", menu_border="#CBE8DC", menu_sel="#DDF3E9",
        menu_text="#2E443C", menu_sep="#D8EDE3",
    ),
    "夜幕": dict(
        panel0=(54, 49, 67, 250), panel1=(36, 32, 46, 248),
        border=(99, 90, 125), border_h=(134, 123, 165), shadow=(0, 0, 0),
        bar_bg=(67, 61, 82), bar0=(152, 131, 224), bar1=(202, 141, 232),
        bar0_off=(255, 150, 180), bar1_off=(255, 110, 150),
        text="#F2ECE4", sub="#9C93AC", pink="#FF8FB0",
        menu_bg="#2F2B39", menu_border="#575168", menu_sel="#4C465B",
        menu_text="#EDE8F2", menu_sep="#474153",
    ),
    "柠檬": dict(
        panel0=(255, 254, 250, 252), panel1=(255, 248, 228, 248),
        border=(244, 228, 170), border_h=(238, 213, 138), shadow=(92, 76, 30),
        bar_bg=(246, 238, 208), bar0=(255, 224, 140), bar1=(250, 196, 90),
        bar0_off=(255, 170, 190), bar1_off=(255, 122, 156),
        text="#54452A", sub="#B5A273", pink="#F2839C",
        menu_bg="#FFFEF7", menu_border="#EFE3B8", menu_sel="#FBF0C9",
        menu_text="#54452A", menu_sep="#F0E7C8",
    ),
}


# ======================================================================
# 天气（Open-Meteo，免 key）
# ======================================================================
WMO_TEXT = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴",
    45: "雾", 48: "雾",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨", 56: "冻雨", 57: "冻雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪",
    80: "阵雨", 81: "阵雨", 82: "强阵雨",
    85: "阵雪", 86: "阵雪",
    95: "雷暴", 96: "雷暴冰雹", 99: "雷暴冰雹",
}


def wmo_kind(code):
    if code == 0:
        return "sun"
    if code in (1, 2):
        return "cloud-sun"
    if code == 3:
        return "cloud"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "thunder"
    return "cloud"




_TOP_EXT = {"rabbit": 0.86, "ox": 0.76, "dragon": 0.78,
           "sheep": 0.72, "rooster": 0.64, "horse": 0.84,
           "monkey": 0.80, "dog": 0.72, "rat": 0.80}

# 各物种身体形态（默认 round = 圆润标准）
_BODY_SHAPE = {"horse": "long", "snake": "long", "ox": "wide", "pig": "wide",
               "dog": "slim", "monkey": "slim"}

# 各物种头型：(宽, 高, 中心纵向偏移)，默认 (0.88, 0.86, 0)
# 马/蛇修长，牛/猪/虎宽扁，鼠/兔小巧，猴心形略高
_HEAD = {
    "horse":  (0.80, 0.98, -0.03),
    "snake":  (0.78, 0.88, 0.00),
    "ox":     (0.94, 0.84, 0.02),
    "pig":    (0.92, 0.82, 0.02),
    "tiger":  (0.94, 0.84, 0.00),
    "rat":    (0.82, 0.84, 0.01),
    "rabbit": (0.86, 0.88, 0.00),
    "monkey": (0.86, 0.90, -0.01),
    "dog":    (0.88, 0.86, 0.00),
    "dragon": (0.86, 0.88, 0.00),
    "panda":  (0.88, 0.86, 0.00),
}

# 各物种帽子（这种 Q 版风格不画头发，改用可爱小帽做差异化）
_HAT = {
    "dog": "cap", "monkey": "beanie", "rat": "beanie",
}

# 各帽型的"头顶以上"延伸系数（自动定尺寸防出界用）
_HAT_EXT = {"cap": 0.28, "beanie": 0.34, "beret": 0.20, "straw": 0.16,
            "party": 0.50, "crown": 0.28, "none": 0.0}

# 各物种眼睛形态：(纵向偏移, 半宽, 全高, 是否竖瞳)
# 牛/马 → 小横椭圆、位置偏高；猪/猴 → 大而圆（猴位置偏低）；
# 龙/蛇 → 细长竖瞳；鸡 → 小而锐利；虎 → 横置带凶感
_EYE = {
    "ox":     (-0.055, 0.060, 0.125, False),
    "horse":  (-0.055, 0.062, 0.130, False),
    "tiger":  (-0.010, 0.082, 0.150, False),
    "pig":    (0.015,  0.078, 0.215, False),
    "monkey": (0.030,  0.076, 0.210, False),
    "dragon": (-0.010, 0.070, 0.145, True),
    "snake":  (0.000,  0.066, 0.120, True),
    "rooster": (-0.020, 0.055, 0.140, False),
}
_EYE_DEFAULT = (0.0, 0.068, 0.190, False)

# 各物种的尾巴样式（默认 cat = 细长弯钩猫尾）
_TAIL = {"rabbit": "puff", "sheep": "puff", "dog": "curl_up", "pig": "curl",
         "horse": "brush", "ox": "brush", "dragon": "fin", "snake": "coil",
         "rooster": "feather", "rat": "whip", "monkey": "long"}

# 各物种的手型（默认 paw = 猫爪；snake 无手，连手臂一起省略）
_HAND = {"rat": "fingers", "ox": "hoof", "tiger": "paw", "rabbit": "puff_paw",
         "dragon": "claw", "snake": "none", "horse": "hoof", "sheep": "hoof",
         "monkey": "monkey", "rooster": "wing", "dog": "dog_paw", "pig": "cloven"}

# 状态 → 手上的道具
PROP_BY_WEATHER = {"rain": "umbrella", "thunder": "umbrella", "snow": "scarf"}

# 帽子选项（右键菜单与设置窗口共用）：(key, 显示名)
HATS = (
    ("auto", "自动（按角色）"), ("none", "不戴帽子"), ("cap", "棒球帽"),
    ("beanie", "毛线帽"), ("beret", "贝雷帽"), ("straw", "草帽"),
    ("party", "派对帽"), ("crown", "皇冠"),
)

# 预设缩放档位（%）
SIZES = (60, 80, 100, 120, 140, 160)

