#!/bin/sh
python3 /app/api_server.py &

# nginx 시작 전 Python API가 준비될 때까지 대기 (최대 30초)
i=0
while [ $i -lt 30 ]; do
  if wget -qO- "http://127.0.0.1:8001/api/reports" >/dev/null 2>&1; then
    break
  fi
  i=$((i+1))
  sleep 1
done

exec nginx -g "daemon off;"
