import os

from dotenv import load_dotenv
from openai import OpenAI

from ingestor import EMBEDDING_MODEL, get_collection

load_dotenv()

TOP_K = 5


def embed_query(query: str) -> list[float]:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=[query])
    return response.data[0].embedding


def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    """Return the top_k most relevant chunks for a query, each with source and score."""
    collection = get_collection()
    if collection.count() == 0:
        return []

    query_embedding = embed_query(query)
    results = collection.query(query_embeddings=[query_embedding], n_results=top_k)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    chunks = []
    for doc, meta, distance in zip(documents, metadatas, distances):
        chunks.append({
            "text": doc,
            "source": meta.get("source"),
            "score": 1 - distance,
        })
    return chunks
