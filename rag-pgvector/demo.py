"""Index the files in docs/ and answer a question with a local Ollama model.

    python demo.py "How long do customers have to ask for a refund?"
"""
import os
import pathlib
import sys

import rag

DSN = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "How long do customers have to ask for a refund?"
    embed = rag.ollama_embedder()
    conn = rag.connect(DSN)
    rag.create_schema(conn, dim=1024)
    for path in sorted(pathlib.Path(__file__).with_name("docs").glob("*.md")):
        rag.index_document(conn, path.name, path.read_text(encoding="utf-8"), embed)
    result = rag.ask(conn, question, embed, query_prefix=rag.MXBAI_QUERY_PREFIX)
    print(result["answer"])
    print("sources:", ", ".join(result["sources"]))
