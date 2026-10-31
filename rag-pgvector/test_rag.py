"""Tests without a model and without API keys.

PostgreSQL + pgvector must be reachable at DATABASE_URL (in CI: a pgvector/pgvector service
container). Embeddings come from fake_embedder; Ollama is replaced by a tiny local HTTP server.
"""
import json
import os
import pathlib
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import rag

DSN = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
DOCS = pathlib.Path(__file__).with_name("docs")
DIM = 256  # fake vectors: bag-of-words distances are larger than a real model's, hence max_distance=0.85 below


class FakeOllama(BaseHTTPRequestHandler):
    requests: list = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.requests.append((self.path, body))
        if self.path == "/api/embed":
            out = {"model": body["model"], "embeddings": rag.fake_embedder(DIM)(body["input"])}
        elif self.path == "/api/chat":
            out = {"model": body["model"], "done": True,
                   "message": {"role": "assistant", "content": "Within 30 days [1]."}}
        else:
            self.send_error(404)
            return
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class RagTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = rag.connect(DSN)
        cls.conn.execute("DROP TABLE IF EXISTS chunks")
        rag.create_schema(cls.conn, DIM)
        cls.embed = staticmethod(rag.fake_embedder(DIM))
        for path in sorted(DOCS.glob("*.md")):
            rag.index_document(cls.conn, path.name, path.read_text(encoding="utf-8"), cls.embed)
        cls.server = HTTPServer(("127.0.0.1", 0), FakeOllama)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.conn.execute("DROP TABLE IF EXISTS chunks")
        cls.conn.close()

    def test_chunking_packs_paragraphs(self):
        text = "\n\n".join(["a" * 500, "b" * 500, "c" * 500])
        self.assertEqual([len(c) for c in rag.chunk_text(text, max_chars=1200)], [1002, 500])

    def test_search_finds_the_right_document(self):
        hits = rag.search(self.conn, "How do I get a refund for my purchase?", self.embed, k=2)
        self.assertEqual(hits[0][0], "refunds.md")
        self.assertLessEqual(hits[0][2], hits[1][2])
        hits = rag.search(self.conn, "internal hostnames do not resolve on the VPN", self.embed, k=1)
        self.assertEqual(hits[0][0], "vpn.md")

    def test_reindex_replaces_old_chunks(self):
        before = self.conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
        rag.index_document(self.conn, "oncall.md", (DOCS / "oncall.md").read_text(), self.embed)
        after = self.conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
        self.assertEqual(before, after)

    def test_hnsw_index_exists(self):
        row = self.conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'chunks_embedding_idx'").fetchone()
        self.assertIn("hnsw", row[0])
        self.assertIn("vector_cosine_ops", row[0])

    def test_ollama_client_and_ask(self):
        FakeOllama.requests.clear()
        embed = rag.ollama_embedder(base_url=self.base_url)
        result = rag.ask(self.conn, "refund within how many days?", embed, k=2, max_distance=0.85,
                         base_url=self.base_url)
        self.assertEqual(result["answer"], "Within 30 days [1].")
        self.assertEqual(result["sources"][0], "refunds.md")
        (p1, embed_req), (p2, chat_req) = FakeOllama.requests
        self.assertEqual((p1, embed_req["model"], embed_req["input"]),
                         ("/api/embed", "mxbai-embed-large", ["refund within how many days?"]))
        self.assertEqual((p2, chat_req["stream"]), ("/api/chat", False))
        self.assertIn("Cite them like [1]", chat_req["messages"][0]["content"])
        self.assertIn("[1] (refunds.md)", chat_req["messages"][1]["content"])

    def test_no_relevant_passage_skips_the_model(self):
        FakeOllama.requests.clear()
        result = rag.ask(self.conn, "zebra quantum", self.embed, max_distance=0.85,
                         base_url=self.base_url)
        self.assertEqual(result["sources"], [])
        self.assertEqual(FakeOllama.requests, [])


if __name__ == "__main__":
    unittest.main()
