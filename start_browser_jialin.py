"""
启动 jialin 账号的 Chrome 浏览器（端口 9222）
"""
from config import get_account_config
from browser_manager import start_chrome, is_chrome_running

def main():
    # 获取 jialin 账号配置
    config = get_account_config('jialin')
    if not config:
        print("❌ 未找到 jialin 账号配置")
        return
    
    port = config.browser.port
    chrome_path = config.browser.chrome_path
    user_data_dir = config.browser.user_data_dir or f"D:\\tmp\\cdp{port}"
    
    print("=" * 50)
    print("启动 jialin 账号的 Chrome 浏览器")
    print("=" * 50)
    print(f"端口: {port}")
    print(f"Chrome路径: {chrome_path}")
    print(f"用户数据目录: {user_data_dir}")
    print()
    
    # 检查是否已在运行
    if is_chrome_running(port):
        print(f"✅ Chrome 已在端口 {port} 运行")
        print("   如需重新启动，请先关闭现有浏览器窗口")
    else:
        print("🚀 正在启动 Chrome...")
        result = start_chrome(
            port=port,
            chrome_path=chrome_path,
            user_data_dir=user_data_dir,
            wait_seconds=5
        )
        
        if result:
            print()
            print("=" * 50)
            print("✅ Chrome 启动成功！")
            print("=" * 50)
            print()
            print("📋 接下来的步骤：")
            print("   1. 在 Chrome 中访问 https://www.binance.com")
            print("   2. 登录 jialin 账号")
            print("   3. 打开交易页面（如：https://www.binance.com/zh-CN/trade/BTC_USDT）")
            print("   4. 保持窗口打开（可以最小化）")
            print()
            print("💡 提示：登录后不要关闭 Chrome 窗口，这样下次启动会自动恢复登录状态")
        else:
            print()
            print("❌ Chrome 启动失败，请检查日志")

if __name__ == "__main__":
    main()

