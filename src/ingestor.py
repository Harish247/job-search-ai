import hashlib
import json
import os
from pathlib import Path

import chromadb
import tiktoken
from chromadb.config import Settings
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader

load_dotenv()

_ROOT = Path(__file__).parent.parent
CHROMA_PATH = _ROOT / "data" / "chroma"
MANIFEST_PATH = _ROOT / "data" / "ingested_files.json"

COLLECTION_NAME = "documents"
EMBEDDING_MODEL = "text-embedding-3-small"
ENCODING_NAME = "cl100k_base"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
SUPPORTED_SUFFIXES = {".txt", ".pdf"}

_client = None
_collection = None


def get_collection():
    global _client, _collection
    if _collection is None:
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(CHROMA_PATH),
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )
        _collection = _client.get_or_create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
    return _collection


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def _read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def load_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return _read_txt(path)
    if suffix == ".pdf":
        return _read_pdf(path)
    raise ValueError(f"Unsupported file type: {suffix}")


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    encoding = tiktoken.get_encoding(ENCODING_NAME)
    tokens = encoding.encode(text)

    if not tokens:
        return []

    step = chunk_size - overlap
    chunks = []
    start = 0
    while start < len(tokens):
        chunk_tokens = tokens[start : start + chunk_size]
        chunks.append(encoding.decode(chunk_tokens))
        if start + chunk_size >= len(tokens):
            break
        start += step
    return chunks


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=chunks)
    return [item.embedding for item in response.data]


def ingest_file(path: Path, manifest: dict | None = None) -> str:
    """Ingest a single file into ChromaDB. Returns 'ingested' or 'skipped'."""
    own_manifest = manifest is None
    if own_manifest:
        manifest = _load_manifest()

    file_hash = _md5(path)
    if file_hash in manifest:
        return "skipped"

    chunks = chunk_text(load_text(path))

    if chunks:
        embeddings = embed_chunks(chunks)
        collection = get_collection()
        ids = [f"{file_hash}_{i}" for i in range(len(chunks))]
        metadatas = [{"source": path.name, "chunk_index": i} for i in range(len(chunks))]
        collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)

    manifest[file_hash] = path.name
    if own_manifest:
        _save_manifest(manifest)

    return "ingested"


def ingest_path(path: str) -> dict:
    """Ingest a single file or all supported files in a directory (recursively).

    Returns a summary dict with counts and a per-file result list.
    """
    p = Path(path)

    if p.is_dir():
        files = sorted(f for f in p.rglob("*") if f.suffix.lower() in SUPPORTED_SUFFIXES)
    else:
        files = [p]

    manifest = _load_manifest()
    ingested = skipped = failed = 0
    results = []

    for file in files:
        try:
            status = ingest_file(file, manifest=manifest)
        except Exception as e:
            results.append({"file": file.name, "status": "failed", "error": str(e)})
            failed += 1
            continue

        results.append({"file": file.name, "status": status, "error": None})
        if status == "ingested":
            ingested += 1
        else:
            skipped += 1

    _save_manifest(manifest)

    return {"ingested": ingested, "skipped": skipped, "failed": failed, "results": results}
