"""macOS アクセシビリティ権限の取得ヘルパー.

エラー(1002)発生時、ユーザーに何をすべきか具体的に示す。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def get_real_python_binary() -> str:
  """venv経由でも実バイナリのフルパスを返す（Accessibility に追加すべきパス）."""
  exe = sys.executable
  try:
    real = os.path.realpath(exe)
    return real
  except Exception:
    return exe


def copy_to_clipboard_mac(text: str) -> bool:
  """テキストをmacOSクリップボードにコピー."""
  try:
    p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
    p.communicate(input=text.encode('utf-8'))
    return p.returncode == 0
  except Exception:
    return False


def reveal_in_finder_mac(path: str):
  """Finder でファイルを選択状態で表示."""
  subprocess.run(['open', '-R', path])


PERMISSION_GUIDE_MAC = '''■ macOSアクセシビリティ権限の許可手順

【ステップ 1】 下の「⚙️ アクセシビリティ設定を開く」をクリック
　 → システム設定が開く

【ステップ 2】 左下の鍵🔒アイコンをクリックしてロック解除
　 → 指紋またはパスワード入力

【ステップ 3】 右上の「＋」ボタンをクリック
　 → ファイル選択ダイアログが開く

【ステップ 4】 cmd + shift + G を押して「フォルダへ移動」を呼び出す
　 → 入力欄が出る

【ステップ 5】 下の「Pythonパスをコピー」ボタンを押す
　 → クリップボードにパスがコピーされる

【ステップ 6】 cmd + V で貼り付け → Enter → 「開く」をクリック
　 → リストに python3.14（または同名）が追加される

【ステップ 7】 追加された行のトグルスイッチをオンにする

【ステップ 8】 このアプリを完全終了（⌘Q）して再起動

それでも効かない場合:
  - 「ターミナル」もリストに追加 → オン
  - 「画面収録」にも同じ手順で追加
  - Mac本体を再起動
'''
