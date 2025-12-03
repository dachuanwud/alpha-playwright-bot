import random
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import os,datetime
import requests
import pandas as pd
import base64
import hmac
import hashlib
import struct
import pyautogui


# ============================================
# 智能等待工具函数
# ============================================

def smart_wait_for_element(page, xpath, timeout=10000, state="visible"):
    """
    智能等待元素出现
    
    Args:
        page: Playwright Page 对象
        xpath: 元素 XPath
        timeout: 超时时间（毫秒）
        state: 等待状态 (visible/attached/hidden)
    
    Returns:
        bool: 元素是否出现
    """
    try:
        locator = page.locator(f"xpath={xpath}")
        locator.wait_for(state=state, timeout=timeout)
        return True
    except PlaywrightTimeout:
        print(f"⚠️ 等待元素超时: {xpath[:50]}...")
        return False
    except Exception as e:
        print(f"⚠️ 等待元素失败: {e}")
        return False


def smart_wait_for_text(page, xpath, expected_text=None, timeout=10000):
    """
    等待元素文本出现或匹配
    
    Args:
        page: Playwright Page 对象
        xpath: 元素 XPath
        expected_text: 期望的文本（None 表示只等待元素有文本）
        timeout: 超时时间（毫秒）
    
    Returns:
        str | None: 元素文本或 None
    """
    start_time = time.time()
    timeout_sec = timeout / 1000
    
    while time.time() - start_time < timeout_sec:
        try:
            text = page.evaluate("""(xpath) => {
                const el = document.evaluate(xpath, document, null, 
                    XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                return el ? (el.innerText || el.textContent || '').trim() : null;
            }""", xpath)
            
            if text:
                if expected_text is None or expected_text in text:
                    return text
        except:
            pass
        
        time.sleep(0.2)
    
    return None


def smart_wait_for_network_idle(page, timeout=30000):
    """
    等待网络请求完成
    
    Args:
        page: Playwright Page 对象
        timeout: 超时时间（毫秒）
    """
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
        return True
    except PlaywrightTimeout:
        print("⚠️ 等待网络空闲超时")
        return False


def smart_wait_and_click(page, xpath, timeout=5000, interval=0.3):
    """
    智能等待元素可点击后点击
    
    Args:
        page: Playwright Page 对象
        xpath: 元素 XPath
        timeout: 超时时间（毫秒）
        interval: 检查间隔（秒）
    
    Returns:
        bool: 是否点击成功
    """
    start_time = time.time()
    timeout_sec = timeout / 1000
    
    while time.time() - start_time < timeout_sec:
        try:
            locator = page.locator(f"xpath={xpath}")
            if locator.count() > 0:
                # 等待元素可见并可点击
                locator.wait_for(state="visible", timeout=1000)
                locator.scroll_into_view_if_needed()
                locator.click(force=True)
                return True
        except:
            pass
        
        time.sleep(interval)
    
    print(f"⚠️ 等待点击超时: {xpath[:50]}...")
    return False

def get_current_page_url(port: int = 9222) -> str:
    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        except Exception:
            # 回退：从 /json/version 读取 ws 调试地址
            try:
                info = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=3).json()
                ws_url = info.get("webSocketDebuggerUrl")
                if ws_url:
                    browser = p.chromium.connect_over_cdp(ws_url)
            except Exception:
                pass

        if not browser:
            return None

        # 获取所有上下文与页面
        for context in browser.contexts:
            if context.pages:
                # 通常最后一个是当前活动页面
                page = context.pages[-1]
                return page.url
        return None  # 没找到页面

