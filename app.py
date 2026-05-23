"""Kindle OCR App — GUI エントリーポイント.

「一括実行」タブはステップガイド形式。
「Kindleキャプチャ」「OCRのみ」タブは個別実行用（上級者向け）。
"""

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
  QApplication,
  QCheckBox,
  QComboBox,
  QDialog,
  QDialogButtonBox,
  QDoubleSpinBox,
  QFileDialog,
  QFrame,
  QGroupBox,
  QHBoxLayout,
  QLabel,
  QLineEdit,
  QMainWindow,
  QMessageBox,
  QProgressBar,
  QPushButton,
  QScrollArea,
  QSpinBox,
  QTabWidget,
  QTextEdit,
  QVBoxLayout,
  QWidget,
)

from src.countdown_overlay import CountdownOverlay
from src.kindle_capture import CaptureConfig, capture_kindle
from src.md_export import export_pdf_to_markdown
from src.ocr import (
  ENGINE_APPLE_VISION,
  ENGINE_AUTO,
  ENGINE_TESSERACT,
  get_default_engine,
  list_available_engines,
  run_ocr,
  run_ocr_from_images,
)
from src.pdf_builder import build_pdf
from src.region_selector import RegionSelector
from src.permission_helper import (
  PERMISSION_GUIDE_MAC,
  copy_to_clipboard_mac,
  get_real_python_binary,
  reveal_in_finder_mac,
)
from src.window_activator import (
  activate_kindle,
  get_python_binary_info,
  is_kindle_running,
  is_mac,
  open_accessibility_settings,
  open_screen_recording_settings,
  send_key_mac,
)
from src import settings as app_settings


class SettingsDialog(QDialog):
  """OCR設定ダイアログ — Google Vision APIキー、Yomitoku 情報."""

  def __init__(self, parent=None):
    super().__init__(parent)
    self.setWindowTitle('⚙️ OCR 詳細設定')
    self.setMinimumSize(620, 480)
    layout = QVBoxLayout(self)

    title = QLabel('OCRエンジンの詳細設定')
    tf = QFont()
    tf.setPointSize(15)
    tf.setBold(True)
    title.setFont(tf)
    layout.addWidget(title)

    # ===== Google Vision =====
    g_box = QGroupBox('Google Cloud Vision API（任意）')
    g_box.setStyleSheet(
      'QGroupBox { background-color: #f0f7ff; border: 1px solid #b0d4ff; '
      'border-radius: 6px; padding: 14px 10px 10px 10px; margin-top: 8px; }'
    )
    g_layout = QVBoxLayout(g_box)
    g_info = QLabel(
      '世界最高精度クラスの日本語OCR（95-98%）。1000ページあたり約 $1.50（≒¥225）。\n'
      'APIキーを入力すると「OCRエンジン」選択に「Google Cloud Vision」が追加されます。'
    )
    g_info.setWordWrap(True)
    g_info.setStyleSheet('color: #1e6b3e; background: transparent; font-size: 12px;')
    g_layout.addWidget(g_info)

    g_row = QHBoxLayout()
    g_row.addWidget(QLabel('APIキー:'))
    self.api_key_input = QLineEdit(app_settings.get_google_api_key())
    self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
    self.api_key_input.setPlaceholderText('AIzaSy... 形式のAPIキー')
    g_row.addWidget(self.api_key_input, 1)
    show_btn = QPushButton('👁')
    show_btn.setCheckable(True)
    show_btn.setMaximumWidth(40)
    show_btn.clicked.connect(
      lambda checked: self.api_key_input.setEchoMode(
        QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
      )
    )
    g_row.addWidget(show_btn)
    g_layout.addLayout(g_row)

    g_help = QLabel(
      'APIキー取得手順:\n'
      '1. https://console.cloud.google.com にアクセス（Gmailでログイン）\n'
      '2. 新規プロジェクト作成\n'
      '3. 「APIとサービス」→「Cloud Vision API」を有効化\n'
      '4. 「APIとサービス」→「認証情報」→「+認証情報を作成」→「APIキー」\n'
      '5. 発行されたAPIキーをここに貼り付け\n'
      '※ 課金有効化が必要（初年度 $300 無料クレジット）'
    )
    g_help.setStyleSheet('color: #666; font-size: 11px; background: transparent;')
    g_help.setWordWrap(True)
    g_layout.addWidget(g_help)
    layout.addWidget(g_box)

    # ===== Yomitoku =====
    y_box = QGroupBox('Yomitoku（Windows/Linux向け 無料 日本語OCR）')
    y_box.setStyleSheet(
      'QGroupBox { background-color: #fff8e1; border: 1px solid #ffd54f; '
      'border-radius: 6px; padding: 14px 10px 10px 10px; margin-top: 8px; }'
    )
    y_layout = QVBoxLayout(y_box)

    try:
      from src.ocr_yomitoku import is_available as yomi_available
      installed = yomi_available()
    except Exception:
      installed = False

    if installed:
      status = QLabel('✅ Yomitoku がインストールされています。OCRエンジン選択に出現します。')
      status.setStyleSheet('color: #1e6b3e; background: transparent; font-weight: bold;')
    else:
      status = QLabel('❌ Yomitoku 未インストール')
      status.setStyleSheet('color: #b71c1c; background: transparent; font-weight: bold;')
    y_layout.addWidget(status)

    y_help = QLabel(
      '日本語特化のオープンソースOCR（90-95%精度）。完全無料・ローカル動作。\n'
      'インストール方法（ターミナルで実行）:\n'
      '  pip install yomitoku\n'
      '※ 初回起動時にモデルファイル（500MB+）が自動DLされます。'
    )
    y_help.setStyleSheet('color: #6B4423; background: transparent; font-size: 12px;')
    y_help.setWordWrap(True)
    y_layout.addWidget(y_help)
    layout.addWidget(y_box)

    layout.addStretch()

    btn_box = QDialogButtonBox(
      QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
    )
    btn_box.accepted.connect(self._save)
    btn_box.rejected.connect(self.reject)
    layout.addWidget(btn_box)

  def _save(self):
    key = self.api_key_input.text().strip()
    app_settings.set_value('google_vision_api_key', key)
    self.accept()


