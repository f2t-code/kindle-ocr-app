#!/usr/bin/env bash
# Mac .app バンドル生成スクリプト
# 生成された .app をダブルクリックで起動すると、macOS が
# Accessibility/Screen Recording の許可ポップアップを正しく表示する。
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="Kindle OCR"
BUNDLE_ID="net.f2t.kindle-ocr"
APP_DIR="$SCRIPT_DIR/$APP_NAME.app"

echo "==> .app バンドルを生成: $APP_DIR"

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# ========== Info.plist ==========
# NSAppleEventsUsageDescription: AppleScript経由のKindle操作で必要
# NSScreenCaptureUsageDescription: スクリーンキャプチャで必要
# LSUIElement=false: 通常のアプリとしてDock表示
cat > "$APP_DIR/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIdentifier</key>
    <string>$BUNDLE_ID</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleVersion</key>
    <string>0.1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>LSUIElement</key>
    <false/>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSAppleEventsUsageDescription</key>
    <string>Kindleアプリを最前面に切り替え、ページ送りキーを送信するために使用します。</string>
    <key>NSScreenCaptureUsageDescription</key>
    <string>Kindleで表示中の本のページをスクリーンショットで取得します。</string>
    <key>NSAccessibilityUsageDescription</key>
    <string>Kindleアプリへのキーボード入力（ページ送り）に必要です。</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
</dict>
</plist>
EOF

# ========== アイコン埋め込み ==========
ICON_SRC="$SCRIPT_DIR/icon_build/AppIcon.icns"
if [ -f "$ICON_SRC" ]; then
  cp "$ICON_SRC" "$APP_DIR/Contents/Resources/AppIcon.icns"
  echo "==> アイコンを埋め込み: AppIcon.icns"
else
  echo "==> ⚠️ アイコン未生成: $ICON_SRC が無いためデフォルトアイコン使用"
  echo "    （python3 scripts/generate_icon.py && iconutil -c icns icon_build/AppIcon.iconset -o icon_build/AppIcon.icns で生成）"
fi

# ========== launcher (起動スクリプト) ==========
# venv の Python を呼んで app.py を起動
# ========== ネイティブランチャー (C) ==========
# bashだとプロセスチェーンが分断されてTCCの「責任プロセス」追跡が崩れる場合がある。
# Cで書いた小さなMach-Oバイナリにし、execvで直接Pythonに置き換える。
LAUNCHER_C="$APP_DIR/Contents/Resources/launcher.c"
cat > "$LAUNCHER_C" <<'EOF'
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <libgen.h>
#include <mach-o/dyld.h>

int main(int argc, char *argv[]) {
    char exe_path[1024];
    uint32_t size = sizeof(exe_path);
    if (_NSGetExecutablePath(exe_path, &size) != 0) {
        fprintf(stderr, "Cannot resolve executable path\n");
        return 1;
    }

    // dirname を破壊するので別バッファに
    char buf[1024];
    strncpy(buf, exe_path, sizeof(buf));
    char *macos_dir = dirname(buf);          // .app/Contents/MacOS
    char contents_dir[1024];
    strncpy(contents_dir, macos_dir, sizeof(contents_dir));
    char *contents = dirname(contents_dir);  // .app/Contents
    char app_dir[1024];
    strncpy(app_dir, contents, sizeof(app_dir));
    char *app = dirname(app_dir);            // .app
    char project_dir[1024];
    strncpy(project_dir, app, sizeof(project_dir));
    char *project = dirname(project_dir);    // .app の親 = プロジェクト

    char venv_python[2048], app_script[2048];
    snprintf(venv_python, sizeof(venv_python), "%s/venv/bin/python3", project);
    snprintf(app_script, sizeof(app_script), "%s/app.py", project);

    if (access(venv_python, X_OK) != 0) {
        system("osascript -e 'display alert \"Kindle OCR\" message \"venv が見つかりません。\\n\\nまず install_mac.sh を実行してください。\"'");
        return 1;
    }

    if (chdir(project) != 0) {
        fprintf(stderr, "chdir failed: %s\n", project);
        return 1;
    }

    unsetenv("PYTHONHOME");
    unsetenv("PYTHONPATH");
    setenv("PYTHONNOUSERSITE", "1", 1);
    setenv("KINDLE_OCR_FROM_BUNDLE", "1", 1);

    char *new_argv[] = { venv_python, app_script, NULL };
    execv(venv_python, new_argv);
    perror("execv failed");
    return 1;
}
EOF

echo "==> Cランチャーをコンパイル"
xcrun clang -O2 -arch arm64 \
  -o "$APP_DIR/Contents/MacOS/launcher" \
  "$LAUNCHER_C"
rm "$LAUNCHER_C"

chmod +x "$APP_DIR/Contents/MacOS/launcher"

# ========== アイコン（任意・なくてもOK） ==========
# Resources/AppIcon.icns があればそれを使う。なくてもデフォルトアイコンで動く。

# ========== Gatekeeper attribute をクリア ==========
xattr -cr "$APP_DIR" 2>/dev/null || true

# ========== コード署名 ==========
# 専用キーチェーンに自己署名証明書があればそれで署名（再ビルド後も同じ署名 → TCC許可維持）。
# 無ければ ad-hoc (-) フォールバック。
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
  echo "==> 自己署名証明書未作成 → ad-hoc 署名（権限が再ビルド毎にリセットされる可能性）"
  echo "    永続化するには: bash scripts/setup_signing_cert.sh"
  SIGN_ARG="-"
fi

codesign --force --deep --sign "$SIGN_ARG" $KEYCHAIN_ARG \
  --options runtime \
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

# ========== TCC 既存エントリのリセット（オプション） ==========
# 環境変数 RESET_TCC=1 が指定された時だけリセット。
# 通常ビルドではユーザーが既に許可した権限を維持する。
if [ "${RESET_TCC:-0}" = "1" ]; then
  echo "==> TCC許可情報をリセット（RESET_TCC=1）"
  tccutil reset Accessibility "$BUNDLE_ID" 2>/dev/null || true
  tccutil reset AppleEvents "$BUNDLE_ID" 2>/dev/null || true
  tccutil reset ScreenCapture "$BUNDLE_ID" 2>/dev/null || true
  tccutil reset SystemPolicyAllFiles "$BUNDLE_ID" 2>/dev/null || true
fi

echo "==> 完了: $APP_DIR"
echo ""
echo "起動方法:"
echo "  1. Finder で「$APP_DIR」をダブルクリック"
echo "  2. 初回起動時、'開発元が未確認' 警告が出たら:"
echo "     右クリック → 開く → 開く"
echo "  3. アプリ起動後、最初のキャプチャ実行時に macOS が"
echo "     「キーボード操作」「画面収録」の許可ポップアップを表示"
echo "  4. それぞれ「許可」をクリック"
echo ""
echo "もしポップアップが出ない場合:"
echo "  → アプリを ⌘Q で完全終了し、もう一度ダブルクリックして再起動"
