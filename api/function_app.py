"""問い合わせ管理アプリの API（Azure Functions / Python）

エンドポイント
  GET  /api/health      動作確認
  GET  /api/inquiries   問い合わせの一覧を返す（新しい順）
  POST /api/inquiries   問い合わせを1件登録する  {"title": "...", "body": "..."}
  GET  /api/ai/config-check  OpenRouter のキーが届いているかを確かめる（コマ6。値は返さない）

接続先などの設定は、コードに書かずに「アプリ設定」（環境変数）から読む。
注意: この時点では認証がなく、誰でも読み書きできる（コマ11で認証を加える）。
"""

import datetime
import hashlib
import json
import os
import uuid

import azure.functions as func
from azure.cosmos import CosmosClient

# TODO(コマ6 演習手順4): マネージドIDで接続するため、ここに次の1行を加える
#   from azure.identity import DefaultAzureCredential

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

MAX_TITLE = 100
MAX_BODY = 2000

_container = None


def get_container():
    """Cosmos DB のコンテナーに接続する（最初の1回だけ接続し、以降は使い回す）"""
    global _container
    if _container is None:
        client = CosmosClient(
            os.environ["COSMOS_ENDPOINT"],
            # TODO(コマ6 演習手順4): キーではなくマネージドIDで接続する
            #   次の行を credential=DefaultAzureCredential(), に書き換える
            credential=os.environ["COSMOS_KEY"],
        )
        database = client.get_database_client(os.environ["COSMOS_DATABASE"])
        _container = database.get_container_client(os.environ["COSMOS_CONTAINER"])
    return _container


def json_response(data, status_code=200):
    return func.HttpResponse(
        json.dumps(data, ensure_ascii=False),
        status_code=status_code,
        mimetype="application/json",
    )


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    return json_response({"status": "ok"})


@app.route(route="inquiries", methods=["GET"])
def list_inquiries(req: func.HttpRequest) -> func.HttpResponse:
    query = (
        "SELECT c.id, c.title, c.body, c.status, c.createdAt "
        "FROM c ORDER BY c.createdAt DESC"
    )
    items = list(
        get_container().query_items(query=query, enable_cross_partition_query=True)
    )
    return json_response(items)


@app.route(route="inquiries", methods=["POST"])
def create_inquiry(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = req.get_json()
    except ValueError:
        return json_response({"error": "JSON の形式が正しくない"}, 400)

    title = str(data.get("title", "")).strip()
    body = str(data.get("body", "")).strip()

    # 入力の検証（サーバー側で必ず行う）
    if not title or not body:
        return json_response({"error": "件名と本文は必須である"}, 400)
    if len(title) > MAX_TITLE or len(body) > MAX_BODY:
        return json_response({"error": "件名または本文が長すぎる"}, 400)

    item = {
        "id": str(uuid.uuid4()),
        "title": title,
        "body": body,
        "status": "未対応",
        "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    get_container().create_item(item)
    return json_response(item, 201)


@app.route(route="ai/config-check", methods=["GET"])
def ai_config_check(req: func.HttpRequest) -> func.HttpResponse:
    """OpenRouter のキー（OPENROUTER_API_KEY）がアプリに届いているかを確かめる（コマ6）

    キーの値そのものは絶対に返さない。代わりに、値から計算した「指紋」
    （SHA-256 の先頭8文字）を返す。指紋から元の値は分からないが、
    値が同じか・変わったかは比べられる。
    """
    value = os.environ.get("OPENROUTER_API_KEY", "")
    if not value:
        status = "missing"  # アプリ設定がない
    elif value.startswith("@Microsoft.KeyVault("):
        status = "unresolved"  # Key Vault 参照を解決できず、参照の文字列がそのまま入っている
    elif value.startswith("sk-or-"):
        status = "ok"
    else:
        status = "unexpected-format"

    result = {"status": status}
    if status == "ok":
        result["fingerprint"] = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return json_response(result)
