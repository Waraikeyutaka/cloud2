"""api/classification.py を確かめるテスト（コマ8）

実行のしかた（Codespace のターミナルで。Azure にも OpenRouter にもつながない）
  pip install pytest pydantic
  python -m pytest lesson08/test_classification.py -v

モデルの代わりに、決まった文字列を順に返す「偽物の LLM」（FakeLLM）を使う。
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import classification as c  # noqa: E402

INQUIRY = {"title": "VPN に接続できない", "body": "在宅勤務で VPN がつながらず、業務が止まっている。"}

VALID = {"category": "ネットワーク・VPN", "priority": "高", "summary": "在宅勤務で VPN に接続できない", "needs_human": False}


class FakeLLM:
    """呼ばれるたびに、用意した出力を先頭から1つずつ返す。受け取った messages も記録する"""

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []

    def __call__(self, messages):
        self.calls.append(messages)
        return self.outputs.pop(0)


def as_json(data):
    return json.dumps(data, ensure_ascii=False)


# ---------------------------------------------------------------------
# 演習手順4: 分類の結果の形
# ---------------------------------------------------------------------
def test_正しいJSONを受け付ける():
    result = c.InquiryClassification.model_validate_json(as_json(VALID))
    assert result.priority == "高"
    assert result.summary == VALID["summary"]
    assert result.needs_human is False


def test_決められた値以外の優先度は受け付けない():
    with pytest.raises(ValueError):
        c.InquiryClassification.model_validate_json(as_json({**VALID, "priority": "緊急"}))


def test_項目が足りなければ受け付けない():
    data = dict(VALID)
    del data["needs_human"]
    with pytest.raises(ValueError):
        c.InquiryClassification.model_validate_json(as_json(data))


def test_定義にない項目があれば受け付けない():
    with pytest.raises(ValueError):
        c.InquiryClassification.model_validate_json(as_json({**VALID, "assignee": "社長"}))


def test_長すぎる要約は受け付けない():
    with pytest.raises(ValueError):
        c.InquiryClassification.model_validate_json(as_json({**VALID, "summary": "あ" * 61}))


def test_JSONSchemaにすべての項目が必須として入っている():
    schema = c.json_schema()["schema"]
    assert set(schema["required"]) == {"category", "priority", "summary", "needs_human"}
    assert schema["additionalProperties"] is False


# ---------------------------------------------------------------------
# 演習手順5: JSON の取り出し
# ---------------------------------------------------------------------
def test_JSONだけの出力はそのまま取り出す():
    assert json.loads(c.extract_json(as_json(VALID))) == VALID


def test_コードブロックで囲まれていても取り出す():
    text = "分類結果は次のとおりです。\n```json\n" + as_json(VALID) + "\n```"
    assert json.loads(c.extract_json(text)) == VALID


def test_JSONがなければValueErrorを出す():
    with pytest.raises(ValueError):
        c.extract_json("分類しました。カテゴリはネットワークです。")


# ---------------------------------------------------------------------
# 演習手順6: 再試行と、諦めたときの扱い
# ---------------------------------------------------------------------
def test_1回目で正しければ1回だけ呼ぶ():
    llm = FakeLLM(as_json(VALID))
    result = c.classify(INQUIRY, llm, max_attempts=3)
    assert result.attempts == 1
    assert result.fallback is False
    assert len(llm.calls) == 1


def test_1回目が誤りなら理由を伝えて出し直させる():
    llm = FakeLLM(as_json({**VALID, "priority": "緊急"}), as_json(VALID))
    result = c.classify(INQUIRY, llm, max_attempts=3)
    assert result.attempts == 2
    assert result.classification.priority == "高"
    assert len(result.errors) == 1
    # 2回目に送った messages の最後の2件は、前の出力（assistant）と、出し直しの指示（user）
    second = llm.calls[1]
    assert second[-2]["role"] == "assistant"
    assert second[-1]["role"] == "user"
    assert "priority" in second[-1]["content"]


def test_上限まで失敗したら人に回す():
    llm = FakeLLM("だめ", "だめ", "だめ", "（4回目は呼ばれないはず）")
    result = c.classify(INQUIRY, llm, max_attempts=3)
    assert len(llm.calls) == 3
    assert result.fallback is True
    assert result.classification.needs_human is True
    assert len(result.errors) == 3


# ---------------------------------------------------------------------
# 振り分け（教員が用意した route を確かめる）
# ---------------------------------------------------------------------
def test_担当は振り分け表で決まる():
    result = c.ClassifyResult(c.InquiryClassification.model_validate(VALID), 1)
    assert c.route(result) == {"assignee": "情報システム課", "status": "振り分け済み"}


def test_人が確認すべきものは振り分け担当に回す():
    result = c.ClassifyResult(c.InquiryClassification.model_validate({**VALID, "needs_human": True}), 1)
    assert c.route(result)["status"] == "要確認"
