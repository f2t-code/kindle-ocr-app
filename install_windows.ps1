# Kindle OCR App — Windowsセットアップ
# 実行: powershell -ExecutionPolicy Bypass -File install_windows.ps1

$ErrorActionPreference = 'Stop'

Write-Host '==> Kindle OCR App セットアップ (Windows)'

function Test-Command($name) {
  return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

# Python 確認
if (-not (Test-Command 'python')) {
  Write-Host '❌ Pythonが見つかりません。'
  Write-Host '   Microsoft Store から "Python 3.12" をインストールするか、'
  Write-Host '   https://www.python.org/downloads/ からダウンロードしてください'
  Write-Host '   ※ インストール時「Add Python to PATH」必須'
  exit 1
}

$pythonVersion = (python --version 2>&1).ToString()
Write-Host "==> $pythonVersion 検出"

# 仮想環境作成
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (-not (Test-Path 'venv')) {
  Write-Host '==> Python仮想環境を作成'
  python -m venv venv
}

Write-Host '==> 仮想環境を有効化'
& .\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

Write-Host '==> 必須Pythonパッケージをインストール'
pip install -r requirements.txt

# OCR エンジン選択
Write-Host ''
Write-Host '======================================================================'
Write-Host '  OCR エンジンの選択（推奨を1つ以上選んでください）'
Write-Host '======================================================================'
Write-Host ''
Write-Host '  [1] Yomitoku のみインストール（日本語特化・無料・90-95%精度・500MB+）'
Write-Host '      →ネット不要で高精度の日本語OCR。推奨。'
Write-Host ''
Write-Host '  [2] Tesseract も使えるようにする（手動インストールあり・80-90%精度）'
Write-Host '      →UB-Mannheim版を別途DL'
Write-Host ''
Write-Host '  [3] 両方インストール'
Write-Host ''
Write-Host '  [4] スキップ（既存設定で進める）'
Write-Host ''
$choice = Read-Host '選択 [1-4]'

if ($choice -eq '1' -or $choice -eq '3') {
  Write-Host ''
  Write-Host '==> Yomitoku をインストール（5-10分かかります）'
  pip install yomitoku
  Write-Host ''
  Write-Host '==> Yomitoku モデル事前ダウンロード（500MB+、初回のみ）'
  python -c "from yomitoku import OCR; OCR(visualize=False); print('モデルダウンロード完了')"
}

if ($choice -eq '2' -or $choice -eq '3') {
  $tesseractDefault = "C:\Program Files\Tesseract-OCR\tesseract.exe"
  if (-not (Test-Command 'tesseract') -and -not (Test-Path $tesseractDefault)) {
    Write-Host ''
    Write-Host '⚠️  Tesseract は別途手動インストールが必要です:'
    Write-Host '   https://github.com/UB-Mannheim/tesseract/wiki'
    Write-Host ''
    Write-Host '   インストール時のチェック必須:'
    Write-Host '    ✅ Additional language data → Japanese'
    Write-Host '    ✅ Additional language data → Japanese (vertical)'
    Write-Host '   インストール先: C:\Program Files\Tesseract-OCR\ を推奨'
    Write-Host ''
    Start-Process 'https://github.com/UB-Mannheim/tesseract/wiki'
    Read-Host 'インストール後 Enterで継続'
  }
}

# Ghostscript（任意）
if (-not (Test-Command 'gswin64c') -and -not (Test-Command 'gs')) {
  Write-Host ''
  Write-Host '(任意) Ghostscriptが未インストール。'
  Write-Host '   PDF最適化を使うなら https://www.ghostscript.com/releases/gsdnld.html'
}

Write-Host ''
Write-Host '======================================================================'
Write-Host '  セットアップ完了'
Write-Host '======================================================================'
Write-Host ''
Write-Host "起動: powershell -ExecutionPolicy Bypass -File $scriptDir\run_windows.ps1"
Write-Host ''
Write-Host '初回起動時の注意:'
Write-Host '  - macOSと違いアクセシビリティ権限は不要です'
Write-Host '  - ウイルス対策ソフトが pyautogui を遮断する場合は除外設定が必要'
