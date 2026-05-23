"""Kindleアプリの自動スクリーンショット.

Mac/Windows両対応。pyautogui + mss を使用。
- スクショ撮影 → 右キー送信 → 待機 のループ
- 直前画像とハッシュ比較し、同一なら最終ページ判定で停止
- ESCキーで中断可能（pyautogui FailSafe: 画面左上端にマウス移動）
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import mss
import mss.tools
import pyautogui

from src.window_activator import activate_kindle, is_kindle_running, is_mac, send_key_mac


@dataclass
class CaptureConfig:
  total_pages: int = 300
  delay_sec: float = 1.0
  countdown_sec: int = 3
  region: Optional[tuple[int, int, int, int]] = None
  page_key: str = 'right'
  auto_activate_kindle: bool = True
  reactivate_every_n: int = 10  # N枚ごとにKindleを再アクティベート（フォーカス奪取対策）

  def region_dict(self) -> Optional[dict]:
    if self.region is None:
      return None
    x, y, w, h = self.region
    return {'left': x, 'top': y, 'width': w, 'height': h}


class CaptureStopped(Exception):
  """ユーザー中断."""


def capture_kindle(
  output_dir: Path,
  config: CaptureConfig,
  progress: Optional[Callable[[int, int, str], None]] = None,
  should_stop: Optional[Callable[[], bool]] = None,
) -> list[Path]:
  """Kindleページを連続スクショ.

  Args:
    output_dir: PNG保存先
    config: キャプチャ設定
    progress: (current, total, message) を受け取るコールバック
    should_stop: True を返すとループ離脱（GUI停止ボタン用）

  Returns:
    生成されたPNGファイルパス（順序保証）
  """
  output_dir = Path(output_dir)
  output_dir.mkdir(parents=True, exist_ok=True)

  pyautogui.FAILSAFE = True

  # 事前チェック: Kindleが起動しているか
  if config.auto_activate_kindle:
    if not is_kindle_running():
      raise RuntimeError(
        'Kindleアプリが起動していません。\n'
        'Kindleを起動して読みたい本の1ページ目を開いてから、再度実行してください。'
      )

  if config.countdown_sec > 0:
    for i in range(config.countdown_sec, 0, -1):
      if progress:
        progress(0, config.total_pages, f'{i}秒後に開始…')
      time.sleep(1.0)

  # Kindleを最前面にアクティベート（これが超重要）
  if config.auto_activate_kindle:
    ok, msg = activate_kindle()
    if progress:
      progress(0, config.total_pages, msg)
    if not ok:
      raise RuntimeError(msg)
    time.sleep(0.5)  # ウィンドウ切り替え完了待ち

  saved: list[Path] = []
  prev_hash: Optional[str] = None
  duplicate_count = 0

  with mss.mss() as sct:
    region = config.region_dict() or sct.monitors[1]

    for i in range(config.total_pages):
      if should_stop and should_stop():
        if progress:
          progress(i, config.total_pages, '中断されました')
        break

      # 定期的にKindleを再アクティベート（他アプリに奪われた場合の保険）
      if config.auto_activate_kindle and i > 0 and i % config.reactivate_every_n == 0:
        activate_kindle()
        time.sleep(0.2)

      img = sct.grab(region)
      # 重複検出用ハッシュ: 中央付近のみ（時計・マウス・カーソルを避ける）
      # 画像全体ハッシュだと時計が変わるだけで「違うページ」と誤判定する
      img_w, img_h = img.size.width, img.size.height
      cx = img_w // 4
      cy = img_h // 4
      cw = img_w // 2
      ch = img_h // 2
      # rgb は 1次元バイト列なので、中央領域を矩形抽出
      try:
        center_bytes = bytes(img.rgb)
        # 簡易抽出（バイト列スライス：各行のRGB×幅）
        bpp = 3
        stride = img_w * bpp
        center = bytearray()
        for row in range(cy, cy + ch):
          start = row * stride + cx * bpp
          center.extend(center_bytes[start:start + cw * bpp])
        digest = hashlib.md5(bytes(center)).hexdigest()
      except Exception:
        digest = hashlib.md5(bytes(img.rgb)).hexdigest()

      if digest == prev_hash:
        duplicate_count += 1
        if duplicate_count >= 2:
          # 2回連続で同じ画面 = ページが進んでいない
          if i < 3:
            raise RuntimeError(
              f'{i}ページでページめくりが効いていない可能性があります。\n'
              '考えられる原因:\n'
              '1. アクセシビリティ権限が未許可\n'
              '   → システム設定 → プライバシーとセキュリティ → アクセシビリティ\n'
              '   　 で「ターミナル」または「Python」を許可\n'
              '2. Kindleアプリが最前面でない\n'
              '3. ページ送りキーが違う（→キー以外を試す）'
            )
          if progress:
            progress(i, config.total_pages, f'最終ページ検出（{i}枚で停止）')
          break
      else:
        duplicate_count = 0

      path = output_dir / f'{i:04d}.png'
      mss.tools.to_png(img.rgb, img.size, output=str(path))
      saved.append(path)
      prev_hash = digest

      if progress:
        progress(i + 1, config.total_pages, f'{i + 1}/{config.total_pages} 枚キャプチャ')

      # pyautogui を使う（Mac/Win共通）
      # Mac では Python が直接 CGEventPost を呼ぶ。
      # 責任プロセスは Kindle OCR.app になるので、osascript 経由より TCC 通過率が高い。
      pyautogui.press(config.page_key)
      time.sleep(config.delay_sec)

  return saved
