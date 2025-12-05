"""
重新启动端口 9222 的 Chrome 浏览器（确保窗口可见）
"""
import subprocess
import time
import os
import requests
from pathlib import Path

port = 9222
chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
user_data_dir = f"D:\\tmp\\cdp{port}"

def kill_chrome_on_port(port):
    """关闭指定端口的 Chrome 进程"""
    try:
        # 获取监听该端口的进程
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        print(f"找到进程 PID: {pid}")
                        try:
                            subprocess.run(f'taskkill /F /PID {pid}', shell=True, check=False)
                            print(f"✅ 已关闭进程 {pid}")
                        except:
                            pass
    except Exception as e:
        print(f"关闭进程时出错: {e}")

def start_chrome_window():
    """启动 Chrome 窗口"""
    # 确保用户数据目录存在
    os.makedirs(user_data_dir, exist_ok=True)
    
    # 构建启动命令
    args = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://www.binance.com/zh-CN/trade/BTC_USDT"
    ]
    
    print("=" * 60)
    print("重新启动 Chrome 浏览器（端口 9222）")
    print("=" * 60)
    print(f"Chrome 路径: {chrome_path}")
    print(f"端口: {port}")
    print(f"用户数据目录: {user_data_dir}")
    print()
    
    # 先尝试关闭现有进程
    print("1. 检查并关闭现有 Chrome 进程...")
    kill_chrome_on_port(port)
    time.sleep(2)
    
    # 启动新的 Chrome
    print("\n2. 启动新的 Chrome 窗口...")
    try:
        # 使用 subprocess.Popen 启动，不使用 CREATE_NO_WINDOW，确保窗口可见
        process = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"✅ Chrome 进程已启动 (PID: {process.pid})")
        
        # 等待启动
        print("\n3. 等待 Chrome 启动...")
        for i in range(10):
            time.sleep(1)
            try:
                response = requests.get(f'http://localhost:{port}/json/version', timeout=1)
                if response.status_code == 200:
                    print("✅ Chrome CDP 已就绪！")
                    print("\n" + "=" * 60)
                    print("✅ 浏览器窗口应该已经打开")
                    print("=" * 60)
                    print("\n📋 接下来的步骤：")
                    print("   1. 检查浏览器窗口是否已打开")
                    print("   2. 如果未登录，请登录 jialin 账号")
                    print("   3. 切换到要交易的代币页面")
                    print("   4. 运行: python main.py --account jialin")
                    return True
            except:
                print(f"   等待中... ({i+1}/10)")
        
        print("⚠️ Chrome 可能还在启动中，请检查浏览器窗口")
        return False
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return False

if __name__ == "__main__":
    if not os.path.exists(chrome_path):
        print(f"❌ Chrome 路径不存在: {chrome_path}")
        print("   请检查 Chrome 是否已安装")
    else:
        start_chrome_window()

