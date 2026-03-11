#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"
FRONTEND_ENV_FILE="$FRONTEND_DIR/.env.local"
FRONTEND_ENV_EXAMPLE="$FRONTEND_DIR/.env.example"
BACKEND_ENV_FILE="$BACKEND_DIR/.env"
FRONTEND_PORT="3100"
BACKEND_PORT="8001"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  local exit_code=$?
  trap - INT TERM EXIT

  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi

  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi

  wait "$BACKEND_PID" 2>/dev/null || true
  wait "$FRONTEND_PID" 2>/dev/null || true

  exit "$exit_code"
}

ensure_prerequisites() {
  if [[ ! -x "$BACKEND_VENV_PYTHON" ]]; then
    echo "[error] 找不到 backend/.venv。請先執行：" >&2
    echo "        cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -e \".[dev]\"" >&2
    exit 1
  fi

  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "[error] 找不到 frontend/node_modules。請先執行：" >&2
    echo "        cd frontend && npm install" >&2
    exit 1
  fi

  if [[ ! -f "$BACKEND_ENV_FILE" ]]; then
    echo "[error] 找不到 backend/.env。請先從 backend/.env.example 複製並填入必要設定。" >&2
    exit 1
  fi

  if [[ ! -f "$FRONTEND_ENV_FILE" ]]; then
    if [[ -f "$FRONTEND_ENV_EXAMPLE" ]]; then
      cp "$FRONTEND_ENV_EXAMPLE" "$FRONTEND_ENV_FILE"
      echo "[info] 已建立 frontend/.env.local。"
    else
      echo "[error] 找不到 frontend/.env.local，也沒有 frontend/.env.example 可複製。" >&2
      exit 1
    fi
  fi
}

start_backend() {
  echo "[start] backend -> http://localhost:${BACKEND_PORT}"
  (
    cd "$BACKEND_DIR"
    exec "$BACKEND_VENV_PYTHON" -m uvicorn app.main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT"
  ) &
  BACKEND_PID=$!
}

start_frontend() {
  echo "[start] frontend -> http://localhost:${FRONTEND_PORT}"
  (
    cd "$FRONTEND_DIR"
    exec npm run dev
  ) &
  FRONTEND_PID=$!
}

main() {
  ensure_prerequisites
  trap cleanup INT TERM EXIT

  start_backend
  start_frontend

  echo "[info] 按 Ctrl+C 會一起停止前後端。"
  wait -n "$BACKEND_PID" "$FRONTEND_PID"
}

main "$@"
