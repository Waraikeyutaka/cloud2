#!/bin/sh
# Key Vault 参照を、今すぐ読み直させる（コマ6）
#
# アプリは Key Vault 参照の値をキャッシュしていて、通常は24時間ごとに読み直す。
# アプリの設定を変更すると、アプリが再起動し、すぐに読み直される。
# そこで、読み直した時刻を記録するだけのアプリ設定（SECRETS_REFRESHED_AT）を書き換える。
set -e
eval "$(azd env get-values)"
az functionapp config appsettings set \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_FUNCTION_NAME" \
  --settings "SECRETS_REFRESHED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output none
echo "アプリの設定を変更した。アプリが再起動して Key Vault 参照を読み直す。1分ほど待ってから確かめる。"
