#!/bin/bash
# 日志查看工具

LOG_DIR="logs"
TODAY=$(date +%Y%m%d)
LOG_FILE="$LOG_DIR/bot_$TODAY.log"
BALANCE_FILE="我是谁.csv"

echo "📋 Alpha Bot 日志查看工具"
echo "================================"
echo ""

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ 日志文件不存在: $LOG_FILE"
    exit 1
fi

case "$1" in
    "tail"|"")
        echo "📌 最新日志（最后 30 行）："
        echo "================================"
        tail -30 "$LOG_FILE"
        ;;
    "follow"|"f")
        echo "📌 实时监控日志（Ctrl+C 退出）："
        echo "================================"
        tail -f "$LOG_FILE"
        ;;
    "error"|"e")
        echo "❌ 错误日志："
        echo "================================"
        grep -i "ERROR\|CRITICAL" "$LOG_FILE" | tail -20
        ;;
    "warning"|"w")
        echo "⚠️  警告日志："
        echo "================================"
        grep -i "WARNING" "$LOG_FILE" | tail -20
        ;;
    "success"|"s")
        echo "✅ 成功操作："
        echo "================================"
        grep -i "SUCCESS\|已点击\|已填写" "$LOG_FILE" | tail -20
        ;;
    "price"|"p")
        echo "💰 价格信息："
        echo "================================"
        grep "当前成交价\|价格数据" "$LOG_FILE" | tail -20
        ;;
    "balance"|"b")
        echo "💵 余额记录："
        echo "================================"
        if [ -f "$BALANCE_FILE" ]; then
            cat "$BALANCE_FILE"
        else
            echo "余额文件不存在"
        fi
        ;;
    "all"|"a")
        echo "📄 完整日志："
        echo "================================"
        cat "$LOG_FILE"
        ;;
    *)
        echo "用法: $0 [选项]"
        echo ""
        echo "选项:"
        echo "  tail/follow   - 查看最新/实时监控日志（默认）"
        echo "  error        - 查看错误日志"
        echo "  warning      - 查看警告日志"
        echo "  success      - 查看成功操作"
        echo "  price        - 查看价格信息"
        echo "  balance      - 查看余额记录"
        echo "  all          - 查看完整日志"
        echo ""
        echo "示例:"
        echo "  $0              # 查看最新日志"
        echo "  $0 follow       # 实时监控"
        echo "  $0 error        # 查看错误"
        echo "  $0 balance       # 查看余额"
        ;;
esac

