"""Minimal RAG with PostgreSQL + pgvector and a local model served by Ollama.

Article: https://tools.adamant-solutions.com/blog/rag-postgres-pgvector/
"""
import hashlib
import json
import math
import re
import urllib.request
from typing import Callable, Sequence

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

Embedder = Callable[[Sequence[str]], list[list[float]]]

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "mxbai-embed-large"  # 1024 dimensions, 512-token context
CHAT_MODEL = "llama3.2:1b"
# The mxbai-embed-large model card asks for this prefix on search queries (not on documents).
MXBAI_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


# ---------- embeddings ----------

def _post_json(url: str, payload: dict, timeout: float = 120) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res)


def ollama_embedder(model: str = EMBED_MODEL, base_url: str = OLLAMA_URL) -> Embedder:
    """Embeddings from Ollama's POST /api/embed (several texts per request)."""
    def embed(texts: Sequence[str]) -> list[list[float]]:
        return _post_json(f"{base_url}/api/embed", {"model": model, "input": list(texts)})["embeddings"]
    return embed


def fake_embedder(dim: int = 1024) -> Embedder:
    """Deterministic test embeddings: hashed bag of words, normalised to length 1.
    Texts that share words get similar vectors. Good for tests, useless for real meaning."""
    def embed(texts: Sequence[str]) -> list[list[float]]:
        out = []
        for text in texts:
            v = [0.0] * dim
            for word in re.findall(r"\w+", text.lower()):
                h = int.from_bytes(hashlib.sha256(word.encode()).digest()[:8], "big")
                v[h % dim] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm for x in v])
        return out
    return embed


# ---------- chunking ----------

def chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    """Split on blank lines, then pack paragraphs into chunks of at most max_chars.
    A paragraph longer than max_chars becomes a chunk of its own: split it further if
    your embedding model has a small context window."""
    chunks, current = [], ""
    for para in (p.strip() for p in re.split(r"\n\s*\n", text)):
        if not para:
            continue
        if current and len(current) + 2 + len(para) > max_chars:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


# ---------- database ----------

def connect(dsn: str) -> psycopg.Connection:
    conn = psycopg.connect(dsn, autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)  # after CREATE EXTENSION: it looks up the vector type
    return conn


def create_schema(conn: psycopg.Connection, dim: int) -> None:
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS chunks (
            id        bigserial PRIMARY KEY,
            source    text NOT NULL,
            content   text NOT NULL,
            embedding vector({int(dim)}) NOT NULL
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS chunks_embedding_idx "
                 "ON chunks USING hnsw (embedding vector_cosine_ops)")


def index_document(conn: psycopg.Connection, source: str, text: str, embed: Embedder) -> int:
    """Replace the chunks of one document. Returns the number of chunks stored."""
    chunks = chunk_text(text)
    vectors = embed(chunks)
    with conn.transaction():
        conn.execute("DELETE FROM chunks WHERE source = %s", (source,))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks (source, content, embedding) VALUES (%s, %s, %s)",
                [(source, c, Vector(v)) for c, v in zip(chunks, vectors)])
    return len(chunks)


def search(conn: psycopg.Connection, query: str, embed: Embedder, k: int = 4,
           query_prefix: str = "") -> list[tuple[str, str, float]]:
    """The k chunks closest to the query by cosine distance (0 = same direction)."""
    qvec = Vector(embed([query_prefix + query])[0])
    return conn.execute(
        "SELECT source, content, embedding <=> %s AS distance "
        "FROM chunks ORDER BY embedding <=> %s LIMIT %s",
        (qvec, qvec, k)).fetchall()


# ---------- generation ----------

def build_messages(question: str, hits: list[tuple[str, str, float]]) -> list[dict]:
    context = "\n\n".join(f"[{i}] ({src})\n{content}" for i, (src, content, _) in enumerate(hits, 1))
    system = ("Answer using only the numbered context passages. Cite them like [1]. "
              "If the answer is not in the context, say you don't know.")
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}]


def ask(conn, question: str, embed: Embedder, k: int = 4, max_distance: float = 0.5,
        chat_model: str = CHAT_MODEL, base_url: str = OLLAMA_URL, query_prefix: str = "") -> dict:
    hits = [h for h in search(conn, question, embed, k, query_prefix) if h[2] <= max_distance]
    if not hits:
        return {"answer": "I don't know: no relevant passage found.", "sources": []}
    res = _post_json(f"{base_url}/api/chat", {"model": chat_model, "stream": False,
                                              "messages": build_messages(question, hits)})
    return {"answer": res["message"]["content"], "sources": [h[0] for h in hits]}
