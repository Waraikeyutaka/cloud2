"""api/history.py の trim_history を確かめるテスト（コマ7）

実行のしかた（Codespace のターミナルで。Azure にも OpenRouter にもつながない）
  pip install pytest
  python -m pytest lesson07/test_history.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from history import estimate_tokens, trim_history  # noqa: E402


def msg(role, length):
    """長さ length の本文を持つメッセージを作る（estimate_tokens は length + 4 になる）"""
    return {"role": role, "content": "あ" * length}


def test_予算に収まっていれば何も捨てない():
    messages = [msg("user", 10), msg("assistant", 10), msg("user", 10)]
    assert trim_history(messages, 100) == messages


def test_予算を超えたら古いほうから捨てる():
    # 1件あたり 46 トークン。予算 100 なら、新しい2件（92）だけが残る
    messages = [msg("user", 42), msg("assistant", 42), msg("user", 42)]
    result = trim_history(messages, 100)
    assert result == messages[1:]


def test_古い順のまま返す():
    messages = [msg("user", 1), msg("assistant", 2), msg("user", 3), msg("assistant", 4), msg("user", 5)]
    result = trim_history(messages, 25)
    assert [len(m["content"]) for m in result] == [3, 4, 5]


def test_途中を抜かさない():
    # 新しい順に 10・200・5。200 が収まらなければ、それより古い 5 は小さくても残さない
    messages = [msg("user", 5), msg("assistant", 200), msg("user", 10)]
    result = trim_history(messages, 50)
    assert result == messages[2:]


def test_最新の1件は予算を超えていても残す():
    messages = [msg("user", 10), msg("assistant", 10), msg("user", 500)]
    result = trim_history(messages, 100)
    assert result == messages[2:]


def test_引数のリストを書き換えない():
    messages = [msg("user", 42), msg("assistant", 42), msg("user", 42)]
    copy = list(messages)
    trim_history(messages, 100)
    assert messages == copy


def test_見積りは文字数に4を足したもの():
    assert estimate_tokens(msg("user", 10)) == 14
