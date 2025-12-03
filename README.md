# Alpha 自动化交易脚本（优化版）

使用 Playwright 连接本地 Chrome，自动执行币安 Alpha 买卖操作。

## ✨ 优化特性

| 特性 | 旧版 | 新版 |
|------|------|------|
| 配置管理 | 硬编码 | 支持 .env 环境变量 |
| 日志系统 | print | 专业 logging + 彩色输出 |
| 代码结构 | 900+ 行单文件 | 模块化设计 |
| 错误处理 | 裸 except | 重试装饰器 + 详细日志 |
| 类型提示 | 无 | 完整类型注解 |
| 验证器处理 | 分散调用 30+ 次 | 装饰器自动处理 |

## 📁 项目结构

```
alpha-playwright-bot/
├── main.py              # 主脚本 ⭐
├── browser_manager.py   # 浏览器操作封装
├── config.py            # 配置管理（支持环境变量）
├── logger.py            # 日志系统
├── trade_stats.py       # 交易统计模块
├── func.py              # 工具函数（兼容旧版）
├── requirements.txt     # 依赖管理
├── env.example.txt      # 环境变量模板
└── logs/                # 日志目录（自动创建）
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置环境变量（推荐）

```bash
# 复制模板
cp env.example.txt .env

# 编辑配置
nano .env
```

或直接编辑 `config.py` 中的默认值。

### 3. 启动 Chrome（调试模式）

**macOS:**
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/chrome-debug" &
```

**Windows:**
```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir="C:\chrome-debug"
```

### 4. 打开交易页面

在启动的 Chrome 中：
1. 访问 Binance Alpha 交易页面
2. 登录账户
3. 选择要交易的代币

### 5. 运行脚本

```bash
# 优化版（推荐）
python main.py

# 原版
python main.py
```

## ⚙️ 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `GOOGLE_SECRET` | 谷歌验证器密钥 | 必填 |
| `CHROME_PORT` | Chrome 调试端口 | 9222 |
| `TRADE_COST` | 单次交易额度 | 256 |
| `TOTAL_RUNS` | 执行次数 | 12 |
| `RESERVED_AMOUNT` | 保留币数 | 0 |
| `MIN_SELL_AMOUNT` | 最小卖出数量 | 1 |
| `REFRESH_INTERVAL` | 刷新间隔（次） | 5 |
| `MIN_INTERVAL` | 最小休息时间（秒） | 15 |
| `MAX_INTERVAL` | 最大休息时间（秒） | 30 |
| `BUY_PRICE_DIFF` | 买价差值 | 0.00000010 |
| `SELL_PRICE_PERCENT` | 卖价百分比 | 0.7 |

### 价格配置注意事项

⚠️ `BUY_PRICE_DIFF` 需要根据交易币种调整：
- 尾数位数不同的币种需要不同的差值
- 设置错误会导致订单无法成交

## 📝 日志说明

日志文件保存在 `logs/` 目录：
- 控制台：彩色输出 + 图标
- 文件：`logs/bot_YYYYMMDD.log`

日志级别：
- 🔍 DEBUG - 调试信息
- 📌 INFO - 常规信息
- ⚠️ WARNING - 警告
- ❌ ERROR - 错误
- 🚨 CRITICAL - 严重错误

## 🔐 安全提醒

1. **不要提交敏感信息**：`.env` 文件已被 `.gitignore` 忽略
2. **验证器密钥**：仅在本地使用，不要分享
3. **测试验证器**：先运行 `3_身份验证器测试.py` 确认密钥正确

## 🐛 常见问题

### Chrome CDP 连接失败

```
❌ 无法连接到 Chrome DevTools
```

解决方案：
1. 确认 Chrome 以调试模式启动
2. 检查端口是否正确
3. 访问 `http://127.0.0.1:9222/json/version` 验证

### 页面元素找不到

Binance UI 可能更新，需要更新 XPath：
1. 使用浏览器开发者工具检查元素
2. 更新 `main.py` 中的 `XPATH` 常量

### 验证器不工作

1. 运行 `python 3_身份验证器测试.py` 测试密钥
2. 确认生成的验证码与手机一致
3. 检查系统时间是否准确

## 📊 性能对比

| 指标 | 旧版 | 新版 |
|------|------|------|
| 代码行数 | ~1400 行 | ~800 行 |
| 重复代码 | 高 | 低 |
| 可维护性 | 差 | 好 |
| 错误追踪 | 困难 | 日志完整 |
| 配置修改 | 改代码 | 改环境变量 |

## 📜 免责声明

该脚本仅供学习与自动化实验使用。使用前请遵循交易所条款与当地法律法规，自行承担风险。

