# CatClock 🐱

桌面可爱猫猫 · 下班倒计时挂件（Windows，PyQt6）。

类似 Catime 的桌面悬浮小窗：多只猫猫 + 多套主题，支持拖动、托盘、开机自启、置顶。

## 功能

- **倒计时**：上班前 / 工作中（进度条）/ 下班后 / 休息日（每周可配，适配单休轮休）
- **9 只角色**：橘猫、奶牛猫、黑猫、三花猫、白猫、蓝猫、暹罗猫、虎斑猫、熊猫
- **5 套主题**：奶油、草莓、薄荷、夜幕、柠檬
- **天气**：Open-Meteo 免费接口（免 key），城市支持逐级降级匹配（区县名也能查）；雷暴/酷暑/严寒猫有对应反应
- **情绪价值**：发工资倒计时、打工人语录轮播（周五专属）、瞳孔跟随鼠标、摇尾巴、摸猫彩蛋、待机伸懒腰/打哈欠、整点报时、久坐提醒、深夜关怀
- **交互**：右键菜单全配置、滚轮等比缩放（60%–160%）、迷你模式、单实例锁、多屏拖动

## 使用

下载 `dist/CatClock.exe`（Release 里），双击运行即可。右键托盘/窗口打开菜单。

开发：

```bash
pip install PyQt6
python cat_clock.py        # 源码运行
python preview_all.py      # 渲染 角色×主题 预览图 preview.png
```

打包：`pyinstaller --noconsole --onefile --name CatClock --icon cat.ico cat_clock.py`

## 配置

存于 `%APPDATA%\CatClock\config.json`，菜单里所有改动自动记忆。