def scroll_all_vertical_elements_to_bottom(page):
    js_code = """
    (() => {
        const elements = [];
        document.querySelectorAll('*').forEach(el => {
            const style = window.getComputedStyle(el);
            if (el.scrollHeight > el.clientHeight &&
                (style.overflowY === "auto" || style.overflowY === "scroll")) {
                elements.push(el);
            }
        });

        console.log(`🔍 找到 ${elements.length} 个有垂直滚动条的元素`);
        elements.forEach(el => el.scrollTop = el.scrollHeight);

        // 滚动整个页面
        window.scrollTo(0, document.body.scrollHeight);
        return elements.length;
    })();
    """
    count = page.evaluate(js_code)
    print(f"✅ 已滚动 {count} 个有垂直滚动条的元素到底部")

def can_scroll(page, xpath, direction):
    """
    检查元素是否可以在指定方向滚动
    
    Args:
        page: Playwright Page 对象
        xpath: 元素 XPath
        direction: 滚动方向 (up/down/top/bottom/left/right)
    
    Returns:
        bool: 是否可滚动
    """
    return page.evaluate("""
    (xpath, direction) => {
        const el = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
        if (!el) return false;
        
        const style = window.getComputedStyle(el);
        
        // 使用 includes 检查数组包含（修复原 bug：in 操作符用于对象属性检查）
        if (["up", "down", "top", "bottom"].includes(direction)) {
            return el.scrollHeight > el.clientHeight && 
                   (style.overflowY === "auto" || style.overflowY === "scroll");
        }
        if (["left", "right"].includes(direction)) {
            return el.scrollWidth > el.clientWidth && 
                   (style.overflowX === "auto" || style.overflowX === "scroll");
        }
        return false;
    }
    """, xpath, direction)


