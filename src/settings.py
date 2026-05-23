"""アプリ設定の永続化（~/.kindle-ocr/config.json）.

APIキーなど機密情報を含むため、ユーザーホーム配下に保存。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


CONFIG_DIR = Path.home() / '.kindle-ocr'
CONFIG_FILE = CONFIG_DIR / 'config.json'


def _ensure_dir():
  CONFIG_DIR.mkdir(parents=True, exist_ok=True)
  try:
    os.chmod(CONFIG_DIR, 0o700)
  except Exception:
    pass


def load() -> dict[str, Any]:
  if not CONFIG_FILE.exists():
    return {}
  try:
    return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
  except Exception:
    return {}


def save(data: dict[str, Any]):
  _ensure_dir()
  CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
  try:
    os.chmod(CONFIG_FILE, 0o600)
  except Exception:
    pass


def get(key: str, default: Any = None) -> Any:
  return load().get(key, default)


def set_value(key: str, value: Any):
  data = load()
  data[key] = value
  save(data)


def get_google_api_key() -> str:
  """Google Cloud Vision APIキーを取得（環境変数優先）."""
  env = os.environ.get('GOOGLE_VISION_API_KEY')
  if env:
    return env
  return get('google_vision_api_key', '') or ''
