#!/usr/bin/env bash
# Mac/Windows 両OS版を1つのZIPにまとめる配布ビルド.
#
# 前提:
#   Mac側: build_pyinstaller_mac.sh が実行済み
#   Win側: Windows実機で build_pyinstaller_windows.ps1 実行済み、
#          できた KindleOCR-Windows.zip を release/Windows/ にコピー済み
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RELEASE_DIR="$SCRIPT_DIR/release"
MAC_DIR="$RELEASE_DIR/Mac"
WIN_DIR="$RELEASE_DIR/Windows"
mkdir -p "$MAC_DIR" "$WIN_DIR"

# ===== Mac版を release/Mac/ にコピー =====
MAC_APP="$SCRIPT_DIR/dist/Kindle OCR.app"
if [ -d "$MAC_APP" ]; then
  echo "==> Mac版をコピー"
  rm -rf "$MAC_DIR/Kindle OCR.app"
  cp -R "$MAC_APP" "$MAC_DIR/"
else
  echo "⚠️  Mac版が無い。先に bash build_pyinstaller_mac.sh を実行してください"
fi

# ===== Windows版の確認 =====
WIN_ZIP="$WIN_DIR/KindleOCR-Windows.zip"
if [ ! -f "$WIN_ZIP" ]; then
  echo "⚠️  Windows版が未配置です。"
  echo "   Windows実機で build_pyinstaller_windows.ps1 を実行し、"
  echo "   生成された dist/KindleOCR-Windows.zip を以下に置いてください:"
  echo "   $WIN_ZIP"
fi

# ===== ユーザー向け README =====
cat > "$RELEASE_DIR/README.txt" <<'EOF'
======================================================================
Kindle OCR App
Kindleで買った本を、検索可能なPDFとMarkdownファイルに変換するツール
======================================================================

【お使いのOSに合わせてご利用ください】

■ Mac の方
  1. "Mac" フォルダを開く
  2. "Kindle OCR.app" をダブルクリック
  3. （初回のみ）「開発元が未確認」警告が出たら、
     アプリアイコンを 右クリック → 開く → 開く
  4. （初回のみ）macOSが「アクセシビリティ」「画面収録」の許可を
     聞いてきたら 許可

■ Windows の方
  1. "Windows" フォルダ内の "KindleOCR-Windows.zip" を解凍
  2. 解凍されたフォルダ内の "Kindle OCR.exe" をダブルクリック
  3. （初回のみ）SmartScreen警告が出たら、
     詳細情報 → 実行 をクリック
  4. ウイルス対策ソフトが遮断する場合は除外設定が必要

【使い方】

1. お読みになりたい本を Kindle アプリで開く
   （見開き表示はOFF、最初のページを表示）
2. このアプリを起動
3. 「📐 範囲を選ぶ」で本文だけドラッグ選択
4. 「実行する」をクリック
5. デスクトップに 検索可能PDF と Markdownファイル が出来上がる

【注意】
- 個人で読むためだけにご利用ください
- 配布・共有・転載は著作権法違反です
- 自己責任でご利用ください

問い合わせ: （あなたの連絡先）
EOF

# ===== 最終ZIPを作成 =====
echo "==> 統合ZIP作成"
cd "$RELEASE_DIR"
ZIP_NAME="KindleOCR_v0.1.0.zip"
rm -f "$ZIP_NAME"
zip -ry "$ZIP_NAME" Mac Windows README.txt -x "*.DS_Store"

cd ..
SIZE=$(du -sh "$RELEASE_DIR/$ZIP_NAME" | awk '{print $1}')

echo ""
echo "======================================================================"
echo "✅ 配布用ZIP完成"
echo "======================================================================"
echo ""
echo "ファイル: $RELEASE_DIR/$ZIP_NAME"
echo "サイズ:   $SIZE"
echo ""
echo "中身:"
echo "  ├ Mac/"
echo "  │  └ Kindle OCR.app"
echo "  ├ Windows/"
echo "  │  └ KindleOCR-Windows.zip"
echo "  └ README.txt"
echo ""
echo "このZIPを5人に配布: メール添付 / Google Drive / Dropbox など"
