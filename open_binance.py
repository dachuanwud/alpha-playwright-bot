"""
在端口 9222 的 Chrome 中打开 Binance 页面
"""
from playwright.sync_api import sync_playwright
import requests

port = 9222

try:
    # 获取 Chrome 的 websocket 调试地址
    version_info = requests.get(f'http://localhost:{port}/json/version').json()
    ws_url = version_info['webSocketDebuggerUrl']
    
    print(f"✅ 连接到 Chrome (端口: {port})")
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(ws_url)
        
        # 打开新页面
        page = browser.new_page()
        page.goto("https://www.binance.com/zh-CN/trade/BTC_USDT")
        
        print("✅ 已打开 Binance 交易页面")
        print("   URL: https://www.binance.com/zh-CN/trade/BTC_USDT")
        print()
        print("💡 提示：")
        print("   1. 如果未登录，请先登录 jialin 账号")
        print("   2. 登录后可以切换到其他交易对")
        print("   3. 保持页面打开，然后运行交易脚本")
        
except Exception as e:
    print(f"❌ 错误: {e}")

