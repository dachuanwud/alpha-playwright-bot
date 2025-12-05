"""
日志模块 - 统一的日志管理
支持控制台彩色输出和文件记录
包含敏感信息脱敏功能
支持多账号日志隔离
"""
import logging
import os
import re
from datetime import datetime
from typing import Optional, Union, Dict


# ============================================
# 敏感信息脱敏工具
# ============================================

def mask_sensitive(value: str, visible_chars: int = 2, mask_char: str = "*") -> str:
    """
    脱敏处理敏感信息
    
    Args:
        value: 原始值
        visible_chars: 前后保留的可见字符数
        mask_char: 脱敏使用的字符
    
    Returns:
        脱敏后的字符串
    
    Examples:
        >>> mask_sensitive("123456")
        "12**56"
        >>> mask_sensitive("abc", visible_chars=1)
        "a*c"
    """
    if not value or len(value) <= visible_chars * 2:
        return mask_char * len(value) if value else ""
    
    return value[:visible_chars] + mask_char * (len(value) - visible_chars * 2) + value[-visible_chars:]


def mask_verification_code(code: str) -> str:
    """脱敏验证码（显示前2位后2位）"""
    return mask_sensitive(code, visible_chars=2)


def mask_balance(balance: Union[float, str], precision: int = 0) -> str:
    """
    脱敏余额（只显示整数部分和量级）
    
    Args:
        balance: 余额
        precision: 保留小数位数
    
    Returns:
        脱敏后的余额字符串
    
    Examples:
        >>> mask_balance(12345.67)
        "12,3**.**"
    """
    try:
        num = float(balance)
        int_part = int(num)
        str_int = f"{int_part:,}"
        
        # 保留前3位，其余用*
        if len(str_int) > 3:
            masked = str_int[:3] + re.sub(r'\d', '*', str_int[3:])
        else:
            masked = str_int
        
        return f"{masked}.**"
    except:
        return "***"


def mask_secret(secret: str) -> str:
    """脱敏密钥（只显示前4位）"""
    if not secret or len(secret) < 4:
        return "****"
    return secret[:4] + "*" * (len(secret) - 4)


def mask_url(url: str) -> str:
    """
    脱敏 URL（隐藏敏感参数）
    """
    if not url:
        return ""
    
    # 隐藏 token、key、secret 等参数
    patterns = [
        (r'(token=)[^&]+', r'\1****'),
        (r'(key=)[^&]+', r'\1****'),
        (r'(secret=)[^&]+', r'\1****'),
        (r'(password=)[^&]+', r'\1****'),
        (r'(auth=)[^&]+', r'\1****'),
    ]
    
    masked_url = url
    for pattern, replacement in patterns:
        masked_url = re.sub(pattern, replacement, masked_url, flags=re.IGNORECASE)
    
    return masked_url


class SensitiveFilter(logging.Filter):
    """
    日志敏感信息过滤器
    自动脱敏日志中的敏感信息
    """
    
    # 敏感词模式
    PATTERNS = [
        # 6位数字（可能是验证码）
        (r'\b(\d{6})\b', lambda m: mask_sensitive(m.group(1), 2)),
        # 密钥格式（大写字母+数字，16位以上）
        (r'\b([A-Z0-9]{16,})\b', lambda m: mask_secret(m.group(1))),
        # 邮箱
        (r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', 
         lambda m: mask_sensitive(m.group(1), 2) + "@" + m.group(2)),
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        # 对日志消息进行脱敏处理
        msg = record.getMessage()
        for pattern, replacer in self.PATTERNS:
            msg = re.sub(pattern, replacer, msg)
        record.msg = msg
        record.args = ()  # 清空参数，因为已经格式化了
        return True


class ColoredFormatter(logging.Formatter):
    """控制台彩色日志格式化器"""
    
    # ANSI 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',     # 青色
        'INFO': '\033[32m',      # 绿色
        'WARNING': '\033[33m',   # 黄色
        'ERROR': '\033[31m',     # 红色
        'CRITICAL': '\033[35m',  # 紫色
    }
    RESET = '\033[0m'
    
    # 日志图标
    ICONS = {
        'DEBUG': '🔍',
        'INFO': '📌',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨',
    }
    
    def __init__(self, account_name: Optional[str] = None):
        """
        初始化格式化器
        
        Args:
            account_name: 账号名称（用于多账号模式）
        """
        super().__init__()
        self.account_name = account_name
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, '')
        icon = self.ICONS.get(record.levelname, '')
        reset = self.RESET
        
        # 格式化时间
        record.asctime = datetime.now().strftime('%H:%M:%S')
        
        # 添加账号前缀
        prefix = f"[{self.account_name}] " if self.account_name else ""
        
        # 添加颜色和图标
        formatted = f"{color}{icon} [{record.asctime}] {prefix}{record.getMessage()}{reset}"
        return formatted


class FileFormatter(logging.Formatter):
    """文件日志格式化器（无颜色）"""
    
    def __init__(self, account_name: Optional[str] = None):
        """
        初始化格式化器
        
        Args:
            account_name: 账号名称（用于多账号模式）
        """
        super().__init__()
        self.account_name = account_name
    
    def format(self, record: logging.LogRecord) -> str:
        record.asctime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        prefix = f"[{self.account_name}] " if self.account_name else ""
        return f"[{record.asctime}] [{record.levelname}] {prefix}{record.getMessage()}"


