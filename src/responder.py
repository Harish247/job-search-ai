import os

from dotenv import load_dotenv
from openai import OpenAI

from retriever import TOP_K, retrieve

load_dotenv()

MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are a helpful assistant that answers questions using only the provided context.
If the context does not contain enough information to answer, say so clearly instead of guessing.
Cite the sources you used by their bracketed number, e.g. [1]."""


def _build_prompt(query: str, chunks: list[dict]) -> str:
    context = "\n\n".join(
        f"[{i}] Source: {chunk['source']}\n{chunk['text']}"
        for i, chunk in enumerate(chunks, start=1)
    )
    return f"""Context:
{context}

Question: {query}

Answer the question using only the context above, citing sources by their bracketed number."""


def answer(query: str, top_k: int = TOP_K) -> dict:
    """Retrieve relevant chunks and generate a grounded answer with source citations."""
    chunks = retrieve(query, top_k=top_k)

    if not chunks:
        return {
            "answer": "No relevant documents found. Try ingesting some documents first.",
            "sources": [],
            "chunks": [],
        }

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(query, chunks)},
        ],
        temperature=0,
    )

    sources = sorted({chunk["source"] for chunk in chunks if chunk.get("source")})

    return {
        "answer": response.choices[0].message.content,
        "sources": sources,
        "chunks": chunks,
    }