def human_scroll(page, xpath=None, direction="down", step_range=(50, 150),
                 delay_range=(0.05, 0.12), scroll_target="element", mode="human",
                 scroll_steps=30, wheel_delta=1000):
    """
    支持六个方向滚动: up/down/top/bottom/left/right
    支持人工滚动和快速滚动。
    
    Args:
        page: Playwright Page 对象
        xpath: 元素 XPath（element 模式必需）
        direction: 滚动方向 (up/down/top/bottom/left/right)
        step_range: 每步滚动像素范围（人工模式）
        delay_range: 每步延迟范围（人工模式）
        scroll_target: 滚动目标 (element/page)
        mode: 滚动模式 (fast/human)
        scroll_steps: 快速滚动步数
        wheel_delta: 滑轮滚动量
    """
    print(f"🔄 开始滚动: target={scroll_target}, direction={direction}, mode={mode}")

    try:
        if mode == "fast":
            if scroll_target == "page":
                delta = wheel_delta if direction in ["down", "bottom", "right"] else -wheel_delta
                for _ in range(scroll_steps):
                    page.mouse.wheel(delta if direction in ["left", "right"] else 0,
                                     delta if direction in ["up", "down", "top", "bottom"] else 0)
                    time.sleep(0.02)
                print(f"✅ 滑轮滚动到 {direction} 完成")
                return
            else:
                if not xpath:
                    raise ValueError("XPath 必须提供以滚动元素")

                # 合并为单次 evaluate 调用
                page.evaluate("""(xpath, direction) => {
                    const el = document.evaluate(xpath, document, null, 
                        XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    if (!el) return;
                    
                    switch(direction) {
                        case 'up':
                        case 'top':
                            el.scrollTop = 0;
                            break;
                        case 'down':
                        case 'bottom':
                            el.scrollTop = el.scrollHeight;
                            break;
                        case 'left':
                            el.scrollLeft = 0;
                            break;
                        case 'right':
                            el.scrollLeft = el.scrollWidth;
                            break;
                    }
                }""", xpath, direction)
                print(f"✅ 元素框内快速滚动到 {direction} 完成")
                return

        # === 人工滚动模式（优化：合并多次 evaluate 调用为单次）===
        scroll_done = False
        while not scroll_done:
            # 获取所有滚动信息（合并为单次调用）
            if scroll_target == "page":
                scroll_info = page.evaluate("""() => ({
                    scrollTop: window.scrollY || document.documentElement.scrollTop,
                    scrollLeft: window.scrollX || document.documentElement.scrollLeft,
                    viewportHeight: window.innerHeight,
                    viewportWidth: window.innerWidth,
                    scrollHeight: document.body.scrollHeight,
                    scrollWidth: document.body.scrollWidth
                })""")
            elif scroll_target == "element":
                if not xpath:
                    raise ValueError("XPath 必须提供以滚动元素")
                scroll_info = page.evaluate("""(xpath) => {
                    const el = document.evaluate(xpath, document, null, 
                        XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    if (!el) return null;
                    return {
                        scrollTop: el.scrollTop,
                        scrollLeft: el.scrollLeft,
                        viewportHeight: el.clientHeight,
                        viewportWidth: el.clientWidth,
                        scrollHeight: el.scrollHeight,
                        scrollWidth: el.scrollWidth
                    };
                }""", xpath)
                
                if not scroll_info:
                    print("⚠️ 未找到滚动元素")
                    return
            else:
                raise ValueError("scroll_target 必须是 'element' 或 'page'")

            # 解构滚动信息
            scrollTop = scroll_info["scrollTop"]
            scrollLeft = scroll_info["scrollLeft"]
            viewportHeight = scroll_info["viewportHeight"]
            viewportWidth = scroll_info["viewportWidth"]
            scrollHeight = scroll_info["scrollHeight"]
            scrollWidth = scroll_info["scrollWidth"]

            # 判断是否到达目标
            if direction in ["up", "top"] and scrollTop <= 0:
                scroll_done = True
                break
            if direction in ["down", "bottom"] and scrollTop + viewportHeight >= scrollHeight:
                scroll_done = True
                break
            if direction == "left" and scrollLeft <= 0:
                scroll_done = True
                break
            if direction == "right" and scrollLeft + viewportWidth >= scrollWidth:
                scroll_done = True
                break

            step = random.randint(*step_range)
            if direction in ["up", "top", "left"]:
                step = -step

            # 执行滚动
            if scroll_target == "page":
                if direction in ["up", "down", "top", "bottom"]:
                    page.evaluate(f"() => window.scrollBy(0, {step})")
                else:
                    page.evaluate(f"() => window.scrollBy({step}, 0)")
            else:
                stepX = step if direction in ["left", "right"] else 0
                stepY = step if direction in ["up", "down", "top", "bottom"] else 0
                page.evaluate("""(xpath, stepX, stepY) => {
                    const el = document.evaluate(xpath, document, null, 
                        XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    if (el) el.scrollBy(stepX, stepY);
                }""", xpath, stepX, stepY)

            print(f"⬆ 滚动 {abs(step)} 像素, 当前 scrollTop={scrollTop}, scrollLeft={scrollLeft}")
            time.sleep(random.uniform(*delay_range))

        print(f"✅ 已滚动到 {direction} 端")

    except Exception as e:
        print(f"⚠️ 滚动失败：{e}")


def scroll_target_page_human(page, xpath=None, direction="down", scroll_target="element", mode="human",port = 9222):
    """
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")

        page = None
        for context in browser.contexts:
            for p in context.pages:
                if target_url in p.url:
                    page = p
                    break
            if page:
                break

        if not page:
            print(f"❌ 没有找到目标页面：{target_url}")
            return
    """
        # print(f"📄 当前页面：{page.url}")
    human_scroll(page, xpath=xpath, direction=direction, scroll_target=scroll_target, mode=mode)


def get_xpath_text(page, xpath):
    """
    根据 XPath 获取元素的文本内容
    """
    try:
        text = page.evaluate("""
        (data) => {
            const el = document.evaluate(data.xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            return el ? el.innerText || el.textContent : null;
        }
        """, {"xpath": xpath})
        return text
    except Exception as e:
        print(f"⚠️ 获取 XPath 文本失败：{e}")
        return None

