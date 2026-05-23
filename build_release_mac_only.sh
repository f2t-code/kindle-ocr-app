#!/usr/bin/env bash
# Macユーザー専用の配布ZIPを作成（README付き）.
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MAC_APP="$SCRIPT_DIR/dist/Kindle OCR.app"
if [ ! -d "$MAC_APP" ]; then
  echo "❌ Mac版が無い。先に bash build_pyinstaller_mac.sh を実行してください"
  exit 1
fi

RELEASE_DIR="$SCRIPT_DIR/release_mac"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

# .app をコピー
echo "==> Mac.appをコピー"
cp -R "$MAC_APP" "$RELEASE_DIR/"

# README
cat > "$RELEASE_DIR/はじめに必ずお読みください.txt" <<'EOF'
======================================================================
Kindle OCR App
Kindleで買った本を、検索可能なPDFとMarkdownファイルに変換するツール
======================================================================

【使い方】

▼ ステップ1: 初回起動

1. 「Kindle OCR.app」をダブルクリック
2. （初回のみ）「開発元が未確認のため開けません」と出たら:
   - アプリアイコンを 右クリック → 開く
   - 警告ダイアログで もう一度「開く」をクリック
3. macOSが以下の許可を求めてきたら、すべて「許可」をクリック:
   - 「アクセシビリティ」（ページ送りキー送信のため）
   - 「画面収録」（Kindleページのスクショ撮影のため）

▼ ステップ2: 本を読みやすい形に変換

1. Kindleアプリを起動して、変換したい本を開く
2. 本の1ページ目を表示（見開きOFFにすると精度が上がります）
3. Kindle OCR.app を起動
4. 「📐 範囲を選ぶ」をクリックして、本文だけをマウスで囲む
   （メニューバーやサイドバーは含めないように）
5. 総ページ数、書名を入力
6. 「▶ 実行する」をクリック
7. 自動で変換が始まる（300ページで5〜10分）
8. 完了するとデスクトップに以下のファイルが出来上がります:
   - 書名_OCR.pdf（検索可能なPDF）
   - 書名.md（Markdownテキスト）

【ご利用にあたって】

- 個人で読むためだけにご利用ください
- 配布・共有・転載は著作権法違反です
- 自己責任でご利用ください

【トラブルがあれば】

連絡先: （あなたの連絡先をここに）
EOF

# ZIP作成
echo "==> 配布用ZIP作成"
cd "$RELEASE_DIR"
ditto -c -k --sequesterRsrc --keepParent . "../KindleOCR-Mac.zip"
cd "$SCRIPT_DIR"

SIZE=$(du -sh KindleOCR-Mac.zip | awk '{print $1}')

echo ""
echo "======================================================================"
echo "✅ Macユーザー専用 配布ZIP完成"
echo "======================================================================"
echo ""
echo "ファイル: $SCRIPT_DIR/KindleOCR-Mac.zip"
echo "サイズ:   $SIZE"
echo ""
echo "中身:"
echo "  ├ Kindle OCR.app"
echo "  └ はじめに必ずお読みください.txt"
echo ""
echo "📨 このZIPをMacユーザー5人にメール添付 / Drive / Dropbox等で配布"

rm -rf "$RELEASE_DIR"
