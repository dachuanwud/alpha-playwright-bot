from playwright.sync_api import sync_playwright
import json, requests

port = 9222

def connect_existing_chrome(port=port):
    # 获取 Chrome 的 websocket 调试地址
    version_info = requests.get(f'http://localhost:{port}/json/version').json()
    ws_url = version_info['webSocketDebuggerUrl']

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(ws_url)
        page = browser.contexts[0].pages[0] if browser.contexts[0].pages else browser.new_page()
        page.goto("https://www.binance.com/zh-CN/my/sub-account/asset-management")
        print("✅ 已打开 binance")

        browser.close()

connect_existing_chrome()