def get_xpath_value(page, xpath):
    """
    获取指定 XPath 对应的元素文本值。
    :param page: Playwright Page 对象
    :param xpath: 元素的 XPath
    :return: 文本内容或 None
    """
    return page.evaluate("""
    (data) => {
        const el = document.evaluate(
            data.xpath,
            document,
            null,
            XPathResult.FIRST_ORDERED_NODE_TYPE,
            null
        ).singleNodeValue;
        return el ? (el.innerText || el.textContent) : null;
    }
    """, {"xpath": xpath})


def get_xpath_value_by_url(page, xpath, debug=False,port = 9222):
    """
    直接根据页面 URL 和 XPath 获取元素的文本值。

    :param target_url: 页面 URL，用于定位目标页面
    :param xpath: XPath 表达式
    :param debug: 是否打印调试信息
    :return: XPath 对应的文本内容或 None
    """
    """
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")

        page = None
        for context in browser.contexts:
            for p in context.pages:
                if target_url in p.url:
                    page = p
                    break
            if page:
                break

        if not page:
            if debug:
                print(f"❌ 没有找到目标页面: {target_url}")
            return None
    """
    if debug:
        # print(f"📄 当前页面：{page.url}")
        pass

    try:
        value = page.evaluate("""
        (data) => {
            const el = document.evaluate(
                data.xpath,
                document,
                null,
                XPathResult.FIRST_ORDERED_NODE_TYPE,
                null
            ).singleNodeValue;
            return el ? (el.innerText || el.textContent) : null;
        }
        """, {"xpath": xpath})
        return value
    except Exception as e:
        if debug:
            print(f"⚠️ 获取 XPath 值失败：{e}")
        return None

def click_tab_by_index(page, index, timeout=3000, debug=False,port = 9222):
    """
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")

        page = None
        for context in browser.contexts:
            for p in context.pages:
                if target_url in p.url:
                    page = p
                    break
            if page:
                break

        if not page:
            if debug:
                print(f"❌ 没有找到目标页面: {target_url}")
            return False
    """
    if debug:
        # print(f"📄 当前页面：{page.url}")
        pass

    try:
        result = page.evaluate("""
        async ({index, timeout}) => {
            let tabs = document.querySelectorAll(".bn-tab.bn-tab__buySell");
            if (!tabs.length) {
                console.warn("未找到任何 tab");
                return false;
            }
            if (index < 0 || index >= tabs.length) {
                console.warn("索引超出范围");
                return false;
            }
            let el = tabs[index];
            el.dispatchEvent(new MouseEvent("click", {
                bubbles: true,
                cancelable: true,
                view: window
            }));
            console.log(`点击了第 ${index} 个 tab: ${el.textContent.trim()}`);

            let start = Date.now();
            while (Date.now() - start < timeout) {
                if (el.getAttribute("aria-selected") === "true") {
                    return true;
                }
                await new Promise(r => setTimeout(r, 50));
            }
            console.warn("切换 tab 超时");
            return false;
        }
        """, {"index": index, "timeout": timeout})

        if debug:
            print(f"🔹 切换结果: {result}")

        return result
    except Exception as e:
        if debug:
            print(f"⚠️ 切换 tab 出错: {e}")
        return False

def fill_price_by_xpath(page, xpath, price, debug=False, port=9222, timeout=5000, clear_first=True):
    """
    填写 Binance 页面输入框（优化版）
    
    Args:
        page: Playwright Page 对象
        xpath: 输入框 XPath
        price: 要填写的价格（字符串或数字）
        debug: 是否打印调试信息
        port: Chrome 端口（兼容参数）
        timeout: 等待超时时间（毫秒）
        clear_first: 是否先清空输入框
    
    Returns:
        bool: 是否填写成功
    """
    try:
        locator = page.locator(f"xpath={xpath}")
        
        # 检查元素是否存在
        if locator.count() == 0:
            if debug:
                print(f"⚠️ 没有找到元素: {xpath[:50]}...")
            return False
        
        # 等待元素可见
        try:
            locator.wait_for(state="visible", timeout=timeout)
        except PlaywrightTimeout:
            if debug:
                print(f"⚠️ 等待元素可见超时")
            return False
        
        # 清空已有内容
        if clear_first:
            locator.clear()
        
        # 填写内容
        locator.fill(str(price))
        
        if debug:
            print(f"✅ 成功填写: {price}")
        return True
        
    except Exception as e:
        if debug:
            print(f"⚠️ 填写失败: {e}")
        return False


