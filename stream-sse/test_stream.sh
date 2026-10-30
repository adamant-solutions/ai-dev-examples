#!/bin/sh
# Starts a fake Ollama and two copies of the FastAPI app, then runs the browser client (sse-client.js) in Node.
# Needs: pip install -r requirements.txt ; Node.js 18+. No model, no API key.
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
r=$(od -An -N1 -tu1 /dev/urandom | tr -d ' ')
F=$((8400 + r % 50)); A=$((8460 + r % 50)); M=$((8520 + r % 50))
$PY fake_ollama.py $F & p1=$!
OLLAMA_URL=http://127.0.0.1:$F $PY -m uvicorn server:app --port $A --log-level warning & p2=$!
OLLAMA_URL=http://127.0.0.1:$F OLLAMA_MODEL=missing $PY -m uvicorn server:app --port $M --log-level warning & p3=$!
trap 'kill $p1 $p2 $p3 2>/dev/null || true' EXIT
for i in 1 2 3 4 5 6 7 8 9 10; do
  curl -sf http://127.0.0.1:$A/ >/dev/null && curl -sf http://127.0.0.1:$M/ >/dev/null && break; sleep 0.5
done
node test.mjs http://127.0.0.1:$A http://127.0.0.1:$M http://127.0.0.1:$F
