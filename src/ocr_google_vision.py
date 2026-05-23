"""Google Cloud Vision API による OCR（REST API直叩き、軽量）.

google-cloud-vision SDK は重いので、urllib で直接呼ぶ。
APIキー方式（OAuth不要、シンプル）を使用。
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional


VISION_ENDPOINT = 'https://vision.googleapis.com/v1/images:annotate'


def is_available(api_key: str = '') -> bool:
  return bool(api_key)


def ocr_image(image_path: Path, api_key: str, languages: list[str] = None) -> list[tuple[str, tuple]]:
  """1枚の画像を OCR し、(テキスト, 正規化座標) のリストを返す.

  返却形式は ocr_apple_vision.ocr_image と同じ:
    (テキスト, (x, y, w, h)) — x,y,w,h は左下原点 0-1 正規化
  """
  if languages is None:
    languages = ['ja', 'en']

  image_path = Path(image_path)
  data = image_path.read_bytes()
  b64 = base64.b64encode(data).decode('ascii')

  request_body = {
    'requests': [{
      'image': {'content': b64},
      'features': [{'type': 'DOCUMENT_TEXT_DETECTION'}],
      'imageContext': {
        'languageHints': languages,
      },
    }],
  }

  url = f'{VISION_ENDPOINT}?key={api_key}'
  req = urllib.request.Request(
    url,
    data=json.dumps(request_body).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST',
  )

  try:
    with urllib.request.urlopen(req, timeout=60) as resp:
      result = json.loads(resp.read())
  except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8', errors='ignore')
    raise RuntimeError(f'Google Vision API エラー HTTP {e.code}: {body[:300]}')
  except Exception as e:
    raise RuntimeError(f'Google Vision API 接続失敗: {e}')

  responses = result.get('responses', [])
  if not responses:
    return []

  resp0 = responses[0]
  if 'error' in resp0:
    msg = resp0['error'].get('message', '不明')
    raise RuntimeError(f'Google Vision API: {msg}')

  full_annotation = resp0.get('fullTextAnnotation', {})
  if not full_annotation:
    return []

  # 画像サイズ取得
  try:
    import fitz
    pix = fitz.Pixmap(str(image_path))
    img_w, img_h = pix.width, pix.height
  except Exception:
    from PIL import Image
    with Image.open(image_path) as im:
      img_w, img_h = im.size

  results: list[tuple[str, tuple]] = []
  # block/paragraph/word/symbol の構造を上から下に走査して text を組み立てる
  for page in full_annotation.get('pages', []):
    for block in page.get('blocks', []):
      for para in block.get('paragraphs', []):
        text_pieces = []
        for word in para.get('words', []):
          word_str = ''.join(s.get('text', '') for s in word.get('symbols', []))
          text_pieces.append(word_str)
        para_text = ''.join(text_pieces)
        if not para_text.strip():
          continue
        # 段落のbboxを取得
        verts = para.get('boundingBox', {}).get('vertices', [])
        if len(verts) >= 4:
          xs = [v.get('x', 0) for v in verts]
          ys = [v.get('y', 0) for v in verts]
          x_min, x_max = min(xs), max(xs)
          y_min, y_max = min(ys), max(ys)
          # Vision REST は左上原点 → 左下原点 0-1 に変換
          nx = x_min / max(img_w, 1)
          nw = (x_max - x_min) / max(img_w, 1)
          nh = (y_max - y_min) / max(img_h, 1)
          ny = 1.0 - (y_max / max(img_h, 1))  # bottom-left origin
          results.append((para_text, (nx, ny, nw, nh)))

  return results


def build_searchable_pdf_from_images(
  images: list[Path],
  output_pdf: Path,
  api_key: str,
  languages: list[str] = None,
  progress: Optional[Callable[[int, int, str], None]] = None,
) -> Path:
  """Google Vision で OCR して検索可能 PDF を生成."""
  import fitz

  if not api_key:
    raise ValueError('Google Vision API キーが未設定です。設定画面で入力してください。')

  output_pdf = Path(output_pdf)
  output_pdf.parent.mkdir(parents=True, exist_ok=True)

  total = len(images)
  if total == 0:
    raise ValueError('画像が0枚です')

  doc = fitz.open()
  for i, img_path in enumerate(images):
    if progress:
      progress(i, total, f'Google Vision OCR: {i + 1}/{total} ページ')

    img_path = Path(img_path)
    pix = fitz.Pixmap(str(img_path))
    page_w, page_h = pix.width, pix.height
    page = doc.new_page(width=page_w, height=page_h)
    page.insert_image(page.rect, filename=str(img_path))

    try:
      ocr_results = ocr_image(img_path, api_key, languages)
    except Exception as e:
      print(f'Google Vision failed on page {i+1}: {e}')
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
