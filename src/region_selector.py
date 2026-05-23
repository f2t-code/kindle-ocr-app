"""キャプチャ範囲のドラッグ選択ウィンドウ.

フルスクリーンで半透明オーバーレイを出し、マウスドラッグで領域選択させる。
ESCで取消、Enter/離した時に確定。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
  QColor,
  QFont,
  QGuiApplication,
  QKeyEvent,
  QMouseEvent,
  QPainter,
  QPen,
  QPixmap,
)
from PySide6.QtWidgets import QWidget


class RegionSelector(QWidget):
  """マウスドラッグでキャプチャ範囲を選ばせるオーバーレイ."""

  selected = Signal(tuple)  # (x, y, w, h) を発火
  cancelled = Signal()

  def __init__(self):
    super().__init__()
    self.setWindowFlags(
      Qt.WindowType.FramelessWindowHint
      | Qt.WindowType.WindowStaysOnTopHint
      | Qt.WindowType.Tool
    )
    self.setCursor(Qt.CursorShape.CrossCursor)
    self._start: Optional[QPoint] = None
    self._end: Optional[QPoint] = None
    self._dragging = False
    self._bg_pixmap: Optional[QPixmap] = None
    self._screen_geo = None  # 物理スクリーン座標を保持

  def show_fullscreen(self):
    """全画面オーバーレイで表示（事前にスクショ取得して背景に）."""
    screen = QGuiApplication.primaryScreen()
    if not screen:
      return
    geo = screen.geometry()
    self._screen_geo = geo
    # 画面全体のスクショを取得（Kindleが見える状態で）
    # WId=0 で画面全体（macOS は WId=0 でフルスクリーン）
    self._bg_pixmap = screen.grabWindow(0)
    self.setGeometry(geo)
    self.showFullScreen()
    self.raise_()
    self.activateWindow()

  def paintEvent(self, _event):
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 1. 背景: 取得したスクショ画像（Kindleが映ってる状態）
    if self._bg_pixmap:
      painter.drawPixmap(self.rect(), self._bg_pixmap)

    # 2. 暗いオーバーレイ（選択しやすくするため）
    painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

    # 3. 選択中の矩形は明るく
    if self._start and self._end:
      rect = QRect(self._start, self._end).normalized()
      # 選択範囲は元のスクショを明るく見せる
      if self._bg_pixmap:
        # 該当部分のスクショを上書き描画（暗いオーバーレイより上）
        sx = rect.x() * self._bg_pixmap.width() // max(self.width(), 1)
        sy = rect.y() * self._bg_pixmap.height() // max(self.height(), 1)
        sw = rect.width() * self._bg_pixmap.width() // max(self.width(), 1)
        sh = rect.height() * self._bg_pixmap.height() // max(self.height(), 1)
        src = QRect(sx, sy, sw, sh)
        painter.drawPixmap(rect, self._bg_pixmap, src)

      # 緑色の枠線
      pen = QPen(QColor('#2ECC71'))
      pen.setWidth(3)
      painter.setPen(pen)
      painter.drawRect(rect)

      # 寸法表示
      painter.setPen(QColor('#fff'))
      font = QFont()
      font.setPointSize(14)
      font.setBold(True)
      painter.setFont(font)
      info = f'{rect.width()} × {rect.height()} px'
      info_pos = rect.bottomRight() + QPoint(8, 20)
      painter.fillRect(info_pos.x() - 4, info_pos.y() - 20, len(info) * 12, 28, QColor(0, 0, 0, 180))
      painter.drawText(info_pos, info)

    # 操作ヒント（画面上部）
    painter.setPen(QColor('#fff'))
    font = QFont()
    font.setPointSize(18)
    font.setBold(True)
    painter.setFont(font)
    hint = 'マウスドラッグで本文エリアを選択　│　ESCで取消'
    rect = self.rect()
    painter.fillRect(rect.x() + (rect.width() - 700) // 2, 40, 700, 50, QColor(0, 0, 0, 200))
    painter.drawText(
      rect.x() + (rect.width() - 700) // 2, 40, 700, 50,
      Qt.AlignmentFlag.AlignCenter, hint,
    )

  def mousePressEvent(self, event: QMouseEvent):
    if event.button() == Qt.MouseButton.LeftButton:
      self._start = event.position().toPoint()
      self._end = event.position().toPoint()
      self._dragging = True
      self.update()

  def mouseMoveEvent(self, event: QMouseEvent):
    if self._dragging:
      self._end = event.position().toPoint()
      self.update()

  def mouseReleaseEvent(self, event: QMouseEvent):
    if event.button() == Qt.MouseButton.LeftButton and self._dragging:
      self._end = event.position().toPoint()
      self._dragging = False
      if self._start and self._end:
        rect = QRect(self._start, self._end).normalized()
        if rect.width() > 20 and rect.height() > 20:
          # Global座標に変換（Multi-display対応）
          screen_pos = self.mapToGlobal(rect.topLeft())
          self.selected.emit((screen_pos.x(), screen_pos.y(), rect.width(), rect.height()))
          self.close()
        else:
          # 選択が小さすぎる → リセット
          self._start = None
          self._end = None
          self.update()

  def keyPressEvent(self, event: QKeyEvent):
    if event.key() == Qt.Key.Key_Escape:
      self.cancelled.emit()
      self.close()
