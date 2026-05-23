#!/usr/bin/env bash
# Mac 用 全部入り Kindle OCR.app をビルド（PyInstaller）.
# 出来た .app は Python インストール不要でダブルクリック起動できる。
#
# 前提:
#   1. bash install_mac.sh で venv セットアップ済み
#   2. bash scripts/setup_signing_cert.sh で署名証明書作成済み
#   3. python3 scripts/generate_icon.py && iconutil でアイコン生成済み
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f venv/bin/activate ]; then
  echo "❌ venv が無い。先に install_mac.sh を実行してください"
  exit 1
fi

# shellcheck disable=SC1091
source venv/bin/activate

# PyInstaller 確認
if ! pip show pyinstaller >/dev/null 2>&1; then
  echo "==> PyInstaller をインストール"
  pip install pyinstaller
fi

# 古いビルド成果物を削除
rm -rf build dist

echo "==> PyInstaller でビルド開始（数分かかります）"
pyinstaller KindleOCR.spec --clean --noconfirm

APP_DIR="dist/Kindle OCR.app"

if [ ! -d "$APP_DIR" ]; then
  echo "❌ ビルド失敗（$APP_DIR が見つかりません）"
  exit 1
fi

# Gatekeeper attribute をクリア
xattr -cr "$APP_DIR" 2>/dev/null || true

# ========== コード署名（自己署名証明書があれば使用） ==========
SIGN_IDENTITY="Kindle OCR Self-Signed"
SIGN_KEYCHAIN="$HOME/Library/Keychains/kindleocr-signing.keychain-db"
SIGN_SHA=""
KEYCHAIN_ARG=""
if [ -f "$SIGN_KEYCHAIN" ]; then
  SIGN_SHA=$(security find-identity -p codesigning "$SIGN_KEYCHAIN" 2>/dev/null \
    | grep "$SIGN_IDENTITY" \
    | head -1 \
    | awk '{print $2}')
  if [ -n "$SIGN_SHA" ]; then
    KEYCHAIN_ARG="--keychain $SIGN_KEYCHAIN"
  fi
fi

if [ -n "$SIGN_SHA" ]; then
  echo "==> 自己署名証明書で署名: $SIGN_IDENTITY ($SIGN_SHA)"
  SIGN_ARG="$SIGN_SHA"
else
  echo "==> ad-hoc 署名"
  SIGN_ARG="-"
fi

# --options runtime はTeam ID不一致でPython frameworkを拒否するため使わない。
# 内部のフレームワーク群を先に再署名 → 最後に .app 自体を署名（順序が重要）
echo "==> 内部フレームワーク・dylib を再署名"
find "$APP_DIR/Contents" \( -name "*.dylib" -o -name "*.so" -o -name "Python" \) \
  -type f 2>/dev/null | while read -r f; do
  codesign --force --sign "$SIGN_ARG" $KEYCHAIN_ARG "$f" 2>/dev/null || true
done

echo "==> .app 全体を deep 署名"
codesign --force --deep --sign "$SIGN_ARG" $KEYCHAIN_ARG \
  --entitlements /dev/stdin \
  "$APP_DIR" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.automation.apple-events</key>
    <true/>
    <key>com.apple.security.device.screen-capture</key>
    <true/>
</dict>
</plist>
PLIST

# 配布用 ZIP 作成
echo "==> 配布用ZIP作成"
cd dist
ditto -c -k --sequesterRsrc --keepParent "Kindle OCR.app" "Kindle OCR.zip"
cd ..

echo ""
echo "======================================================================"
echo "✅ ビルド完了"
echo "======================================================================"
echo ""
echo "出力ファイル:"
echo "  - $SCRIPT_DIR/dist/Kindle OCR.app    （単体配布可能）"
echo "  - $SCRIPT_DIR/dist/Kindle OCR.zip    （配布用、解凍してダブルクリック）"
echo ""
ZIP_SIZE=$(du -sh "dist/Kindle OCR.zip" | awk '{print $1}')
APP_SIZE=$(du -sh "dist/Kindle OCR.app" | awk '{print $1}')
echo "サイズ:"
echo "  - .app:  $APP_SIZE"
echo "  - .zip:  $ZIP_SIZE"
echo ""
echo "配布相手への案内文:"
echo "  「KindleOCR.zip をダウンロード→解凍→Kindle OCR.app をダブルクリック」"
echo "  「初回起動時、開発元未確認の警告が出たら 右クリック→開く→開く」"
echo "  「アクセシビリティ・画面収録の許可ポップアップが出たら 許可」"
