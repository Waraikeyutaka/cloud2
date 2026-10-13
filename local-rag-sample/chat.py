# 質問に関連する文書を探し、LLM に答えさせる
import json
import os

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY", "sk-or-xxxx")  # .env がないとき用
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

CHAT_MODEL = "example/chat-model:free"
EMBED_MODEL = "example/embedding-model"
TOP_K = 3

store = json.load(open("vector_store.json", encoding="utf-8"))
history = []  # これまでの会話


def search(question):
    q = client.embeddings.create(model=EMBED_MODEL, input=question).data[0].embedding
    scored = []
    for r in store:
        v = np.array(r["embedding"])
        score = np.dot(q, v) / (np.linalg.norm(q) * np.linalg.norm(v))
        scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:TOP_K]]


def answer(question):
    docs = search(question)
    context = "\n".join(d["text"] for d in docs)
    prompt = f"次の資料を参考に質問に答えてください。\n資料:\n{context}\n質問: {question}"
    print("DEBUG prompt:", prompt)
    history.append({"role": "user", "content": prompt})
    res = client.chat.completions.create(model=CHAT_MODEL, messages=history)
    text = res.choices[0].message.content
    history.append({"role": "assistant", "content": text})
    return text


while True:
    q = input("質問> ")
    if q == "exit":
        break
    print(answer(q))
