# ⛽ OilPrice - Oil Price Monitoring & Push Notification Tool

[中文文档](README.md)

Query real-time oil prices across China and push notifications via WeCom (Enterprise WeChat).

## Features

- **Real-time Oil Price Query** — Fetch 92#, 95#, 98# gasoline and 0# diesel prices for all 31 provinces from Autohome
- **Price Adjustment Prediction** — Get next adjustment date and estimated price changes from qiyoujiage.com
- **Smart Prediction Algorithm** — Auto-generate oil price adjustment predictions based on international crude oil prices (Brent & WTI) and China's 10-working-day adjustment cycle
- **Multiple Prediction Modes** — Supports `qiyoujiage` (scraping only), `custom` (algorithm only), `fallback` (scrape first, algorithm backup — default), `both` (show both sources)
- **WeCom Push Notifications** — Push messages as text cards to personal WeChat via WeCom app
- **National Comparison** — Display provinces with highest/lowest 92# gasoline prices nationwide

## Data Sources

| Source | Website | Purpose |
|--------|---------|---------|
| Autohome | [autohome.com.cn/oil](https://www.autohome.com.cn/oil/) | Real-time oil prices by province (primary source) |
| qiyoujiage.com | [qiyoujiage.com](http://www.qiyoujiage.com/) | Price adjustment predictions (supplementary source) |
| Sina Finance | [hq.sinajs.cn](https://hq.sinajs.cn/) | International crude oil prices (Brent & WTI) for custom prediction algorithm |

## Requirements

- Python 3.12
- [Poetry](https://python-poetry.org/) package manager

## Quick Start

### 1. Install Dependencies

```bash
poetry install
```

### 2. Configure Environment Variables

Copy the example configuration file and fill in the values:

```bash
cp .env.example .env
```

Edit the `.env` file:

```env
# WeCom Configuration (required)
CORP_ID=your_corp_id
SECRET=your_secret
AGENT_ID=your_agent_id

# User IDs to receive messages, comma-separated (required)
USER_IDS=user1,user2

# Province for local oil price query (optional, default: guangdong)
PROVINCE=guangdong

# Oil price adjustment prediction mode (optional, default: fallback)
# qiyoujiage - Use only qiyoujiage.com data
# custom     - Use only custom algorithm (based on international crude oil price trends)
# fallback   - Prefer qiyoujiage.com, fallback to custom algorithm on failure (default)
# both       - Use both sources and display results from each
PREDICTION_MODE=fallback
```

### 3. Run

```bash
# Method 1: Run as module (recommended)
poetry run python -m oilprice

# Method 2: Run entry file directly
poetry run python src/main.py

# Query and display only, without sending messages
poetry run python -m oilprice --dry-run

# Specify .env file path
poetry run python -m oilprice --env /path/to/.env
```

## Province Configuration Reference

| Identifier | Province | Identifier | Province |
|------------|----------|------------|----------|
| beijing | Beijing | shanghai | Shanghai |
| guangdong | Guangdong | zhejiang | Zhejiang |
| jiangsu | Jiangsu | sichuan | Sichuan |
| hubei | Hubei | hunan | Hunan |
| hebei | Hebei | fujian | Fujian |
| shandong | Shandong | liaoning | Liaoning |
| henan | Henan | shaanxi | Shaanxi |
| chongqing | Chongqing | tianjin | Tianjin |
| shanxi | Shanxi | jiangxi | Jiangxi |
| anhui | Anhui | guangxi | Guangxi |
| yunnan | Yunnan | guizhou | Guizhou |
| jilin | Jilin | heilongjiang | Heilongjiang |
| neimenggu | Inner Mongolia | hainan | Hainan |
| gansu | Gansu | qinghai | Qinghai |
| ningxia | Ningxia | xinjiang | Xinjiang |
| xizang | Tibet | | |

## Push Message Example

```
⛽ Guangdong Oil Prices Today (2026-03-14)

📍 Guangdong Oil Prices
  92# Gasoline: ¥7.66/L
  95# Gasoline: ¥8.29/L
  98# Gasoline: ¥10.29/L
  0# Diesel: ¥7.30/L

📢 Next price adjustment: March 20 at 24:00
  Price increase ¥0.55/L - ¥0.67/L

🔮 Next price adjustment: March 20 at 24:00
  International oil prices (Brent $70.56/barrel (↑1.25%), WTI $67.32/barrel (↑0.98%)) trending upward, estimated price increase ~¥0.06/L

📊 National 92#: Lowest Xinjiang ¥7.46 | Highest Hainan ¥8.75
```

## Project Structure

```
src/
├── main.py              # Top-level entry (direct execution and Nuitka build entry)
└── oilprice/
    ├── __init__.py      # Package entry point
    ├── __main__.py      # python -m oilprice support
    ├── main.py          # CLI entry point and main flow
    ├── config.py        # .env configuration loader
    ├── scraper.py       # Oil price data scraping and parsing
    ├── prediction.py    # Price adjustment prediction based on international crude oil
    ├── formatter.py     # Message content formatting
    └── notifier.py      # WeCom message push

tests/
├── conftest.py       # Test fixtures and mock data
├── test_config.py    # Configuration module tests
├── test_scraper.py   # Scraper module tests
├── test_prediction.py # Prediction algorithm tests
├── test_formatter.py # Formatter module tests
└── test_notifier.py  # Notifier module tests
```

## Development & Testing

```bash
# Run all tests
poetry run pytest tests/ -v

# Code formatting
poetry run black src/ tests/
poetry run isort src/ tests/

# Build local executable (requires nuitka)
poetry run python -m nuitka --onefile --output-dir=dist --output-filename=oilprice ./src/main.py
```

## Release a New Version

Push a tag in the `v*` format to trigger the CI/CD pipeline:

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions will automatically:
1. Run all tests
2. Build Windows and Linux onefile executables using Nuitka
3. Create a GitHub Release and upload build artifacts

After the build completes, download the executable for your platform from the [Releases page](../../releases).

## WeCom Configuration Guide

1. Log in to the [WeCom Admin Console](https://work.weixin.qq.com/)
2. Go to **App Management** → **Self-built** → Create an app
3. Obtain the following information:
   - **Corp ID**: Enterprise Information page → Enterprise ID
   - **Secret**: App Details page → Secret
   - **Agent ID**: App Details page → AgentId
4. Fill in the `.env` file with the obtained information

## License

MIT
