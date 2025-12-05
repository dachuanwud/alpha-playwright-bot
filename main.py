"""
Alpha 自动化交易脚本 - 优化版
使用 Playwright 连接本地 Chrome，自动执行买卖操作

支持多账号模式：
    python main.py --account "账号A"
    
单账号模式（向后兼容）：
    python main.py
"""
import re
import time
import os
import datetime
import argparse
from typing import Optional

import pandas as pd

# 导入优化后的模块
from config import get_config, get_account_config, Config
from browser_manager import BrowserManager, random_sleep, elapsed_time
from logger import (
    log, info, warning, error, success, step, mask_balance,
    use_account_logger, reset_logger
)
from trade_stats import TradeStats, TimedOperation


class AlphaTrader:
    """Alpha 交易机器人"""
    
    # XPath 常量
    XPATH = {
        # 价格相关 - 主选择器和备用选择器
        "current_price": "(//*[contains(@class, 'ReactVirtualized__Grid__innerScrollContainer')]//*[contains(@class, 'flex-1') and contains(@class, 'cursor-pointer')])[1]",
        # 备用价格选择器：从成交记录中获取
        "current_price_alt": "//*[@aria-label='grid']//*[contains(@class, 'cursor-pointer')][1]",
        # 备用价格选择器2：价格输入框的当前值
        "current_price_input": '//*[@id="limitPrice"]',
        "available_balance": "//*[contains(@class, 'bn-flex') and contains(@class, 'text-TertiaryText') and contains(@class, 'items-center') and contains(@class, 'justify-between') and contains(@class, 'w-full')]//*[contains(@class, 'text-PrimaryText')]",
        
        # 输入框
        "limit_price": '//*[@id="limitPrice"]',
        "limit_amount": '//*[@id="limitAmount"]',
        "limit_total_buy": "//input[@id='limitTotal' and contains(@class, 'bn-textField-input') and contains(@placeholder, '最小')]",
        "limit_total_sell": "//input[@id='limitTotal' and contains(@class, 'bn-textField-input') and contains(@placeholder, '卖出')]",
        # 卖出界面的反向买入价输入框（placeholder 包含"买入"）
        "limit_total_buy_reverse": "//input[@id='limitTotal' and contains(@class, 'bn-textField-input') and contains(@placeholder, '买入')]",
        
        # 按钮
        "buy_button": "//*[contains(@class, 'bn-button') and contains(@class, 'bn-button__buy') and contains(@class, 'data-size-middle')]",
        "sell_button": "//*[contains(@class, 'bn-button') and contains(@class, 'bn-button__sell') and contains(@class, 'data-size-middle') and contains(@class, 'w-full')]",
        "confirm_button": '/html/body/div[4]/div[2]/div/div/button',
        "cancel_slippage": '/html/body/div[4]/div[2]/div/div/div[3]/button[2]',
        "confirm_slippage": '/html/body/div[4]/div[2]/div/div/div[3]/button[1]',
        "continue_button": '/html/body/div[4]/div[2]/div/div/button',
        
        # 订单相关
        "order_table": "//tbody[contains(@class, 'bn-web-table-tbody')]",
        "order_rows": "//tbody[contains(@class, 'bn-web-table-tbody')]/tr[@aria-rowindex]",
        # 取消单个订单的按钮（订单行末尾的取消链接）
        "cancel_single_btn": "//tbody[contains(@class, 'bn-web-table-tbody')]//tr[1]//a[contains(text(), '取消') or contains(text(), '撤单') or contains(text(), 'Cancel') or contains(@class, 'cancel')]",
        # 备用：查找订单行中的取消按钮（通过文字）
        "cancel_order_link": "//*[@id='bn-tab-pane-orderOrder']//a[contains(text(), '取消') or contains(text(), '撤单') or contains(text(), 'Cancel')]",
        # 取消全部按钮（表头）
        "cancel_all_btn": "//*[@id='bn-tab-pane-orderOrder']//div[contains(text(), '取消') or contains(text(), '撤单') or contains(text(), 'Cancel')]",
        "cancel_confirm": '/html/body/div[4]/div[2]/div/div/div[2]/button',
        # 备用确认按钮
        "cancel_confirm_alt": "//button[contains(text(), '确认') or contains(text(), '确定')]",
        
        # 滚动目标
        "trade_scroll": '//*[@id="__APP"]/div[2]/div[7]/div',
        "grid_scroll": "(//*[contains(@class, 'flexlayout__tab_moveable')])[3]//*[@tabindex='0' and @aria-label='grid']",
        "grid_scroll_alt": "//*[contains(@class, 'w-full') and contains(@class, 'h-full')]//*[@aria-label='grid']",
        
        # 页面加载检测
        "page_loaded": "(//*[contains(@class, 'bg-BasicBg')]//*[contains(@class, 'items-center')]//*[contains(@class, 'text-PrimaryText')])[1]",
    }
    
    # CSS 选择器
    CSS = {
        "checkbox": ".bn-checkbox.bn-checkbox__square.data-size-md"
    }
    
    def __init__(self, config: Config):
        """
        初始化交易机器人
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.browser = BrowserManager(
            port=config.browser.port,
            secret=config.security.secret
        )
        
        # 交易状态
        self.target_url: Optional[str] = None
        self.buy_price: float = 0
        self.complete_trades: int = 0  # 完成的完整交易次数（买入+卖出都成功）
        self.loop_count: int = 0  # 循环次数
        self.buy_pending: bool = False  # 是否有待卖出的买入（买入成功但还没卖出）
        self.refresh_set: set = set()
        self.start_time: float = 0
        
        # 交易统计
        self.stats = TradeStats()
        
        # 余额不足连续失败计数
        self.insufficient_balance_count: int = 0
        self.max_insufficient_retries: int = 5  # 最大连续余额不足重试次数
        
        # 买单等待时间配置（优化：快速响应）
        self.buy_order_timeout: int = 5  # 买单挂单超时时间（秒）- 价格变化快，不宜等太久
        self.buy_order_check_interval: int = 1  # 检查买单成交的间隔（秒）- 快速检测
    
    def run(self) -> None:
        """运行交易机器人"""
        self.start_time = time.time()
        
        step("启动 Alpha 交易机器人")
        self.config.print_config()
        
        # 连接浏览器
        if not self._connect():
            return
        
        # 主循环
        try:
            self._main_loop()
        except KeyboardInterrupt:
            warning("\n⚠️ 用户中断 (Ctrl+C)")
            self._print_interrupt_summary()
        except Exception as e:
            error(f"运行异常: {e}")
            self._print_interrupt_summary()
        finally:
            self._cleanup()
    
    def _print_interrupt_summary(self) -> None:
        """中断时打印统计摘要"""
        try:
            # 尝试获取当前余额作为结束余额
            self.browser.click_tab(0)
            time.sleep(0.5)
            balance_text = self.browser.get_text(self.XPATH["available_balance"])
            if balance_text:
                try:
                    end_balance = float(balance_text.split(" ")[0])
                    self.stats.set_end_balance(end_balance)
                    info(f"当前余额: {end_balance:.4f}")
                except (ValueError, IndexError):
                    pass
        except Exception:
            pass
        
        # 打印统计摘要
        if self.stats.start_balance > 0:
            self.stats.print_summary()
        else:
            warning("无有效统计数据（未开始交易）")
    
    def _connect(self) -> bool:
        """连接到浏览器"""
        from browser_manager import get_current_page_url, ensure_chrome_running
        
        # ========== 1. 确保 Chrome 运行 ==========
        port = self.config.browser.port
        chrome_path = self.config.browser.chrome_path
        user_data_dir = self.config.browser.user_data_dir
        
        # 自动生成 user_data_dir（如果未指定）
        if not user_data_dir:
            user_data_dir = f"D:\\tmp\\cdp{port}"
        
        if not ensure_chrome_running(port, chrome_path, user_data_dir):
            error("无法启动 Chrome，请检查配置")
            return False
        
        # ========== 2. 获取当前页面 URL ==========
        current_url = None
        for attempt in range(10):
            url = get_current_page_url(port)
            
            if url and "devtools" not in url:
                current_url = url
                success(f"获取到目标页面: {url[:60]}...")
                break
            
            warning(f"尝试获取页面 ({attempt + 1}/10)...")
            time.sleep(10)
        else:
            error("无法获取有效页面，程序退出")
            return False
        
        # 连接浏览器
        if not self.browser.connect(current_url):
            return False
            
        if current_url and "accounts.binance.com" in current_url:
            warning("⚠️ 警告: 当前连接的是账户安全页面，可能无法进行交易！")
            warning("请确保浏览器已打开 Binance 现货交易页面")
        
        desired_url = (self.config.browser.target_url or "").strip()
        if desired_url:
            if not self.browser.page:
                error("未找到可切换的页面实例")
                return False
            page_url = self.browser.get_current_url()
            if not page_url or desired_url not in page_url:
                info(f"跳转至配置的目标页面: {desired_url}")
                try:
                    self.browser.page.goto(
                        desired_url,
                        wait_until="domcontentloaded",
                        timeout=max(self.config.browser.timeout, 10000)
                    )
                    success("目标页面就绪")
                except Exception as e:
                    error(f"跳转目标页面失败: {e}")
                    return False
            self.target_url = desired_url
        else:
            self.target_url = current_url or self.browser.get_current_url()
        
        return True
    
    def _main_loop(self) -> None:
        """
        主交易循环 - 纯反向订单模式
        
        流程：买入+挂反向卖单 → 等待反向卖单成交 → 完成1次交易 → 继续买入...
        """
        while True:
            loop_start = time.time()
            self.loop_count += 1
            
            step(f"循环 {self.loop_count} - 已完成 {self.complete_trades}/{self.config.trade.total_runs} 笔交易")
            
            # 定期刷新
            if self.loop_count % self.config.interval.refresh_interval == 0:
                self._refresh_page("定期刷新页面")
            
            # 加载页面数据（获取当前价格）
            if not self._load_page_data():
                continue
            
            # ========== 步骤1：执行买入 + 挂反向卖单 ==========
            buy_result = self._execute_buy_with_reverse()
            
            if not buy_result["success"]:
                # 买入失败，短暂等待后重试
                time.sleep(2)
                continue
            
            # ========== 步骤2：检查是否已完成完整交易 ==========
            if buy_result.get("complete_trade", False):
                # 买卖都已成交，直接计数！
                self.complete_trades += 1
                success(f"🎉 完成第 {self.complete_trades} 笔完整交易！（买卖快速成交）")
            else:
                # ========== 步骤2b：等待反向卖单成交 ==========
                info("等待反向卖单成交...")
                reverse_filled = self._wait_for_reverse_order_filled(
                    initial_holding=buy_result["holding"],
                    max_wait=self.config.interval.reverse_order_timeout
                )
                
                if reverse_filled:
                    # 反向卖单成交 = 完成1次完整交易！
                    self.complete_trades += 1
                    success(f"🎉 完成第 {self.complete_trades} 笔完整交易！（反向卖单自动成交）")
                else:
                    # 超时未成交，主动市价卖出（_market_sell 内部会先取消挂单）
                    warning("反向卖单超时，主动市价卖出")
                    
                    # 主动市价卖出（确保不卡住，最多重试3次）
                    sell_success = False
                    for retry in range(3):
                        if self._market_sell():
                            sell_success = True
                            break
                        else:
                            warning(f"市价卖出失败，重试 ({retry+1}/3)...")
                            time.sleep(2)
                    
                    self.complete_trades += 1
                    if sell_success:
                        success(f"🎉 完成第 {self.complete_trades} 笔完整交易！（主动卖出成交）")
                    else:
                        warning(f"⚠️ 第 {self.complete_trades} 笔交易：卖出可能未完成，请手动检查！")
            
            # ========== 步骤3：检查是否达标 ==========
            if self.complete_trades >= self.config.trade.total_runs:
                self._finalize()
                break
            
            # 统计与休眠
            elapsed_time(loop_start, "本次耗时")
            elapsed_time(self.start_time, "总耗时")
            info(f"📊 进度: {self.complete_trades}/{self.config.trade.total_runs}")
            random_sleep(
                self.config.interval.min_interval,
                self.config.interval.max_interval
            )
    
    def _load_page_data(self) -> bool:
        """加载页面数据"""
        info("页面加载中...")
        
        # 多个价格选择器，按优先级尝试
        price_xpaths = [
            ("主选择器", self.XPATH["current_price"]),
            ("备用选择器", self.XPATH["current_price_alt"]),
        ]
        
        retry_count = 0
        while True:
            self.browser.check_verification()
            
            # 滚动到顶部
            self.browser.scroll_to("top")
            
            # 滚动成交记录到顶部
            self.browser.scroll_to("top", xpath=self.XPATH["grid_scroll"])
            
            # 等待一下让页面渲染
            time.sleep(1)
            
            # 尝试多个选择器获取价格
            for selector_name, xpath in price_xpaths:
                try:
                    price_text = self.browser.get_text(xpath)
                    
                    # 调试输出原始获取内容
                    if retry_count % 3 == 0:
                        info(f"[{selector_name}] 获取到的原始价格文本: '{price_text}'")
                    
                    if price_text:
                        # 清理价格文本：去除空格、换行、逗号等
                        cleaned_price = price_text.strip().replace(',', '').replace('\n', '').replace(' ', '')
                        
                        # 尝试提取数字部分（处理可能包含其他字符的情况）
                        price_match = re.search(r'[\d.]+', cleaned_price)
                        if price_match:
                            price_value = float(price_match.group())
                            if price_value > 0:
                                self.buy_price = price_value
                                success(f"价格数据加载完成 [{selector_name}]: {self.buy_price}")
                                return True
                            
                except (ValueError, TypeError) as e:
                    if retry_count % 3 == 0:
                        warning(f"[{selector_name}] 价格解析异常: {e}")
                except Exception as e:
                    if retry_count % 3 == 0:
                        warning(f"[{selector_name}] 获取价格出错: {e}")
            
            retry_count += 1
            warning(f"获取价格失败 (第{retry_count}次)，继续尝试...")
            time.sleep(10)
    
    def _market_sell(self) -> bool:
        """
        市价卖出当前持仓（反向卖单超时时使用）
        优化：先取消挂单释放锁定的资产，再获取实际持仓进行卖出
        
        Returns:
            是否卖出成功
        """
        info("执行市价卖出...")
        
        # ===== 关键修复：先取消所有挂单，释放被锁定的资产 =====
        pending_count = self._get_pending_order_count()
        if pending_count > 0:
            warning(f"发现 {pending_count} 个挂单锁定资产，先取消...")
            self.browser.scroll_to("bottom")
            self._cancel_orders()
            time.sleep(1)  # 等待取消生效
            
            # 验证取消结果
            remaining = self._get_pending_order_count()
            if remaining > 0:
                warning(f"仍有 {remaining} 个挂单，再次尝试取消...")
                self._cancel_orders()
                time.sleep(1)
        
        # 切换到卖出 Tab
        self.browser.click_tab(1)
        time.sleep(0.5)
        
        # 获取持仓数量（取消挂单后再获取，这样才能拿到真实可用数量）
        holding = self._get_current_holding()
        info(f"当前可卖持仓: {holding}")
        
        min_sell = self.config.trade.min_sell_amount
        if holding <= min_sell:
            info(f"持仓 {holding} <= 最小卖出量 {min_sell}，无需卖出")
            return True  # 没有持仓也算成功
        
        # 优化：尝试获取当前最新价格，而不是使用买入时的旧价格
        current_price = self.buy_price # 默认回退值
        try:
            # 尝试从盘口/输入框获取最新价格
            price_text = self.browser.get_text(self.XPATH["current_price"])
            if not price_text:
                price_text = self.browser.get_text(self.XPATH["current_price_alt"])
            
            if price_text:
                cleaned = price_text.strip().replace(',', '').replace('\n', '').replace(' ', '')
                match = re.search(r'[\d.]+', cleaned)
                if match:
                    current_price = float(match.group())
                    info(f"获取到最新市价: {current_price}")
        except Exception as e:
            warning(f"获取最新市价失败，使用旧价格: {e}")

        # 填写卖出价格（略低于当前市价，确保快速成交）
        # 这里使用 0.9995 (万5滑点) 确保一定要卖出去，防止卡单
        sell_price = current_price * 0.9995
        info(f"市价卖出价: {sell_price:.6f}")
        self.browser.fill_input(self.XPATH["limit_price"], sell_price)
        
        # 填写卖出数量
        sell_amount = holding - self.config.trade.reserved_amount
        info(f"卖出数量: {sell_amount:.4f}")
        self.browser.fill_input(self.XPATH["limit_amount"], sell_amount)
        
        # 不勾选反向订单
        self.browser.scroll_to("bottom", xpath=self.XPATH["trade_scroll"])
        self.browser.toggle_checkbox(self.CSS["checkbox"], should_check=False)
        self.browser.scroll_to("bottom")
        
        # 提交卖出
        info("点击卖出")
        if not self.browser.click(self.XPATH["sell_button"]):
            warning("点击卖出按钮失败")
            return False
        
        time.sleep(0.3)
        
        # 确认
        if self.browser.click(self.XPATH["confirm_button"], timeout=1):
            success("✅ 市价卖出已成交")
            self.browser.click(self.XPATH["continue_button"], timeout=1)
            return True
        elif self.browser.click(self.XPATH["confirm_slippage"], timeout=0.5):
            success("✅ 市价卖出已成交")
            return True
        
        warning("卖出确认失败")
        return False
    
    def _force_sell_all(self) -> None:
        """
        强制清仓卖出（仅用于结束时清仓）
        """
        info("执行清仓卖出...")
        self._market_sell()
    
    def _cancel_orders(self) -> None:
        """取消未成交订单"""
        # 检查是否有挂单
        initial_count = self._get_pending_order_count()
        if initial_count == 0:
            info("无挂单需要取消")
            return

        info(f"检查未成交挂单 (共 {initial_count} 个)...")
        
        # 向右滚动订单表格（确保取消按钮可见）
        self.browser.scroll_to("right", xpath=self.XPATH["order_table"])
        time.sleep(0.5)
        
        # 尝试多次取消，直到没有挂单
        max_retries = 3
        for i in range(max_retries):
            cancelled = False
            
            # 方法1: 尝试点击表头的取消全部按钮 (最优先)
            if not cancelled:
                if self.browser.click(self.XPATH["cancel_all_btn"], timeout=2):
                    info("点击了取消全部按钮")
                    cancelled = True
            
            # 方法2: 尝试点击订单行的取消链接
            if not cancelled:
                if self.browser.click(self.XPATH["cancel_order_link"], timeout=1):
                    info("点击了取消链接")
                    cancelled = True
            
            # 方法3: 尝试点击单个订单取消按钮
            if not cancelled:
                if self.browser.click(self.XPATH["cancel_single_btn"], timeout=1):
                    info("点击了单个取消按钮")
                    cancelled = True
            
            if cancelled:
                # 确认取消弹窗
                time.sleep(0.5)
                confirm_clicked = self.browser.click(self.XPATH["cancel_confirm"], timeout=2)
                if not confirm_clicked:
                    confirm_clicked = self.browser.click(self.XPATH["cancel_confirm_alt"], timeout=2)
                
                if confirm_clicked:
                    success("✅ 点击确认取消")
                    self.stats.record_cancel(True)
                    time.sleep(1) # 等待取消生效
                else:
                    warning("未找到确认取消按钮")
            
            # 检查是否还有挂单
            current_count = self._get_pending_order_count()
            if current_count == 0:
                success("✅ 所有挂单已取消")
                break
            else:
                if i < max_retries - 1:
                    warning(f"仍有 {current_count} 个挂单，重试取消 ({i+1}/{max_retries})...")
                    # 重新滚动一下
                    self.browser.scroll_to("bottom") 
                    self.browser.scroll_to("right", xpath=self.XPATH["order_table"])
                    time.sleep(1)
    
    def _execute_buy_with_reverse(self) -> dict:
        """
        执行买入操作（带反向卖单）
        
        Returns:
            dict: {
                "success": bool,  # 买入是否成功
                "holding": float,  # 买入后的持仓数量（用于后续检测反向卖单成交）
                "buy_price": float,  # 买入价格
                "complete_trade": bool,  # 是否已完成完整交易（买卖都成交）
            }
        """
        result = {"success": False, "holding": 0, "buy_price": 0, "complete_trade": False}
        buy_start = time.time()
        
        # 滚动到顶部
        self.browser.scroll_to("top")
        self.browser.scroll_to("top", xpath=self.XPATH["grid_scroll_alt"])
        
        # 切换到买入
        info("切换买入")
        self.browser.click_tab(0)
        
        # 获取最新价格
        price_text = self.browser.get_text(self.XPATH["current_price"])
        if price_text:
            self.buy_price = float(price_text)
        info(f"当前成交价: {self.buy_price}")
        
        # 获取余额（重要：记录买入前余额用于后续判断）
        balance_text = self.browser.get_text(self.XPATH["available_balance"])
        balance_before = 0
        if balance_text:
            try:
                balance_before = float(balance_text.split(" ")[0])
            except (ValueError, IndexError):
                balance_before = 0
            info(f"可用余额: {balance_before:.2f}")
            
            # 第一次记录余额
            if self.loop_count == 1:
                self._save_balance(balance_before)
                self.stats.set_start_balance(balance_before)
        
        # ========== 余额检查 ==========
        required_balance = self.config.trade.cost * 1.01
        if balance_before < required_balance:
            warning(f"⚠️ 余额不足！需要: {required_balance:.2f}, 当前: {balance_before:.2f}")
            self.insufficient_balance_count += 1
            
            # 检查是否有待成交的反向卖单
            pending_count = self._get_pending_order_count()
            if pending_count > 0:
                info(f"有 {pending_count} 个挂单等待成交")
                
                # 如果连续2次余额不足且有挂单，主动市价卖出（会自动先取消挂单）
                if self.insufficient_balance_count >= 2:
                    warning(f"⚠️ 连续 {self.insufficient_balance_count} 次余额不足，主动市价卖出")
                    
                    # 市价卖出持仓（内部会先取消挂单释放资产）
                    sell_success = False
                    for retry in range(3):
                        if self._market_sell():
                            sell_success = True
                            break
                        warning(f"市价卖出失败，重试 ({retry+1}/3)...")
                        time.sleep(2)
                    
                    if sell_success:
                        self.complete_trades += 1
                        success(f"🎉 完成第 {self.complete_trades} 笔交易！（主动市价卖出）")
                        self.insufficient_balance_count = 0
                        
                        # 标记为已完成完整交易，主循环不需要再处理
                        result["success"] = True
                        result["complete_trade"] = True
                        duration_ms = (time.time() - buy_start) * 1000
                        self.stats.record_buy(self.buy_price, 0, True, duration_ms, "主动市价卖出")
                        return result
                    else:
                        # 卖出失败，强制计为完成避免卡住
                        warning("⚠️ 市价卖出失败，强制跳过避免卡住")
                        self.complete_trades += 1
                        self.insufficient_balance_count = 0
                        result["success"] = True
                        result["complete_trade"] = True
                        return result
                else:
                    # 第一次余额不足，等待一小段时间
                    info(f"等待挂单成交... ({self.insufficient_balance_count}/2)")
                    time.sleep(5)
            
            if self.insufficient_balance_count >= 5:
                self._refresh_page("余额不足，刷新页面")
                self.insufficient_balance_count = 0
            
            duration_ms = (time.time() - buy_start) * 1000
            self.stats.record_buy(self.buy_price, 0, False, duration_ms, f"余额不足: {balance_before:.2f}")
            return result
        
        self.insufficient_balance_count = 0
        
        # ========== 勾选反向订单 ==========
        info("勾选反向订单")
        if not self.browser.toggle_checkbox(self.CSS["checkbox"], should_check=True):
            self._refresh_page("复选框失败，刷新页面")
            duration_ms = (time.time() - buy_start) * 1000
            self.stats.record_buy(self.buy_price, 0, False, duration_ms, "复选框操作失败")
            return result
        
        # ========== 填写买入信息 ==========
        buy_price = self.buy_price * self.config.price.buy_price_percent + self.config.price.buy_price_diff
        info(f"输入买价: {buy_price:.6f}")
        self.browser.fill_input(self.XPATH["limit_price"], buy_price)
        
        info(f"输入成交额: {self.config.trade.cost}")
        self.browser.fill_input(self.XPATH["limit_total_buy"], self.config.trade.cost)
        
        # 填写反向卖单价格
        reverse_sell_price = buy_price * self.config.price.sell_price_percent
        info(f"输入反向卖价: {reverse_sell_price:.6f}")
        self.browser.fill_input(self.XPATH["limit_total_sell"], reverse_sell_price)
        
        # ========== 提交订单 ==========
        self.browser.scroll_to("bottom", xpath=self.XPATH["trade_scroll"])
        self.browser.scroll_to("bottom")
        
        info("点击购买")
        if not self.browser.click(self.XPATH["buy_button"], timeout=5):
            warning("点击购买按钮失败")
            duration_ms = (time.time() - buy_start) * 1000
            self.stats.record_buy(buy_price, 0, False, duration_ms, "点击购买按钮失败")
            return result
        
        # 快速确认
        time.sleep(0.3)
        confirm_clicked = self.browser.click(self.XPATH["confirm_button"], timeout=1)
        
        if not confirm_clicked:
            if self.browser.click(self.XPATH["cancel_slippage"], timeout=0.5):
                warning("滑点过大，取消交易")
                duration_ms = (time.time() - buy_start) * 1000
                self.stats.record_buy(buy_price, 0, False, duration_ms, "滑点过大")
                return result
            
            confirm_clicked = self.browser.click(self.XPATH["confirm_button"], timeout=1)
            if not confirm_clicked:
                warning("未能点击确认按钮")
                duration_ms = (time.time() - buy_start) * 1000
                self.stats.record_buy(buy_price, 0, False, duration_ms, "未能点击确认按钮")
                return result
        
        # 等待订单提交完成
        time.sleep(0.8)
        
        # ========== 验证交易结果（核心修复：检测余额变化） ==========
        info("验证交易结果...")
        
        # 切换回买入Tab获取最新余额
        self.browser.click_tab(0)
        time.sleep(0.3)
        
        balance_text = self.browser.get_text(self.XPATH["available_balance"])
        balance_after = 0
        if balance_text:
            try:
                balance_after = float(balance_text.split(" ")[0])
            except (ValueError, IndexError):
                pass
        
        balance_change = balance_after - balance_before
        expected_amount = self.config.trade.cost / buy_price if buy_price > 0 else 0
        
        info(f"余额变化: {balance_before:.2f} -> {balance_after:.2f} (变化: {balance_change:+.2f})")
        
        # ========== 判断交易状态 ==========
        # 情况1：余额几乎不变（变化小于成本的5%），说明买卖都快速成交了！
        if abs(balance_change) < self.config.trade.cost * 0.05:
            duration_ms = (time.time() - buy_start) * 1000
            self.stats.record_buy(buy_price, expected_amount, True, duration_ms)
            success(f"🎉 完整交易已成交！买入+卖出都已完成（余额变化: {balance_change:+.2f}）")
            
            result["success"] = True
            result["holding"] = 0  # 买卖都成交了，持仓回到原来
            result["buy_price"] = buy_price
            result["complete_trade"] = True  # 标记为完整交易已完成
            return result
        
        # 情况2：余额大幅减少（约等于成本），说明买单成交，等待反向卖单
        if balance_change < -self.config.trade.cost * 0.5:
            # 切换到卖出Tab查看持仓
            self.browser.click_tab(1)
            time.sleep(0.3)
            holding = self._get_current_holding()
            
            duration_ms = (time.time() - buy_start) * 1000
            self.stats.record_buy(buy_price, expected_amount, True, duration_ms)
            success(f"✅ 买入成交！持仓: {holding:.4f}，等待反向卖单...")
            
            result["success"] = True
            result["holding"] = holding
            result["buy_price"] = buy_price
            return result
        
        # 情况3：余额未明显变化，可能订单还在挂单中
        info(f"订单可能在挂单中，等待成交...")
        
        # 等待并检查成交状态
        for wait_sec in range(1, self.buy_order_timeout + 1):
            time.sleep(1)
            
            # 检查验证弹窗
            self.browser.check_verification()
            
            # 获取最新余额
            self.browser.click_tab(0)
            balance_text = self.browser.get_text(self.XPATH["available_balance"])
            if balance_text:
                try:
                    current_balance = float(balance_text.split(" ")[0])
                    balance_change = current_balance - balance_before
                    
                    # 如果余额几乎恢复，说明买卖都成交了
                    if abs(balance_change) < self.config.trade.cost * 0.05:
                        duration_ms = (time.time() - buy_start) * 1000
                        self.stats.record_buy(buy_price, expected_amount, True, duration_ms)
                        success(f"🎉 等待后完整交易成交！（{wait_sec}s，余额变化: {balance_change:+.2f}）")
                        
                        result["success"] = True
                        result["holding"] = 0
                        result["buy_price"] = buy_price
                        result["complete_trade"] = True
                        return result
                    
                    # 如果余额大幅减少，说明买单成交了
                    if balance_change < -self.config.trade.cost * 0.5:
                        self.browser.click_tab(1)
                        time.sleep(0.3)
                        holding = self._get_current_holding()
                        
                        duration_ms = (time.time() - buy_start) * 1000
                        self.stats.record_buy(buy_price, expected_amount, True, duration_ms)
                        success(f"✅ 等待后买入成交！持仓: {holding:.4f}")
                        
                        result["success"] = True
                        result["holding"] = holding
                        result["buy_price"] = buy_price
                        return result
                        
                except (ValueError, IndexError):
                    pass
            
            pending_count = self._get_pending_order_count()
            info(f"等待中... {wait_sec}s, 余额: {current_balance:.2f}, 挂单: {pending_count}")
        
        # 超时未成交，取消买单
        warning("买单超时未成交，取消买单")
        self._cancel_orders()
        duration_ms = (time.time() - buy_start) * 1000
        self.stats.record_buy(buy_price, 0, False, duration_ms, "买单超时未成交")
        
        return result
    
    def _get_current_holding(self) -> float:
        """获取当前持仓数量"""
        raw_value = self.browser.get_text(self.XPATH["available_balance"])
        if not raw_value:
            return 0
        
        match = re.search(r'[\d,]+(?:\.\d+)?', raw_value)
        if not match:
            return 0
        
        return float(match.group(0).replace(',', ''))
    
    def _wait_for_reverse_order_filled(self, initial_holding: float, max_wait: int = 60) -> bool:
        """
        等待反向卖单成交
        
        判断依据（任一满足即为成交）：
        1. 挂单消失（从有变成无）
        2. 余额恢复（说明卖单成交回款）
        3. 持仓明显减少
        
        Args:
            initial_holding: 买入后的初始持仓
            max_wait: 最大等待时间（秒）
        
        Returns:
            是否成交
        """
        info(f"等待反向卖单成交，初始持仓: {initial_holding:.4f}，最长等待 {max_wait} 秒")
        
        start_time = time.time()
        check_interval = 3  # 每3秒检查一次
        
        # 记录初始状态
        had_pending_orders = True  # 假设刚下单时有挂单
        initial_pending_count = -1  # 初始挂单数量（-1 表示未知）
        
        while time.time() - start_time < max_wait:
            time.sleep(check_interval)
            
            # 检查验证弹窗
            self.browser.check_verification()
            
            # 检查挂单数量（核心判断依据）
            pending_count = self._get_pending_order_count()
            
            # 记录第一次检测到的挂单数
            if initial_pending_count == -1:
                initial_pending_count = pending_count
                had_pending_orders = pending_count > 0
            
            elapsed = int(time.time() - start_time)
            
            # ========== 判断条件1：挂单消失 ==========
            # 如果之前有挂单，现在没有了 = 成交！
            if had_pending_orders and pending_count == 0:
                success(f"✅ 反向卖单已成交！（挂单已消失，{elapsed}s）")
                return True
            
            # ========== 判断条件2：检查余额恢复 ==========
            # 切换到买入Tab检查余额
            self.browser.click_tab(0)
            time.sleep(0.2)
            balance_text = self.browser.get_text(self.XPATH["available_balance"])
            current_balance = 0
            if balance_text:
                try:
                    current_balance = float(balance_text.split(" ")[0])
                except (ValueError, IndexError):
                    pass
            
            # 如果余额大于等于买入成本（说明卖单已成交回款）
            if current_balance >= self.config.trade.cost * 0.9:
                success(f"✅ 反向卖单已成交！（余额已恢复: {current_balance:.2f}，{elapsed}s）")
                return True
            
            # ========== 判断条件3：检查持仓变化 ==========
            self.browser.click_tab(1)
            time.sleep(0.2)
            current_holding = self._get_current_holding()
            
            # 如果持仓明显减少
            if current_holding < initial_holding * 0.5:
                success(f"✅ 反向卖单已成交！持仓: {initial_holding:.4f} → {current_holding:.4f}")
                return True
            
            info(f"等待中... {elapsed}s, 余额: {current_balance:.2f}, 挂单: {pending_count}")
        
        warning(f"等待 {max_wait} 秒后反向卖单仍未成交")
        return False
    
    def _finalize(self) -> None:
        """完成交易后的清理和统计"""
        step("完成交易，执行最终状态检查")
        
        # ========== 1. 等待最后一笔交易结算 ==========
        info("等待最后一笔交易结算 (10s)...")
        time.sleep(10)
        
        # ========== 2. 检查并取消未成交订单 ==========
        self.browser.scroll_to("bottom")
        pending_count = self._get_pending_order_count()
        if pending_count > 0:
            info(f"发现 {pending_count} 个未成交订单，执行取消...")
            self._cancel_orders()
            time.sleep(3)
        
        # ========== 3. 检查并清仓 ==========
        self.browser.scroll_to("top")
        self.browser.click_tab(1)  # 切换到卖出Tab
        time.sleep(0.5)
        
        holding = self._get_current_holding()
        if holding and holding > self.config.trade.min_sell_amount:
            info(f"发现持仓 {holding:.4f}，执行清仓...")
            self._force_sell_all()
            time.sleep(5)
        else:
            info("无需清仓，持仓为空或低于最小卖出量")
        
        # ========== 4. 等待余额稳定 ==========
        info("等待余额稳定 (5s)...")
        time.sleep(5)
        
        # ========== 5. 获取最终余额（多次采样确保稳定）==========
        final_balance = None
        balance_samples = []
        
        for retry in range(5):
            self.browser.click_tab(0)
            time.sleep(1)
            
            balance_text = self.browser.get_text(self.XPATH["available_balance"])
            if balance_text:
                try:
                    balance = float(balance_text.split(" ")[0])
                    if balance > 0:
                        balance_samples.append(balance)
                        # 连续2次相同则认为稳定
                        if len(balance_samples) >= 2 and balance_samples[-1] == balance_samples[-2]:
                            final_balance = balance
                            info(f"余额已稳定: {final_balance:.4f}")
                            break
                except (ValueError, IndexError):
                    pass
            
            if retry < 4:
                info(f"确认余额中... ({retry+1}/5)")
                time.sleep(2)
        
        # 如果没有连续相同，取最后一个有效值
        if final_balance is None and balance_samples:
            final_balance = balance_samples[-1]
            info(f"使用最后采样余额: {final_balance:.4f}")
        
        # ========== 6. 记录并统计 ==========
        if final_balance is not None and final_balance > 0:
            success(f"✅ 最终余额: {final_balance:.4f} USDT")
            self._save_balance(final_balance)
            self.stats.set_end_balance(final_balance)
        else:
            warning("⚠️ 无法获取最终余额，统计数据可能不准确")
        
        elapsed_time(self.start_time, "总运行时间")
        
        # 打印交易统计摘要
        self.stats.print_summary()
        
        # 保存统计数据
        self.stats.save_to_file()
    
    def _refresh_page(self, reason: str) -> None:
        """刷新页面"""
        info(reason)
        self.browser.scroll_to("top")
        self.browser.refresh_until_element(
            self.target_url,
            self.XPATH["page_loaded"],
            delay=60
        )
    
    def _get_pending_order_count(self) -> int:
        """
        获取当前标的的待成交订单数量
        
        Returns:
            待成交订单数量
        """
        try:
            # 通过 JavaScript 获取当前标的的订单数量
            # 只统计 "当前委托" Tab 下的订单（id='bn-tab-pane-orderOrder'）
            count = self.browser.page.evaluate("""
                () => {
                    // 方法1：查找当前委托 Tab 下的订单表格
                    const orderPane = document.querySelector('#bn-tab-pane-orderOrder');
                    if (orderPane) {
                        const rows = orderPane.querySelectorAll('tbody.bn-web-table-tbody > tr[aria-rowindex]');
                        return rows ? rows.length : 0;
                    }
                    
                    // 方法2：回退到通用选择器（可能不精准）
                    const rows = document.querySelectorAll('tbody.bn-web-table-tbody > tr[aria-rowindex]');
                    return rows ? rows.length : 0;
                }
            """)
            return count if count else 0
        except Exception as e:
            warning(f"获取挂单数量失败: {e}")
            return 0
    
    def _wait_for_buy_order_filled(
        self, 
        initial_holding: float = 0, 
        expected_amount: float = 0,
        max_wait: int = 10, 
        check_interval: int = 2
    ) -> bool:
        """
        等待买单成交（通过持仓变化判断）
        
        Args:
            initial_holding: 初始持仓
            expected_amount: 预期买入数量
            max_wait: 最大等待时间（秒）
            check_interval: 检查间隔（秒）
        
        Returns:
            是否成交
        """
        info(f"等待买单成交，初始持仓: {initial_holding:.4f}，最长 {max_wait} 秒...")
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            time.sleep(check_interval)
            
            # 检查验证弹窗
            self.browser.check_verification()
            
            # 检查持仓变化
            current_holding = self._get_current_holding()
            
            # 如果持仓增加了（买入成交）
            if current_holding >= initial_holding + expected_amount * 0.5:
                success(f"✅ 买单已成交！持仓: {initial_holding:.4f} → {current_holding:.4f}")
                return True
            
            elapsed = int(time.time() - start_time)
            pending_count = self._get_pending_order_count()
            info(f"等待买单... {elapsed}s, 持仓: {current_holding:.4f}, 挂单: {pending_count}")
        
        warning(f"等待 {max_wait} 秒后买单仍未成交")
        return False
    
    def _verify_buy_success(self, buy_price: float) -> bool:
        """
        验证买入是否成功（通过检查持仓变化）
        
        Args:
            buy_price: 买入价格
        
        Returns:
            是否买入成功
        """
        # 切换到卖出 Tab 检查持仓
        info("验证买入结果...")
        self.browser.click_tab(1)
        time.sleep(0.3)
        
        # 获取持仓数量
        raw_value = self.browser.get_text(self.XPATH["available_balance"])
        if not raw_value:
            warning("无法获取持仓，无法验证买入结果")
            return False
        
        match = re.search(r'[\d,]+(?:\.\d+)?', raw_value)
        if not match:
            warning("解析持仓失败")
            return False
        
        current_holding = float(match.group(0).replace(',', ''))
        
        # 计算预期买入数量
        expected_amount = self.config.trade.cost / buy_price if buy_price > 0 else 0
        
        # 如果持仓大于预期买入量的一半，认为买入成功
        # （允许一定误差，因为可能有部分成交）
        if current_holding >= expected_amount * 0.5:
            info(f"✅ 验证通过！持仓: {current_holding:.4f}, 预期买入: {expected_amount:.4f}")
            return True
        else:
            # 持仓不足，可能买单还在挂单中
            pending_count = self._get_pending_order_count()
            if pending_count > 0:
                info(f"持仓: {current_holding:.4f}, 有 {pending_count} 个挂单等待成交")
                # 等待一小段时间再检查
                time.sleep(self.buy_order_timeout)
                
                # 再次检查持仓
                raw_value = self.browser.get_text(self.XPATH["available_balance"])
                if raw_value:
                    match = re.search(r'[\d,]+(?:\.\d+)?', raw_value)
                    if match:
                        new_holding = float(match.group(0).replace(',', ''))
                        if new_holding > current_holding:
                            info(f"✅ 等待后成交！持仓: {current_holding:.4f} -> {new_holding:.4f}")
                            return True
                
                # 仍未成交，取消挂单
                warning(f"买单 {self.buy_order_timeout}s 未成交，取消挂单")
                self.browser.scroll_to("bottom")
                self._cancel_orders()
                return False
            else:
                warning(f"持仓不足且无挂单: {current_holding:.4f}")
                return False
    
    def _wait_for_sell_order_filled(self, max_wait: int = 30, check_interval: int = 3) -> bool:
        """
        等待卖单成交（优化版：减少Tab切换）
        
        Args:
            max_wait: 最大等待时间（秒），优化为30秒
            check_interval: 检查间隔（秒），优化为3秒
        
        Returns:
            是否等待成功
        """
        info(f"等待卖单成交，最长 {max_wait} 秒...")
        
        # 获取初始余额（只获取一次）
        initial_balance = self._get_usdt_balance_fast()
        if initial_balance is None:
            initial_balance = 0
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            time.sleep(check_interval)
            
            # 优先检查挂单数量（不需要切换Tab）
            pending_count = self._get_pending_order_count()
            
            # 如果没有挂单了，说明已经成交
            if pending_count == 0:
                success("✅ 卖单已成交！（无挂单）")
                return True
            
            # 检查余额变化（减少频率）
            elapsed = int(time.time() - start_time)
            if elapsed % 6 == 0:  # 每6秒检查一次余额
                current_balance = self._get_usdt_balance_fast()
                if current_balance and current_balance > initial_balance + 1:
                    success(f"✅ 卖单已成交！余额: {initial_balance:.2f} -> {current_balance:.2f}")
                    return True
                balance_str = f"{current_balance:.2f}" if current_balance else "N/A"
                info(f"等待中... {elapsed}s, 挂单: {pending_count}, 余额: {balance_str}")
        
        warning(f"等待 {max_wait} 秒后仍未成交")
        return False
    
    def _get_usdt_balance(self) -> Optional[float]:
        """
        获取 USDT 余额（会切换到买入Tab）
        
        Returns:
            USDT 余额或 None
        """
        # 切换到买入 Tab 获取 USDT 余额
        self.browser.click_tab(0)
        time.sleep(0.3)  # 缩短等待时间
        
        return self._get_usdt_balance_fast()
    
    def _get_usdt_balance_fast(self) -> Optional[float]:
        """
        快速获取 USDT 余额（不切换Tab，假设当前已在买入Tab）
        
        Returns:
            USDT 余额或 None
        """
        balance_text = self.browser.get_text(self.XPATH["available_balance"])
        if balance_text:
            try:
                return float(balance_text.split(" ")[0])
            except (ValueError, IndexError):
                pass
        return None
    
    def _save_balance(self, balance: float) -> None:
        """保存余额记录"""
        filename = f"{self.config.trade.username}.csv"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        data = pd.DataFrame([[timestamp, balance]], columns=["时间", "可用余额"])
        file_exists = os.path.exists(filename)
        data.to_csv(filename, mode="a", header=not file_exists, index=False, encoding="utf-8-sig")
        
        info(f"余额已记录: {balance}")
    
    def _cleanup(self) -> None:
        """清理资源"""
        if self.browser:
            self.browser.disconnect()


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Alpha 自动化交易脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                    # 单账号模式（使用环境变量配置）
  python main.py --account "账号A"  # 多账号模式（使用 accounts.yaml 中的配置）
  python main.py --list             # 列出所有账号
        """
    )
    
    parser.add_argument(
        "--account", "-a",
        type=str,
        default=None,
        help="指定要运行的账号名称（对应 accounts.yaml 中的 name）"
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="列出所有账号配置"
    )
    
    return parser.parse_args()


