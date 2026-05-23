# Windows 用 全部入り Kindle OCR.exe をビルド（PyInstaller）.
# 出来た .exe は Python インストール不要でダブルクリック起動できる。
#
# 前提:
#   1. install_windows.ps1 で venv セットアップ済み
#   2. Yomitoku もインストール済み（推奨）

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (-not (Test-Path 'venv\Scripts\Activate.ps1')) {
  Write-Host '❌ venv が無い。先に install_windows.ps1 を実行してください'
  exit 1
}

& .\venv\Scripts\Activate.ps1

# PyInstaller 確認
$piCheck = pip show pyinstaller 2>$null
if (-not $piCheck) {
  Write-Host '==> PyInstaller をインストール'
  pip install pyinstaller
}

# 古いビルド削除
if (Test-Path 'build') { Remove-Item 'build' -Recurse -Force }
if (Test-Path 'dist') { Remove-Item 'dist' -Recurse -Force }

Write-Host '==> PyInstaller でビルド開始（数分かかります）'
pyinstaller KindleOCR.spec --clean --noconfirm

$exePath = 'dist\Kindle OCR\Kindle OCR.exe'

if (-not (Test-Path $exePath)) {
  Write-Host "❌ ビルド失敗（$exePath が見つかりません）"
  exit 1
}

# 配布用 ZIP 作成
Write-Host '==> 配布用ZIP作成'
Compress-Archive -Path 'dist\Kindle OCR' -DestinationPath 'dist\KindleOCR-Windows.zip' -Force

$zipSize = (Get-Item 'dist\KindleOCR-Windows.zip').Length / 1MB
$zipSizeStr = "{0:N1} MB" -f $zipSize

Write-Host ''
Write-Host '======================================================================'
Write-Host '✅ ビルド完了'
Write-Host '======================================================================'
Write-Host ''
Write-Host '出力ファイル:'
Write-Host "  - dist\Kindle OCR\Kindle OCR.exe       （フォルダ配布）"
Write-Host "  - dist\KindleOCR-Windows.zip            （配布用 $zipSizeStr）"
Write-Host ''
Write-Host '配布相手への案内文:'
Write-Host '  「KindleOCR-Windows.zip をダウンロード→解凍→Kindle OCR フォルダ内の'
Write-Host '   Kindle OCR.exe をダブルクリック」'
Write-Host '  「SmartScreen警告が出たら 詳細情報→実行 をクリック」'
Write-Host ''
Write-Host '⚠️ ウイルス対策ソフトが pyautogui を遮断する可能性あり。'
Write-Host '   その場合は除外設定が必要。'
