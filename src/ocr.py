"""ocrmypdf を呼び出してPDFをOCR化.

tesseract の言語データが必要（jpn, eng）。
"""

from __future__ import annotations

import glob
import os
import platform
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional


# OCRエンジン識別子
ENGINE_AUTO = 'auto'
ENGINE_APPLE_VISION = 'apple_vision'
ENGINE_TESSERACT = 'tesseract'
ENGINE_GOOGLE_VISION = 'google_vision'
ENGINE_YOMITOKU = 'yomitoku'
ENGINE_MLX_QWEN = 'mlx_qwen'


def get_default_engine() -> str:
  """OS と利用可能ライブラリから自動でエンジンを選ぶ."""
  if platform.system() == 'Darwin':
    try:
      from src.ocr_apple_vision import is_available
      if is_available():
        return ENGINE_APPLE_VISION
    except ImportError:
      pass
  # Windows/Linux: Yomitoku が入っていれば優先、なければ Tesseract
  try:
    from src.ocr_yomitoku import is_available as yomi_available
    if yomi_available():
      return ENGINE_YOMITOKU
  except ImportError:
    pass
  return ENGINE_TESSERACT


def list_available_engines() -> list[tuple[str, str]]:
  """利用可能なOCRエンジンを (識別子, 表示名) で返す."""
  from src.settings import get_google_api_key

  engines = []
  if platform.system() == 'Darwin':
    try:
      from src.ocr_apple_vision import is_available
      if is_available():
        engines.append((ENGINE_APPLE_VISION, 'Apple Vision（Mac標準・無料・高精度）'))
    except ImportError:
      pass

  # Yomitoku は入っていれば候補に出す
  try:
    from src.ocr_yomitoku import is_available as yomi_available
    if yomi_available():
      engines.append((ENGINE_YOMITOKU, 'Yomitoku（日本語特化・無料）'))
  except ImportError:
    pass

  # mlx-vlm (Qwen2.5-VL) は Apple Silicon かつ mlx-vlm 導入時のみ候補
  try:
    from src.ocr_mlx_qwen import is_available as mlx_available
    if mlx_available():
      engines.append((ENGINE_MLX_QWEN, 'Qwen2.5-VL（ローカルAI・高精度・要DL）'))
  except ImportError:
    pass

  engines.append((ENGINE_TESSERACT, 'Tesseract（互換性重視・無料）'))

  # Google Vision は API キー設定済みのときだけ候補
  if get_google_api_key():
    engines.append((ENGINE_GOOGLE_VISION, 'Google Cloud Vision（API・最高精度）'))

  return engines


# ocrmypdf の進捗出力をパースする正規表現
# 例: "Scanning contents:  45/141" / "OCR:  60/141 pages" / "[ocrmypdf] 30/141"
_PAGE_PROGRESS_PATTERNS = [
  re.compile(r'(\d+)\s*/\s*(\d+)\s*pages?', re.IGNORECASE),
  re.compile(r':\s*(\d+)\s*/\s*(\d+)\b'),
  re.compile(r'page\s+(\d+)\s+of\s+(\d+)', re.IGNORECASE),
]


def _parse_progress(line: str) -> Optional[tuple[int, int]]:
  for pat in _PAGE_PROGRESS_PATTERNS:
    m = pat.search(line)
    if m:
      try:
        cur = int(m.group(1))
        total = int(m.group(2))
        if 0 < cur <= total and total < 10000:
          return cur, total
      except (ValueError, IndexError):
        pass
  return None


def _poll_ocr_progress(
  stop_event: threading.Event,
  initial_dirs: set,
  total_pages: int,
  callback: Callable[[int, int, str], None],
):
  """ocrmypdf の作業 tempdir 内の hocr ファイル数をポーリングして進捗を取得.

  ocrmypdf は1ページOCR完了ごとに `NNNNNN_ocr_hocr.txt` を生成する。
  これを数えることで実態に近い進捗が分かる。
  """
  tmpdir = os.environ.get('TMPDIR', '/tmp')
  pattern_dirs = os.path.join(tmpdir, 'ocrmypdf.io.*')
  last_reported = 0
  while not stop_event.is_set():
    current_dirs = set(glob.glob(pattern_dirs))
    new_dirs = current_dirs - initial_dirs
    max_done = 0
    for d in new_dirs:
      try:
        hocr_files = glob.glob(os.path.join(d, '*_ocr_hocr.txt'))
        max_done = max(max_done, len(hocr_files))
      except Exception:
        pass
    if max_done > last_reported:
      last_reported = max_done
      try:
        callback(max_done, total_pages, f'OCR: {max_done}/{total_pages} ページ完了')
      except Exception:
        pass
    if stop_event.wait(timeout=2.0):
      break