def toggle_checkbox(page,selector, should_check=True, interval=0.5, timeout=10, debug=False,port = 9222):
    """
    模拟油猴 toggleCheckbox，支持 CSS Selector。
    :param selector: CSS 选择器（例如 ".bn-checkbox.bn-checkbox__square.data-size-md"）
    :param should_check: True=勾选，False=取消勾选
    :param interval: 检测间隔（秒）
    :param timeout: 超时时间（秒）
    :param debug: 是否打印调试信息
    """
    """
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")

        page = None
        for context in browser.contexts:
            for p in context.pages:
                page = p
                break
            if page:
                break

        if not page:
            if debug:
                print("❌ 没有找到可用页面")
            return False
    """
    start_time = time.time()

    while True:
        try:
            checkbox = page.query_selector(selector)
            if not checkbox:
                if debug:
                    print("⏳ 未找到目标复选框，继续等待...")
            else:
                # 检测勾选状态
                is_checked = page.evaluate("(el) => el.classList.contains('checked')", checkbox)

                if debug:
                    print(f"当前勾选状态: {is_checked}, 目标状态: {should_check}")

                if should_check and not is_checked:
                    checkbox.click(force=True)
                    if debug:
                        print("🔄 勾选复选框")
                elif not should_check and is_checked:
                    checkbox.click(force=True)
                    if debug:
                        print("🔄 取消勾选复选框")
                else:
                    if debug:
                        print("✅ 勾选状态已符合预期")
                    return True

            if time.time() - start_time > timeout:
                if debug:
                    print("❌ 超时：复选框状态未达到预期")
                return False

            time.sleep(interval)
        except Exception as e:
            if debug:
                print(f"⚠️ 操作失败: {e}")
            return False

def click_button_by_xpath(page, xpath, timeout=3, interval=0.5, debug=False, port=9222, screenshot_on_fail=False):
    """
    点击指定 XPath 的按钮（优化版）
    
    Args:
        page: Playwright Page 对象
        xpath: 按钮 XPath
        timeout: 超时时间（秒）
        interval: 检测间隔（秒）
        debug: 是否打印调试信息
        port: Chrome 端口（兼容参数）
        screenshot_on_fail: 失败时是否截图
    
    Returns:
        bool: 是否点击成功
    """
    start_time = time.time()
    last_error = None
    
    while time.time() - start_time < timeout:
        try:
            locator = page.locator(f"xpath={xpath}")
            
            # 检查元素是否存在
            if locator.count() == 0:
                if debug:
                    print("⏳ 按钮未找到，继续等待...")
                time.sleep(interval)
                continue
            
            # 等待元素可见并可点击
            try:
                locator.wait_for(state="visible", timeout=1000)
            except:
                time.sleep(interval)
                continue
            
            # 滚动到可见区域并点击
            locator.scroll_into_view_if_needed()
            locator.click(force=True)
            
            if debug:
                print(f"✅ 已点击按钮")
            return True
            
        except Exception as e:
            last_error = e
            time.sleep(interval)
    
    # 超时处理
    if debug:
        print(f"❌ 点击超时: {last_error or '未找到按钮'}")
    
    # 失败截图
    if screenshot_on_fail:
        try:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            page.screenshot(path=f"logs/click_fail_{timestamp}.png")
        except:
            pass
    
    return False

