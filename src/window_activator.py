"""Kindleアプリを最前面にアクティベート（Mac / Windows両対応）.

これがないと、矢印キーが別アプリ（オーバーレイ表示中のPython自身など）に
送られてしまい、Kindleのページが進まない。
"""

from __future__ import annotations

import platform
import subprocess
from typing import Optional


# Mac版Kindle:
#  新版（Mac App Store）: /Applications/Amazon Kindle.app、プロセス名 "Kindle"
#  旧版（レガシー・サポート終了）: /Applications/Kindle.app、プロセス名 "Kindle"
# プロセス名は両方とも "Kindle" なのでバンドルパスで判別する。
LEGACY_KINDLE_PATH_PATTERNS = ['/Kindle.app']  # 旧版を示すパス（"Amazon Kindle.app" は含まれない）
KINDLE_APP_PRIORITY_MAC = ['Amazon Kindle', 'Kindle Classic', 'Kindle']
KINDLE_PROCESS_NAMES_WIN = ['Kindle.exe']


def is_mac() -> bool:
  return platform.system() == 'Darwin'


def is_windows() -> bool:
  return platform.system() == 'Windows'


def list_running_kindle_processes_mac() -> list[dict]:
  """Mac で「現在起動中」のKindle系プロセス一覧を返す.

  各要素: {'name': プロセス名, 'path': バンドルのPOSIXパス, 'is_legacy': 旧版か}
  自動起動はしない。
  """
  # プロセス名と bundle path を一括取得
  script = '''
  tell application "System Events"
    set procs to every process whose name contains "Kindle"
    set output to ""
    repeat with p in procs
      set pName to name of p
      try
        set pFile to (file of p as alias)
        set pPath to POSIX path of pFile
      on error
        set pPath to ""
      end try
      set output to output & pName & "|" & pPath & linefeed
    end repeat
    return output
  end tell
  '''
  result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
  if result.returncode != 0 or not result.stdout.strip():
    return []

  procs: list[dict] = []
  for line in result.stdout.strip().split('\n'):
    if '|' not in line:
      continue
    name, path = line.split('|', 1)
    name = name.strip()
    path = path.strip()
    is_legacy = any(pat in path for pat in LEGACY_KINDLE_PATH_PATTERNS) and '/Amazon Kindle.app' not in path
    procs.append({'name': name, 'path': path, 'is_legacy': is_legacy})
  return procs


def find_kindle_app_mac(preferred: Optional[str] = None) -> Optional[dict]:
  """Mac で起動中のKindleプロセスを返す（新版を優先、レガシーは最後）."""
  procs = list_running_kindle_processes_mac()
  if not procs:
    return None
  # 新版（is_legacy=False）を優先
  non_legacy = [p for p in procs if not p['is_legacy']]
  if non_legacy:
    return non_legacy[0]
  return procs[0]  # 全部レガシーならその先頭（呼び出し元でエラーにする）


def is_kindle_running() -> bool:
  if is_mac():
    return len(list_running_kindle_processes_mac()) > 0
  if is_windows():
    try:
      result = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq Kindle.exe'],
        capture_output=True, text=True
      )
      return 'Kindle.exe' in result.stdout
    except Exception:
      return False
  return False


def is_legacy_kindle_only() -> bool:
  """旧版（サポート終了）Kindleしか起動していない場合 True."""
  if not is_mac():
    return False
  procs = list_running_kindle_processes_mac()
  if not procs:
    return False
  return all(p['is_legacy'] for p in procs)


