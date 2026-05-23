"""Yomitoku OCR（日本語特化、無料・ローカル、Windows用代替）.

pip install yomitoku が必要。500MB+ のモデルファイルを初回DLする。
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional


def is_available() -> bool:
  try:
    import yomitoku  # noqa: F401
    return True
  except ImportError:
    return False


def ocr_image_with_yomitoku(image_path: Path, languages: list[str] = None) -> list[tuple[str, tuple]]:
  """Yomitoku で OCR し、(テキスト, 正規化座標) のリストを返す."""
  try:
    from yomitoku import OCR
    from yomitoku.data.functions import load_image
  except ImportError:
    raise RuntimeError(
      'Yomitoku がインストールされていません。\n'
      'ターミナルで:  pip install yomitoku\n'
      '（初回起動時にモデルファイルが自動DLされます。500MB前後）'
    )

  ocr = OCR(visualize=False)
  img = load_image(str(image_path))
  results, _ = ocr(img)

  # 画像サイズ
  import fitz
  pix = fitz.Pixmap(str(image_path))
  img_w, img_h = pix.width, pix.height

  output: list[tuple[str, tuple]] = []
  # results.words は単語リスト、各要素に bbox(x1,y1,x2,y2) と content がある
  for word in (results.words or []):
    bbox = getattr(word, 'box', None) or getattr(word, 'bbox', None)
    text = getattr(word, 'content', '') or getattr(word, 'text', '')
    if not bbox or not text:
      continue
    if len(bbox) >= 4:
      x1, y1, x2, y2 = bbox[:4]
      nx = x1 / max(img_w, 1)
      nw = (x2 - x1) / max(img_w, 1)
      nh = (y2 - y1) / max(img_h, 1)
      ny = 1.0 - (y2 / max(img_h, 1))
      output.append((str(text), (nx, ny, nw, nh)))

  return output


def build_searchable_pdf_from_images(
  images: list[Path],
  output_pdf: Path,
  languages: list[str] = None,
  progress: Optional[Callable[[int, int, str], None]] = None,
) -> Path:
  """Yomitoku で OCR して検索可能 PDF を生成."""
  import fitz

  if not is_available():
    raise RuntimeError(
      'Yomitoku が未インストールです。\n'
      'pip install yomitoku を実行してください（500MB+のモデルが初回DLされます）。'
    )

  output_pdf = Path(output_pdf)
  output_pdf.parent.mkdir(parents=True, exist_ok=True)

  total = len(images)
  if total == 0:
    raise ValueError('画像が0枚です')

  doc = fitz.open()
  for i, img_path in enumerate(images):
    if progress:
      progress(i, total, f'Yomitoku OCR: {i + 1}/{total} ページ')

    img_path = Path(img_path)
    pix = fitz.Pixmap(str(img_path))
    page_w, page_h = pix.width, pix.height
    page = doc.new_page(width=page_w, height=page_h)
    page.insert_image(page.rect, filename=str(img_path))

    try:
      ocr_results = ocr_image_with_yomitoku(img_path, languages)
    except Exception as e:
      print(f'Yomitoku failed on page {i+1}: {e}')
      ocr_results = []

    for text, (x, y, w, h) in ocr_results:
      pdf_x = x * page_w
      pdf_y = (1.0 - y - h) * page_h
      pdf_w = w * page_w
      pdf_h = h * page_h
      rect = fitz.Rect(pdf_x, pdf_y, pdf_x + pdf_w, pdf_y + pdf_h)
      fs = max(pdf_h * 0.85, 4)
      for font in ['japan-s', 'japan', 'china-ss']:
        try:
          rc = page.insert_textbox(rect, text, fontsize=fs, fontname=font, render_mode=3, overlay=True)
          if rc > 0:
            break
        except Exception:
          continue

  if progress:
    progress(total, total, '保存中…')
  doc.save(str(output_pdf), garbage=4, deflate=True)
  doc.close()
  return output_pdf