class PermissionDialog(QDialog):
  """アクセシビリティ権限の取得手順を案内するダイアログ."""

  def __init__(self, parent=None):
    super().__init__(parent)
    self.setWindowTitle('🔐 アクセシビリティ権限の許可手順')
    self.setMinimumSize(720, 640)

    layout = QVBoxLayout(self)

    title = QLabel('Pythonに「キー操作の送信」を許可してください')
    title_font = QFont()
    title_font.setPointSize(16)
    title_font.setBold(True)
    title.setFont(title_font)
    layout.addWidget(title)

    # 許可すべきバイナリパスをまず大きく表示
    py_path = get_real_python_binary()
    path_label = QLabel('⬇️ システム設定の「アクセシビリティ」に下記パスを追加してください ⬇️')
    path_label.setStyleSheet('color: #555; font-size: 12px; margin-top: 8px;')
    layout.addWidget(path_label)

    path_box = QLineEdit(py_path)
    path_box.setReadOnly(True)
    path_font = QFont('Menlo, Consolas, monospace')
    path_font.setPointSize(13)
    path_box.setFont(path_font)
    path_box.setStyleSheet(
      'color: #222; background-color: #FFF8E1; '
      'padding: 10px; border: 2px solid #FFA000; border-radius: 4px;'
    )
    layout.addWidget(path_box)

    btn_row = QHBoxLayout()
    copy_btn = QPushButton('📋 Pythonパスをコピー')
    copy_btn.setStyleSheet(
      'background-color: #2ECC71; color: white; font-weight: bold; '
      'padding: 10px; border-radius: 6px; border: none;'
    )
    def on_copy():
      if copy_to_clipboard_mac(py_path):
        copy_btn.setText('✅ コピーしました')
      else:
        copy_btn.setText('❌ コピー失敗')
    copy_btn.clicked.connect(on_copy)
    btn_row.addWidget(copy_btn)

    finder_btn = QPushButton('📁 Finderで表示')
    finder_btn.clicked.connect(lambda: reveal_in_finder_mac(py_path))
    btn_row.addWidget(finder_btn)

    settings_btn = QPushButton('⚙️ アクセシビリティ設定を開く')
    settings_btn.setStyleSheet(
      'background-color: #2E86DE; color: white; font-weight: bold; '
      'padding: 10px; border-radius: 6px; border: none;'
    )
    settings_btn.clicked.connect(lambda: open_accessibility_settings())
    btn_row.addWidget(settings_btn)
    layout.addLayout(btn_row)

    # 手順テキスト
    guide_label = QLabel('手順:')
    guide_label.setStyleSheet('font-weight: bold; margin-top: 12px;')
    layout.addWidget(guide_label)

    guide_text = QTextEdit()
    guide_text.setReadOnly(True)
    guide_text.setPlainText(PERMISSION_GUIDE_MAC)
    guide_text.setStyleSheet(
      'color: #222; background-color: #fafafa; '
      'border: 1px solid #d0d0d0; padding: 8px; '
      'font-family: -apple-system, "Hiragino Kaku Gothic ProN", sans-serif; font-size: 13px;'
    )
    layout.addWidget(guide_text, 1)

    btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    btn_box.rejected.connect(self.reject)
    layout.addWidget(btn_box)


# ===== スタイル定数（ライト固定、ダークモードでも見えるよう全色を明示） =====
APP_STYLESHEET = '''
  QWidget { color: #222; background-color: #f5f5f5; }
  QMainWindow { background-color: #f5f5f5; }
  QGroupBox { color: #222; background-color: #fafafa; }
  QLabel { color: #222; background: transparent; }
  QCheckBox {
    color: #222;
    background: transparent;
    padding: 6px 4px;
    spacing: 10px;
  }
  QCheckBox::indicator {
    width: 22px;
    height: 22px;
    border: 2px solid #888;
    border-radius: 4px;
    background-color: #ffffff;
  }
  QCheckBox::indicator:hover {
    border-color: #2E86DE;
    background-color: #f0f7ff;
  }
  QCheckBox::indicator:checked {
    background-color: #2ECC71;
    border-color: #27AE60;
    image: none;
  }
  QCheckBox::indicator:checked:hover {
    background-color: #27AE60;
  }
  QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    color: #222;
    background-color: #ffffff;
    border: 1px solid #c0c0c0;
    border-radius: 4px;
    padding: 4px 6px;
  }
  QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #2E86DE;
  }
  QComboBox QAbstractItemView {
    color: #222;
    background-color: #ffffff;
    selection-background-color: #2E86DE;
    selection-color: #ffffff;
  }
  QPushButton {
    color: #222;
    background-color: #e8e8e8;
    border: 1px solid #c0c0c0;
    border-radius: 4px;
    padding: 6px 12px;
  }
  QPushButton:hover { background-color: #d8d8d8; }
  QPushButton:disabled { color: #888; background-color: #e0e0e0; }
  QTabWidget::pane { border: 1px solid #c0c0c0; background-color: #f5f5f5; }
  QTabBar::tab {
    color: #222;
    background-color: #e0e0e0;
    padding: 8px 16px;
    border: 1px solid #c0c0c0;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
  }
  QTabBar::tab:selected { background-color: #ffffff; font-weight: bold; }
  QProgressBar {
    color: #222;
    background-color: #ffffff;
    border: 1px solid #c0c0c0;
    border-radius: 4px;
    text-align: center;
  }
  QProgressBar::chunk { background-color: #2E86DE; }
  QTextEdit { color: #222; background-color: #ffffff; border: 1px solid #c0c0c0; }
'''

STYLE_STEP_HEADER = '''
  background-color: #2E86DE;
  color: white;
  padding: 8px 12px;
  font-size: 15px;
  font-weight: bold;
  border-radius: 4px;
'''

STYLE_STEP_BOX = '''
  QGroupBox {
    border: 2px solid #d0d0d0;
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    background-color: #fafafa;
    color: #222;
  }
'''

STYLE_HELP = 'color: #555; background: transparent; font-size: 12px;'

STYLE_BIG_BUTTON = '''
  QPushButton {
    background-color: #2ECC71;
    color: white;
    font-size: 18px;
    font-weight: bold;
    padding: 14px;
    border-radius: 8px;
    border: none;
  }
  QPushButton:hover { background-color: #27AE60; }
  QPushButton:disabled { background-color: #95A5A6; color: #ddd; }
'''

STYLE_STOP_BUTTON = '''
  QPushButton {
    background-color: #E74C3C;
    color: white;
    font-weight: bold;
    padding: 8px 16px;
    border-radius: 6px;
    border: none;
  }
  QPushButton:disabled { background-color: #95A5A6; color: #ddd; }
'''


class Worker(QObject):
  progress = Signal(int, int, str)
  log = Signal(str)
  finished = Signal(object)
  failed = Signal(str)

  def __init__(self, func, *args, **kwargs):
    super().__init__()
    self._func = func
    self._args = args
    self._kwargs = kwargs
    self._stop = False

  def stop(self):
    self._stop = True

  def should_stop(self) -> bool:
    return self._stop

  def run(self):
    try:
      result = self._func(*self._args, **self._kwargs)
      self.finished.emit(result)
    except Exception:
      self.failed.emit(traceback.format_exc())


def make_step_header(num: int, title: str) -> QLabel:
  label = QLabel(f'STEP {num}　{title}')
  label.setStyleSheet(STYLE_STEP_HEADER)
  return label


def make_help(text: str) -> QLabel:
  label = QLabel(text)
  label.setStyleSheet(STYLE_HELP)
  label.setWordWrap(True)
  return label


