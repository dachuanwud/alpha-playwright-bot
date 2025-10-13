import threading
import time
from playwright.sync_api import sync_playwright
from config import *
from func import *

# 全局暂停控制
pause_event = threading.Event()
pause_event.set()  # 默认主程序可以运行

# ---------------------------
# 独立监控验证码
# ---------------------------
def monitor_verification(page, check_interval=2):
    """独立线程监控币安身份验证器，并控制主程序暂停/恢复"""
    print("👁️ 启动独立验证码监控线程...")

    while True:
        try:
            time.sleep(0.5)

            # 检测验证器是否存在（Shadow DOM 检测）
            found_verification = page.evaluate("""
                () => {
                    try {
                        const shadowHost = document.querySelector("#mfa-shadow-host");
                        if (!shadowHost || !shadowHost.shadowRoot) return false;

                        const target = shadowHost.shadowRoot.querySelector(
                            "div > div > div > div > div > div.height-container > div > div > div.mfa-verify-page > div.bn-formItem.web > div"
                        );

                        return target !== null;
                    } catch (err) {
                        return false;
                    }
                }
            """)

            if found_verification:
                print("⚠️ 检测到币安身份验证器弹窗 → 暂停主程序")
                pause_event.clear()  # 暂停
            else:
                if not pause_event.is_set():
                    print("✅ 验证通过 → 恢复主程序")
                    pause_event.set()

        except Exception as e:
            print(f"⚠️ 监控异常: {e}")

        time.sleep(check_interval)

# ---------------------------
# 主程序
# ---------------------------
def main_program():
    count = 0
    while True:
        pause_event.wait()  # 阻塞直到允许执行
        count += 1
        print(f"▶️ 主程序运行中... 第 {count} 次循环")
        time.sleep(3)  # 模拟工作

# ---------------------------
# 启动同步程序
# ---------------------------
if __name__ == "__main__":
    get_url_count = 0
    target_url = None

    while True:
        get_url_count += 1
        print("🔍 当前页面 URL:", get_current_page_url(port) + "\n")
        target_url = get_current_page_url(port=port)

        if "devtools" in target_url:
            print("❌ URL 是 devtools , 重新获取")
            time.sleep(10)
        else:
            print("✅ URL 不包含 devtools , 成功获取页面\n")
            break

        if get_url_count >= 10:
            print("🚫 尝试十次未获取到网页，程序停止")
            exit()

    # 连接控制
    p, browser, page = init_browser(port=9222, target_url_contains=target_url)
    if not page:
        exit()
    page.set_default_timeout(5000)

    cnt = 0
    while True:
        cnt = cnt + 1
        print(cnt)
        monitor_verification(page, check_interval=2)

