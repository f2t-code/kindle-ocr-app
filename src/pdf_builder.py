"""PNG画像群を1つのPDFに結合.

img2pdf を使用（ロスレス、高速、PILより画質劣化なし）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import img2pdf


def build_pdf(images: Iterable[Path], output_pdf: Path) -> Path:
  """画像をPDFに結合.

  Args:
    images: PNG/JPGファイルのパス（順序通りに渡す）
    output_pdf: 出力PDFパス

  Returns:
    生成されたPDFパス
  """
  output_pdf = Path(output_pdf)
  output_pdf.parent.mkdir(parents=True, exist_ok=True)

  image_paths = [str(p) for p in images]
  if not image_paths:
    raise ValueError('画像が0枚です')

  pdf_bytes = img2pdf.convert(image_paths)
  output_pdf.write_bytes(pdf_bytes)
  return output_pdf
