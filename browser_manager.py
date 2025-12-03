"""
浏览器管理模块 - 封装 Playwright 操作
提供统一的浏览器连接、页面操作和错误处理
"""
import random
import time
import os
from datetime import datetime
from functools import wraps
from typing import Optional, Callable, Any, Tuple
from contextlib import contextmanager

import requests
from playwright.sync_api import sync_playwright, Page, Browser, Playwright, TimeoutError as PlaywrightTimeout

from logger import log, info, error, warning, success


# ============================================
# 截图目录
# ============================================
SCREENSHOT_DIR = "logs/screenshots"


# ============================================
# 装饰器
# ============================================

def retry(max_attempts: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
    """
    重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay: 重试间隔（秒）
        exceptions: 需要重试的异常类型
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        warning(f"{func.__name__} 失败 (尝试 {attempt}/{max_attempts}): {e}")
                        time.sleep(delay)
                    else:
                        error(f"{func.__name__} 最终失败: {e}")
            raise last_exception
        return wrapper
    return decorator


def with_verification(func: Callable) -> Callable:
    """
    自动处理验证器弹窗的装饰器
    在执行操作前检查并处理验证器
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if hasattr(self, 'check_verification'):
            self.check_verification()
        return func(self, *args, **kwargs)
    return wrapper


def with_screenshot_on_error(func: Callable) -> Callable:
    """
    操作失败时自动截图的装饰器
    用于调试和错误追踪
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            # 尝试截图
            if hasattr(self, 'screenshot_on_error'):
                self.screenshot_on_error(func.__name__)
            raise e
    return wrapper


# ============================================
# 浏览器管理类
# ============================================

class BrowserManager:
    """
    浏览器管理器 - 统一管理 Playwright 连接和页面操作
    """
    
    def __init__(self, port: int = 9222, secret: str = ""):
        """
        初始化浏览器管理器
        
        Args:
            port: Chrome 调试端口
            secret: 谷歌验证器密钥
        """
        self.port = port
        self.secret = secret
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._connected = False
    
    def connect(self, target_url: Optional[str] = None) -> bool:
        """
        连接到 Chrome CDP
        
        Args:
            target_url: 目标页面 URL（可选，用于定位特定页面）
            
        Returns:
            连接是否成功
        """
        try:
            self.playwright = sync_playwright().start()
            
            # 尝试直接连接
            try:
                self.browser = self.playwright.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{self.port}"
                )
            except Exception:
                # 回退：从 /json/version 获取 WebSocket URL
                try:
                    resp = requests.get(
                        f"http://127.0.0.1:{self.port}/json/version",
                        timeout=3
                    )
                    ws_url = resp.json().get("webSocketDebuggerUrl")
                    if ws_url:
                        self.browser = self.playwright.chromium.connect_over_cdp(ws_url)
                except Exception as e:
                    error(f"无法连接到 Chrome: {e}")
                    return False
            
            if not self.browser:
                error("无法连接到 Chrome DevTools，请确认端口浏览器已启动")
                return False
            
            # 查找目标页面
            self.page = self._find_page(target_url)
            if not self.page:
                error("没找到可用页面")
                return False
            
            self.page.set_default_timeout(5000)
            self._connected = True
            success(f"已连接到页面: {self.page.url[:50]}...")
            return True
            
        except Exception as e:
            error(f"连接失败: {e}")
            return False
    
    def _find_page(self, target_url: Optional[str] = None) -> Optional[Page]:
        """查找目标页面"""
        target_page = None
        best_candidate = None
        
        for context in self.browser.contexts:
            for pg in context.pages:
                url = pg.url
                # 跳过 devtools 页面
                if url.startswith("devtools://"):
                    continue
                
                # 如果指定了 URL，严格匹配
                if target_url and target_url in url:
                    return pg
                
                # 如果未指定 target_url，则智能查找
                if not target_url:
                    # 优先找现货交易页面
                    if "binance.com" in url and ("spot" in url or "trade" in url):
                        target_page = pg
                        break
                    
                    # 避开账号安全页面，作为备选
                    if "accounts.binance.com" not in url:
                        best_candidate = pg
            
            if target_page:
                break
        
        if target_page:
            return target_page
        if best_candidate:
            return best_candidate
            
        # 如果都没找到，且没有指定 target_url，返回任意一个非 devtools 页面
        if not target_url:
             for context in self.browser.contexts:
                for pg in context.pages:
                    if not pg.url.startswith("devtools://"):
                        return pg

        return None
    
    def disconnect(self) -> None:
        """断开连接"""
        if self.playwright:
            self.playwright.stop()
        self._connected = False
        info("已断开浏览器连接")
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected and self.page is not None
    
    def get_current_url(self) -> Optional[str]:
        """获取当前页面 URL"""
        if self.page:
            return self.page.url
        return None
    
    # ============================================
    # 截图功能
    # ============================================
    
    def take_screenshot(
        self,
        name: str = "screenshot",
        full_page: bool = False
    ) -> Optional[str]:
        """
        截取当前页面截图
        
        Args:
            name: 截图名称（不含扩展名）
            full_page: 是否截取整个页面
        
        Returns:
            截图文件路径或 None
        """
        if not self.page:
            return None
        
        try:
            # 确保目录存在
            os.makedirs(SCREENSHOT_DIR, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{name}_{timestamp}.png"
            filepath = os.path.join(SCREENSHOT_DIR, filename)
            
            # 截图
            self.page.screenshot(path=filepath, full_page=full_page)
            info(f"截图已保存: {filepath}")
            return filepath
            
        except Exception as e:
            warning(f"截图失败: {e}")
            return None
    
    def screenshot_on_error(self, operation_name: str = "error") -> Optional[str]:
        """
        错误时截图（用于调试）
        
        Args:
            operation_name: 操作名称，用于文件命名
        
        Returns:
            截图文件路径或 None
        """
        return self.take_screenshot(f"error_{operation_name}", full_page=True)
    
    # ============================================
    # 验证器处理
    # ============================================
    
    def check_verification(self, check_interval: float = 5) -> None:
        """
        检查并处理验证器弹窗
        
        Args:
            check_interval: 检查间隔（秒）
        """
        if not self.secret:
            return
            
        try:
            found = self._detect_verification_popup()
            
            if found:
                warning("检测到币安身份验证器弹窗 → 等待消失...")
                
                while found:
                    time.sleep(check_interval)
                    code = self._generate_totp()
                    self._input_verification_code(code)
                    found = self._detect_verification_popup()
                    
                    if found:
                        info("验证器仍存在，继续等待...")
                
                success("验证器已消失，继续执行程序")
                
        except Exception as e:
            warning(f"验证器检测异常: {e}")
    
    def _detect_verification_popup(self) -> bool:
        """检测验证器弹窗是否存在"""
        return self.page.evaluate("""
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
    
    def _generate_totp(self) -> str:
        """生成 TOTP 验证码"""
        import base64
        import hmac
        import hashlib
        import struct
        
        t = int(time.time())
        secret_padded = self.secret.strip().replace(" ", "").upper()
        secret_padded += "=" * ((8 - len(secret_padded) % 8) % 8)
        key = base64.b32decode(secret_padded)
        counter = struct.pack(">Q", int(t // 30))
        hmac_hash = hmac.new(key, counter, hashlib.sha1).digest()
        offset = hmac_hash[-1] & 0x0F
        code = (
            ((hmac_hash[offset] & 0x7F) << 24)
            | ((hmac_hash[offset + 1] & 0xFF) << 16)
            | ((hmac_hash[offset + 2] & 0xFF) << 8)
            | (hmac_hash[offset + 3] & 0xFF)
        )
        otp = code % (10 ** 6)
        return str(otp).zfill(6)
    
    def _input_verification_code(self, code: str) -> bool:
        """
        输入验证码
        
        Args:
            code: 6位验证码
            
        Returns:
            是否输入成功
        """
        try:
            # 聚焦输入框并清空已有内容
            self.page.evaluate("""
                () => {
                    const shadowHost = document.querySelector("#mfa-shadow-host");
                    const inputEl = shadowHost.shadowRoot.querySelector(
                        'input[data-e2e="input-mfa"]'
                    );
                    if (inputEl) {
                        inputEl.focus();
                        inputEl.value = '';  // 清空已有内容
                    }
                }
            """)
            time.sleep(0.3)
            
            # 先全选并删除已有内容（双保险）
            self.page.keyboard.press("Control+A")
            time.sleep(0.05)
            self.page.keyboard.press("Backspace")
            time.sleep(0.1)
            
            # 输入验证码
            self.page.keyboard.type(code, delay=0.08)
            info(f"已输入验证码: {code[:2]}****")  # 脱敏显示
            return True
            
        except Exception as e:
            warning(f"输入验证码失败: {e}")
            return False
    
    # ============================================
    # 滚动操作
    # ============================================
    
    @with_verification
    def scroll_to(
        self,
        direction: str = "bottom",
        xpath: Optional[str] = None,
        mode: str = "fast"
    ) -> None:
        """
        滚动页面或元素
        
        Args:
            direction: 方向 (top/bottom/left/right)
            xpath: 元素 XPath（None 表示整个页面）
            mode: 模式 (fast/human)
        """
        target = "元素" if xpath else "页面"
        info(f"滚动{target}到 {direction}")
        
        try:
            if mode == "fast":
                self._fast_scroll(direction, xpath)
            else:
                self._human_scroll(direction, xpath)
        except Exception as e:
            warning(f"滚动失败: {e}")
    
    def _fast_scroll(self, direction: str, xpath: Optional[str] = None) -> None:
        """快速滚动"""
        if xpath:
            # 滚动元素
            js_map = {
                "top": "el.scrollTop = 0;",
                "bottom": "el.scrollTop = el.scrollHeight;",
                "left": "el.scrollLeft = 0;",
                "right": "el.scrollLeft = el.scrollWidth;"
            }
            js = f"""(xpath) => {{
                const el = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                if (el) {{ {js_map.get(direction, js_map['bottom'])} }}
            }}"""
            self.page.evaluate(js, xpath)
        else:
            # 滚动页面
            wheel_delta = 1000 if direction in ["down", "bottom", "right"] else -1000
            for _ in range(30):
                if direction in ["left", "right"]:
                    self.page.mouse.wheel(wheel_delta, 0)
                else:
                    self.page.mouse.wheel(0, wheel_delta)
                time.sleep(0.02)
    
    def _human_scroll(self, direction: str, xpath: Optional[str] = None) -> None:
        """人性化滚动"""
        step_range = (50, 150)
        delay_range = (0.05, 0.12)
        
        while True:
            if xpath:
                scroll_pos = self.page.evaluate("""(xpath) => {
                    const el = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    return el ? {
                        top: el.scrollTop,
                        height: el.clientHeight,
                        scrollHeight: el.scrollHeight
                    } : null;
                }""", xpath)
            else:
                scroll_pos = self.page.evaluate("""() => ({
                    top: window.scrollY,
                    height: window.innerHeight,
                    scrollHeight: document.body.scrollHeight
                })""")
            
            if not scroll_pos:
                break
                
            # 检查是否到达目标
            if direction in ["up", "top"] and scroll_pos["top"] <= 0:
                break
            if direction in ["down", "bottom"] and scroll_pos["top"] + scroll_pos["height"] >= scroll_pos["scrollHeight"]:
                break
            
            # 滚动
            step = random.randint(*step_range)
            if direction in ["up", "top"]:
                step = -step
            
            if xpath:
                self.page.evaluate(f"""(xpath) => {{
                    const el = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    if (el) el.scrollBy(0, {step});
                }}""", xpath)
            else:
                self.page.evaluate(f"window.scrollBy(0, {step})")
            
            time.sleep(random.uniform(*delay_range))
    
    # ============================================
    # 智能等待
    # ============================================
    
    def wait_for_element(
        self,
        xpath: str,
        timeout: int = 10000,
        state: str = "visible"
    ) -> bool:
        """
        智能等待元素出现
        
        Args:
            xpath: 元素 XPath
            timeout: 超时时间（毫秒）
            state: 等待状态 (visible/attached/hidden)
        
        Returns:
            元素是否出现
        """
        try:
            locator = self.page.locator(f"xpath={xpath}")
            locator.wait_for(state=state, timeout=timeout)
            return True
        except PlaywrightTimeout:
            warning(f"等待元素超时")
            return False
        except Exception as e:
            warning(f"等待元素失败: {e}")
            return False
    
    def wait_for_text(
        self,
        xpath: str,
        expected_text: Optional[str] = None,
        timeout: int = 10000
    ) -> Optional[str]:
        """
        等待元素文本出现或匹配
        
        Args:
            xpath: 元素 XPath
            expected_text: 期望的文本（None 表示只等待元素有文本）
            timeout: 超时时间（毫秒）
        
        Returns:
            元素文本或 None
        """
        start_time = time.time()
        timeout_sec = timeout / 1000
        
        while time.time() - start_time < timeout_sec:
            try:
                text = self.page.evaluate("""(xpath) => {
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
    
    def wait_for_network_idle(self, timeout: int = 30000) -> bool:
        """等待网络请求完成"""
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
            return True
        except PlaywrightTimeout:
            warning("等待网络空闲超时")
            return False
    
    # ============================================
    # 元素操作
    # ============================================
    
    @with_verification
    def get_text(self, xpath: str) -> Optional[str]:
        """获取元素文本"""
        try:
            return self.page.evaluate("""(xpath) => {
                const el = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                return el ? (el.innerText || el.textContent) : null;
            }""", xpath)
        except Exception as e:
            warning(f"获取文本失败: {e}")
            return None

    @with_verification
    def get_input_value(self, xpath: str) -> Optional[str]:
        """获取输入框的值"""
        try:
            return self.page.evaluate("""(xpath) => {
                const el = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                return el ? el.value : null;
            }""", xpath)
        except Exception as e:
            warning(f"获取输入框值失败: {e}")
            return None
    
    @with_verification
    def fill_input(
        self,
        xpath: str,
        value: str,
        timeout: int = 5000,
        clear_first: bool = True
    ) -> bool:
        """
        填写输入框（优化版）
        
        Args:
            xpath: 输入框 XPath
            value: 要填写的值
            timeout: 等待超时时间（毫秒）
            clear_first: 是否先清空输入框
        
        Returns:
            是否填写成功
        """
        try:
            locator = self.page.locator(f"xpath={xpath}")
            
            # 检查元素是否存在
            if locator.count() == 0:
                warning(f"未找到输入框元素")
                return False
            
            # 等待元素可见
            try:
                locator.wait_for(state="visible", timeout=timeout)
            except PlaywrightTimeout:
                warning("等待输入框可见超时")
                return False
            
            # 清空已有内容
            if clear_first:
                locator.clear()
            
            # 填写内容
            locator.fill(str(value))
            info(f"已填写: {value}")
            return True
            
        except Exception as e:
            warning(f"填写失败: {e}")
            self.screenshot_on_error("fill_input")
            return False
    
    @with_verification
    def click(
        self,
        xpath: str,
        timeout: float = 3,
        interval: float = 0.3,
        screenshot_on_fail: bool = True
    ) -> bool:
        """
        点击元素（优化版）
        
        Args:
            xpath: 元素 XPath
            timeout: 超时时间（秒）
            interval: 检查间隔（秒）
            screenshot_on_fail: 失败时是否截图
        
        Returns:
            是否点击成功
        """
        start = time.time()
        last_error = None
        
        while time.time() - start < timeout:
            try:
                locator = self.page.locator(f"xpath={xpath}")
                
                # 检查元素是否存在
                if locator.count() == 0:
                    time.sleep(interval)
                    continue
                
                # 等待元素可见
                try:
                    locator.wait_for(state="visible", timeout=1000)
                except:
                    time.sleep(interval)
                    continue
                
                # 滚动到可见区域并点击
                locator.scroll_into_view_if_needed()
                locator.click(force=True)
                info("已点击按钮")
                return True
                
            except Exception as e:
                last_error = e
                time.sleep(interval)
        
        # 超时处理
        warning(f"点击超时: {last_error or '未找到按钮'}")
        
        # 失败截图
        if screenshot_on_fail:
            self.screenshot_on_error("click")
        
        return False
    
    @with_verification
    def click_tab(self, index: int, timeout: int = 3000) -> bool:
        """点击 Tab 按钮"""
        try:
            result = self.page.evaluate("""
                async ({index, timeout}) => {
                    let tabs = document.querySelectorAll(".bn-tab.bn-tab__buySell");
                    if (!tabs.length || index < 0 || index >= tabs.length) return false;
                    
                    let el = tabs[index];
                    el.dispatchEvent(new MouseEvent("click", {
                        bubbles: true, cancelable: true, view: window
                    }));
                    
                    let start = Date.now();
                    while (Date.now() - start < timeout) {
                        if (el.getAttribute("aria-selected") === "true") return true;
                        await new Promise(r => setTimeout(r, 50));
                    }
                    return false;
                }
            """, {"index": index, "timeout": timeout})
            
            info(f"切换到 Tab {index}: {'成功' if result else '失败'}")
            return result
        except Exception as e:
            warning(f"切换 Tab 失败: {e}")
            return False
    
    @with_verification
    def toggle_checkbox(
        self,
        selector: str,
        should_check: bool = True,
        timeout: float = 10
    ) -> bool:
        """切换复选框状态"""
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                checkbox = self.page.query_selector(selector)
                if not checkbox:
                    time.sleep(0.5)
                    continue
                
                is_checked = self.page.evaluate(
                    "(el) => el.classList.contains('checked')",
                    checkbox
                )
                
                if should_check == is_checked:
                    info(f"复选框状态已符合预期: {should_check}")
                    return True
                
                checkbox.click(force=True)
                info(f"{'勾选' if should_check else '取消'}复选框")
                time.sleep(0.5)
                
            except Exception as e:
                warning(f"复选框操作失败: {e}")
                return False
        
        warning("复选框操作超时")
        return False
    
    # ============================================
    # 页面操作
    # ============================================
    
    def refresh_until_element(
        self,
        target_url: str,
        xpath: str,
        delay: float = 3,
        timeout: float = 60
    ) -> bool:
        """刷新页面直到元素出现"""
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                if self.page.url != target_url:
                    info(f"跳转到: {target_url[:50]}...")
                    self.page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                else:
                    info("刷新页面...")
                    self.page.reload(wait_until="domcontentloaded", timeout=60000)
                
                element = self.page.locator(f"xpath={xpath}")
                if element:
                    success("页面加载完成，目标元素已出现")
                    return True
                    
            except Exception as e:
                warning(f"刷新失败: {e}")
            
            time.sleep(delay)
        
        error("刷新超时")
        return False


# ============================================
# 便捷函数
# ============================================

def get_current_page_url(port: int = 9222) -> Optional[str]:
    """快速获取当前页面 URL (智能识别交易页)"""
    with sync_playwright() as p:
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
            return None
        
        target_url = None
        best_candidate = None
        
        for context in browser.contexts:
            for page in context.pages:
                url = page.url
                if url.startswith("devtools://"):
                    continue
                
                # 优先找现货交易页面
                if "binance.com" in url and ("spot" in url or "trade" in url):
                    target_url = url
                    break
                
                # 避开账号安全页面
                if "accounts.binance.com" not in url:
                    best_candidate = url
            
            if target_url:
                break
        
        if target_url:
            return target_url
        if best_candidate:
            return best_candidate
            
        # 如果没有更好的选择，返回最后一个页面
        for context in browser.contexts:
            if context.pages:
                return context.pages[-1].url
        
        return None


def random_sleep(min_seconds: float = 1, max_seconds: float = 5) -> float:
    """随机休眠"""
    duration = random.uniform(min_seconds, max_seconds)
    info(f"休眠 {int(duration)}s...")
    time.sleep(duration)
    return duration


def elapsed_time(start_time: float, text: str = "用时") -> None:
    """打印耗时"""
    elapsed = time.time() - start_time
    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = elapsed % 60
    print(f"【⏱️ {text}: {hours}h {minutes}m {seconds:.2f}s】")