def run_ocr_from_images(
  images: list[Path],
  output_pdf: Path,
  engine: str = ENGINE_AUTO,
  language: str = 'jpn+eng',
  progress: Optional[Callable[[int, int, str], None]] = None,
) -> Path:
  """画像群からダイレクトに検索可能PDFを生成（エンジン自動選択）.

  Args:
    images: 入力PNG群
    output_pdf: 出力PDFパス
    engine: 'auto' / 'apple_vision' / 'tesseract'
    language: tesseract用言語コード or Vision用'jpn+eng'

  Returns:
    出力PDFパス
  """
  if engine == ENGINE_AUTO:
    engine = get_default_engine()

  # 言語コード変換
  lang_map_apple = {
    'jpn': ['ja-JP'], 'eng': ['en-US'], 'jpn+eng': ['ja-JP', 'en-US'],
    'jpn_vert': ['ja-JP'], 'jpn_vert+eng': ['ja-JP', 'en-US'],
  }
  lang_map_google = {
    'jpn': ['ja'], 'eng': ['en'], 'jpn+eng': ['ja', 'en'],
    'jpn_vert': ['ja'], 'jpn_vert+eng': ['ja', 'en'],
  }

  if engine == ENGINE_APPLE_VISION:
    from src.ocr_apple_vision import build_searchable_pdf_from_images
    langs = lang_map_apple.get(language, ['ja-JP', 'en-US'])
    return build_searchable_pdf_from_images(images, output_pdf, langs, progress)

  if engine == ENGINE_GOOGLE_VISION:
    from src.ocr_google_vision import build_searchable_pdf_from_images as g_build
    from src.settings import get_google_api_key
    api_key = get_google_api_key()
    if not api_key:
      raise RuntimeError('Google Vision API キーが未設定です。設定画面で入力してください。')
    langs = lang_map_google.get(language, ['ja', 'en'])
    return g_build(images, output_pdf, api_key, langs, progress)

  if engine == ENGINE_YOMITOKU:
    from src.ocr_yomitoku import build_searchable_pdf_from_images as y_build
    return y_build(images, output_pdf, None, progress)

  if engine == ENGINE_MLX_QWEN:
    from src.ocr_mlx_qwen import build_searchable_pdf_from_images as q_build
    return q_build(images, output_pdf, None, progress)

  # Tesseract フォールバック: img2pdf → ocrmypdf
  from src.pdf_builder import build_pdf
  import tempfile
  tmp = Path(tempfile.mkdtemp(prefix='ocr_pipe_'))
  raw_pdf = tmp / 'raw.pdf'
  build_pdf(images, raw_pdf)
  return run_ocr(
    raw_pdf, output_pdf, language=language,
    page_progress=progress,
  )


def find_ocrmypdf() -> Optional[str]:
  """ocrmypdf 実行ファイルを探す.

  PATH 上、または pip user install の場所を確認。
  """
  import shutil

  found = shutil.which('ocrmypdf')
  if found:
    return found

  user_bin = Path(sys.prefix) / 'bin' / 'ocrmypdf'
  if user_bin.exists():
    return str(user_bin)

  candidates = [
    Path.home() / 'Library/Python' / f'{sys.version_info.major}.{sys.version_info.minor}' / 'bin' / 'ocrmypdf',
    Path.home() / '.local' / 'bin' / 'ocrmypdf',
  ]
  for c in candidates:
    if c.exists():
      return str(c)

  return None


def _count_pdf_pages(pdf_path: Path) -> int:
  """PDF のページ数を取得（pdfinfo を使用）."""
  import shutil
  bin_path = shutil.which('pdfinfo')
  if not bin_path:
    return 0
  try:
    result = subprocess.run(
      [bin_path, str(pdf_path)],
      capture_output=True, text=True, timeout=10
    )
    for line in result.stdout.split('\n'):
      if line.startswith('Pages:'):
        return int(line.split(':')[1].strip())
  except Exception:
    pass
  return 0


