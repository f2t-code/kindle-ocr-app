#!/usr/bin/env python3
"""Kindle OCR App アイコン生成スクリプト.

Pillow で macOS 標準サイズ群の PNG を生成し、iconutil で .icns 化する。
デザイン: 紫→青グラデの角丸スクエア背景に、白いブック + 虫眼鏡。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

# macOS .icns に必要なサイズ
ICON_SIZES = [16, 32, 64, 128, 256, 512, 1024]


def lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
  return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(4))


def draw_gradient_squircle(
  size: int,
  color_top: tuple = (74, 144, 226, 255),  # #4A90E2
  color_bottom: tuple = (108, 92, 231, 255),  # #6C5CE7
  corner_radius_ratio: float = 0.225,
) -> Image.Image:
  """グラデーション付き角丸スクエア（macOS app icon標準形状）."""
  img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
  px = img.load()
  # 縦方向グラデーション
  for y in range(size):
    t = y / max(size - 1, 1)
    color = lerp_color(color_top, color_bottom, t)
    for x in range(size):
      px[x, y] = color

  # 角丸マスク
  mask = Image.new('L', (size, size), 0)
  mask_draw = ImageDraw.Draw(mask)
  radius = int(size * corner_radius_ratio)
  mask_draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)

  result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
  result.paste(img, (0, 0), mask)
  return result


def draw_book(canvas: Image.Image, size: int):
  """本のシルエット（白）にテキスト行を表す."""
  draw = ImageDraw.Draw(canvas)

  # 本のサイズ・位置（中央やや左寄せ）
  book_w = int(size * 0.55)
  book_h = int(size * 0.65)
  book_x = int(size * 0.18)
  book_y = int(size * 0.20)

  # 影
  shadow = Image.new('RGBA', (size, size), (0, 0, 0, 0))
  sdraw = ImageDraw.Draw(shadow)
  sdraw.rounded_rectangle(
    (book_x + int(size * 0.015), book_y + int(size * 0.015),
     book_x + book_w + int(size * 0.015), book_y + book_h + int(size * 0.015)),
    radius=int(size * 0.04),
    fill=(0, 0, 0, 70),
  )
  shadow = shadow.filter(ImageFilter.GaussianBlur(radius=size * 0.012))
  canvas.alpha_composite(shadow)

  # 本体（白）
  draw.rounded_rectangle(
    (book_x, book_y, book_x + book_w, book_y + book_h),
    radius=int(size * 0.04),
    fill=(255, 255, 255, 255),
  )

  # 背表紙ライン（左端、紫）
  spine_w = int(size * 0.04)
  draw.rectangle(
    (book_x, book_y, book_x + spine_w, book_y + book_h),
    fill=(108, 92, 231, 255),
  )

  # テキスト行（オレンジっぽい線でOCRされた文字を表現）
  text_color = (255, 153, 51, 255)  # #FF9933
  text_left = book_x + int(size * 0.10)
  text_right = book_x + book_w - int(size * 0.05)
  line_h = int(size * 0.018)
  gap = int(size * 0.05)
  start_y = book_y + int(size * 0.13)

  for i in range(7):
    y = start_y + i * gap
    if y + line_h > book_y + book_h - int(size * 0.05):
      break
    # 行末をランダムっぽく短くしてリアリティを出す
    end = text_right - (int(size * 0.10) if i % 3 == 2 else 0)
    draw.rounded_rectangle(
      (text_left, y, end, y + line_h),
      radius=line_h // 2,
      fill=text_color,
    )


def draw_magnifier(canvas: Image.Image, size: int):
  """虫眼鏡を右下に重ねる（OCR=検索を象徴）."""
  draw = ImageDraw.Draw(canvas, 'RGBA')

  # 虫眼鏡の中心位置（右下寄り）
  cx = int(size * 0.70)
  cy = int(size * 0.70)
  radius = int(size * 0.18)
  border_w = max(int(size * 0.035), 3)

  # ハイライト用シャドウ
  shadow = Image.new('RGBA', (size, size), (0, 0, 0, 0))
  sdraw = ImageDraw.Draw(shadow)
  sdraw.ellipse(
    (cx - radius + int(size * 0.01), cy - radius + int(size * 0.01),
     cx + radius + int(size * 0.01), cy + radius + int(size * 0.01)),
    outline=(0, 0, 0, 90), width=border_w + 2,
  )
  shadow = shadow.filter(ImageFilter.GaussianBlur(radius=size * 0.012))
  canvas.alpha_composite(shadow)

  # レンズ円（半透明白で本の上にも被さる感じ）
  draw.ellipse(
    (cx - radius, cy - radius, cx + radius, cy + radius),
    fill=(255, 255, 255, 200),
    outline=(255, 255, 255, 255),
    width=border_w,
  )

  # 取っ手（右下に向かう）
  handle_start_x = cx + int(radius * 0.7071)
  handle_start_y = cy + int(radius * 0.7071)
  handle_end_x = handle_start_x + int(size * 0.10)
  handle_end_y = handle_start_y + int(size * 0.10)
  handle_w = max(int(size * 0.05), 4)
  draw.line(
    (handle_start_x, handle_start_y, handle_end_x, handle_end_y),
    fill=(255, 255, 255, 255),
    width=handle_w,
  )
  # 取っ手の先端の丸み
  draw.ellipse(
    (handle_end_x - handle_w // 2, handle_end_y - handle_w // 2,
     handle_end_x + handle_w // 2, handle_end_y + handle_w // 2),
    fill=(255, 255, 255, 255),
  )

  # レンズ内のハイライト（上左に薄く）
  hl_radius = int(radius * 0.5)
  hl_x = cx - int(radius * 0.35)
  hl_y = cy - int(radius * 0.35)
  draw.ellipse(
    (hl_x - hl_radius // 2, hl_y - hl_radius // 2,
     hl_x + hl_radius // 2, hl_y + hl_radius // 2),
    fill=(255, 255, 255, 80),
  )


def render_icon(size: int) -> Image.Image:
  canvas = draw_gradient_squircle(size)
  draw_book(canvas, size)
  draw_magnifier(canvas, size)
  return canvas


def main():
  out_dir = Path(__file__).parent.parent / 'icon_build'
  iconset_dir = out_dir / 'AppIcon.iconset'
  iconset_dir.mkdir(parents=True, exist_ok=True)

  # macOS iconutil が期待するファイル名規則
  iconset_specs = [
    (16, 'icon_16x16.png'),
    (32, 'icon_16x16@2x.png'),
    (32, 'icon_32x32.png'),
    (64, 'icon_32x32@2x.png'),
    (128, 'icon_128x128.png'),
    (256, 'icon_128x128@2x.png'),
    (256, 'icon_256x256.png'),
    (512, 'icon_256x256@2x.png'),
    (512, 'icon_512x512.png'),
    (1024, 'icon_512x512@2x.png'),
  ]

  # 1024 を生成してから各サイズへリサイズ（綺麗）
  master = render_icon(1024)
  master.save(out_dir / 'icon_master_1024.png')
  print(f'マスター画像保存: {out_dir / "icon_master_1024.png"}')

  for size, fname in iconset_specs:
    img = master.resize((size, size), Image.LANCZOS) if size != 1024 else master
    img.save(iconset_dir / fname)
    print(f'  {fname} ({size}x{size})')

  print(f'\nicon_build/{iconset_dir.name} を出力しました')
  print('次にこのコマンドで .icns に変換:')
  print(f'  iconutil -c icns "{iconset_dir}" -o "{out_dir / "AppIcon.icns"}"')


if __name__ == '__main__':
  main()
