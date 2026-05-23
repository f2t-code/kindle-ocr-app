"""カウントダウン中、画面中央に大きく表示するフローティングウィンドウ.

常に最前面表示で、Kindleアプリに切り替えても見える。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class CountdownOverlay(QWidget):
  finished = Signal()

  def __init__(self, seconds: int = 5, message: str = '今すぐKindleアプリを最前面にクリック！'):
    super().__init__()
    self.seconds_left = seconds
    self.message = message

    self.setWindowFlags(
      Qt.WindowType.FramelessWindowHint
      | Qt.WindowType.WindowStaysOnTopHint
      | Qt.WindowType.Tool
    )
    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    palette = self.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 220))
    self.setPalette(palette)
    self.setAutoFillBackground(True)
    self.setStyleSheet('''
      QWidget {
        background-color: rgba(0, 0, 0, 220);
        border-radius: 20px;
      }
      QLabel {
        color: #fff;
        background: transparent;
      }
    ''')

    layout = QVBoxLayout(self)
    layout.setContentsMargins(40, 30, 40, 30)

    self.msg_label = QLabel(message)
    msg_font = QFont()
    msg_font.setPointSize(20)
    msg_font.setBold(True)
    self.msg_label.setFont(msg_font)
    self.msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.msg_label.setStyleSheet('color: #FFE066;')
    layout.addWidget(self.msg_label)

    self.count_label = QLabel(str(seconds))
    count_font = QFont()
    count_font.setPointSize(120)
    count_font.setBold(True)
    self.count_label.setFont(count_font)
    self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(self.count_label)

    self.hint_label = QLabel('停止: マウスを画面左上端へ')
    hint_font = QFont()
    hint_font.setPointSize(12)
    self.hint_label.setFont(hint_font)
    self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.hint_label.setStyleSheet('color: #aaa;')
    layout.addWidget(self.hint_label)

    self.resize(600, 360)

    self._timer = QTimer(self)
    self._timer.timeout.connect(self._tick)

  def start(self):
    self._center_on_screen()
    self.show()
    self.raise_()
    self._timer.start(1000)

  def _center_on_screen(self):
    screen = self.screen()
    if screen:
      geo = screen.geometry()
      self.move(
        geo.x() + (geo.width() - self.width()) // 2,
        geo.y() + (geo.height() - self.height()) // 2,
      )

  def _tick(self):
    self.seconds_left -= 1
    if self.seconds_left <= 0:
      self._timer.stop()
      self.count_label.setText('開始！')
      QTimer.singleShot(500, self._finish)
    else:
      self.count_label.setText(str(self.seconds_left))

  def _finish(self):
    self.close()
    self.finished.emit()
