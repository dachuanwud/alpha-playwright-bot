@echo off
chcp 65001 >nul
echo ========================================
echo 启动 jialin 账号的 Chrome (端口 9222)
echo ========================================
echo.

REM ============================================
REM 请根据你的 Chrome 安装路径修改下面的路径
REM ============================================
REM 常见路径：
REM   C:\Program Files\Google\Chrome\Application\chrome.exe
REM   C:\Program Files (x86)\Google\Chrome\Application\chrome.exe
REM   或者直接使用 chrome（如果已添加到 PATH）

set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe

REM 尝试多个可能的 Chrome 路径
if not exist "%CHROME_PATH%" (
    set CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe
)

if not exist "%CHROME_PATH%" (
    REM 尝试使用 chrome 命令（如果已添加到 PATH）
    where chrome >nul 2>&1
    if %errorlevel% equ 0 (
        set CHROME_PATH=chrome
    ) else (
        echo ❌ 错误: 找不到 Chrome 可执行文件
        echo.
        echo 请修改此脚本中的 CHROME_PATH 变量，设置为你的 Chrome 实际路径
        echo 或者将 Chrome 添加到系统 PATH 环境变量
        echo.
        pause
        exit /b 1
    )
)

echo ✅ 找到 Chrome: %CHROME_PATH%
echo.
echo 🚀 正在启动 Chrome...
echo    端口: 9222
echo    用户数据目录: C:\ChromeProfiles\jialin
echo.

start "" "%CHROME_PATH%" --remote-debugging-port=9222 --user-data-dir="C:\ChromeProfiles\jialin"

echo.
echo ========================================
echo ✅ Chrome 已启动！
echo ========================================
echo.
echo 📋 接下来的步骤：
echo    1. 在 Chrome 中访问 https://www.binance.com
echo    2. 登录 jialin 账号
echo    3. 打开交易页面（如：https://www.binance.com/zh-CN/trade/BTC_USDT）
echo    4. 保持窗口打开（可以最小化）
echo.
echo 💡 提示：登录后不要关闭 Chrome 窗口，这样下次启动会自动恢复登录状态
echo.
pause


