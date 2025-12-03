"""
配置管理模块 - 支持环境变量和类型验证
优先从环境变量读取，否则使用默认值
"""
import os
from dataclasses import dataclass, field
from typing import Optional

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_env(key: str, default: str = "", type_cast: type = str):
    """从环境变量获取配置，支持类型转换"""
    value = os.getenv(key, default)
    if value == "" and default == "":
        return default
    try:
        if type_cast == bool:
            return value.lower() in ('true', '1', 'yes')
        return type_cast(value)
    except (ValueError, TypeError):
        return default


@dataclass
class TradeConfig:
    """交易配置"""
    username: str = field(default_factory=lambda: get_env("USERNAME", "我是谁"))
    cost: float = field(default_factory=lambda: get_env("TRADE_COST", "256", float))
    total_runs: int = field(default_factory=lambda: get_env("TOTAL_RUNS", "36", int))
    reserved_amount: float = field(default_factory=lambda: get_env("RESERVED_AMOUNT", "0", float))
    min_sell_amount: float = field(default_factory=lambda: get_env("MIN_SELL_AMOUNT", "1", float))


@dataclass
class BrowserConfig:
    """浏览器配置"""
    port: int = field(default_factory=lambda: get_env("CHROME_PORT", "9222", int))
    timeout: int = field(default_factory=lambda: get_env("PAGE_TIMEOUT", "5000", int))
    target_url: str = field(default_factory=lambda: get_env("TARGET_URL", ""))


@dataclass 
class IntervalConfig:
    """间隔配置"""
    refresh_interval: int = field(default_factory=lambda: get_env("REFRESH_INTERVAL", "5", int))
    min_interval: int = field(default_factory=lambda: get_env("MIN_INTERVAL", "5", int))
    max_interval: int = field(default_factory=lambda: get_env("MAX_INTERVAL", "10", int))
    # 反向订单等待超时时间（秒）- 买入后等待反向卖单成交的最长时间
    # 缩短为30秒，超时后立即市价卖出，避免长时间卡住
    reverse_order_timeout: int = field(default_factory=lambda: get_env("REVERSE_ORDER_TIMEOUT", "30", int))


@dataclass
class PriceConfig:
    """价格配置"""
    # 买入价格上浮百分比
    # 优化：从 1.0002 (万2) 降低到 1.0001 (万1)，降低买入成本但仍保持一定成交速度
    buy_price_percent: float = field(default_factory=lambda: get_env("BUY_PRICE_PERCENT", "1.0001", float))
    
    # 保留旧的固定差值（默认0）
    buy_price_diff: float = field(default_factory=lambda: get_env("BUY_PRICE_DIFF", "0", float))
    
    # 卖出价格百分比
    # 设置为 0.9998 (万2折让)，确保反向卖单能快速成交
    # 如果超时未成交，会有后续的 _market_sell 兜底
    sell_price_percent: float = field(default_factory=lambda: get_env("SELL_PRICE_PERCENT", "0.9998", float))


@dataclass
class SecurityConfig:
    """安全配置"""
    secret: str = field(default_factory=lambda: get_env("GOOGLE_SECRET", ""))
    
    def __post_init__(self):
        if not self.secret:
            print("⚠️ 警告: GOOGLE_SECRET 未设置，验证器功能将不可用")


@dataclass
class Config:
    """主配置类 - 聚合所有配置"""
    trade: TradeConfig = field(default_factory=TradeConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    interval: IntervalConfig = field(default_factory=IntervalConfig)
    price: PriceConfig = field(default_factory=PriceConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    def __post_init__(self):
        self.validate()
    
    def validate(self) -> None:
        """验证配置有效性"""
        errors = []
        
        if self.trade.cost <= 0:
            errors.append("cost 必须大于 0")
        if self.trade.total_runs <= 0:
            errors.append("total_runs 必须大于 0")
        if not (0 < self.price.sell_price_percent <= 1):
            errors.append("sell_price_percent 必须在 0-1 之间")
        if not (1 <= self.price.buy_price_percent <= 1.1):
            errors.append("buy_price_percent 必须在 1-1.1 之间（即最多加价10%）")
        if self.browser.port < 1024 or self.browser.port > 65535:
            errors.append("port 必须在 1024-65535 之间")
            
        if errors:
            raise ValueError(f"配置错误: {'; '.join(errors)}")
    
    def print_config(self) -> None:
        """打印当前配置（隐藏敏感信息）"""
        print("\n📋 当前配置:")
        print(f"  用户名: {self.trade.username}")
        print(f"  端口: {self.browser.port}")
        print(f"  单次交易额: {self.trade.cost}")
        print(f"  执行次数: {self.trade.total_runs}")
        print(f"  保留币数: {self.trade.reserved_amount}")
        print(f"  最小卖出: {self.trade.min_sell_amount}")
        print(f"  刷新间隔: {self.interval.refresh_interval}")
        print(f"  休息间隔: {self.interval.min_interval}-{self.interval.max_interval}s")
        print(f"  反向订单超时: {self.interval.reverse_order_timeout}s")
        print(f"  买价上浮: {(self.price.buy_price_percent - 1) * 100:.2f}%")
        print(f"  买价差值: {self.price.buy_price_diff}")
        print(f"  卖价百分比: {self.price.sell_price_percent}")
        if self.browser.target_url:
            print(f"  目标页面: {self.browser.target_url}")
        print(f"  验证器: {'已配置' if self.security.secret else '未配置'}")
        print()


# ============================================
# 兼容旧版配置 - 保持向后兼容
# ============================================

# 创建全局配置实例
_config = Config()

# 导出旧版变量名（向后兼容）
username = _config.trade.username
cost = _config.trade.cost
total_runs = _config.trade.total_runs
reserved_amount = _config.trade.reserved_amount
min_sell_amount = _config.trade.min_sell_amount
port = _config.browser.port
secret = _config.security.secret
refresh_interval = _config.interval.refresh_interval
min_interval = _config.interval.min_interval
max_interval = _config.interval.max_interval
buy_price_percent = _config.price.buy_price_percent
buy_price_diff = _config.price.buy_price_diff
sell_price_percent = _config.price.sell_price_percent


# 获取配置实例
def get_config() -> Config:
    """获取配置实例"""
    return _config


if __name__ == "__main__":
    # 测试配置
    config = get_config()
    config.print_config()

