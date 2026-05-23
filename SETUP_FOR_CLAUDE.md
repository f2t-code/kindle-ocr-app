# Claude Code でセットアップする

このアプリは Claude Code（CLI）に手順を渡せば自動でセットアップできます。

## 最速セットアップ（Claude Code ユーザー向け）

### Mac

Claude Code に以下を貼り付け:

```
https://github.com/f2t-code/kindle-ocr-app/releases/latest から
KindleOCR-Mac.zip をダウンロードして、解凍して、
Kindle OCR.app を /Applications に移動して起動して。
```

または、ソースから動かしたい場合:

```
https://github.com/f2t-code/kindle-ocr-app を ~/dev/ に clone して、
bash install_mac.sh を実行してセットアップして、
bash run_mac.sh で起動して。
```

### Windows

Claude Code（または Cursor）に:

```
https://github.com/f2t-code/kindle-ocr-app/releases/latest から
KindleOCR-Windows.zip をダウンロードして、解凍して、
Kindle OCR.exe を起動して。
```

ソースから動かしたい場合:

```
https://github.com/f2t-code/kindle-ocr-app を C:\dev\ に clone して、
PowerShell で install_windows.ps1 を実行して、
run_windows.ps1 で起動して。
```

## ユーザーが必ずやる作業（自動化不可）

Claude Code はクローンやビルドはできますが、**OS の権限ダイアログはクリックしてもらう必要**があります。

### Mac の場合

1. 初回起動時の「開発元が未確認」ダイアログ:
   - アプリを **右クリック → 開く** で承認
2. 「キーボード入力を求めています」ポップアップ:
   - **「許可」** をクリック
3. 「画面を録画する許可」ポップアップ:
   - **「許可」** をクリック

### Windows の場合

1. SmartScreen 警告:
   - **「詳細情報」→「実行」** をクリック
2. ウイルス対策ソフトが遮断した場合:
   - 除外フォルダに追加（ガイド参照）

## 動作確認

アプリ画面で **「🔧 診断テスト」** をクリック。
全項目 ✅ なら使える状態。

## トラブル時

Claude Code に:

```
~/dev/kindle-ocr-app の Kindle OCR.app で 'ページが進まない' エラーが出る。
診断テストの結果を見て解決策を提案して。
```

と頼めば、Claude Code が診断 → 対処してくれます。

## 補足

このリポは Claude Code を使った AI 駆動開発で実装されています。
コードを改造したい場合、Claude Code に `src/` 配下のファイルを
指して「○○を変更して」と頼めば修正してくれます。