def run_ocr(
  input_pdf: Path,
  output_pdf: Path,
  language: str = 'jpn+eng',
  skip_text: bool = True,
  optimize: int = 1,
  jobs: int = 4,
  high_quality: bool = True,
  progress: Optional[Callable[[str], None]] = None,
  page_progress: Optional[Callable[[int, int, str], None]] = None,
) -> Path:
  """OCRを実行して検索可能PDFを生成.

  Args:
    input_pdf: 入力PDF
    output_pdf: 出力PDF
    language: tesseract 言語コード（例: jpn, eng, jpn+eng, jpn_vert）
    skip_text: True なら既存テキストレイヤーがあるページをスキップ
    optimize: 最適化レベル 0-3
    jobs: 並列ワーカー数
    high_quality: True で傾き補正・ノイズ除去・高解像度OCRを有効化
    progress: ステータス文字列を受け取るコールバック

  Returns:
    出力PDFパス

  Raises:
    FileNotFoundError: ocrmypdf が見つからない
    subprocess.CalledProcessError: OCR失敗
  """
  bin_path = find_ocrmypdf()
  if not bin_path:
    raise FileNotFoundError(
      'ocrmypdf が見つかりません。pip install ocrmypdf を実行してください。'
    )

  input_pdf = Path(input_pdf)
  output_pdf = Path(output_pdf)
  output_pdf.parent.mkdir(parents=True, exist_ok=True)

  cmd = [
    bin_path,
    '-l', language,
    '--optimize', str(optimize),
    '--jobs', str(jobs),
    '--output-type', 'pdf',
  ]
  if skip_text:
    cmd.append('--skip-text')

  if high_quality:
    import shutil
    cmd += [
      '--deskew',                  # 傾き補正
      '--oversample', '400',       # 解像度を400DPI相当にアップサンプリング
    ]
    # unpaper がインストールされていれば clean を有効化
    if shutil.which('unpaper'):
      cmd.append('--clean')
    # remove-background は十分な余白がないと失敗するので省略
    # tesseract オプション: 縦書きでなければ PSM 6（均一テキストブロック）
    if 'vert' not in language:
      cmd += ['--tesseract-pagesegmode', '6']

  cmd += [str(input_pdf), str(output_pdf)]

  if progress:
    progress(f'OCR開始: {input_pdf.name}')

  # ページ数を事前取得（進捗ポーリング用）
  total_pages = _count_pdf_pages(input_pdf)

  # OCR開始前の ocrmypdf temp dir スナップショット
  tmp_root = os.environ.get('TMPDIR', '/tmp')
  initial_dirs = set(glob.glob(os.path.join(tmp_root, 'ocrmypdf.io.*')))

  # 進捗ポーリングスレッド起動
  stop_event = threading.Event()
  poll_thread = None
  if page_progress and total_pages > 0:
    poll_thread = threading.Thread(
      target=_poll_ocr_progress,
      args=(stop_event, initial_dirs, total_pages, page_progress),
      daemon=True,
    )
    poll_thread.start()

  proc = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
    env={**os.environ, 'TERM': 'dumb'},
  )

  stderr_lines: list[str] = []
  if proc.stdout:
    for line in proc.stdout:
      line = line.rstrip()
      if not line:
        continue
      stderr_lines.append(line)
      if progress:
        progress(line[:200])

  proc.wait()
  stop_event.set()
  if poll_thread:
    poll_thread.join(timeout=3)

  # OCR完了 → 進捗を満杯に
  if page_progress and total_pages > 0:
    page_progress(total_pages, total_pages, f'OCR: {total_pages}/{total_pages} ページ完了')

  if proc.returncode != 0:
    err = '\n'.join(stderr_lines[-30:])
    if progress:
      progress(f'OCR失敗: {err[-500:]}')
    raise subprocess.CalledProcessError(
      proc.returncode, cmd, output='\n'.join(stderr_lines), stderr=err
    )

  if progress:
    progress(f'OCR完了: {output_pdf.name}')
  return output_pdf
