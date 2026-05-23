# GitHub 連携セットアップ

f2t-code（info@f2t.jp）アカウントで自動ビルドを動かす手順。

## 1. GitHub にリポジトリ作成

ブラウザで https://github.com/new にアクセス（f2t-code でログイン状態で）:

- Repository name: `kindle-ocr-app`
- 公開設定: **Private** 推奨（コードを公開したくないなら）/ Public（無制限ビルド希望なら）
- Initialize this repository: **チェックしない**（ローカルから push するので）
- 「Create repository」

## 2. ローカルから push

このフォルダ（`~/dev/kindle-ocr-app/`）で:

```bash
cd ~/dev/kindle-ocr-app

# Git identity を f2t-code に切替（情報源: rules/git-identity.md）
git init -b main
git config user.email "info@f2t.jp"
git config user.name "f2t-code"

# 不要ファイルを除外（.gitignore 適用済み）
git add .
git commit -m "Initial commit: Kindle OCR App"

# GitHub の f2t-code/kindle-ocr-app に紐付け
git remote add origin git@github.com:f2t-code/kindle-ocr-app.git

# push（gh auth switch が必要な場合あり）
gh auth switch -u f2t-code  # tomo3131 アカウントから切替
git push -u origin main
```

## 3. GitHub Actions の起動

push すると自動でビルドが走ります:

1. https://github.com/f2t-code/kindle-ocr-app/actions にアクセス
2. 「Build Kindle OCR」ワークフローが実行中（数分〜10分）
3. 完了したらアーティファクト（ビルド成果物）をダウンロード可能

## 4. 配布版を取得する2つの方法

### 方法A: 手動実行 → アーティファクト DL
1. Actions タブ → 「Build Kindle OCR」 → 「Run workflow」
2. 数分後、ワークフロー実行結果の下部に「Artifacts」がある
3. `KindleOCR-Mac` `KindleOCR-Windows` をダウンロード（ZIP）
4. 解凍するとそれぞれの配布ZIP

### 方法B: タグを切って自動 Release（推奨）
```bash
git tag v0.1.0
git push origin v0.1.0
```
→ GitHub Releases ページに自動で公開されます。
　配布相手に Releases の URL を送るだけでOK。

## 5. 普段のフロー

1. ローカルでコード修正
2. `git add . && git commit -m "..."`
3. `git push`
4. GitHub Actions が自動ビルド
5. （リリース時）`git tag v0.x.y && git push origin v0.x.y`

## トラブルシュート

### git push でパーミッションエラー
- `gh auth switch -u f2t-code` で f2t-code アカウントに切替
- または SSH 鍵を f2t-code の GitHub に登録

### Actions が「No such file」エラー
- `.github/workflows/build.yml` の指定パスが正しいか確認
- スペース入りファイル名は要クォート

### Windows ビルドだけ失敗
- tesseract インストールに時間がかかりタイムアウトする場合あり
- Actions タブで再実行（「Re-run failed jobs」）

### プライベートリポの月2000分制限超え
- Public に変更（無制限になる）
- または有料プランへ
