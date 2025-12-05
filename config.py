"""
配置管理模块 - 支持环境变量、类型验证和多账号配置
优先从环境变量读取，否则使用默认值
支持从 accounts.yaml 加载多账号配置
"""
import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 尝试加载 YAML 支持
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# ============================================
# 配置文件路径
# ============================================
CONFIG_DIR = Path(__file__).parent
ACCOUNTS_FILE = CONFIG_DIR / "accounts.yaml"


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
    # Chrome 自动启动配置
    chrome_path: str = field(default_factory=lambda: get_env(
        "CHROME_PATH", 
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    ))
    user_data_dir: str = field(default_factory=lambda: get_env("USER_DATA_DIR", ""))  # 留空则自动生成


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
# 多账号配置支持
# ============================================

@dataclass
class AccountConfig:
    """单个账号配置"""
    name: str                          # 账号名称（唯一标识）
    enabled: bool = True               # 是否启用
    port: int = 9222                   # Chrome 调试端口
    secret: str = ""                   # 谷歌验证器密钥
    
    # 交易配置（可选，不填则使用默认值）
    cost: Optional[float] = None
    total_runs: Optional[int] = None
    reserved_amount: Optional[float] = None
    min_sell_amount: Optional[float] = None
    
    # 间隔配置
    refresh_interval: Optional[int] = None
    min_interval: Optional[int] = None
    max_interval: Optional[int] = None
    reverse_order_timeout: Optional[int] = None
    
    # 价格配置
    buy_price_percent: Optional[float] = None
    buy_price_diff: Optional[float] = None
    sell_price_percent: Optional[float] = None
    
    # 浏览器配置
    timeout: Optional[int] = None
    target_url: Optional[str] = None
    chrome_path: Optional[str] = None      # Chrome 可执行文件路径
    user_data_dir: Optional[str] = None    # 用户数据目录


def _load_yaml_file(filepath: Path) -> Optional[Dict[str, Any]]:
    """加载 YAML 文件"""
    if not YAML_AVAILABLE:
        print("⚠️ 警告: pyyaml 未安装，无法加载 accounts.yaml")
        print("   请运行: pip install pyyaml")
        return None
    
    if not filepath.exists():
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"❌ 加载 {filepath} 失败: {e}")
        return None


def load_accounts(filepath: Path = ACCOUNTS_FILE) -> List[AccountConfig]:
    """
    从 YAML 文件加载账号列表
    
    Args:
        filepath: 配置文件路径
    
    Returns:
        AccountConfig 列表（仅包含 enabled=True 的账号）
    """
    data = _load_yaml_file(filepath)
    if not data:
        return []
    
    # 获取默认配置
    defaults = data.get('defaults', {})
    
    # 解析账号列表
    accounts = []
    for acc_data in data.get('accounts', []):
        if not acc_data.get('name'):
            print("⚠️ 跳过无名称的账号配置")
            continue
        
        # 合并默认配置和账号配置
        merged = {**defaults, **acc_data}
        
        try:
            # 自动生成 user_data_dir（如果未指定）
            port = merged.get('port', 9222)
            user_data_base = merged.get('user_data_base', 'D:\\tmp')
            user_data_dir = merged.get('user_data_dir') or f"{user_data_base}\\cdp{port}"
            
            account = AccountConfig(
                name=merged.get('name'),
                enabled=merged.get('enabled', True),
                port=port,
                secret=merged.get('secret', ''),
                cost=merged.get('cost'),
                total_runs=merged.get('total_runs'),
                reserved_amount=merged.get('reserved_amount'),
                min_sell_amount=merged.get('min_sell_amount'),
                refresh_interval=merged.get('refresh_interval'),
                min_interval=merged.get('min_interval'),
                max_interval=merged.get('max_interval'),
                reverse_order_timeout=merged.get('reverse_order_timeout'),
                buy_price_percent=merged.get('buy_price_percent'),
                buy_price_diff=merged.get('buy_price_diff'),
                sell_price_percent=merged.get('sell_price_percent'),
                timeout=merged.get('timeout'),
                target_url=merged.get('target_url'),
                chrome_path=merged.get('chrome_path'),
                user_data_dir=user_data_dir,
            )
            accounts.append(account)
        except Exception as e:
            print(f"⚠️ 解析账号 {acc_data.get('name', '?')} 失败: {e}")
    
    return accounts


def get_enabled_accounts(filepath: Path = ACCOUNTS_FILE) -> List[AccountConfig]:
    """
    获取所有启用的账号
    
    Returns:
        仅包含 enabled=True 的 AccountConfig 列表
    """
    return [acc for acc in load_accounts(filepath) if acc.enabled]