def activate_kindle(preferred: Optional[str] = None) -> tuple[bool, str]:
  """Kindleアプリを最前面に切り替える（起動済みのものだけ、自動起動しない）.

  Args:
    preferred: 優先アプリ名（GUI設定）

  Returns:
    (success, message)
  """
  if is_mac():
    proc = find_kindle_app_mac(preferred)
    if not proc:
      return False, (
        'Kindleアプリが起動していません。\n'
        '「Amazon Kindle」（Mac App Store版・新版）を起動して、'
        '読みたい本の1ページ目を開いてから再実行してください。'
      )

    if proc['is_legacy']:
      return False, (
        f'⚠️ 検出されたKindle「{proc["path"]}」は旧版（サポート終了）です。\n'
        'このアプリは「This app is no longer supported」エラーで本が表示できません。\n\n'
        '対処:\n'
        '1. 旧Kindle.app を ⌘Q で完全終了\n'
        '2. Mac App Store の「Amazon Kindle」（新版）を起動\n'
        '3. 読みたい本を開いて再実行'
      )

    # 自動起動を避けるため System Events 経由でアクティベート
    script = (
      f'tell application "System Events" to '
      f'set frontmost of first process whose name is "{proc["name"]}" to true'
    )
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    if result.returncode != 0:
      return False, f'Kindleのアクティベート失敗: {result.stderr.strip()}'
    return True, f'Kindleアプリ「{proc["path"]}」を最前面に切り替えました'

  if is_windows():
    try:
      import pygetwindow as gw
      # タイトル先頭が "Kindle" or "Amazon Kindle" のウィンドウを優先
      all_windows = gw.getAllWindows()
      candidates = [w for w in all_windows if w.title and (
        w.title.startswith('Kindle') or w.title.startswith('Amazon Kindle')
        or ' - Kindle' in w.title  # "BookTitle - Kindle" 形式
      )]
      if not candidates:
        # フォールバック: タイトルに Kindle を含む（誤マッチもあり得る）
        candidates = [w for w in all_windows if w.title and 'Kindle' in w.title]
      if not candidates:
        return False, (
          'Kindleウィンドウが見つかりません。\n'
          'Amazon Kindle for PC を起動して読みたい本を開いてください。'
        )
      w = candidates[0]
      try:
        if w.isMinimized:
          w.restore()
      except Exception:
        pass
      try:
        w.activate()
      except Exception:
        # pywin32 の SetForegroundWindow が失敗するケースがある（フォーカス窃取防止）
        # 代替: ウィンドウをいったん最小化→復元でフォーカスを取る
        try:
          w.minimize()
          w.restore()
        except Exception:
          pass
      return True, f'Kindleウィンドウ「{w.title}」を最前面に切り替えました'
    except ImportError:
      return False, 'pygetwindow が未インストール。pip install pygetwindow を実行してください。'
    except Exception as e:
      return False, f'Kindleアクティベート失敗: {e}'

  return False, f'未対応OS: {platform.system()}'


# macOS key code → AppleScript key code
MAC_KEY_CODES = {
  'right': 124,
  'left': 123,
  'down': 125,
  'up': 126,
  'space': 49,
  'pagedown': 121,
  'pageup': 116,
}


def send_key_mac(key_name: str) -> tuple[bool, str]:
  """Mac: AppleScript経由でキーを送信（Kindle前提）.

  pyautogui よりこちらの方が「アクセシビリティが osascript に必要」と
  明示的になり、エラーが出れば即わかる。
  """
  code = MAC_KEY_CODES.get(key_name)
  if code is None:
    return False, f'未対応キー: {key_name}'
  script = f'tell application "System Events" to key code {code}'
  result = subprocess.run(
    ['osascript', '-e', script],
    capture_output=True, text=True, timeout=5
  )
  if result.returncode != 0:
    return False, f'キー送信失敗: {result.stderr.strip()}'
  return True, ''


def open_accessibility_settings():
  """システム設定 → プライバシーとセキュリティ → アクセシビリティ を開く."""
  if is_mac():
    subprocess.run([
      'open',
      'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'
    ])


def open_screen_recording_settings():
  """システム設定 → プライバシーとセキュリティ → 画面収録 を開く."""
  if is_mac():
    subprocess.run([
      'open',
      'x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture'
    ])


def get_python_binary_info() -> str:
  """現在のPythonバイナリの実体パスを返す（権限付与のため）."""
  import sys
  import os
  exe = sys.executable
  try:
    real = os.path.realpath(exe)
  except Exception:
    real = exe
  return f'sys.executable: {exe}\n実体パス: {real}'


def check_accessibility_permission_mac() -> tuple[bool, str]:
  """Mac でアクセシビリティ権限が付与されているか確認.

  権限がないと pyautogui の key press が無音で失敗する。
  完全な検出は難しいが、簡易チェックとしてAppleScript経由でキーイベントを試す。
  """
  if not is_mac():
    return True, ''
  try:
    script = 'tell application "System Events" to keystroke ""'
    result = subprocess.run(
      ['osascript', '-e', script],
      capture_output=True, text=True, timeout=3
    )
    if 'not allowed' in result.stderr.lower() or '1002' in result.stderr or result.returncode != 0:
      return False, (
        'アクセシビリティ権限が不足している可能性があります。\n'
        'システム設定 → プライバシーとセキュリティ → アクセシビリティ で\n'
        '「ターミナル」または「Python」を許可してください。'
      )
    return True, ''
  except Exception:
    return True, ''  # チェック失敗時は許可されている前提で続行
