# zettaranc-skill

zettaranc（万千）投资思维框架与表达方式的 Codex/AI Skill。

## 数据源

当前版本使用**本地通达信数据源**，直接读取通达信安装目录下的 `vipdoc` 日线文件：

```text
D:\TongDaXin\vipdoc\sh\lday\sh600519.day
D:\TongDaXin\vipdoc\sz\lday\sz000001.day
```

不需要外部行情 API，不需要网络凭证。通达信客户端更新本地数据后，skill 再同步 SQLite 数据库并计算指标。

## 配置

复制 `.env.example` 为 `.env`，或直接写入：

```ini
DATA_MODE=tdx
TDX_PATH=D:\TongDaXin
DATA_DIR=data
DB_PATH=data/stock_data.db
```

## 常用命令

```powershell
# 初始化数据库
D:\python3.11\python.exe -m modules.data_sync init

# 同步单只股票日线
D:\python3.11\python.exe -m modules.data_sync sync --ts_code 600519.SH

# 计算/刷新单只股票指标缓存
D:\python3.11\python.exe -m modules.data_sync indicators --ts_code 600519.SH

# 查看状态
D:\python3.11\python.exe -m modules.data_sync status
```

## 核心结构

```text
modules/
  tdx_client.py       # 本地通达信 .day 文件读取
  tdx_data_sync.py    # 写入 SQLite，并刷新指标缓存
  data_sync.py        # 命令行入口
  database.py         # SQLite 表结构
  indicators.py       # 技术指标计算
  screener.py         # 选股器
  strategies.py       # 战法识别
  setup_wizard.py     # 数据源配置
  trade_parser.py     # 交易记录解析
  trade_manager.py    # 交易记录 CRUD
  trade_reviewer.py   # 复盘数据上下文
```

## 限制

本地通达信日线数据覆盖 OHLCV 和由此派生的技术指标。财务数据、资金流、龙虎榜、涨停列表等不由本地 `.day` 文件提供；需要这些维度时，应单独使用公开资料辅助判断。

## 免责声明

本项目仅用于学习和研究，不构成投资建议。金融市场风险极高，任何基于历史数据和公开表达蒸馏出的框架都可能失效。