def get_account_by_name(name: str, filepath: Path = ACCOUNTS_FILE) -> Optional[AccountConfig]:
    """
    根据名称获取账号配置
    
    Args:
        name: 账号名称
        filepath: 配置文件路径
    
    Returns:
        AccountConfig 或 None
    """
    for acc in load_accounts(filepath):
        if acc.name == name:
            return acc
    return None


def build_config_from_account(account: AccountConfig) -> Config:
    """
    从 AccountConfig 构建完整的 Config 对象
    
    Args:
        account: 账号配置
    
    Returns:
        完整的 Config 对象
    """
    # 创建 TradeConfig
    trade = TradeConfig(
        username=account.name,
        cost=account.cost if account.cost is not None else get_env("TRADE_COST", "256", float),
        total_runs=account.total_runs if account.total_runs is not None else get_env("TOTAL_RUNS", "36", int),
        reserved_amount=account.reserved_amount if account.reserved_amount is not None else get_env("RESERVED_AMOUNT", "0", float),
        min_sell_amount=account.min_sell_amount if account.min_sell_amount is not None else get_env("MIN_SELL_AMOUNT", "1", float),
    )
    
    # 创建 BrowserConfig
    default_chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    browser = BrowserConfig(
        port=account.port,
        timeout=account.timeout if account.timeout is not None else get_env("PAGE_TIMEOUT", "5000", int),
        target_url=account.target_url if account.target_url is not None else get_env("TARGET_URL", ""),
        chrome_path=account.chrome_path if account.chrome_path is not None else get_env("CHROME_PATH", default_chrome_path),
        user_data_dir=account.user_data_dir if account.user_data_dir is not None else "",
    )
    
    # 创建 IntervalConfig
    interval = IntervalConfig(
        refresh_interval=account.refresh_interval if account.refresh_interval is not None else get_env("REFRESH_INTERVAL", "5", int),
        min_interval=account.min_interval if account.min_interval is not None else get_env("MIN_INTERVAL", "5", int),
        max_interval=account.max_interval if account.max_interval is not None else get_env("MAX_INTERVAL", "10", int),
        reverse_order_timeout=account.reverse_order_timeout if account.reverse_order_timeout is not None else get_env("REVERSE_ORDER_TIMEOUT", "30", int),
    )
    
    # 创建 PriceConfig
    price = PriceConfig(
        buy_price_percent=account.buy_price_percent if account.buy_price_percent is not None else get_env("BUY_PRICE_PERCENT", "1.0001", float),
        buy_price_diff=account.buy_price_diff if account.buy_price_diff is not None else get_env("BUY_PRICE_DIFF", "0", float),
        sell_price_percent=account.sell_price_percent if account.sell_price_percent is not None else get_env("SELL_PRICE_PERCENT", "0.9998", float),
    )
    
    # 创建 SecurityConfig（不触发警告）
    security = SecurityConfig.__new__(SecurityConfig)
    security.secret = account.secret
    
    # 创建 Config（跳过 __post_init__ 中的 validate，稍后手动调用）
    config = Config.__new__(Config)
    config.trade = trade
    config.browser = browser
    config.interval = interval
    config.price = price
    config.security = security
    
    # 验证配置
    config.validate()
    
    return config


def get_account_config(account_name: str, filepath: Path = ACCOUNTS_FILE) -> Optional[Config]:
    """
    根据账号名称获取完整配置
    
    Args:
        account_name: 账号名称
        filepath: 配置文件路径
    
    Returns:
        完整的 Config 对象或 None
    """
    account = get_account_by_name(account_name, filepath)
    if not account:
        print(f"❌ 未找到账号: {account_name}")
        return None
    
    return build_config_from_account(account)


def list_accounts(filepath: Path = ACCOUNTS_FILE) -> None:
    """打印所有账号信息"""
    accounts = load_accounts(filepath)
    
    if not accounts:
        print("📋 未找到任何账号配置")
        print(f"   请检查 {filepath} 是否存在")
        return
    
    print(f"\n📋 账号列表 (共 {len(accounts)} 个):")
    print("-" * 50)
    
    enabled_count = 0
    for acc in accounts:
        status = "✅ 启用" if acc.enabled else "⏸️ 禁用"
        secret_status = "🔐" if acc.secret else "⚠️"
        
        print(f"  {acc.name}")
        print(f"    状态: {status}")
        print(f"    端口: {acc.port}")
        print(f"    验证器: {secret_status}")
        if acc.cost:
            print(f"    交易额: {acc.cost}")
        print()
        
        if acc.enabled:
            enabled_count += 1
    
    print(f"共 {enabled_count} 个账号已启用")


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
    print("=" * 50)
    print("单账号模式（环境变量）")
    print("=" * 50)
    config = get_config()
    config.print_config()
    
    print("\n" + "=" * 50)
    print("多账号模式（accounts.yaml）")
    print("=" * 50)
    list_accounts()
