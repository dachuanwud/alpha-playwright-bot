import threading
import time
from playwright.sync_api import sync_playwright
from config import *
from func import *

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
def input_verification_code(page, code):
    """模拟鼠标点击并输入验证码"""
    try:
        found = page.evaluate("""
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
        if not found:
            print("❌ 没有找到验证输入框")
            return False

        # 点击输入框
        page.evaluate("""
            () => {
                const shadowHost = document.querySelector("#mfa-shadow-host");
                const inputEl = shadowHost.shadowRoot.querySelector(
                    'input[data-e2e="input-mfa"]'
                );
                if (inputEl) inputEl.focus();
            }
        """)
        time.sleep(0.5)

        # 模拟键盘输入
        page.keyboard.type(code, delay=0.1)  # 每个字符延迟 0.1 秒
        print(f"✅ 已输入验证码: {code}")
        return True

    except Exception as e:
        print(f"⚠️ 输入验证码失败: {e}")
        return False


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

    input_verification_code(page, get_google_code(secret))

