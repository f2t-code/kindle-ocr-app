# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — 全部入り Kindle OCR.app をビルドする.

ビルド: pyinstaller KindleOCR.spec
出力:   dist/Kindle OCR.app
"""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('src', 'src'),  # 自前モジュール
    ],
    hiddenimports=[
        # PyObjC frameworks (Mac)
        'Vision',
        'Quartz',
        'AppKit',
        'Foundation',
        'CoreFoundation',
        'CoreGraphics',
        'ApplicationServices',
        # OCR / PDF
        'fitz',
        'pymupdf',
        'img2pdf',
        # mss
        'mss.darwin',
        'mss.windows',
        # PIL
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',  # 未使用
        'matplotlib',
        'numpy.tests',
        'pandas',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Kindle OCR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app (no terminal)
    disable_windowed_traceback=False,
    target_arch='arm64' if sys.platform == 'darwin' else None,
    codesign_identity=None,  # build_pyinstaller.sh で後段で署名
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Kindle OCR',
)

# Mac .app バンドル
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Kindle OCR.app',
        icon='icon_build/AppIcon.icns',
        bundle_identifier='net.f2t.kindle-ocr',
        version='0.1.0',
        info_plist={
            'CFBundleShortVersionString': '0.1.0',
            'CFBundleVersion': '0.1.0',
            'LSMinimumSystemVersion': '11.0',
            'NSHighResolutionCapable': True,
            'NSAppleEventsUsageDescription': (
                'Kindleアプリを最前面に切り替え、ページ送りキーを送信するために使用します。'
            ),
            'NSScreenCaptureUsageDescription': (
                'Kindleで表示中の本のページをスクリーンショットで取得します。'
            ),
            'NSAccessibilityUsageDescription': (
                'Kindleアプリへのキーボード入力（ページ送り）に必要です。'
            ),
        },
    )
