"""Apple Vision Framework を使った OCR (Mac専用、無料、高精度).

PyObjC で macOS 標準の Vision API を呼び出して日本語+英語を認識。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional


def is_available() -> bool:
  """Apple Vision が使える環境か（Mac かつ PyObjC Vision がインポート可能）."""
  import platform
  if platform.system() != 'Darwin':
    return False
  try:
    import Vision  # noqa: F401
    return True
  except ImportError:
    return False


def ocr_image(image_path: Path, languages: list[str] = None) -> list[tuple[str, tuple]]:
  """1枚の画像を OCR し、(テキスト, 正規化座標) のリストを返す.

  正規化座標は (x, y, width, height) で 0.0-1.0 の範囲（画像左下原点）。
  """
  import Vision
  from Quartz import CIImage
  from Foundation import NSURL

  if languages is None:
    languages = ['ja-JP', 'en-US']

  image_path = Path(image_path)
  url = NSURL.fileURLWithPath_(str(image_path))
  ci_image = CIImage.imageWithContentsOfURL_(url)
  if ci_image is None:
    return []

  results: list[tuple[str, tuple]] = []
  request = Vision.VNRecognizeTextRequest.alloc().init()
  request.setRecognitionLanguages_(languages)
  request.setRecognitionLevel_(0)  # 0 = accurate (1 = fast)
  request.setUsesLanguageCorrection_(True)

  handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(ci_image, None)
  success, error = handler.performRequests_error_([request], None)
  if not success:
    return []

  observations = request.results() or []
  for obs in observations:
    candidates = obs.topCandidates_(1)
    if not candidates:
      continue
    text = str(candidates[0].string())
    bbox = obs.boundingBox()
    x = bbox.origin.x
    y = bbox.origin.y
    w = bbox.size.width
    h = bbox.size.height
    results.append((text, (x, y, w, h)))

  return results


def build_searchable_pdf_from_images(
  images: list[Path],
  output_pdf: Path,
  languages: list[str] = None,
  progress: Optional[Callable[[int, int, str], None]] = None,
) -> Path:
  """画像群を Apple Vision で OCR し、検索可能 PDF を生成.

  Args:
    images: PNG/JPG パスのリスト（順序通り）
    output_pdf: 出力 PDF パス
    languages: 認識言語コード（デフォルト: 日本語+英語）
    progress: (current, total, message) コールバック

  Returns:
    生成された PDF パス
  """
  import fitz  # PyMuPDF

  output_pdf = Path(output_pdf)
  output_pdf.parent.mkdir(parents=True, exist_ok=True)

  if languages is None:
    languages = ['ja-JP', 'en-US']

  total = len(images)
  if total == 0:
    raise ValueError('画像が0枚です')

  doc = fitz.open()

  for i, img_path in enumerate(images):
    if progress:
      progress(i, total, f'Apple Vision OCR: {i + 1}/{total} ページ')

    img_path = Path(img_path)
    # 画像サイズを取得
    pix = fitz.Pixmap(str(img_path))
    page_w = pix.width
    page_h = pix.height

    # PDF ページ作成（画像と同じサイズ）
    page = doc.new_page(width=page_w, height=page_h)
    page.insert_image(page.rect, filename=str(img_path))

    # Apple Vision で OCR
    try:
      ocr_results = ocr_image(img_path, languages)
    except Exception as e:
      print(f'Vision OCR failed on page {i + 1}: {e}')
      ocr_results = []

    # 各テキストブロックに invisible text を挿入（検索可能にする）
    # PyMuPDFの組み込み日本語フォント 'japan-s' (Gothic) を使用
    for text, (x, y, w, h) in ocr_results:
      # Vision の座標は左下原点 0-1 正規化、PyMuPDF は左上原点なので変換
      pdf_x = x * page_w
      pdf_y = (1.0 - y - h) * page_h
      pdf_w = w * page_w
      pdf_h = h * page_h

      rect = fitz.Rect(pdf_x, pdf_y, pdf_x + pdf_w, pdf_y + pdf_h)
      fs = max(pdf_h * 0.85, 4)

      # 不可視テキスト埋め込み
      # PyMuPDFのCJK組み込みフォント: 'japan-s' (Gothic), 'japan' (Mincho)
      inserted = False
      for font in ['japan-s', 'japan', 'china-ss']:
        try:
          rc = page.insert_textbox(
            rect,
            text,
            fontsize=fs,
            fontname=font,
            render_mode=3,  # 不可視
            overlay=True,
          )
          # rc <= 0 は失敗（テキストが入らない）
          if rc > 0:
            inserted = True
            break
        except Exception:
          continue

      if not inserted:
        # フォールバック: ベースラインに insert_text で1行ずつ
        try:
          page.insert_text(
            fitz.Point(pdf_x, pdf_y + fs),
            text,
            fontsize=fs,
            fontname='japan-s',
            render_mode=3,
          )
        except Exception:
          pass

  if progress:
    progress(total, total, '保存中…')

  doc.save(str(output_pdf), garbage=4, deflate=True)
  doc.close()
  return output_pdf
