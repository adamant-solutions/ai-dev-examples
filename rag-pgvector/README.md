# Minimal RAG with PostgreSQL + pgvector and a local model (Python)

Article: https://tools.adamant-solutions.com/blog/rag-postgres-pgvector/

- `rag.py`: chunking, embeddings from Ollama's `POST /api/embed`, storage in a `vector(n)` column with an HNSW index (`vector_cosine_ops`), search with the `<=>` cosine distance operator, a distance cut-off, and the answer from Ollama's `POST /api/chat` with numbered sources.
- `demo.py`: indexes `docs/` and answers a question with real local models.
- `test_rag.py`: runs against a real PostgreSQL + pgvector, but with deterministic fake embeddings and a fake Ollama server, so it needs no model and no API key.

Versions checked on 2026-10-31: psycopg 3.3.6 and pgvector (Python) 0.5.1 on PyPI; Docker image `pgvector/pgvector:0.8.7-pg18` (pgvector 0.8.7, PostgreSQL 18); Ollama 0.40.5 with `mxbai-embed-large` (1024 dimensions, 512-token context) and `llama3.2:1b`.

```bash
docker run -d --name pgvector -e POSTGRES_PASSWORD=postgres -p 5432:5432 pgvector/pgvector:0.8.7-pg18
pip install -r requirements.txt
python -m unittest -v                      # fake embeddings, no model needed

ollama pull mxbai-embed-large && ollama pull llama3.2:1b
python demo.py "How long do customers have to ask for a refund?"
```

`DATABASE_URL` overrides the default `postgresql://postgres:postgres@localhost:5432/postgres`.
The distance cut-off (`max_distance=0.5`) was chosen by looking at `mxbai-embed-large` on the sample documents: measure it again for your model and your data.
