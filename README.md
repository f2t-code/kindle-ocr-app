# Kindle OCR App

Kindleアプリで表示中の本を自動でスクリーンショット → 1つのPDFに結合 → OCRで検索可能なPDFに変換するMac/Windows両対応のGUIアプリ。

## 主な機能

- **Kindleキャプチャ+OCR+MD タブ**: 総ページ数を指定して「実行」を押すだけで、Kindleキャプチャ → OCR → PDF/MD出力まで自動
- **キャプチャのみタブ**: スクリーンショットだけ実行（OCRなし）
- **OCRのみタブ**: 既存のPDFをOCR化（このアプリ以外で作ったPDFも可）

## ダウンロード（事前ビルド版）

技術知識不要、ダブルクリックで起動できる事前ビルド版:

📥 [最新リリース（Mac/Windows両OS版）](https://github.com/f2t-code/kindle-ocr-app/releases/latest)

- **Mac の方**: `KindleOCR-Mac.zip` （約80MB）
- **Windows の方**: `KindleOCR-Windows.zip` （約300MB）

詳しい初回セットアップ手順: [USER_GUIDE.md](USER_GUIDE.md)

## Claude Code でセットアップしたい場合

Claude Code ユーザーは [SETUP_FOR_CLAUDE.md](SETUP_FOR_CLAUDE.md) を参照してください。Claude に貼り付けるだけのコマンド集があります。

## ソースからセットアップ

### macOS

```bash
cd ~/dev/kindle-ocr-app
bash install_mac.sh
```

初回起動時に **画面収録** と **アクセシビリティ** の権限を要求されるので、システム設定で許可してください。

起動:
```bash
bash run_mac.sh
```

### Windows

```powershell
cd $HOME\dev\kindle-ocr-app
powershell -ExecutionPolicy Bypass -File install_windows.ps1
```

事前にPythonが必要:
- Python 3.10以上（python.org または Microsoft Store）— インストール時「Add Python to PATH」必須

セットアップ中にOCRエンジンを選べます:
- **Yomitoku（推奨）**: 日本語特化・無料・90-95%精度・500MB+モデル自動DL
- **Tesseract**: 80-90%精度・別途UB-Mannheim版インストール必要
- **Google Cloud Vision**（任意）: 95-98%精度・APIキー要・有料

起動:
```powershell
powershell -ExecutionPolicy Bypass -File run_windows.ps1
```

Windows特有の注意:
- macOSと違い**アクセシビリティ権限・画面収録権限は不要**（ダウンロード後すぐ動く）
- ウイルス対策ソフト（Avast/Norton等）が pyautogui を遮断するケースがある → 除外設定
- 最初の起動で「不明な発行元」警告が出たら「詳細情報→実行」

## 使い方（最短ルート）

1. Kindleアプリで読みたい本の1ページ目を開く
2. このアプリを起動 → 「一括実行」タブ
3. 総ページ数を入力（多めでもOK、同一画面検出で自動停止）
4. 書名（出力ファイル名）を入力
5. 「▶ 一括実行」をクリック
6. カウントダウン中にKindleアプリを最前面にする
7. 完了通知が出るまで待機（数百ページなら数十分〜数時間）

## 緊急停止

- マウスを画面左上端に動かす（pyautoguiのfailsafe）
- またはアプリの「停止」ボタン

## ファイル構成

```
kindle-ocr-app/
├── app.py              # GUIエントリー
├── src/
│   ├── kindle_capture.py  # スクショ自動化
│   ├── pdf_builder.py     # PNG→PDF結合
│   └── ocr.py             # ocrmypdf呼び出し
├── requirements.txt    # Python依存
├── install_mac.sh      # Macセットアップ
├── install_windows.ps1 # Winセットアップ
├── run_mac.sh          # Mac起動
└── run_windows.ps1     # Win起動
```

## 必要なシステム依存

| ツール | Mac | Windows |
|---|---|---|
| Python 3.10+ | 標準 or `brew install python` | python.org または MS Store |
| tesseract + jpn データ | `brew install tesseract tesseract-lang` | UB-Mannheim ビルド |
| ghostscript（任意） | `brew install ghostscript` | ghostscript.com |

## トラブルシュート

**Macで「画面が真っ黒なPNG」が保存される**
→ システム設定 → プライバシーとセキュリティ → 画面収録 で Terminal/Python を許可

**WindowsでOCRに失敗する**
→ `tesseract --list-langs` で `jpn` が出るか確認。出なければtesseractインストール時に日本語データを入れ忘れている可能性大

**ページがめくれない**
→ ページ送りキーを `right` 以外（`pagedown` / `space` / `down`）に変更

**同じページを連続キャプチャしてしまう**
→ ページ間隔を 1.5〜2.0秒 に増やす（ページめくりアニメーション待ち）

## 法的な注意

- 私的複製（自分一人で読むため）のみ利用可
- ファイルを他人に渡したり、クラウドで共有することは違法
- 配布、転載、販売は禁止
- 自己責任で利用してください

## ライセンス

私的利用のみ。商用利用・再配布禁止。
