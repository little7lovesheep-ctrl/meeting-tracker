#!/bin/bash
cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

echo "启动 Meeting Tracker..."
echo ""

# 启动后端
cd backend
.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# 启动前端
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

sleep 4

# 启动 ngrok 隧道
$PROJECT_DIR/ngrok http 5173 --log /tmp/ngrok.log > /dev/null 2>&1 &
NGROK_PID=$!

sleep 4

# 获取公网地址
PUBLIC_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | grep -o '"public_url":"https://[^"]*"' | head -1 | cut -d'"' -f4)

echo ""
echo "=========================================="
echo "✓ 本地访问: http://localhost:5173"
echo "✓ 公网访问: ${PUBLIC_URL}"
echo "=========================================="
echo ""
echo "团队通过公网链接即可访问和编辑"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 写入公网地址供后端生成钉钉链接
echo "${PUBLIC_URL}" > /tmp/meeting-tracker-frontend-url.txt

trap "kill $BACKEND_PID $FRONTEND_PID $NGROK_PID 2>/dev/null; exit" INT TERM
wait
