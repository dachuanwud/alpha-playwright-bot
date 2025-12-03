#!/bin/bash
# Chrome CDP 启动脚本 (macOS)
# 用法: ./start_chrome.sh [端口号]

PORT=${1:-9222}
USER_DATA_DIR="/tmp/chrome-debug-$PORT"

echo "🚀 启动 Chrome CDP 调试模式"
echo "   端口: $PORT"
echo "   用户数据: $USER_DATA_DIR"

# 检查端口是否已占用
if lsof -i :$PORT > /dev/null 2>&1; then
    echo "⚠️  端口 $PORT 已被占用"
    echo "   可能 Chrome 已在运行，尝试连接..."
    
    # 验证 CDP 是否可用
    if curl -s "http://127.0.0.1:$PORT/json/version" > /dev/null 2>&1; then
        echo "✅ Chrome CDP 已可用"
        exit 0
    else
        echo "❌ 端口被其他程序占用，请更换端口"
        exit 1
    fi
fi

# 启动 Chrome
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=$PORT \
    --user-data-dir="$USER_DATA_DIR" \
    --no-first-run \
    --disable-background-networking \
    --disable-component-update \
    --disable-default-apps \
    --disable-sync \
    "https://www.binance.com/zh-CN/alpha" &

echo "⏳ 等待 Chrome 启动..."
sleep 3

# 验证启动成功
if curl -s "http://127.0.0.1:$PORT/json/version" > /dev/null 2>&1; then
    echo "✅ Chrome CDP 启动成功！"
    echo ""
    echo "📌 下一步："
    echo "   1. 在打开的 Chrome 中登录 Binance"
    echo "   2. 进入要交易的代币页面"
    echo "   3. 运行: python main_new.py"
else
    echo "❌ Chrome 启动失败，请检查日志"
    exit 1
fi