def main():
    """主入口"""
    args = parse_args()
    
    # 列出账号
    if args.list:
        from config import list_accounts
        list_accounts()
        return
    
    try:
        # 根据参数选择配置来源
        if args.account:
            # 多账号模式：从 accounts.yaml 加载指定账号
            config = get_account_config(args.account)
            if not config:
                error(f"未找到账号: {args.account}")
                error("请检查 accounts.yaml 配置文件")
                return
            
            # 切换到账号专属日志
            use_account_logger(args.account)
            step(f"启动账号: {args.account}")
        else:
            # 单账号模式：使用环境变量
            config = get_config()
        
        # 创建并运行交易机器人
        trader = AlphaTrader(config)
        trader.run()
        
    except ValueError as e:
        error(f"配置错误: {e}")
    except Exception as e:
        error(f"启动失败: {e}")
    finally:
        # 重置日志
        reset_logger()


def run_account(account_name: str) -> None:
    """
    运行指定账号（供多进程调用）
    
    Args:
        account_name: 账号名称
    """
    try:
        # 切换到账号专属日志
        use_account_logger(account_name)
        
        # 获取账号配置
        config = get_account_config(account_name)
        if not config:
            error(f"未找到账号配置: {account_name}")
            return
        
        step(f"启动账号: {account_name}")
        
        # 创建并运行交易机器人
        trader = AlphaTrader(config)
        trader.run()
        
    except Exception as e:
        error(f"账号 {account_name} 运行异常: {e}")
    finally:
        reset_logger()


if __name__ == "__main__":
    main()
