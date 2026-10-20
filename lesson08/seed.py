"""架空の問い合わせ（sample_inquiries.json）を、API に登録する（コマ8）

使い方（azd up の後に、Codespace のターミナルで）
  eval "$(azd env get-values)"
  python lesson08/seed.py

API_BASE_URL（azd の環境の値）に、POST /api/inquiries で1件ずつ送る。LLM は呼ばない。
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

base = os.environ.get("API_BASE_URL")
if not base:
    sys.exit('API_BASE_URL がない。先に eval "$(azd env get-values)" を実行する。')

items = json.loads(Path(__file__).with_name("sample_inquiries.json").read_text(encoding="utf-8"))
for item in items:
    request = urllib.request.Request(
        f"{base}/api/inquiries",
        data=json.dumps(item, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        print(response.status, item["title"])
print(f"{len(items)} 件を登録した。")
