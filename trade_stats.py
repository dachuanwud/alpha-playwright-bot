"""
交易统计模块 - 记录和展示交易统计信息
"""
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import json
import os


@dataclass
class TradeRecord:
    """单次交易记录"""
    timestamp: str
    trade_type: str  # "buy" / "sell" / "cancel"
    price: float
    amount: float
    success: bool
    duration_ms: float
    error_msg: Optional[str] = None


@dataclass
class TradeStats:
    """交易统计摘要"""
    
    # 计数器
    total_attempts: int = 0
    successful_buys: int = 0
    failed_buys: int = 0
    successful_sells: int = 0
    failed_sells: int = 0
    canceled_orders: int = 0
    errors: int = 0
    
    # 金额统计
    total_buy_volume: float = 0.0
    total_sell_volume: float = 0.0
    start_balance: float = 0.0
    end_balance: float = 0.0
    
    # 时间统计
    start_time: float = field(default_factory=time.time)
    total_operation_time_ms: float = 0.0
    
    # 交易记录
    records: List[TradeRecord] = field(default_factory=list)
    
    # 错误记录
    error_messages: List[str] = field(default_factory=list)
    
    def record_buy(self, price: float, amount: float, success: bool, duration_ms: float, error_msg: str = None):
        """记录买入操作"""
        self.total_attempts += 1
        self.total_operation_time_ms += duration_ms
        
        if success:
            self.successful_buys += 1
            self.total_buy_volume += price * amount
        else:
            self.failed_buys += 1
            self.errors += 1
            if error_msg:
                self.error_messages.append(f"[BUY] {error_msg}")
        
        self.records.append(TradeRecord(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            trade_type="buy",
            price=price,
            amount=amount,
            success=success,
            duration_ms=duration_ms,
            error_msg=error_msg
        ))
    
    def record_sell(self, price: float, amount: float, success: bool, duration_ms: float, error_msg: str = None):
        """记录卖出操作"""
        self.total_operation_time_ms += duration_ms
        
        if success:
            self.successful_sells += 1
            self.total_sell_volume += price * amount
        else:
            self.failed_sells += 1
            self.errors += 1
            if error_msg:
                self.error_messages.append(f"[SELL] {error_msg}")
        
        self.records.append(TradeRecord(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            trade_type="sell",
            price=price,
            amount=amount,
            success=success,
            duration_ms=duration_ms,
            error_msg=error_msg
        ))
    
    def record_cancel(self, success: bool = True):
        """记录取消订单"""
        if success:
            self.canceled_orders += 1
        
        self.records.append(TradeRecord(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            trade_type="cancel",
            price=0,
            amount=0,
            success=success,
            duration_ms=0
        ))
    
    def record_error(self, error_msg: str):
        """记录错误"""
        self.errors += 1
        self.error_messages.append(f"[ERROR] {error_msg}")
    
    def set_start_balance(self, balance: float):
        """设置初始余额"""
        self.start_balance = balance
    
    def set_end_balance(self, balance: float):
        """设置最终余额"""
        self.end_balance = balance
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_buys / self.total_attempts) * 100
    
    @property
    def profit(self) -> float:
        """计算盈亏（负数即为消耗的手续费+磨损）"""
        return self.end_balance - self.start_balance
    
    @property
    def total_fee_consumed(self) -> float:
        """
        本次刷单消耗的手续费（通过余额变化计算）
        负的 profit 就是消耗的总成本（手续费+价差磨损）
        """
        return -self.profit if self.profit < 0 else 0
    
    @property
    def total_runtime(self) -> float:
        """总运行时间（秒）"""
        return time.time() - self.start_time
    
    @property
    def avg_operation_time_ms(self) -> float:
        """平均操作时间（毫秒）"""
        total_ops = self.successful_buys + self.failed_buys + self.successful_sells + self.failed_sells
        if total_ops == 0:
            return 0.0
        return self.total_operation_time_ms / total_ops
    
    def print_summary(self):
        """打印交易统计摘要"""
        runtime = self.total_runtime
        hours = int(runtime // 3600)
        minutes = int((runtime % 3600) // 60)
        seconds = runtime % 60
        
        print("\n")
        print("╔══════════════════════════════════════════════════╗")
        print("║              📊 交易统计摘要                      ║")
        print("╠══════════════════════════════════════════════════╣")
        print(f"║  总尝试次数:     {self.total_attempts:>6}                        ║")
        print(f"║  成功买入:       {self.successful_buys:>6}                        ║")
        print(f"║  失败买入:       {self.failed_buys:>6}                        ║")
        print(f"║  成功卖出:       {self.successful_sells:>6}                        ║")
        print(f"║  失败卖出:       {self.failed_sells:>6}                        ║")
        print(f"║  取消订单:       {self.canceled_orders:>6}                        ║")
        print(f"║  错误次数:       {self.errors:>6}                        ║")
        print("╠══════════════════════════════════════════════════╣")
        print(f"║  成功率:         {self.success_rate:>6.1f}%                       ║")
        print(f"║  平均耗时:       {self.avg_operation_time_ms:>6.0f}ms                      ║")
        print("╠══════════════════════════════════════════════════╣")
        print(f"║  初始余额:       {self.start_balance:>10.2f} USDT            ║")
        print(f"║  最终余额:       {self.end_balance:>10.2f} USDT            ║")
        print("╠══════════════════════════════════════════════════╣")
        print("║            💰 损耗分析 (重点)                     ║")
        print("╠══════════════════════════════════════════════════╣")
        print(f"║  余额变化:       {self.profit:>+10.4f} USDT            ║")
        print(f"║  ⚡ 总消耗:      {self.total_fee_consumed:>10.4f} USDT            ║")
        if self.successful_buys > 0:
            avg_cost = self.total_fee_consumed / self.successful_buys
            print(f"║  📉 单笔消耗:    {avg_cost:>10.4f} USDT            ║")
            # 预估36笔损耗
            estimated_36 = avg_cost * 36
            print(f"║  📊 预估36笔:    {estimated_36:>10.4f} USDT            ║")
        print("╠══════════════════════════════════════════════════╣")
        print(f"║  总运行时间:     {hours:>2}h {minutes:>2}m {seconds:>5.1f}s                  ║")
        print("╚══════════════════════════════════════════════════╝")
        
        # 打印错误信息（如果有）
        if self.error_messages:
            print("\n⚠️ 错误记录:")
            for i, msg in enumerate(self.error_messages[-5:], 1):  # 只显示最后5条
                print(f"  {i}. {msg}")
            if len(self.error_messages) > 5:
                print(f"  ... 还有 {len(self.error_messages) - 5} 条错误")
    
    def save_to_file(self, filename: str = None):
        """
        保存统计数据到文件
        
        Args:
            filename: 文件名（默认使用时间戳）
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"logs/stats_{timestamp}.json"
        
        # 确保目录存在
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
        
        data = {
            "summary": {
                "total_attempts": self.total_attempts,
                "successful_buys": self.successful_buys,
                "failed_buys": self.failed_buys,
                "successful_sells": self.successful_sells,
                "failed_sells": self.failed_sells,
                "canceled_orders": self.canceled_orders,
                "errors": self.errors,
                "success_rate": self.success_rate,
                "start_balance": self.start_balance,
                "end_balance": self.end_balance,
                "profit": self.profit,
                "total_fee_consumed": self.total_fee_consumed,
                "avg_cost_per_trade": self.total_fee_consumed / self.successful_buys if self.successful_buys > 0 else 0,
                "total_runtime_seconds": self.total_runtime,
                "avg_operation_time_ms": self.avg_operation_time_ms
            },
            "records": [
                {
                    "timestamp": r.timestamp,
                    "type": r.trade_type,
                    "price": r.price,
                    "amount": r.amount,
                    "success": r.success,
                    "duration_ms": r.duration_ms,
                    "error": r.error_msg
                }
                for r in self.records
            ],
            "errors": self.error_messages
        }
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"📁 统计数据已保存: {filename}")


class TimedOperation:
    """计时操作上下文管理器"""
    
    def __init__(self, name: str = "operation", threshold_ms: int = 5000):
        """
        Args:
            name: 操作名称
            threshold_ms: 警告阈值（毫秒）
        """
        self.name = name
        self.threshold_ms = threshold_ms
        self.start_time = 0
        self.duration_ms = 0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.time() - self.start_time) * 1000
        
        if self.duration_ms > self.threshold_ms:
            print(f"⚠️ {self.name} 耗时过长: {self.duration_ms:.0f}ms (阈值: {self.threshold_ms}ms)")
        
        return False  # 不抑制异常


# 全局统计实例
_global_stats: Optional[TradeStats] = None


def get_stats() -> TradeStats:
    """获取全局统计实例"""
    global _global_stats
    if _global_stats is None:
        _global_stats = TradeStats()
    return _global_stats


def reset_stats():
    """重置统计"""
    global _global_stats
    _global_stats = TradeStats()


if __name__ == "__main__":
    # 测试
    stats = TradeStats()
    stats.set_start_balance(1000.0)
    
    # 模拟交易
    stats.record_buy(price=0.5, amount=100, success=True, duration_ms=500)
    stats.record_buy(price=0.51, amount=100, success=True, duration_ms=450)
    stats.record_buy(price=0.52, amount=100, success=False, duration_ms=600, error_msg="滑点过大")
    stats.record_sell(price=0.55, amount=200, success=True, duration_ms=480)
    stats.record_cancel()
    
    stats.set_end_balance(1050.0)
    stats.print_summary()
    stats.save_to_file()

