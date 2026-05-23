"""OCR済みPDFからMarkdownファイルを生成.

pdftotext で抽出 → 軽くクリーンアップ → ページ区切りでマーク
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def find_pdftotext() -> Optional[str]:
  """pdftotext バイナリを探す（poppler 同梱）."""
  return shutil.which('pdftotext')


_NOISE_PATTERNS = [
  # Kindle macOS のメニューバー（先頭付近に出る）
  re.compile(r'^.*Kindle\s*ファ?\s*イル.*編集.*表示.*ウイ?\s*ン?\s*ド?\s*ウ.*ヘ?ル?プ.*$', re.MULTILINE),
  re.compile(r'^.*5月\s*\d+\s*[日土火水木金][^\n]*$', re.MULTILINE),  # 日付スタンプ
  re.compile(r'^.*\d{1,2}:\d{2}\s*$', re.MULTILINE),  # 時刻
  # OCR ガベージ: 大量のスペースで区切られた1-2文字の文字列が並ぶ行
  re.compile(r'^(?:\s{2,}[\W_]{1,3}){5,}.*$', re.MULTILINE),
  # @ で始まる macOS Kindle ヘッダー
  re.compile(r'^@\s*Kindle.*$', re.MULTILINE),
  # CLAUDE CODE のような大きい文字が崩れた行
  re.compile(r'^.*CLAU[BD]E\s*CODE.*$', re.MULTILINE),
]


def clean_text(text: str) -> str:
  """OCR結果テキストのクリーンアップ.

  Kindleアプリ UI 由来のノイズを除去し、空白を整える。
  """
  # ノイズパターン除去
  for pat in _NOISE_PATTERNS:
    text = pat.sub('', text)
  # 半角空白の暴走を圧縮（OCRで生じる単語間の異常な空白）
  text = re.sub(r' {3,}', '  ', text)
  # 1〜2文字だけで終わる行（ノイズ）
  text = re.sub(r'^\s*[\W_]{1,2}\s*$\n?', '', text, flags=re.MULTILINE)
  # 連続する空白行を最大2行に
  text = re.sub(r'\n{3,}', '\n\n', text)
  # 行末のスペース除去
  text = re.sub(r'[ \t]+\n', '\n', text)
  # ハイフンで折り返した語をくっつける (英語)
  text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
  return text.strip()


def export_pdf_to_markdown(pdf_path: Path, md_path: Path, book_title: str = '') -> Path:
  """OCR済みPDF → Markdownファイル.

  Args:
    pdf_path: 入力PDF（OCR済み・テキストレイヤーあり）
    md_path: 出力 .md ファイル
    book_title: 書名（先頭にタイトルとして書く）

  Returns:
    生成されたmdパス

  Raises:
    FileNotFoundError: pdftotextが無い、または入力PDF不在
  """
  pdf_path = Path(pdf_path)
  md_path = Path(md_path)
  md_path.parent.mkdir(parents=True, exist_ok=True)

  if not pdf_path.exists():
    raise FileNotFoundError(f'入力PDFが存在しません: {pdf_path}')

  bin_path = find_pdftotext()
  if not bin_path:
    raise FileNotFoundError(
      'pdftotext が見つかりません。\n'
      'Mac: brew install poppler\n'
      'Windows: poppler-windows をPATHに追加'
    )

  # ページ区切り文字（^L = 0x0c）でテキスト抽出
  result = subprocess.run(
    [bin_path, '-layout', '-enc', 'UTF-8', str(pdf_path), '-'],
    capture_output=True, text=True
  )
  if result.returncode != 0:
    raise RuntimeError(f'pdftotext失敗: {result.stderr}')

  raw_text = result.stdout

  # ページごとに分割 (^L)
  pages = raw_text.split('\f')

  lines: list[str] = []
  if book_title:
    lines.append(f'# {book_title}\n')
    lines.append(f'> OCRで抽出した本文。誤認識を含む可能性があります。\n')

  for i, page_text in enumerate(pages, start=1):
    cleaned = clean_text(page_text)
    if not cleaned:
      continue
    lines.append(f'\n---\n\n## p.{i}\n\n{cleaned}\n')

  md_path.write_text('\n'.join(lines), encoding='utf-8')
  return md_path