class AllInOneTab(QWidget):
  """ステップガイド型の一括実行タブ.

  STEP 1: Kindle準備（チェックリスト）
  STEP 2: 設定入力
  STEP 3: 実行
  """

  def __init__(self, log_fn):
    super().__init__()
    self.log_fn = log_fn
    self._thread = None
    self._worker = None
    self._overlay = None
    self._pending_run = None
    self._selector: Optional[RegionSelector] = None
    self._capture_region: Optional[tuple[int, int, int, int]] = None  # (x, y, w, h)

    root = QVBoxLayout(self)
    root.setSpacing(8)

    intro = QLabel('Kindleアプリで開いた本を、検索可能なPDFに変換します。')
    intro_font = QFont()
    intro_font.setPointSize(14)
    intro_font.setBold(True)
    intro.setFont(intro_font)
    root.addWidget(intro)

    # ===== STEP 1: Kindle準備 =====
    root.addWidget(make_step_header(1, 'Kindleアプリで本を準備'))

    step1 = QGroupBox()
    step1.setStyleSheet(STYLE_STEP_BOX)
    s1 = QVBoxLayout(step1)

    s1.addWidget(make_help(
      'このアプリは「Kindleで表示中の本のページ」をスクショで連続取得します。'
      '実行前に以下を準備してください:'
    ))

    self.chk1 = QCheckBox('① Kindleアプリを起動した（起動済みなら自動で最前面に切り替わります）')
    self.chk2 = QCheckBox('② 読みたい本を開き、「1ページ目（最初のページ）」を表示している')
    self.chk3 = QCheckBox('③ 見開き表示はOFF（単ページ表示にしている）')
    if is_mac():
      self.chk4 = QCheckBox('④ 「アクセシビリティ」権限を許可した（後述）/ キャプチャ中は触らない承知')
    else:
      self.chk4 = QCheckBox('④ キャプチャ中はマウス・キーボードに触らないことを承知')

    for chk in [self.chk1, self.chk2, self.chk3, self.chk4]:
      chk.setStyleSheet('QCheckBox { padding: 4px; font-size: 13px; }')
      chk.stateChanged.connect(self._update_start_button)
      s1.addWidget(chk)

    s1.addWidget(make_help(
      '🆘 緊急停止: マウスを画面左上端（0,0座標）に動かすと即座に停止します（pyautogui failsafe）。'
    ))

    # macOS のみ権限ヘルパーボックスを表示（Windowsでは権限管理不要）
    if is_mac():
      perm_box = QGroupBox('🔐 macOS 権限ヘルパー')
      perm_box.setStyleSheet(
        'QGroupBox { color: #6B4423; background-color: #FFF3CD; '
        'padding: 12px 8px 8px 8px; border-radius: 4px; border: 1px solid #FFC107; }'
      )
      perm_layout = QVBoxLayout(perm_box)

      perm_info = QLabel(
        '初回実行時、macOSは「アクセシビリティ」と「画面収録」の許可を要求します。\n'
        'まず下の「診断テスト」を実行 → 失敗した項目の権限を許可 → アプリ再起動。'
      )
      perm_info.setStyleSheet('color: #6B4423; background: transparent; font-size: 12px;')
      perm_info.setWordWrap(True)
      perm_layout.addWidget(perm_info)

      perm_btn_row = QHBoxLayout()
      diag_btn = QPushButton('🔧 診断テスト')
      diag_btn.clicked.connect(self._run_diagnostic)
      perm_btn_row.addWidget(diag_btn)

      help_btn = QPushButton('📖 権限の許可手順を見る')
      help_btn.setStyleSheet(
        'background-color: #2E86DE; color: white; font-weight: bold; '
        'padding: 6px 12px; border-radius: 4px; border: none;'
      )
      help_btn.clicked.connect(self._show_permission_helper)
      perm_btn_row.addWidget(help_btn)
      perm_layout.addLayout(perm_btn_row)

      perm_btn_row2 = QHBoxLayout()
      acc_btn = QPushButton('⚙️ アクセシビリティ設定を開く')
      acc_btn.clicked.connect(lambda: open_accessibility_settings())
      perm_btn_row2.addWidget(acc_btn)

      sr_btn = QPushButton('⚙️ 画面収録設定を開く')
      sr_btn.clicked.connect(lambda: open_screen_recording_settings())
      perm_btn_row2.addWidget(sr_btn)
      perm_layout.addLayout(perm_btn_row2)

      s1.addWidget(perm_box)
    else:
      # Windows / Linux 用: 簡易ノートのみ
      win_info = QLabel(
        '💡 Windows では権限設定は不要です。Kindleアプリを起動して「実行する」を押すだけ。\n'
        '（tesseractインストール時に日本語言語データを必ず含めてください）'
      )
      win_info.setStyleSheet(
        'color: #1e6b3e; background-color: #d4edda; padding: 10px; '
        'border-radius: 4px; border: 1px solid #c3e6cb; font-size: 12px;'
      )
      win_info.setWordWrap(True)
      s1.addWidget(win_info)
    root.addWidget(step1)

    # ===== STEP 2: 設定 =====
    root.addWidget(make_step_header(2, 'キャプチャ設定'))

    step2 = QGroupBox()
    step2.setStyleSheet(STYLE_STEP_BOX)
    s2 = QVBoxLayout(step2)

    # 総ページ数
    r1 = QHBoxLayout()
    r1.addWidget(QLabel('総ページ数:'))
    self.total_pages = QSpinBox()
    self.total_pages.setRange(1, 9999)
    self.total_pages.setValue(300)
    self.total_pages.setMaximumWidth(100)
    r1.addWidget(self.total_pages)
    r1.addWidget(make_help('本のページ数より少し多めに（同じ画面を2回検出したら自動停止）'))
    r1.addStretch()
    s2.addLayout(r1)

    # 言語
    r2 = QHBoxLayout()
    r2.addWidget(QLabel('言語（OCR）:'))
    self.language = QComboBox()
    self.language.addItem('日本語+英語（横書き）', 'jpn+eng')
    self.language.addItem('日本語のみ（横書き）', 'jpn')
    self.language.addItem('英語のみ', 'eng')
    self.language.addItem('日本語+英語（縦書き）', 'jpn_vert+eng')
    self.language.addItem('日本語のみ（縦書き）', 'jpn_vert')
    self.language.setMinimumWidth(220)
    r2.addWidget(self.language)
    r2.addWidget(make_help('小説・縦書き本は「縦書き」、ビジネス書・横書き本は「横書き」'))
    r2.addStretch()
    s2.addLayout(r2)

    # OCRエンジン選択
    r_engine = QHBoxLayout()
    r_engine.addWidget(QLabel('OCRエンジン:'))
    self.engine = QComboBox()
    self._refill_engines()
    self.engine.setMinimumWidth(280)
    r_engine.addWidget(self.engine)
    settings_btn = QPushButton('⚙️ 詳細設定…')
    settings_btn.clicked.connect(self._open_settings)
    settings_btn.setStyleSheet(
      'background-color: #e8e8e8; padding: 4px 12px; border-radius: 4px; '
      'border: 1px solid #c0c0c0;'
    )
    r_engine.addWidget(settings_btn)
    r_engine.addStretch()
    s2.addLayout(r_engine)
    s2.addWidget(make_help(
      'Apple Vision: Mac標準・最速・無料 / Tesseract: 互換性重視 / '
      'Google Vision: APIキー設定で最高精度 / Yomitoku: 日本語特化（要インストール）'
    ))

    # ページ間隔
    r3 = QHBoxLayout()
    r3.addWidget(QLabel('ページめくり間隔:'))
    self.delay = QDoubleSpinBox()
    self.delay.setRange(0.3, 10.0)
    self.delay.setSingleStep(0.1)
    self.delay.setValue(1.0)
    self.delay.setSuffix(' 秒')
    self.delay.setMaximumWidth(100)
    r3.addWidget(self.delay)
    r3.addWidget(make_help('Kindleのページめくりアニメーション完了待ち。ブレるなら長めに'))
    r3.addStretch()
    s2.addLayout(r3)

    # カウントダウン
    r4 = QHBoxLayout()
    r4.addWidget(QLabel('開始までの猶予:'))
    self.countdown = QSpinBox()
    self.countdown.setRange(3, 30)
    self.countdown.setValue(5)
    self.countdown.setSuffix(' 秒')
    self.countdown.setMaximumWidth(100)
    r4.addWidget(self.countdown)
    r4.addWidget(make_help('実行ボタン後、この秒数で「Kindleウィンドウに切り替え」する時間'))
    r4.addStretch()
    s2.addLayout(r4)

    # キャプチャ範囲（重要）
    r_region = QHBoxLayout()
    r_region.addWidget(QLabel('キャプチャ範囲:'))
    self.region_label = QLabel('全画面（フルスクリーン）')
    self.region_label.setStyleSheet(
      'color: #222; background-color: #ffffff; '
      'padding: 4px 8px; border: 1px solid #c0c0c0; border-radius: 4px;'
    )
    r_region.addWidget(self.region_label, 1)
    pick_btn = QPushButton('📐 範囲を選ぶ…')
    pick_btn.setStyleSheet(
      'background-color: #2E86DE; color: white; font-weight: bold; '
      'padding: 6px 12px; border-radius: 4px; border: none;'
    )
    pick_btn.clicked.connect(self._pick_region)
    r_region.addWidget(pick_btn)
    reset_btn = QPushButton('リセット')
    reset_btn.clicked.connect(self._reset_region)
    r_region.addWidget(reset_btn)
    s2.addLayout(r_region)
    s2.addWidget(make_help(
      'OCR精度を上げるため、Kindleの「本文だけ」をドラッグで選択。'
      'メニューバーやサイドバーを含めないと精度が大幅向上。'
    ))

    # 出力
    s2.addWidget(QFrame())  # spacer
    r5 = QHBoxLayout()
    r5.addWidget(QLabel('書名（出力ファイル名）:'))
    self.book_name = QLineEdit('my_book')
    r5.addWidget(self.book_name)
    s2.addLayout(r5)

    r6 = QHBoxLayout()
    r6.addWidget(QLabel('保存先フォルダ:'))
    self.output_dir = QLineEdit(str(Path.home() / 'Desktop'))
    r6.addWidget(self.output_dir)
    browse = QPushButton('参照…')
    browse.clicked.connect(self._browse_dir)
    r6.addWidget(browse)
    s2.addLayout(r6)
    s2.addWidget(make_help('完成PDFは「保存先フォルダ／書名_OCR.pdf」に出力されます'))

    root.addWidget(step2)

    # ===== STEP 3: 実行 =====
    root.addWidget(make_step_header(3, '実行'))

    step3 = QGroupBox()
    step3.setStyleSheet(STYLE_STEP_BOX)
    s3 = QVBoxLayout(step3)

    self.run_hint = QLabel(
      '上の①〜④をすべてチェックしてから「実行」ボタンが押せるようになります。\n'
      '実行ボタンを押すと、カウントダウン後にKindleアプリを自動で最前面に切り替えて\n'
      'キャプチャを開始します。手動でKindleを切り替える必要はありません。'
    )
    self.run_hint.setStyleSheet(
      'color: #333; background-color: #FFF9C4; '
      'font-size: 13px; padding: 10px; border-radius: 4px; '
      'border: 1px solid #F0DC8C;'
    )
    self.run_hint.setWordWrap(True)
    s3.addWidget(self.run_hint)

    btn_row = QHBoxLayout()
    self.start_btn = QPushButton('▶ 実行する')
    self.start_btn.setStyleSheet(STYLE_BIG_BUTTON)
    self.start_btn.setEnabled(False)
    self.start_btn.clicked.connect(self._start)
    btn_row.addWidget(self.start_btn, 3)

    self.stop_btn = QPushButton('■ 停止')
    self.stop_btn.setStyleSheet(STYLE_STOP_BUTTON)
    self.stop_btn.setEnabled(False)
    self.stop_btn.clicked.connect(self._stop)
    btn_row.addWidget(self.stop_btn, 1)
    s3.addLayout(btn_row)

    self.progress = QProgressBar()
    self.progress.setMinimumHeight(28)
    s3.addWidget(self.progress)

    self.status = QLabel('待機中')
    status_font = QFont()
    status_font.setPointSize(13)
    self.status.setFont(status_font)
    s3.addWidget(self.status)

    root.addWidget(step3)
    root.addStretch()

  def _show_permission_helper(self):
    self._show_simple_permission_guide()

  def _show_simple_permission_guide(self):
    """設定アプリを開いてシンプルな2ステップ指示を出す."""
    import os
    # .appバンドルから起動された場合、C launcher が環境変数をセットしている
    in_bundle = os.environ.get('KINDLE_OCR_FROM_BUNDLE') == '1'
    if in_bundle:
      # .appバンドルから起動 → 設定リストに「Kindle OCR」が追加されているはず
      open_accessibility_settings()
      msg = (
        '✅ 「システム設定 → アクセシビリティ」を開きました\n\n'
        '━━━ 設定アプリでやること（2ステップ） ━━━\n\n'
        '【ステップ1】 リストの中に「Kindle OCR」を探す\n'
        '　（「Python」や「Terminal」ではなく「Kindle OCR」）\n\n'
        '【ステップ2】 右側のトグルスイッチを ON\n'
        '　（パスワードを求められたら入力）\n\n'
        '━━━ 完了したら ━━━\n\n'
        '1. このアプリを ⌘Q で完全終了\n'
        '2. Finder で「Kindle OCR.app」をダブルクリック再起動\n'
        '3. もう一度「🔧 診断テスト」を実行\n\n'
        '━━━ もし「Kindle OCR」がリストに無い場合 ━━━\n\n'
        '左下の「＋」ボタンをクリック →\n'
        'Finder で ~/dev/kindle-ocr-app/Kindle OCR.app を選んで追加'
      )
      title = '権限設定（あと2ステップ）'
    else:
      # ターミナル起動 → .appで再起動を促す
      msg = (
        'ターミナル経由で起動した場合は、macOSの権限管理が機能しません。\n\n'
        '✨ 解決方法: 専用の.appバンドルで起動する\n\n'
        '【手順】\n'
        '1. このアプリを ⌘Q で完全終了\n'
        '2. Finder で ~/dev/kindle-ocr-app/ を開く\n'
        '3. 「Kindle OCR.app」をダブルクリック\n\n'
        '初回起動後、もう一度「🔧 診断テスト」を実行。\n'
        '権限エラーが出たら同じダイアログで設定方法を案内します。'
      )
      title = '権限が必要 — .appで再起動してください'

    msg_box = QMessageBox(self)
    msg_box.setWindowTitle(title)
    msg_box.setText(msg)
    msg_box.setIcon(QMessageBox.Icon.Information)
    msg_box.exec()

  def _refill_engines(self):
    """OCRエンジン一覧をリフレッシュ（設定変更後に呼ぶ）."""
    current_data = self.engine.currentData() if self.engine.count() else None
    self.engine.blockSignals(True)
    self.engine.clear()
    for eid, ename in list_available_engines():
      self.engine.addItem(ename, eid)
    # 直前の選択を復元
    if current_data:
      idx = self.engine.findData(current_data)
      if idx >= 0:
        self.engine.setCurrentIndex(idx)
    self.engine.blockSignals(False)

  def _open_settings(self):
    dlg = SettingsDialog(self)
    if dlg.exec():
      self._refill_engines()
      self.log_fn('OCR設定を更新しました')

  def _pick_region(self):
    """フルスクリーンオーバーレイで範囲を選ばせる.

    手順:
    1. このウィンドウを最小化（前面から退ける）
    2. Kindle を最前面にアクティベート
    3. 少し待ってからスクショ取得 → 範囲選択オーバーレイ表示
    """
    # メインウィンドウを最小化（Kindleが完全に見えるように）
    main_win = self.window()
    if main_win:
      main_win.showMinimized()

    # Kindleを前面に
    if is_mac():
      activate_kindle()

    # 0.8秒後にスクショ取得→オーバーレイ表示
    QTimer.singleShot(800, self._launch_selector)

  def _launch_selector(self):
    self._selector = RegionSelector()
    self._selector.selected.connect(self._on_region_selected)
    self._selector.cancelled.connect(self._on_region_cancelled)
    self._selector.show_fullscreen()

  def _on_region_selected(self, region: tuple):
    x, y, w, h = region
    self._capture_region = region
    self.region_label.setText(f'x={x}, y={y}, 幅={w}, 高さ={h}（{w}×{h}px）')
    self.log_fn(f'キャプチャ範囲を設定: {region}')
    self._selector = None
    self._restore_main_window()

  def _on_region_cancelled(self):
    self._selector = None
    self.log_fn('範囲選択を取消')
    self._restore_main_window()

  def _restore_main_window(self):
    main_win = self.window()
    if main_win:
      main_win.showNormal()
      main_win.raise_()
      main_win.activateWindow()

  def _reset_region(self):
    self._capture_region = None
    self.region_label.setText('全画面（フルスクリーン）')
    self.log_fn('キャプチャ範囲をリセット（全画面）')

  def _run_diagnostic(self):
    """Mac権限・Kindle検出・キー送信を診断."""
    import mss
    lines = []
    lines.append('=== Kindle OCR App 診断 ===\n')

    # 1. Pythonバイナリ
    lines.append('【1】Pythonバイナリ')
    lines.append(get_python_binary_info())
    lines.append('→ アクセシビリティ・画面収録 はこのバイナリ（の親プロセス）に許可が必要')
    lines.append('')

    # 2. Kindle検出
    lines.append('【2】Kindleアプリ検出')
    if is_kindle_running():
      lines.append('✅ Kindleアプリが起動中')
    else:
      lines.append('❌ Kindleアプリが起動していません')
      lines.append('→ Kindleアプリを起動して本を開いてから再実行')
    lines.append('')

    # 3. Kindleアクティベート
    lines.append('【3】Kindleアクティベート')
    ok, msg = activate_kindle()
    lines.append(('✅ ' if ok else '❌ ') + msg)
    lines.append('')

    # 4. スクショ
    lines.append('【4】スクリーンショット')
    try:
      with mss.mss() as sct:
        img = sct.grab(sct.monitors[1])
        lines.append(f'✅ スクショ成功 ({img.size.width}×{img.size.height}px)')
    except Exception as e:
      lines.append(f'❌ スクショ失敗: {e}')
      lines.append('→ 「画面収録」権限を許可してください')
    lines.append('')

    # 5. アクセシビリティ権限を ctypes 経由で直接検証
    key_send_ok = True
    lines.append('【5】アクセシビリティ権限を直接検証（ctypes）')
    try:
      import ctypes
      lib = ctypes.CDLL('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
      lib.AXIsProcessTrusted.restype = ctypes.c_bool
      trusted = bool(lib.AXIsProcessTrusted())
      lines.append(f'AXIsProcessTrusted: {trusted}')
      if trusted:
        lines.append('✅ プロセスはアクセシビリティ許可済み')
      else:
        key_send_ok = False
        lines.append('❌ プロセスはアクセシビリティ未許可')
        lines.append('→ pyautogui.press() は無音で失敗します')
        lines.append('→ .appバンドル経由起動 + 「Kindle OCR」をリストに追加 + トグルON が必要')
    except Exception as e:
      lines.append(f'⚠️ 検証失敗: {e}')
    lines.append('')

    # 6. 実証テスト: Kindle アクティベート → スクショ → 右キー → スクショ → 差分検証
    lines.append('【6】Kindle に対する実キー送信テスト')
    try:
      import time
      import hashlib
      import mss
      import mss.tools
      import pyautogui

      # Kindle 最前面化
      ok, msg = activate_kindle()
      if not ok:
        lines.append(f'⚠️ Kindleアクティベート失敗: {msg}')
      else:
        time.sleep(0.6)

        with mss.mss() as sct:
          # 画面中央付近のみ比較（時計やマウスカーソル位置を避ける）
          mon = sct.monitors[1]
          w, h = mon['width'], mon['height']
          region = {
            'left': mon['left'] + w // 4,
            'top': mon['top'] + h // 4,
            'width': w // 2,
            'height': h // 2,
          }

          img1 = sct.grab(region)
          hash1 = hashlib.md5(bytes(img1.rgb)).hexdigest()

          # 右キー送信
          pyautogui.press('right')
          time.sleep(1.2)  # Kindleのページめくり待ち

          img2 = sct.grab(region)
          hash2 = hashlib.md5(bytes(img2.rgb)).hexdigest()

          if hash1 != hash2:
            lines.append('✅ Kindleのページが進みました（キー送信成功）')
          else:
            key_send_ok = False
            lines.append('❌ Kindleのページが変わりません')
            lines.append('→ キーがKindleに届いていません')
            lines.append('→ Pythonがアクセシビリティ権限を持っていない可能性大')
    except Exception as e:
      lines.append(f'⚠️ 実証テスト失敗: {e}')
    lines.append('')

    if key_send_ok:
      lines.append('=== ✅ すべて成功 — キャプチャ実行可能 ===')
    else:
      lines.append('=== ⚠️ 権限不足あり — このあと設定アプリを開きます ===')

    report = '\n'.join(lines)
    self.log_fn('診断テスト実行')
    for line in lines:
      self.log_fn(line)

    msg_box = QMessageBox(self)
    msg_box.setWindowTitle('診断結果')
    msg_box.setText(report)
    msg_box.setIcon(QMessageBox.Icon.Information)
    msg_box.exec()

    # キー送信失敗 → 設定アプリを開いて簡潔なガイドを出す
    if is_mac() and not key_send_ok:
      self._show_simple_permission_guide()

  def _update_start_button(self):
    ok = all([self.chk1.isChecked(), self.chk2.isChecked(),
              self.chk3.isChecked(), self.chk4.isChecked()])
    self.start_btn.setEnabled(ok)

  def _browse_dir(self):
    d = QFileDialog.getExistingDirectory(self, '保存先', self.output_dir.text())
    if d:
      self.output_dir.setText(d)

  def _start(self):
    book_name = self.book_name.text().strip() or 'kindle_book'
    output_dir = Path(self.output_dir.text())
    if not output_dir.exists():
      QMessageBox.warning(self, 'エラー', f'保存先フォルダが存在しません:\n{output_dir}')
      return

    config = CaptureConfig(
      total_pages=self.total_pages.value(),
      delay_sec=self.delay.value(),
      countdown_sec=0,  # オーバーレイで代替するのでcapture内のカウントダウンは0
      region=self._capture_region,
    )
    language = self.language.currentData()

    self._pending_run = (config, language, book_name, output_dir)

    self.start_btn.setEnabled(False)
    self.stop_btn.setEnabled(True)
    self.status.setText('カウントダウン中…Kindleアプリを最前面にクリックしてください')

    countdown_sec = self.countdown.value()
    self._overlay = CountdownOverlay(
      seconds=countdown_sec,
      message='カウントダウン後、自動でKindleを最前面に切り替えます',
    )
    self._overlay.finished.connect(self._begin_capture)
    self._overlay.start()
    self.log_fn(f'カウントダウン開始: {countdown_sec}秒')

  def _begin_capture(self):
    if self._pending_run is None:
      return
    config, language, book_name, output_dir = self._pending_run
    self._pending_run = None

    tmp_dir = Path(tempfile.mkdtemp(prefix='kindle_ocr_'))
    png_dir = tmp_dir / 'pngs'
    raw_pdf = tmp_dir / f'{book_name}_raw.pdf'
    ocr_pdf = output_dir / f'{book_name}_OCR.pdf'
    md_path = output_dir / f'{book_name}.md'

    self.progress.setMaximum(config.total_pages)
    self.progress.setValue(0)
    self.log_fn(f'キャプチャ開始 → {ocr_pdf}')

    self._thread = QThread()

    engine = self.engine.currentData()

    def pipeline(progress_cb, stop_cb):
      progress_cb(0, config.total_pages, 'Step 1/3: Kindleキャプチャ中…')
      images = capture_kindle(png_dir, config, progress=progress_cb, should_stop=stop_cb)
      if not images:
        raise RuntimeError('キャプチャ画像が0枚（ページが進まなかった可能性）')

      # Apple Vision なら画像から直接、Tesseract なら img2pdf 経由
      progress_cb(0, len(images), 'Step 2/3: OCR実行中…')
      run_ocr_from_images(
        images, ocr_pdf,
        engine=engine,
        language=language,
        progress=lambda cur, total, m: progress_cb(cur, total, f'Step 2/3: {m}'),
      )

      progress_cb(len(images), len(images), 'Step 3/3: Markdownファイル生成中…')
      try:
        export_pdf_to_markdown(ocr_pdf, md_path, book_title=book_name)
      except Exception as e:
        progress_cb(len(images), len(images), f'⚠️ MD生成スキップ: {e}')

      return (ocr_pdf, md_path if md_path.exists() else None)

    self._worker = Worker(
      pipeline,
      progress_cb=lambda c, t, m: self._worker.progress.emit(c, t, m),
      stop_cb=lambda: self._worker.should_stop(),
    )
    self._worker.moveToThread(self._thread)
    self._thread.started.connect(self._worker.run)
    self._worker.progress.connect(self._on_progress)
    self._worker.finished.connect(self._on_finished)
    self._worker.failed.connect(self._on_failed)
    self._thread.start()

  def _stop(self):
    if self._worker:
      self._worker.stop()
    self.log_fn('停止リクエスト送信')

  def _on_progress(self, c, t, m):
    self.progress.setMaximum(max(t, 1))
    self.progress.setValue(c)
    self.status.setText(m)
    self.log_fn(m)

  def _on_finished(self, result):
    # pipeline は (ocr_pdf, md_path or None) を返すが、レガシー互換のため Path 単体も許容
    if isinstance(result, tuple):
      ocr_pdf, md_path = result
    else:
      ocr_pdf, md_path = result, None
    self.log_fn(f'全工程完了: {ocr_pdf}')
    if md_path:
      self.log_fn(f'Markdown生成: {md_path}')
    self.status.setText(f'✅ 完了: {ocr_pdf}')
    files_msg = f'検索可能PDF:\n{ocr_pdf}'
    if md_path:
      files_msg += f'\n\nMarkdownファイル:\n{md_path}'
    QMessageBox.information(
      self, '完了',
      files_msg + '\n\nPreview/Acrobatで開けば、テキスト選択・検索ができます。'
    )
    self._cleanup()

  def _on_failed(self, tb):
    self.log_fn(f'エラー: {tb}')
    QMessageBox.critical(self, 'エラー', tb)
    self.status.setText('❌ エラー（ログを確認）')
    self._cleanup()

  def _cleanup(self):
    self._update_start_button()
    self.stop_btn.setEnabled(False)
    if self._thread:
      self._thread.quit()
      self._thread.wait()
      self._thread = None
      self._worker = None


class CaptureOnlyTab(QWidget):
  """Kindleキャプチャのみ（OCRなし、PNGファイル出力）."""

  def __init__(self, log_fn):
    super().__init__()
    self.log_fn = log_fn
    self._thread = None
    self._worker = None
    self._overlay = None
    self._pending_run = None

    layout = QVBoxLayout(self)

    intro = QLabel('Kindleページをスクショして PNG ファイルとして保存します（OCRなし）')
    intro.setStyleSheet('font-weight: bold; padding: 6px;')
    layout.addWidget(intro)

    settings = QGroupBox('キャプチャ設定')
    s_layout = QVBoxLayout(settings)

    r1 = QHBoxLayout()
    r1.addWidget(QLabel('総ページ数:'))
    self.total_pages = QSpinBox()
    self.total_pages.setRange(1, 9999)
    self.total_pages.setValue(300)
    r1.addWidget(self.total_pages)
    r1.addWidget(QLabel('間隔(秒):'))
    self.delay = QDoubleSpinBox()
    self.delay.setRange(0.1, 10.0)
    self.delay.setSingleStep(0.1)
    self.delay.setValue(1.0)
    r1.addWidget(self.delay)
    r1.addWidget(QLabel('カウントダウン(秒):'))
    self.countdown = QSpinBox()
    self.countdown.setRange(3, 30)
    self.countdown.setValue(5)
    r1.addWidget(self.countdown)
    s_layout.addLayout(r1)

    r2 = QHBoxLayout()
    r2.addWidget(QLabel('ページ送りキー:'))
    self.page_key = QComboBox()
    self.page_key.addItems(['right', 'left', 'down', 'up', 'space', 'pagedown'])
    r2.addWidget(self.page_key)
    r2.addStretch()
    s_layout.addLayout(r2)

    r3 = QHBoxLayout()
    r3.addWidget(QLabel('出力フォルダ:'))
    self.output_dir = QLineEdit(str(Path.home() / 'Desktop' / 'kindle_capture'))
    r3.addWidget(self.output_dir)
    browse = QPushButton('参照…')
    browse.clicked.connect(self._browse_dir)
    r3.addWidget(browse)
    s_layout.addLayout(r3)

    layout.addWidget(settings)

    btn_row = QHBoxLayout()
    self.start_btn = QPushButton('▶ キャプチャ開始')
    self.start_btn.setStyleSheet(STYLE_BIG_BUTTON)
    self.start_btn.clicked.connect(self._start)
    btn_row.addWidget(self.start_btn)

    self.stop_btn = QPushButton('■ 停止')
    self.stop_btn.setStyleSheet(STYLE_STOP_BUTTON)
    self.stop_btn.setEnabled(False)
    self.stop_btn.clicked.connect(self._stop)
    btn_row.addWidget(self.stop_btn)
    layout.addLayout(btn_row)

    self.progress = QProgressBar()
    layout.addWidget(self.progress)
    self.status = QLabel('待機中')
    layout.addWidget(self.status)

    layout.addWidget(make_help(
      '⚠️ 実行後、画面中央のカウントダウン中にKindleウィンドウを最前面にクリックしてください。'
      'マウスを画面左上端に動かすと緊急停止。'
    ))
    layout.addStretch()

  def _browse_dir(self):
    d = QFileDialog.getExistingDirectory(self, '出力フォルダ', self.output_dir.text())
    if d:
      self.output_dir.setText(d)

  def _start(self):
    config = CaptureConfig(
      total_pages=self.total_pages.value(),
      delay_sec=self.delay.value(),
      countdown_sec=0,
      page_key=self.page_key.currentText(),
    )
    output_dir = Path(self.output_dir.text())
    self._pending_run = (config, output_dir)

    self.start_btn.setEnabled(False)
    self.stop_btn.setEnabled(True)
    self.status.setText('カウントダウン中…Kindleを最前面に')

    self._overlay = CountdownOverlay(
      seconds=self.countdown.value(),
      message='カウントダウン後、自動でKindleを最前面に切り替えます',
    )
    self._overlay.finished.connect(self._begin)
    self._overlay.start()

  def _begin(self):
    if self._pending_run is None:
      return
    config, output_dir = self._pending_run
    self._pending_run = None
    self.progress.setMaximum(config.total_pages)
    self.log_fn(f'キャプチャ開始: {output_dir}')

    self._thread = QThread()
    self._worker = Worker(
      capture_kindle,
      output_dir,
      config,
      progress=lambda c, t, m: self._worker.progress.emit(c, t, m),
      should_stop=lambda: self._worker.should_stop(),
    )
    self._worker.moveToThread(self._thread)
    self._thread.started.connect(self._worker.run)
    self._worker.progress.connect(self._on_progress)
    self._worker.finished.connect(self._on_finished)
    self._worker.failed.connect(self._on_failed)
    self._thread.start()

  def _stop(self):
    if self._worker:
      self._worker.stop()

  def _on_progress(self, c, t, m):
    self.progress.setValue(c)
    self.status.setText(m)

  def _on_finished(self, result):
    self.log_fn(f'キャプチャ完了: {len(result)}枚')
    self.status.setText(f'✅ 完了: {len(result)}枚')
    self._cleanup()

  def _on_failed(self, tb):
    self.log_fn(f'エラー: {tb}')
    QMessageBox.critical(self, 'エラー', tb)
    self._cleanup()

  def _cleanup(self):
    self.start_btn.setEnabled(True)
    self.stop_btn.setEnabled(False)
    if self._thread:
      self._thread.quit()
      self._thread.wait()
      self._thread = None
      self._worker = None


class OcrOnlyTab(QWidget):
  """既存PDFをOCR化するだけのタブ."""

  def __init__(self, log_fn):
    super().__init__()
    self.log_fn = log_fn
    self._thread = None
    self._worker = None

    layout = QVBoxLayout(self)

    intro = QLabel('既存のPDFをOCR化して検索可能PDFを生成（Kindleキャプチャは行いません）')
    intro.setStyleSheet('font-weight: bold; padding: 6px;')
    layout.addWidget(intro)

    settings = QGroupBox('OCR設定')
    s_layout = QVBoxLayout(settings)

    r1 = QHBoxLayout()
    r1.addWidget(QLabel('入力PDF:'))
    self.input_pdf = QLineEdit()
    r1.addWidget(self.input_pdf)
    b1 = QPushButton('参照…')
    b1.clicked.connect(self._browse_input)
    r1.addWidget(b1)
    s_layout.addLayout(r1)

    r2 = QHBoxLayout()
    r2.addWidget(QLabel('出力PDF:'))
    self.output_pdf = QLineEdit()
    r2.addWidget(self.output_pdf)
    b2 = QPushButton('参照…')
    b2.clicked.connect(self._browse_output)
    r2.addWidget(b2)
    s_layout.addLayout(r2)

    r3 = QHBoxLayout()
    r3.addWidget(QLabel('言語:'))
    self.language = QComboBox()
    self.language.addItem('日本語+英語（横書き）', 'jpn+eng')
    self.language.addItem('日本語のみ（横書き）', 'jpn')
    self.language.addItem('英語のみ', 'eng')
    self.language.addItem('日本語+英語（縦書き）', 'jpn_vert+eng')
    r3.addWidget(self.language)
    r3.addWidget(QLabel('並列数:'))
    self.jobs = QSpinBox()
    self.jobs.setRange(1, 16)
    self.jobs.setValue(4)
    r3.addWidget(self.jobs)
    self.skip_text = QCheckBox('既存テキストレイヤーがあるページはスキップ')
    self.skip_text.setChecked(True)
    r3.addWidget(self.skip_text)
    self.high_quality = QCheckBox('高画質モード（傾き補正・高解像度OCR）')
    self.high_quality.setChecked(True)
    r3.addWidget(self.high_quality)
    s_layout.addLayout(r3)

    layout.addWidget(settings)

    self.start_btn = QPushButton('▶ OCR実行')
    self.start_btn.setStyleSheet(STYLE_BIG_BUTTON)
    self.start_btn.clicked.connect(self._start)
    layout.addWidget(self.start_btn)

    self.progress = QProgressBar()
    self.progress.setRange(0, 0)
    self.progress.setVisible(False)
    layout.addWidget(self.progress)
    self.status = QLabel('待機中')
    layout.addWidget(self.status)
    layout.addStretch()

  def _browse_input(self):
    f, _ = QFileDialog.getOpenFileName(self, '入力PDF', str(Path.home() / 'Desktop'), 'PDF (*.pdf)')
    if f:
      self.input_pdf.setText(f)
      if not self.output_pdf.text():
        p = Path(f)
        self.output_pdf.setText(str(p.with_name(p.stem + '_OCR.pdf')))

  def _browse_output(self):
    f, _ = QFileDialog.getSaveFileName(self, '出力PDF', str(Path.home() / 'Desktop'), 'PDF (*.pdf)')
    if f:
      self.output_pdf.setText(f)

  def _start(self):
    in_pdf = Path(self.input_pdf.text())
    out_pdf = Path(self.output_pdf.text())
    if not in_pdf.exists():
      QMessageBox.warning(self, 'エラー', '入力PDFが見つかりません')
      return

    self.start_btn.setEnabled(False)
    self.progress.setVisible(True)
    self.status.setText('OCR実行中…')
    self.log_fn(f'OCR開始: {in_pdf.name}')

    self._thread = QThread()
    self._worker = Worker(
      run_ocr,
      in_pdf,
      out_pdf,
      language=self.language.currentData(),
      skip_text=self.skip_text.isChecked(),
      jobs=self.jobs.value(),
      high_quality=self.high_quality.isChecked(),
      progress=lambda m: self._worker.log.emit(m),
    )
    self._worker.moveToThread(self._thread)
    self._thread.started.connect(self._worker.run)
    self._worker.log.connect(self.log_fn)
    self._worker.finished.connect(self._on_finished)
    self._worker.failed.connect(self._on_failed)
    self._thread.start()

  def _on_finished(self, result):
    self.log_fn(f'OCR完了: {result}')
    self.status.setText(f'✅ 完了: {result}')
    QMessageBox.information(self, '完了', f'OCR完了\n\n{result}')
    self._cleanup()

  def _on_failed(self, tb):
    self.log_fn(f'OCRエラー: {tb}')
    QMessageBox.critical(self, 'エラー', tb)
    self._cleanup()

  def _cleanup(self):
    self.start_btn.setEnabled(True)
    self.progress.setVisible(False)
    if self._thread:
      self._thread.quit()
      self._thread.wait()
      self._thread = None
      self._worker = None


class MainWindow(QMainWindow):
  def __init__(self):
    super().__init__()
    self.setWindowTitle('Kindle OCR App')
    self.resize(900, 820)

    central = QWidget()
    self.setCentralWidget(central)
    layout = QVBoxLayout(central)
    layout.setContentsMargins(12, 12, 12, 12)

    def wrap_scroll(widget):
      """中身が縦に長くなるTabをスクロール可能にする."""
      sa = QScrollArea()
      sa.setWidgetResizable(True)
      sa.setWidget(widget)
      sa.setStyleSheet('QScrollArea { border: none; background-color: #f5f5f5; }')
      return sa

    tabs = QTabWidget()
    tabs.addTab(wrap_scroll(AllInOneTab(self.log)), '📖 Kindleキャプチャ＋OCR＋MD')
    tabs.addTab(wrap_scroll(CaptureOnlyTab(self.log)), '📸 キャプチャのみ')
    tabs.addTab(wrap_scroll(OcrOnlyTab(self.log)), '🔍 OCRのみ')
    layout.addWidget(tabs, 1)

    log_label = QLabel('実行ログ:')
    log_label.setStyleSheet('font-weight: bold; margin-top: 6px;')
    layout.addWidget(log_label)
    self.log_view = QTextEdit()
    self.log_view.setReadOnly(True)
    self.log_view.setMaximumHeight(120)
    self.log_view.setStyleSheet(
      'color: #222; background-color: #ffffff; border: 1px solid #c0c0c0;'
      'font-family: Menlo, Consolas, monospace; font-size: 11px;'
    )
    layout.addWidget(self.log_view)

  def log(self, message: str):
    from datetime import datetime
    ts = datetime.now().strftime('%H:%M:%S')
    self.log_view.append(f'[{ts}] {message}')


def apply_light_theme(app: QApplication):
  """ダークモードのMacでもライト固定で表示."""
  app.setStyle('Fusion')
  palette = QPalette()
  palette.setColor(QPalette.ColorRole.Window, QColor('#f5f5f5'))
  palette.setColor(QPalette.ColorRole.WindowText, QColor('#222'))
  palette.setColor(QPalette.ColorRole.Base, QColor('#ffffff'))
  palette.setColor(QPalette.ColorRole.AlternateBase, QColor('#f0f0f0'))
  palette.setColor(QPalette.ColorRole.ToolTipBase, QColor('#ffffe1'))
  palette.setColor(QPalette.ColorRole.ToolTipText, QColor('#222'))
  palette.setColor(QPalette.ColorRole.Text, QColor('#222'))
  palette.setColor(QPalette.ColorRole.Button, QColor('#e8e8e8'))
  palette.setColor(QPalette.ColorRole.ButtonText, QColor('#222'))
  palette.setColor(QPalette.ColorRole.BrightText, QColor('#cc0000'))
  palette.setColor(QPalette.ColorRole.Highlight, QColor('#2E86DE'))
  palette.setColor(QPalette.ColorRole.HighlightedText, QColor('#ffffff'))
  palette.setColor(QPalette.ColorRole.PlaceholderText, QColor('#888'))
  app.setPalette(palette)
  app.setStyleSheet(APP_STYLESHEET)


def main():
  app = QApplication(sys.argv)
  apply_light_theme(app)
  window = MainWindow()
  window.show()
  sys.exit(app.exec())


if __name__ == '__main__':
  main()
