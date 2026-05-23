#!/usr/bin/env bash
# 専用キーチェーンを作成し、自己署名コード署名証明書を入れる.
# パスワードを既知の値で固定するので、codesign がプロンプト無しで使える。
# 冪等。
set -eo pipefail

IDENTITY_NAME="Kindle OCR Self-Signed"
KEYCHAIN_NAME="kindleocr-signing.keychain-db"
KEYCHAIN_PATH="$HOME/Library/Keychains/$KEYCHAIN_NAME"
KEYCHAIN_PASS="kindleocr-build"

# 既存キーチェーン内に有効な証明書があれば終了
if [ -f "$KEYCHAIN_PATH" ] && security find-identity -v -p codesigning "$KEYCHAIN_PATH" 2>/dev/null | grep -q "$IDENTITY_NAME"; then
  echo "✅ 専用キーチェーン内に証明書あり: $IDENTITY_NAME"
  echo "   キーチェーン: $KEYCHAIN_PATH"
  exit 0
fi

# 既存の重複証明書を login.keychain から削除
echo "==> login.keychain の旧証明書をクリーンアップ"
while security delete-identity -c "$IDENTITY_NAME" 2>/dev/null; do :; done
while security delete-certificate -c "$IDENTITY_NAME" 2>/dev/null; do :; done

# 既存の専用キーチェーンを削除（再作成）
if [ -f "$KEYCHAIN_PATH" ]; then
  security delete-keychain "$KEYCHAIN_PATH" 2>/dev/null || true
fi

# 専用キーチェーン作成（既知パスワード）
echo "==> 専用キーチェーン作成: $KEYCHAIN_NAME"
security create-keychain -p "$KEYCHAIN_PASS" "$KEYCHAIN_PATH"
security unlock-keychain -p "$KEYCHAIN_PASS" "$KEYCHAIN_PATH"
security set-keychain-settings "$KEYCHAIN_PATH"  # ロックタイムアウト無効

# サーチリストに追加（codesign が見つけられるように）
EXISTING_KEYCHAINS=$(security list-keychains -d user | sed 's/"//g' | tr -d '\n' | sed "s|$KEYCHAIN_PATH||g")
security list-keychains -d user -s $KEYCHAIN_PATH $EXISTING_KEYCHAINS

echo "==> 自己署名証明書を作成: $IDENTITY_NAME"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cd "$TMP"

# OpenSSL 設定（コード署名用拡張を含む）
cat > openssl.conf <<EOF
[req]
distinguished_name = dn
prompt = no
x509_extensions = v3_req

[dn]
CN = $IDENTITY_NAME
O = Kindle OCR Local Build
C = JP

[v3_req]
keyUsage = critical, digitalSignature
extendedKeyUsage = critical, codeSigning
basicConstraints = critical, CA:FALSE
subjectKeyIdentifier = hash
EOF

# RSA 鍵生成
openssl genrsa -out key.pem 2048 2>/dev/null

# 自己署名 X.509 証明書（10年有効）
openssl req -new -x509 \
  -key key.pem \
  -out cert.pem \
  -days 3650 \
  -config openssl.conf 2>/dev/null

# PKCS#12 (.p12) にエクスポート（パスワード "kindleocr"、legacy 形式で macOS 互換性確保）
CERT_PASS="kindleocr"
openssl pkcs12 -export \
  -legacy \
  -out cert.p12 \
  -inkey key.pem \
  -in cert.pem \
  -name "$IDENTITY_NAME" \
  -password "pass:$CERT_PASS" 2>/dev/null

# 専用キーチェーンにインポート
security import cert.p12 \
  -k "$KEYCHAIN_PATH" \
  -P "$CERT_PASS" \
  -T /usr/bin/codesign \
  -T /usr/bin/security \
  -A 2>&1 | grep -v "ACL" || true

# キーアクセス ACL を partition list で許可（既知パスワードなのでプロンプト無し）
security set-key-partition-list \
  -S apple-tool:,apple:,codesign: \
  -s \
  -k "$KEYCHAIN_PASS" \
  "$KEYCHAIN_PATH" >/dev/null 2>&1 || true

# trust 設定はユーザー認証を要求するため省略（コード署名には不要）

# 確認（trust 設定無しのため -v でなく通常の find-identity を使う）
if security find-identity -p codesigning "$KEYCHAIN_PATH" 2>/dev/null | grep -q "$IDENTITY_NAME"; then
  echo "✅ 署名証明書を作成しました"
  echo "   キーチェーン: $KEYCHAIN_PATH"
  echo "   識別名: $IDENTITY_NAME"
  echo "   注: 自己署名のため trust 未設定だが codesign は動作"
  echo ""
  echo "次回 build_mac_app.sh を実行すると、この証明書で署名されます。"
  echo "一度 macOS で「Kindle OCR」を許可すれば、再ビルド後も維持されます。"
else
  echo "❌ 署名証明書の作成に失敗"
  exit 1
fi