def setup_logger(
    name: str = "alpha_bot",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    log_dir: str = "logs",
    account_name: Optional[str] = None
) -> logging.Logger:
    """
    创建并配置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        log_file: 日志文件名（可选）
        log_dir: 日志目录
        account_name: 账号名称（用于多账号日志隔离）
        
    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 控制台 Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(ColoredFormatter(account_name))
    logger.addHandler(console_handler)
    
    # 文件 Handler（可选）
    if log_file:
        os.makedirs(log_dir, exist_ok=True)
        file_path = os.path.join(log_dir, log_file)
        file_handler = logging.FileHandler(file_path, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(FileFormatter(account_name))
        logger.addHandler(file_handler)
    
    return logger


def setup_account_logger(
    account_name: str,
    level: int = logging.INFO,
    log_dir: str = "logs"
) -> logging.Logger:
    """
    为单个账号创建独立的日志记录器
    
    Args:
        account_name: 账号名称
        level: 日志级别
        log_dir: 日志目录
        
    Returns:
        配置好的 Logger 实例
    """
    # 使用账号名称作为 logger 名称，确保独立
    logger_name = f"alpha_bot_{account_name}"
    
    # 生成账号专属日志文件名
    date_str = datetime.now().strftime('%Y%m%d')
    log_file = f"{account_name}_{date_str}.log"
    
    return setup_logger(
        name=logger_name,
        level=level,
        log_file=log_file,
        log_dir=log_dir,
        account_name=account_name
    )


# ============================================
# 多账号日志管理器
# ============================================

class AccountLoggerManager:
    """
    多账号日志管理器
    管理多个账号的独立日志实例
    """
    
    _loggers: Dict[str, logging.Logger] = {}
    _current_account: Optional[str] = None
    
    @classmethod
    def get_logger(cls, account_name: str) -> logging.Logger:
        """
        获取指定账号的日志记录器
        
        Args:
            account_name: 账号名称
            
        Returns:
            Logger 实例
        """
        if account_name not in cls._loggers:
            cls._loggers[account_name] = setup_account_logger(account_name)
        return cls._loggers[account_name]
    
    @classmethod
    def set_current_account(cls, account_name: str) -> None:
        """
        设置当前账号（用于便捷函数）
        
        Args:
            account_name: 账号名称
        """
        cls._current_account = account_name
        # 确保已创建该账号的 logger
        cls.get_logger(account_name)
    
    @classmethod
    def get_current_logger(cls) -> logging.Logger:
        """
        获取当前账号的日志记录器
        如果未设置当前账号，返回默认 logger
        """
        if cls._current_account:
            return cls.get_logger(cls._current_account)
        return log
    
    @classmethod
    def get_current_account(cls) -> Optional[str]:
        """获取当前账号名称"""
        return cls._current_account


# 创建默认日志记录器
log = setup_logger(
    name="alpha_bot",
    log_file=f"bot_{datetime.now().strftime('%Y%m%d')}.log"
)


# ============================================
# 便捷函数（支持多账号）
# ============================================

def _get_active_logger() -> logging.Logger:
    """获取当前活动的 logger"""
    return AccountLoggerManager.get_current_logger()


def debug(msg: str) -> None:
    _get_active_logger().debug(msg)

def info(msg: str) -> None:
    _get_active_logger().info(msg)

def warning(msg: str) -> None:
    _get_active_logger().warning(msg)

def error(msg: str) -> None:
    _get_active_logger().error(msg)

def critical(msg: str) -> None:
    _get_active_logger().critical(msg)

def success(msg: str) -> None:
    """成功消息（使用 INFO 级别，带 ✅ 图标）"""
    account_prefix = ""
    current = AccountLoggerManager.get_current_account()
    if current:
        account_prefix = f"[{current}] "
    print(f"\033[32m✅ {account_prefix}{msg}\033[0m")
    _get_active_logger().info(f"[SUCCESS] {msg}")

def step(msg: str) -> None:
    """步骤消息（带分隔线）"""
    account_prefix = ""
    current = AccountLoggerManager.get_current_account()
    if current:
        account_prefix = f"[{current}] "
    print(f"\n{'='*50}")
    print(f"📍 {account_prefix}{msg}")
    print(f"{'='*50}")
    _get_active_logger().info(f"[STEP] {msg}")


# ============================================
# 账号切换便捷函数
# ============================================

def use_account_logger(account_name: str) -> None:
    """
    切换到指定账号的日志记录器
    
    Args:
        account_name: 账号名称
    
    Example:
        >>> use_account_logger("账号A")
        >>> info("这条日志会写入账号A的日志文件")
    """
    AccountLoggerManager.set_current_account(account_name)


def reset_logger() -> None:
    """重置为默认日志记录器"""
    AccountLoggerManager._current_account = None


# 导出脱敏函数
__all__ = [
    # 日志相关
    'log', 'setup_logger', 'setup_account_logger',
    'debug', 'info', 'warning', 'error', 'critical', 'success', 'step',
    # 多账号支持
    'AccountLoggerManager', 'use_account_logger', 'reset_logger',
    # 脱敏函数
    'mask_sensitive', 'mask_verification_code', 'mask_balance', 'mask_secret', 'mask_url',
    'SensitiveFilter'
]
