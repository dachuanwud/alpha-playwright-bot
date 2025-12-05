"""
多账号运行器 - 使用多进程同时运行多个账号

使用方式:
    python multi_runner.py              # 启动所有启用的账号
    python multi_runner.py --list       # 列出所有账号
    python multi_runner.py --dry-run    # 预览将要启动的账号（不实际启动）

注意:
    运行前需要为每个账号手动启动独立的 Chrome 实例，例如:
    chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\\ChromeProfiles\\AccountA"
    chrome.exe --remote-debugging-port=9223 --user-data-dir="C:\\ChromeProfiles\\AccountB"
"""
import os
import sys
import time
import signal
import multiprocessing
from datetime import datetime
from typing import List, Dict, Optional

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    get_enabled_accounts, 
    list_accounts, 
    AccountConfig,
    ACCOUNTS_FILE
)


class ProcessStatus:
    """进程状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class MultiAccountRunner:
    """
    多账号运行器
    
    使用多进程为每个账号启动独立的交易进程
    """
    
    def __init__(self):
        self.processes: Dict[str, multiprocessing.Process] = {}
        self.statuses: Dict[str, str] = {}
        self.start_times: Dict[str, datetime] = {}
        self.shutdown_flag = multiprocessing.Event()
        
    def _run_single_account(self, account_name: str) -> None:
        """
        运行单个账号（在子进程中执行）
        
        Args:
            account_name: 账号名称
        """
        # 重新导入模块（子进程需要独立导入）
        from main import run_account
        
        try:
            run_account(account_name)
        except KeyboardInterrupt:
            print(f"\n[{account_name}] 收到中断信号，正在退出...")
        except Exception as e:
            print(f"\n[{account_name}] 运行异常: {e}")
    
    def start_account(self, account: AccountConfig) -> bool:
        """
        启动单个账号的进程
        
        Args:
            account: 账号配置
            
        Returns:
            是否启动成功
        """
        if account.name in self.processes:
            print(f"⚠️ 账号 {account.name} 已在运行中")
            return False
        
        print(f"🚀 启动账号: {account.name} (端口: {account.port})")
        
        # 创建子进程
        process = multiprocessing.Process(
            target=self._run_single_account,
            args=(account.name,),
            name=f"AlphaTrader-{account.name}",
            daemon=False  # 非守护进程，主进程退出时不自动终止
        )
        
        try:
            process.start()
            self.processes[account.name] = process
            self.statuses[account.name] = ProcessStatus.RUNNING
            self.start_times[account.name] = datetime.now()
            return True
        except Exception as e:
            print(f"❌ 启动账号 {account.name} 失败: {e}")
            self.statuses[account.name] = ProcessStatus.FAILED
            return False
    
    def stop_account(self, account_name: str, timeout: float = 10) -> bool:
        """
        停止单个账号的进程
        
        Args:
            account_name: 账号名称
            timeout: 等待超时时间（秒）
            
        Returns:
            是否停止成功
        """
        if account_name not in self.processes:
            return True
        
        process = self.processes[account_name]
        
        if not process.is_alive():
            del self.processes[account_name]
            return True
        
        print(f"⏹️ 停止账号: {account_name}")
        
        # 先尝试优雅终止
        process.terminate()
        process.join(timeout=timeout)
        
        # 如果还没结束，强制终止
        if process.is_alive():
            print(f"⚠️ 账号 {account_name} 未响应，强制终止")
            process.kill()
            process.join(timeout=5)
        
        self.statuses[account_name] = ProcessStatus.STOPPED
        del self.processes[account_name]
        return True
    
    def stop_all(self, timeout: float = 10) -> None:
        """
        停止所有账号进程
        
        Args:
            timeout: 每个进程的等待超时时间
        """
        print("\n" + "=" * 50)
        print("正在停止所有账号...")
        print("=" * 50)
        
        self.shutdown_flag.set()
        
        # 按顺序停止所有进程
        for name in list(self.processes.keys()):
            self.stop_account(name, timeout)
        
        print("✅ 所有账号已停止")
    
    def get_status(self) -> Dict[str, dict]:
        """
        获取所有账号状态
        
        Returns:
            账号状态字典
        """
        result = {}
        
        for name, process in list(self.processes.items()):
            is_alive = process.is_alive()
            
            if not is_alive and self.statuses.get(name) == ProcessStatus.RUNNING:
                # 进程意外退出
                exit_code = process.exitcode
                self.statuses[name] = ProcessStatus.COMPLETED if exit_code == 0 else ProcessStatus.FAILED
            
            start_time = self.start_times.get(name)
            running_time = ""
            if start_time and is_alive:
                delta = datetime.now() - start_time
                hours = int(delta.total_seconds() // 3600)
                minutes = int((delta.total_seconds() % 3600) // 60)
                running_time = f"{hours}h {minutes}m"
            
            result[name] = {
                "status": self.statuses.get(name, ProcessStatus.PENDING),
                "alive": is_alive,
                "pid": process.pid if process else None,
                "running_time": running_time,
                "exit_code": process.exitcode if not is_alive else None
            }
        
        return result
    
    def print_status(self) -> None:
        """打印所有账号状态"""
        status = self.get_status()
        
        print("\n" + "=" * 60)
        print(f"📊 账号运行状态 ({datetime.now().strftime('%H:%M:%S')})")
        print("=" * 60)
        
        if not status:
            print("  无运行中的账号")
            return
        
        for name, info in status.items():
            status_icon = {
                ProcessStatus.RUNNING: "🟢",
                ProcessStatus.COMPLETED: "✅",
                ProcessStatus.FAILED: "❌",
                ProcessStatus.STOPPED: "⏹️",
                ProcessStatus.PENDING: "⏳"
            }.get(info["status"], "❓")
            
            pid_str = f"PID:{info['pid']}" if info['pid'] else ""
            time_str = f"运行:{info['running_time']}" if info['running_time'] else ""
            exit_str = f"退出码:{info['exit_code']}" if info['exit_code'] is not None else ""
            
            details = " | ".join(filter(None, [pid_str, time_str, exit_str]))
            
            print(f"  {status_icon} {name}: {info['status']}" + (f" ({details})" if details else ""))
        
        print()
    
    def run_all(self, accounts: List[AccountConfig], monitor_interval: int = 60) -> None:
        """
        启动并监控所有账号
        
        Args:
            accounts: 要启动的账号列表
            monitor_interval: 状态监控间隔（秒）
        """
        if not accounts:
            print("❌ 没有启用的账号")
            return
        
        print("\n" + "=" * 60)
        print(f"🚀 多账号启动器 - 共 {len(accounts)} 个账号")
        print("=" * 60)
        
        # 设置信号处理
        def signal_handler(signum, frame):
            print("\n\n📛 收到中断信号，准备停止所有账号...")
            self.stop_all()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 启动所有账号（间隔启动，避免同时连接导致问题）
        for i, account in enumerate(accounts):
            if not account.enabled:
                continue
            
            self.start_account(account)
            
            # 间隔 3 秒启动下一个账号
            if i < len(accounts) - 1:
                print(f"   等待 3 秒后启动下一个账号...")
                time.sleep(3)
        
        # 打印初始状态
        self.print_status()
        
        # 监控循环
        print(f"📡 开始监控，每 {monitor_interval} 秒刷新状态 (Ctrl+C 停止)")
        print("-" * 60)
        
        try:
            while True:
                time.sleep(monitor_interval)
                
                # 检查是否所有进程都结束了
                all_stopped = all(
                    not p.is_alive() for p in self.processes.values()
                )
                
                if all_stopped and self.processes:
                    print("\n✅ 所有账号已完成运行")
                    self.print_status()
                    break
                
                # 打印状态
                self.print_status()
                
                # 检查并重启失败的进程（可选）
                # self._restart_failed_processes(accounts)
                
        except KeyboardInterrupt:
            print("\n\n📛 用户中断")
            self.stop_all()


def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="多账号运行器 - 同时运行多个交易账号",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python multi_runner.py              # 启动所有启用的账号
  python multi_runner.py --list       # 列出所有账号
  python multi_runner.py --dry-run    # 预览将要启动的账号

注意:
  运行前需要为每个账号手动启动独立的 Chrome 实例，例如:
  
  # 账号A (端口 9222)
  chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\\ChromeProfiles\\AccountA"
  
  # 账号B (端口 9223)
  chrome.exe --remote-debugging-port=9223 --user-data-dir="C:\\ChromeProfiles\\AccountB"
        """
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="列出所有账号配置"
    )
    
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="预览将要启动的账号（不实际启动）"
    )
    
    parser.add_argument(
        "--monitor", "-m",
        type=int,
        default=60,
        help="状态监控间隔（秒），默认 60"
    )
    
    args = parser.parse_args()
    
    # 列出账号
    if args.list:
        list_accounts()
        return
    
    # 检查配置文件
    if not ACCOUNTS_FILE.exists():
        print(f"❌ 未找到配置文件: {ACCOUNTS_FILE}")
        print("请先创建 accounts.yaml 配置文件")
        return
    
    # 获取启用的账号
    accounts = get_enabled_accounts()
    
    if not accounts:
        print("❌ 没有启用的账号")
        print("请检查 accounts.yaml 中的账号配置，确保 enabled: true")
        return
    
    # 预览模式
    if args.dry_run:
        print("\n" + "=" * 50)
        print("📋 将要启动的账号（预览模式）")
        print("=" * 50)
        for acc in accounts:
            secret_status = "🔐 有验证器" if acc.secret else "⚠️ 无验证器"
            print(f"  • {acc.name}")
            print(f"    端口: {acc.port}")
            print(f"    验证器: {secret_status}")
            if acc.cost:
                print(f"    交易额: {acc.cost}")
            print()
        print(f"共 {len(accounts)} 个账号将被启动")
        print("\n使用 'python multi_runner.py' 实际启动")
        return
    
    # 启动多账号运行器
    runner = MultiAccountRunner()
    runner.run_all(accounts, monitor_interval=args.monitor)


if __name__ == "__main__":
    # Windows 多进程需要这个保护
    multiprocessing.freeze_support()
    main()

