# Alpha 自动化脚本（Binance 网页端）

本项目使用 Playwright 连接到本地已开启 DevTools 端口的 Chrome，对币安网页进行滚动、下单、取消未成交、验证码处理、刷新与节奏控制，并记录余额。

## 快速开始

1) 安装依赖
```bash
pip install playwright pandas pyautogui requests
playwright install chromium
```

2) 启动带远程调试端口的 Chrome
- 推荐脚本：`1_依据端口创建网页.py`（已配置 `E:\myChome\` 与端口 9222）。
- 启动后访问 `http://127.0.0.1:9222/json/version` 应能看到 JSON。

3) 配置
- 编辑 `config.py`：`port`, `cost`, `total_runs`, `reserved_amount`, `min_sell_amount`, `refresh_interval`, `min_interval`, `max_interval`, `buy_price_diff`, `sell_price_percent`。
- 如需自动输入 2FA，请在本地填写 `secret`（仅本地使用，不要提交仓库）。

4) 运行
```bash
python main.py
```

## 安全与合规
- 不要把 `config.py` 中的 `secret` 或任何私密信息提交到公共仓库。
- `.gitignore` 已忽略 CSV、临时文本与本地浏览器配置目录，但请在提交前自查。
- KYC/风控等验证需在浏览器内手动完成；2FA 可由脚本自动输入。

## 目录
- `main.py`：主流程控制。
- `func.py`：浏览器连接与页面操作工具。
- `config.py`：参数配置。
- `1_依据端口创建网页.py`：启动端口浏览器。
- `2_操控浏览器测试.py`：Windows 批量端口/提权示例。

## 免责声明
该脚本仅供学习与自动化实验使用。使用前请遵循交易所条款与当地法律法规，自行承担风险。