def random_sleep(min_seconds=1, max_seconds=5):
    """
    随机休眠一定时间
    :param min_seconds: 最小休眠时间（秒）
    :param max_seconds: 最大休眠时间（秒）
    """
    duration = random.uniform(min_seconds, max_seconds)
    print(f"【休眠 {int(duration)}s 。。。】")
    time.sleep(duration)
    return duration

def check_element_exists(page, xpath,port = 9222):
    """
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        page = None

        for context in browser.contexts:
            for p in context.pages:
                if target_url in p.url:
                    page = p
                    break
            if page:
                break

        if not page:
            print(f"❌ 没有找到目标页面：{target_url}")
            return False
        """

    try:
        element =  page.locator(f"xpath={xpath}")
        if element:
            print("✅ 元素存在")
            return True
        else:
            print("❌ 元素不存在")
            return False
    except Exception as e:
        print(f"⚠️ 检查失败: {e}")
        return False

def find_xpath_by_placeholder(page,placeholder_text):
    # with sync_playwright() as p:
    #    browser = p.chromium.launch(headless=False)  # 启动浏览器
    #
    xpath = f"//input[@placeholder='{placeholder_text}']"
    if page.locator(f"xpath={xpath}").count() > 0:
        return xpath

    return None

def save_initial_balance(count, folder="."):
    # 确保目录存在（默认当前目录）
    os.makedirs(folder, exist_ok=True)

    # 带时间戳的文件名
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(folder, f"初始余额_{timestamp}.txt")

    # 写入内容
    with open(filename, "w", encoding="utf-8") as f:
        f.write(str(count))

    print(f"✅ 已保存初始余额 {count} 到文件: {filename}")
    return filename

def save_balance_to_csv(num, filename="balance_log"):
    filename = filename+".csv"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_data = pd.DataFrame([[timestamp, num]], columns=["时间", "可用余额"])
    file_exists = os.path.exists(filename)
    new_data.to_csv(filename, mode="a", header=not file_exists, index=False, encoding="utf-8-sig")



def refresh_specific_page_until_element(page, target_url, xpath, delay=3, debug=False):
    """
    安全刷新指定页面直到目标元素加载成功（推荐版本）

    📘 功能说明：
        此函数会持续刷新指定网页（target_url），直到检测到页面上出现指定元素（element_selector）。
        若当前页面不是目标网址，则会自动跳转。
        若刷新失败或检测到验证页面，会自动等待几秒后重试。
        可防止 Binance 这类网站因异步加载导致的“卡死”问题。

    🧩 参数说明：
        :param page: Playwright Page 对象
            当前浏览器页面对象（例如 connect_over_cdp 获取的 page）

        :param target_url: str
            需要刷新的目标网址（必须完整，例如 "https://www.binance.com/zh-CN/alpha/bsc/0x123..."）

        :param element_selector: str
            要检测的元素选择器，用于确认页面加载完成
            可为 CSS 或 XPath 选择器，例如：
                - ".bn-checkbox.bn-checkbox__square"
                - "//*[@id='bn-tab-pane-orderOrder']/div"

        :param delay: int 或 float（默认 3）
            每次刷新失败后等待的秒数（防止频繁请求导致被封）

        :param debug: bool（默认 False）
            是否打印调试信息。True 时会打印每一步的状态（推荐调试阶段开启）。

    ✅ 返回值：
        True  —— 页面刷新成功且目标元素已加载
        False —— 永远不会返回 False，因为函数会持续刷新直到成功，可按需改动

    ⚠️ 注意事项：
        - 不会调用 page.reload() 在错误页面上乱刷新
        - 若遇到验证页面，会自动暂停 10 秒再继续
        - 若网络超时或出错，会自动捕获异常并重试
    """

    while True:
        try:
            # 检查当前页面地址是否正确
            if page.url != target_url:
                if debug:
                    print(f"⚠️ 当前不是目标页，跳转到: {target_url}")
                page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            else:
                if debug:
                    print(f"🔄 正在刷新页面: {target_url}")
                page.reload(wait_until="domcontentloaded", timeout=60000)

            # 检查是否是验证码或验证页
            """
            content = page.content()
            if "验证" in content or "Captcha" in content:
                print("⚠️ 检测到验证页面，暂停刷新 10 秒...")
                time.sleep(10)
                continue
            """
            # 检查目标元素是否存在
            element =  page.locator(f"xpath={xpath}")
            if element:
                if debug:
                    print("✅ 页面刷新成功，目标元素已加载")
                return True
            else:
                if debug:
                    print("⚠️ 元素未出现，继续刷新...")
                time.sleep(delay)

        except Exception as e:
            print(f"❌ 刷新失败: {e}")
            time.sleep(delay)


