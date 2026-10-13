"""環境変数 OPENROUTER_API_KEY の「指紋」を表示する（コマ6）

キーの値は表示しない。値から計算した SHA-256 の先頭8文字だけを表示する。
API の /api/ai/config-check が返す fingerprint と比べて、
Key Vault に入れた値がアプリに届いているかを確かめるのに使う。
"""

import hashlib
import os
import sys

value = os.environ.get("OPENROUTER_API_KEY", "")
if not value:
    sys.exit("環境変数 OPENROUTER_API_KEY がない（Codespaces のシークレットを確かめる）")
print(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8])
