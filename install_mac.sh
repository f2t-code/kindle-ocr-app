#!/usr/bin/env bash
# Kindle OCR App — macOSセットアップ
set -euo pipefail

echo "==> Kindle OCR App セットアップ (macOS)"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrewが見つかりません。https://brew.sh からインストールしてください"
  exit 1
fi

echo "==> tesseract と言語データをインストール"
brew list tesseract >/dev/null 2>&1 || brew install tesseract
brew list tesseract-lang >/dev/null 2>&1 || brew install tesseract-lang
brew list ghostscript >/dev/null 2>&1 || brew install ghostscript
brew list unpaper >/dev/null 2>&1 || brew install unpaper  # --clean（ノイズ除去）に必要

echo "==> Python仮想環境を作成"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "==> セットアップ完了"
echo "起動: bash $SCRIPT_DIR/run_mac.sh"
echo ""
echo "⚠️ 初回起動時に macOS が「画面収録」と「アクセシビリティ」の権限を要求します。"
echo "  システム設定 → プライバシーとセキュリティ で Python (またはターミナル) を許可してください。"