def init_browser(port=9222, target_url_contains=None):
    """
    连接到已经打开的 Chrome（CDP 模式），并找到指定 URL 的页面

    :param port: int
        Chrome 调试端口，默认 9222
    :param target_url_contains: str 或 None
        如果不为 None，则只返回 URL 中包含此字符串的页面

    :return: tuple (p, browser, page)
        p: Playwright 对象
        browser: 浏览器对象
        page: 找到的页面对象（None 表示未找到）
    """
    p = sync_playwright().start()
    browser = None
    try:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    except Exception:
        try:
            info = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=3).json()
            ws_url = info.get("webSocketDebuggerUrl")
            if ws_url:
                browser = p.chromium.connect_over_cdp(ws_url)
        except Exception:
            pass

    if not browser:
        print("❌ 无法连接到 Chrome DevTools，请确认端口浏览器已启动并端口正确")
        return None, None, None

    page = None
    for context in browser.contexts:
        for pg in context.pages:
            # 排除 devtools 页面
            if pg.url.startswith("devtools://"):
                continue

            # 如果指定了关键字，匹配它
            if target_url_contains:
                if target_url_contains in pg.url:
                    page = pg
                    break
            else:
                page = pg
                break
        if page:
            break

    if not page:
        print("❌ 没找到可用页面")
        return None, None, None

    return p, browser, page


def elapsed_time(start_time,text):

    elapsed = time.time() - start_time
    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = elapsed % 60
    print(f"【⏱️ {text}: {hours}h {minutes}m {seconds:.2f}s】")


def get_beijing_time():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)

def wait_for_time_pass(pause_periods):
    while True:
        now = get_beijing_time().time()
        in_pause = False

        for start_str, end_str in pause_periods:
            start_time = datetime.datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.datetime.strptime(end_str, "%H:%M").time()

            if start_time <= now <= end_time:
                in_pause = True
                wait_seconds = (datetime.datetime.combine(datetime.datetime.today(), end_time) - get_beijing_time()).total_seconds()
                print(f"⏸ 当前北京时间 {now} 在暂停时间段 {start_str}-{end_str} 内，等待 {wait_seconds:.0f} 秒...")
                time.sleep(max(wait_seconds, 1))
                break

        if not in_pause:
            break

