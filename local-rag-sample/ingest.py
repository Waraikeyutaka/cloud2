# 文書を読み込んで分割し、埋め込みを作って vector_store.json に保存する
import glob
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY", "sk-or-xxxx")  # .env がないとき用
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

EMBED_MODEL = "example/embedding-model"
CHUNK_SIZE = 500


def split(text):
    return [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]


def main():
    records = []
    for path in glob.glob("docs/*.txt"):
        text = open(path, encoding="utf-8").read()
        for chunk in split(text):
            vec = client.embeddings.create(model=EMBED_MODEL, input=chunk).data[0].embedding
            records.append({"source": path, "text": chunk, "embedding": vec})
            print("embedded:", path)
    with open("vector_store.json", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)
    print("done:", len(records), "chunks")


main()
