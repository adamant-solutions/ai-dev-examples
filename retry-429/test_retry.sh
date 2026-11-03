#!/bin/sh
# Runs the three clients against the local 429 test server. Used before publishing the article.
set -e
cd "$(dirname "$0")"
for client in "python3 -c \"import retry; print(retry.post_json('http://127.0.0.1:PORT/v1/chat', {'prompt':'hi'}))\"" \
              "node -e \"import('./retry.mjs').then(async m=>console.log(await m.postJson('http://127.0.0.1:PORT/v1/chat',{prompt:'hi'})))\"" \
              "java RetryClient.java http://127.0.0.1:PORT/v1/chat"; do
  port=$((8300 + $(od -An -N1 -tu1 /dev/urandom | tr -d ' ') % 90))
  python3 fake_server.py $port & pid=$!
  for _ in $(seq 1 50); do python3 -c "import socket;socket.create_connection(('127.0.0.1',$port),0.2)" 2>/dev/null && break; sleep 0.2; done
  out=$(eval "$(echo "$client" | sed "s/PORT/$port/")"); kill $pid; wait $pid 2>/dev/null || true
  echo "$out" | grep -q "attempts" || { echo "FAIL: $client"; exit 1; }
done
echo "all clients OK"
