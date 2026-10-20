#!/bin/sh
# モックLLM に、わざと誤った出力を返させる（コマ8）
#   使い方: sh lesson08/set-mock-fault.sh none|invalid_once|always_invalid
#     none           : 正しい JSON を返す（既定）
#     invalid_once   : 1回目だけ、決まりに合わない値を返す
#     always_invalid : 毎回、JSON ではない文を返す
#   アプリ設定を変えるとアプリが再起動する。1分ほど待ってから確かめる。
set -e
case "$1" in
  none|invalid_once|always_invalid) ;;
  *) echo "使い方: sh lesson08/set-mock-fault.sh none|invalid_once|always_invalid" >&2; exit 1 ;;
esac
eval "$(azd env get-values)"
az functionapp config appsettings set \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_FUNCTION_NAME" \
  --settings "MOCK_FAULT=$1" \
  --output none
echo "MOCK_FAULT を $1 にした。1分ほど待ってから確かめる。"
