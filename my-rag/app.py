import os

import streamlit as st
from dotenv import load_dotenv

from rag_core import answer, CHAT_MODEL, TOP_K


load_dotenv()


# ページ設定
st.set_page_config(page_title="プロ野球選手検索・比較アプリ",layout="wide")

st.title("⚾ プロ野球選手検索・比較アプリ")
st.caption(
    "NPB（日本野球機構）の公式情報をもとにした選手データから、選手について回答します。"
    "回答は簡潔にし、出典を明示します。"
)


# サイドバー: モデルと検索件数
with st.sidebar:
    st.header("設定")

    model = st.selectbox(
        "生成モデル",
        options=[
            # Nvidia 系
            "nvidia/nemotron-3-super-120b-a12b:free",
            "nvidia/nemotron-nano-9b-v2:free",

            # poolside 系
            "poolside/laguna-m.1:free",
            "poolside/laguna-xs-2.1:free",

            # その他の無料モデル
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "meta-llama/llama-3.3-70b-instruct:free",
        ],
        index=0,
    )

    n_results = st.slider(
        "検索件数 (n_results)",
        min_value=1,
        max_value=10,
        value=TOP_K
    )


# 会話履歴の初期化
if "history" not in st.session_state:
    st.session_state["history"] = []


# 履歴の表示
for msg in st.session_state["history"]:

    with st.chat_message(msg["role"]):

        st.write(msg["content"])

        # AIの回答の場合は出典を表示
        if msg["role"] == "assistant" and "sources" in msg:

            with st.expander(
                f" 出典（NPB公式情報・{len(msg['sources'])} 件）"
            ):

                for i, s in enumerate(
                    msg["sources"],
                    start=1
                ):

                    st.caption(
                        f"[{i}] {s['id']} "
                        f"(distance={s['distance']:.4f})"
                    )

                    st.write(s["document"])


# ユーザー入力
if prompt := st.chat_input("選手について質問してください"):

    # ユーザーの質問を表示
    with st.chat_message("user"):
        st.write(prompt)

    # 会話履歴に追加
    st.session_state["history"].append({
        "role": "user",
        "content": prompt
    })

    # ユーザーが選択したモデルをRAGコアに渡して回答を生成
    with st.spinner("NPBの選手データを検索中..."):

        result = answer(
            prompt,
            history=st.session_state["history"][:-1],
            model=model,
        )

    # AIの回答を表示
    with st.chat_message("assistant"):

        st.write(result["answer"])

        # 出典を表示
        with st.expander(
            f"📚 出典（NPB公式情報・{len(result['sources'])} 件）"
        ):

            for i, s in enumerate(
                result["sources"],
                start=1
            ):

                st.caption(
                    f"[{i}] {s['id']} "
                    f"(distance={s['distance']:.4f})"
                )

                st.write(s["document"])

    # AIの回答を履歴に保存
    st.session_state["history"].append({
        "role": "assistant",
        "content": result["answer"],
        "sources": result["sources"],
    })