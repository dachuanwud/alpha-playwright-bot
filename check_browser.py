"""检查浏览器状态"""
import requests

port = 9222
try:
    # 获取所有页面
    pages = requests.get(f'http://localhost:{port}/json').json()
    print(f"✅ Chrome 在端口 {port} 运行中")
    print(f"📄 已打开 {len(pages)} 个页面/标签页:\n")
    
    for i, page in enumerate(pages[:10], 1):
        title = page.get('title', '无标题')[:50]
        url = page.get('url', '')[:80]
        print(f"  {i}. {title}")
        print(f"     {url}\n")
    
    if len(pages) > 10:
        print(f"  ... 还有 {len(pages) - 10} 个页面")
        
except Exception as e:
    print(f"❌ 无法连接到端口 {port}: {e}")