def generate_totp(secret: str, digits: int = 6, period: int = 30, t: int = None) -> str:
    if t is None:
        t = int(time.time())
    secret_padded = secret.strip().replace(" ", "").upper()
    secret_padded += "=" * ((8 - len(secret_padded) % 8) % 8)
    key = base64.b32decode(secret_padded)
    counter = struct.pack(">Q", int(t // period))
    hmac_hash = hmac.new(key, counter, hashlib.sha1).digest()
    offset = hmac_hash[-1] & 0x0F
    code = (
        ((hmac_hash[offset] & 0x7F) << 24)
        | ((hmac_hash[offset + 1] & 0xFF) << 16)
        | ((hmac_hash[offset + 2] & 0xFF) << 8)
        | (hmac_hash[offset + 3] & 0xFF)
    )
    otp = code % (10 ** digits)
    return str(otp).zfill(digits)


def get_google_code(secret: str,is_print = False) -> str:
    totp = generate_totp(secret)
    remaining = 30 - (int(time.time()) % 30)
    if is_print == True:
        print(f"🔢 当前验证码: {totp}（剩余 {remaining}s）")

    return totp

# 监控验证其是否存在
def pause_for_verification(page,secret, check_interval=5):
    """直接监控币安身份验证器，发现后持续等待直到消失"""
    # print("👁️ 启动验证码监控...")

    try:

        # 第一次检测
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
            print("⚠️ 检测到币安身份验证器弹窗 → 等待消失...")

            # 持续检测直到弹窗消失
            while found_verification:
                time.sleep(check_interval)

                # 网络验证器每次更新
                code = get_google_code(secret)

                input_verification_code(page, code)
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
                print("⏳ 验证器仍存在，继续等待...")

            print("✅ 验证器已消失，继续执行程序")

        else:
            pass

    except Exception as e:
        print(f"⚠️ 监控异常: {e}")


# ---------------------------
# 输入验证码
# ---------------------------
def input_verification_code(page, code):
    """
    模拟鼠标点击并输入验证码
    
    Args:
        page: Playwright Page 对象
        code: 6位验证码
    
    Returns:
        bool: 是否输入成功
    """
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

        # 点击输入框并聚焦
        page.evaluate("""
            () => {
                const shadowHost = document.querySelector("#mfa-shadow-host");
                const inputEl = shadowHost.shadowRoot.querySelector(
                    'input[data-e2e="input-mfa"]'
                );
                if (inputEl) {
                    inputEl.focus();
                    // 清空已有内容
                    inputEl.value = '';
                }
            }
        """)
        time.sleep(0.3)

        # 先全选并删除已有内容（双保险）
        page.keyboard.press("Control+A")
        time.sleep(0.05)
        page.keyboard.press("Backspace")
        time.sleep(0.1)

        # 模拟键盘输入验证码
        page.keyboard.type(code, delay=0.08)
        print(f"✅ 已输入验证码: {code[:2]}****")  # 脱敏显示
        return True

    except Exception as e:
        print(f"⚠️ 输入验证码失败: {e}")
        return False

"""
暂停程序在指定的不交易时间段（北京时间，UTC+8）。
示例用法：
    off_periods = ["23:00-07:00", "12:30-13:00"]
    pause_if_in_off_periods(off_periods)

函数特性：
- 接受 "HH:MM-HH:MM" 格式的区间字符串列表（可以有多个区间）
- 支持跨午夜（例如 23:00-07:00）
- 如果当前时间落在任意区间内，将阻塞直到该区间结束（若多个区间重叠，等待到最晚的结束时间）
- 可选参数 check_interval 控制 sleep 的切片间隔（秒），默认 10 秒，便于响应 Ctrl+C
"""



def pause_if_in_off_periods(off_periods):
    """
    检查当前时间是否在暂停时间段，如果在就直接 sleep 到该时间段结束。
    off_periods: [("08:30", "09:00"), ...]，本地时间
    """
    now = datetime.datetime.now().time()  # 当前本地时间 (naive)

    for start_str, end_str in off_periods:
        start_time = datetime.datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.datetime.strptime(end_str, "%H:%M").time()

        # 当前在暂停段内
        if start_time <= now < end_time:
            # 计算 sleep 秒数
            now_dt = datetime.datetime.now()
            end_dt = now_dt.replace(hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0)

            # 如果结束时间已经过了今天，sleep 到明天
            if end_dt <= now_dt:
                end_dt += datetime.timedelta(days=1)

            sleep_seconds = (end_dt - now_dt).total_seconds()
            print(f"⏸ 当前时间 {now}, 在暂停时间段，直接等待 {sleep_seconds:.1f} 秒，到 {end_dt}")
            time.sleep(sleep_seconds)
            return  # 结束暂停，继续执行



# -------------------------
# 示例
# -------------------------


