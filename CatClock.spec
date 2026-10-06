# -*- mode: python ; coding: utf-8 -*-


# H1：体积优化（实测 36M → 目标 ~20M）
# 1) 剔除用不到的 Qt 模块
_EXCLUDES = [
    'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineQuick',
    'PyQt6.QtQuick', 'PyQt6.QtQuick3D', 'PyQt6.QtQuickWidgets', 'PyQt6.QtQml',
    'PyQt6.QtQmlModels', 'PyQt6.QtQmlWorkerScript', 'PyQt6.Qt3DCore',
    'PyQt6.Qt3DRender', 'PyQt6.Qt3DInput', 'PyQt6.Qt3DLogic', 'PyQt6.Qt3DAnimation',
    'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets', 'PyQt6.QtBluetooth',
    'PyQt6.QtNfc', 'PyQt6.QtPositioning', 'PyQt6.QtSerialPort', 'PyQt6.QtSql',
    'PyQt6.QtTest', 'PyQt6.QtDesigner', 'PyQt6.QtHelp', 'PyQt6.QtCharts',
    'PyQt6.QtDataVisualization', 'PyQt6.QtSvg', 'PyQt6.QtSvgWidgets',
    'PyQt6.QtOpenGL', 'PyQt6.QtOpenGLWidgets', 'PyQt6.QtPrintSupport',
    'PyQt6.QtNetworkAuth', 'PyQt6.QtWebSockets', 'PyQt6.QtWebChannel',
    'PyQt6.QtRemoteObjects', 'PyQt6.QtSensors', 'PyQt6.QtSpatialAudio',
    'PyQt6.QtTextToSpeech', 'PyQt6.QtPdf', 'PyQt6.QtPdfWidgets', 'PyQt6.QtUiTools',
    'tkinter', 'unittest', 'pydoc', 'doctest', 'lib2to3', 'numpy',
]

a = Analysis(
    ['cat_clock.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['catclock', 'catclock.data', 'catclock.draw', 'catclock.util',
                   'catclock.weather', 'catclock.ui', 'catclock.update', 'catclock.stats',
                   'catclock.settings', 'catclock.quotes', 'catclock.gfx', 'catclock.parts',
                   'catclock.icons', 'catclock.log', 'catclock.paint', 'catclock.menu',
                   'catclock.notify', 'catclock.interact'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_EXCLUDES,
    noarchive=False,
    optimize=2,
)

# 2) 剔除被 Qt hook 一并拖进来的巨型 DLL（软件 OpenGL、ffmpeg、Quick/Qml/Designer/Pdf）
import os as _os

_DROP_DLL = {
    'opengl32sw.dll',            # 20M：软件 OpenGL 兜底，Windows 下用不到
    'avcodec-61.dll', 'avformat-61.dll', 'avutil-59.dll',
    'swscale-8.dll', 'swresample-5.dll',          # QtMultimedia 的 ffmpeg
    'qt6quick.dll', 'qt6qml.dll', 'qt6qmlmodels.dll',
    'qt6designer.dll', 'qt6pdf.dll', 'qt6pdfwidgets.dll',
    'qt6webenginecore.dll', 'qt6multimedia.dll',
    'd3dcompiler_47.dll',
}
a.binaries = [b for b in a.binaries
              if _os.path.basename(str(b[0])).lower() not in _DROP_DLL]
a.datas = [d for d in a.datas
           if _os.path.basename(str(d[0])).lower() not in _DROP_DLL]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CatClock',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['cat.ico'],
)
