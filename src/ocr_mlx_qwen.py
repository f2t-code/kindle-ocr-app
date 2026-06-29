"""mlx-vlm + Qwen2.5-VL によるローカルOCR（Mac/Apple Silicon専用）.

pip install mlx-vlm が必要。初回実行時に Qwen2.5-VL モデル（数GB）を
Hugging Face から自動DLする。

設計上の制約（重要）:
  Qwen-VL は画像を読んで「ページ全文のプレーンテキスト」を返すだけで、
  単語ごとの座標（bbox）は返さない。Apple Vision / Yomitoku のように
  各語の真下に透明テキストを敷く正確な検索レイヤーは作れないため、
  本バックエンドは「ページ全文を1ブロックでページ全体に透明配置」する。
  → Ctrl+F 検索・全文コピーは効くが、ハイライト位置は画像と一致しない。
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Callable, Optional

# デフォルトモデル（環境変数 KINDLE_OCR_MLX_MODEL で上書き可）。
# 3B-4bit は ~2GB・1ページ約35秒で、印刷書籍ページなら高精度（実機検証済み）。
# より高精度が要る場合（手書き・劣化スキャン等）は環境変数で 7B に切替:
#   KINDLE_OCR_MLX_MODEL=mlx-community/Qwen2.5-VL-7B-Instruct-4bit
DEFAULT_MODEL = 'mlx-community/Qwen2.5-VL-3B-Instruct-4bit'

# 1ページあたりの最大生成トークン数（長文ページでも全文を取り切る余裕を持たせる）
DEFAULT_MAX_TOKENS = 4096

# VLM へ渡す画像の長辺上限（px）。
# Qwen-VL は入力画素数に上限があり、巨大画像はリサイズで文字が潰れて
# 出力が破綻する（"!!!" 暴走）。長辺をこのサイズに収めてから渡す。
# 大きすぎると破綻、小さすぎると小さな文字を読めないので 2000 前後が無難。
MAX_IMAGE_EDGE = int(os.environ.get('KINDLE_OCR_MLX_MAX_EDGE', '2000') or '2000')

# OCR用プロンプト（転記に専念させ、余計な説明を出させない）
_OCR_PROMPT = (
  'この画像に書かれている文字をすべて、書かれている順序のまま正確に書き起こしてください。'
  '縦書きの場合は読む順序（右の列から左へ）に従ってください。'
  '見出し・本文・ルビ・注釈もすべて含めてください。'
  '書き起こしたテキストだけを出力し、説明や前置きは一切付けないでください。'
)

# モデルは重いので一度ロードしたらプロセス内でキャッシュする
_MODEL_CACHE: dict = {}


def get_model_id() -> str:
  """使用するモデルIDを返す（環境変数優先）."""
  return os.environ.get('KINDLE_OCR_MLX_MODEL', DEFAULT_MODEL).strip() or DEFAULT_MODEL


def is_available() -> bool:
  """mlx-vlm が使える環境か（Apple Silicon Mac かつ mlx_vlm が import 可能）."""
  if platform.system() != 'Darwin':
    return False
  # mlx は Apple Silicon 専用。Intel Mac では動かない
  if platform.machine() not in ('arm64', 'aarch64'):
    return False
  try:
    import mlx_vlm  # noqa: F401
    return True
  except ImportError:
    return False


def _load_model(model_id: str):
  """モデルとプロセッサをロード（キャッシュ利用）."""
  if model_id in _MODEL_CACHE:
    return _MODEL_CACHE[model_id]

  from mlx_vlm import load
  from mlx_vlm.utils import load_config

  model, processor = load(model_id)
  config = load_config(model_id)
  _MODEL_CACHE[model_id] = (model, processor, config)
  return _MODEL_CACHE[model_id]


def _prepare_image(image_path: Path) -> tuple[str, Optional[str]]:
  """VLM へ渡す画像を準備（長辺が上限超なら縮小して一時ファイルに保存）.

  Returns:
    (渡すべき画像パス, 後始末すべき一時ファイルパス or None)
  """
  from PIL import Image

  with Image.open(str(image_path)) as im:
    w, h = im.size
    longest = max(w, h)
    if longest <= MAX_IMAGE_EDGE:
      return str(image_path), None
    scale = MAX_IMAGE_EDGE / float(longest)
    new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
    im = im.convert('RGB')
    im = im.resize(new_size, Image.LANCZOS)
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix='mlx_ocr_', suffix='.png')
    os.close(fd)
    im.save(tmp)
  return tmp, tmp


def ocr_image_text(
  image_path: Path,
  model_id: Optional[str] = None,
  max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
  """1枚の画像を Qwen-VL でOCRし、ページ全文テキストを返す.

  座標は返さない（Qwen-VL の制約）。
  巨大画像は MAX_IMAGE_EDGE まで縮小してから渡す（暴走防止）。
  """
  if not is_available():
    raise RuntimeError(
      'mlx-vlm が未インストール、または非対応環境です。\n'
      'Apple Silicon Mac で  pip install mlx-vlm  を実行してください。'
    )

  from mlx_vlm import generate
  from mlx_vlm.prompt_utils import apply_chat_template

  model_id = model_id or get_model_id()
  model, processor, config = _load_model(model_id)

  formatted_prompt = apply_chat_template(
    processor, config, _OCR_PROMPT, num_images=1
  )
  img_arg, tmp = _prepare_image(Path(image_path))
  try:
    result = generate(
      model,
      processor,
      formatted_prompt,
      image=[img_arg],
      max_tokens=max_tokens,
      # 温度はデフォルト0.0（貪欲法＝OCRに最適）。
      # 反復ループ（同一行の暴走）を抑えるため repetition_penalty を付与。
      repetition_penalty=1.1,
      repetition_context_size=40,
      verbose=False,
    )
  finally:
    if tmp:
      try:
        os.remove(tmp)
      except OSError:
        pass
  # generate は GenerationResult を返す（.text に本文）。
  # 念のため文字列が返る古い実装にもフォールバック。
  text = getattr(result, 'text', None)
  if text is None:
    text = str(result)
  return text.strip()


def _insert_text_layer(page, text: str, page_w: float, page_h: float) -> None:
  """ページ全文を不可視テキストとしてページ全体に敷く（検索・コピー用）.

  Qwen は座標を返さないため、行を上から等間隔に並べて配置する。
  位置は画像と一致しないが、Ctrl+F 検索と全文コピーは機能する。
  """
  if not text:
    return

  lines = [ln for ln in text.splitlines() if ln.strip()]
  if not lines:
    lines = [text]

  # 余白を少し取り、行を縦に等間隔配置
  margin = page_w * 0.04
  usable_h = page_h * 0.92
  top = page_h * 0.04
  row_h = usable_h / max(len(lines), 1)
  fontsize = max(min(row_h * 0.6, 14.0), 4.0)

  for idx, line in enumerate(lines):
    y0 = top + idx * row_h
    rect = page.rect.__class__(margin, y0, page_w - margin, y0 + row_h)
    inserted = False
    for font in ('japan-s', 'japan', 'china-ss'):
      try:
        rc = page.insert_textbox(
          rect, line,
          fontsize=fontsize, fontname=font,
          render_mode=3,  # 不可視
          overlay=True,
        )
        if rc > 0:
          inserted = True
          break
      except Exception:
        continue
    if not inserted:
      # 入り切らない場合はベースラインに1行で（はみ出しは許容、検索目的）
      try:
        page.insert_text(
          page.rect.__class__(margin, y0, page_w - margin, y0 + row_h).tl
          + (0, fontsize),
          line,
          fontsize=fontsize, fontname='japan-s', render_mode=3,
        )
      except Exception:
        pass


def build_searchable_pdf_from_images(
  images: list[Path],
  output_pdf: Path,
  languages: list[str] = None,  # 互換性のため受けるが Qwen では未使用
  progress: Optional[Callable[[int, int, str], None]] = None,
) -> Path:
  """画像群を Qwen-VL でOCRし、検索可能PDFを生成.

  Args:
    images: 入力画像（PNG/JPG）パスのリスト（順序通り）
    output_pdf: 出力PDFパス
    languages: 受け取るが未使用（contract 互換のため）
    progress: (current, total, message) コールバック

  Returns:
    出力PDFパス
  """
  import fitz  # PyMuPDF

  if not is_available():
    raise RuntimeError(
      'mlx-vlm が未インストール、または非対応環境です。\n'
      'Apple Silicon Mac で  pip install mlx-vlm  を実行してください。'
    )

  output_pdf = Path(output_pdf)
  output_pdf.parent.mkdir(parents=True, exist_ok=True)

  total = len(images)
  if total == 0:
    raise ValueError('画像が0枚です')

  model_id = get_model_id()
  doc = fitz.open()

  for i, img_path in enumerate(images):
    if progress:
      progress(i, total, f'Qwen-VL OCR: {i + 1}/{total} ページ')

    img_path = Path(img_path)
    pix = fitz.Pixmap(str(img_path))
    page_w, page_h = pix.width, pix.height
    page = doc.new_page(width=page_w, height=page_h)
    page.insert_image(page.rect, filename=str(img_path))

    try:
      text = ocr_image_text(img_path, model_id=model_id)
    except Exception as e:
      print(f'Qwen-VL OCR failed on page {i + 1}: {e}')
      text = ''

    _insert_text_layer(page, text, page_w, page_h)

  if progress:
    progress(total, total, '保存中…')

  doc.save(str(output_pdf), garbage=4, deflate=True)
  doc.close()
  return output_pdf
