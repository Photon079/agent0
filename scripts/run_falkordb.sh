#!/usr/bin/env bash
set -euo pipefail

echo "Starting FalkorDB docker container (career-graph-db)..."
docker run -d -p 6379:6379 --name career-graph-db \
  -e REDIS_ARGS="--requirepass HackathonSecret2026" \
  falkordb/falkordb:latest

echo "FalkorDB container started."
echo
echo "Clean up later with:  docker rm -f career-graph-db"