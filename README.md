# ⛽ OilPrice - 油价监控推送工具

[English](README_EN.md)

查询全国实时油价，并通过企业微信应用推送到微信。

## 功能特性

- **实时油价查询** — 从汽车之家获取全国 31 个省份的 92#、95#、98# 汽油及 0# 柴油价格
- **油价调整预测** — 从汽油价格网获取下次调价日期和预计涨跌幅度
- **智能预测算法** — 基于国际原油价格（布伦特、WTI）和中国10个工作日调价周期，自动生成油价调整预测
- **多预测模式** — 支持 `qiyoujiage`（仅汽油价格网）、`custom`（仅自定义算法）、`fallback`（优先汽油价格网，失败时回退）、`both`（同时展示两个来源）
- **企业微信推送** — 通过企业微信应用以文本卡片形式推送到个人微信
- **全国对比** — 展示 92# 汽油全国最高/最低价格省份

## 数据源

| 数据源 | 网站 | 用途 |
|--------|------|------|
| 汽车之家 | [autohome.com.cn/oil](https://www.autohome.com.cn/oil/) | 全国各省实时油价（主数据源） |
| 汽油价格网 | [qiyoujiage.com](http://www.qiyoujiage.com/) | 油价调整预测信息（补充数据源） |
| 新浪财经 | [hq.sinajs.cn](https://hq.sinajs.cn/) | 国际原油价格（布伦特、WTI），用于自定义预测算法 |

## 环境要求

- Python 3.12
- [Poetry](https://python-poetry.org/) 包管理器

## 快速开始

### 1. 安装依赖

```bash
poetry install
```

### 2. 配置环境变量

复制示例配置文件并填写：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 企业微信配置（必填）
CORP_ID=your_corp_id
SECRET=your_secret
AGENT_ID=your_agent_id

# 接收消息的用户ID，多个用逗号分隔（必填）
USER_IDS=user1,user2

# 省份，用于查询本地油价（可选，默认 guangdong）
PROVINCE=guangdong

# 油价调整预测模式（可选，默认 fallback）
# qiyoujiage - 仅使用汽油价格网数据
# custom     - 仅使用自定义算法（基于国际油价波动预测）
# fallback   - 优先使用汽油价格网，失败时使用自定义算法（默认）
# both       - 同时使用两个来源并发送
PREDICTION_MODE=fallback
```

### 3. 运行

```bash
# 查询油价并推送到微信
poetry run python -m oilprice

# 仅查询展示，不发送消息
poetry run python -m oilprice --dry-run

# 指定 .env 文件路径
poetry run python -m oilprice --env /path/to/.env
```

## 省份配置参考

| 英文标识 | 省份 | 英文标识 | 省份 |
|---------|------|---------|------|
| beijing | 北京 | shanghai | 上海 |
| guangdong | 广东 | zhejiang | 浙江 |
| jiangsu | 江苏 | sichuan | 四川 |
| hubei | 湖北 | hunan | 湖南 |
| hebei | 河北 | fujian | 福建 |
| shandong | 山东 | liaoning | 辽宁 |
| henan | 河南 | shaanxi | 陕西 |
| chongqing | 重庆 | tianjin | 天津 |
| shanxi | 山西 | jiangxi | 江西 |
| anhui | 安徽 | guangxi | 广西 |
| yunnan | 云南 | guizhou | 贵州 |
| jilin | 吉林 | heilongjiang | 黑龙江 |
| neimenggu | 内蒙古 | hainan | 海南 |
| gansu | 甘肃 | qinghai | 青海 |
| ningxia | 宁夏 | xinjiang | 新疆 |
| xizang | 西藏 | | |

## 推送消息示例

```
⛽ 广东今日油价 (2026年03月14日)

📍 广东油价
  92#汽油: 7.66 元/升
  95#汽油: 8.29 元/升
  98#汽油: 10.29 元/升
  0#柴油: 7.30 元/升

📢 下次油价3月20日24时调整
  油价上涨0.55元/升-0.67元/升

🔮 下次油价3月20日24时调整
  国际油价(布伦特70.56美元/桶(↑1.25%),WTI67.32美元/桶(↑0.98%))呈上涨趋势，预计油价上调约0.06元/升

📊 全国92#: 最低 新疆 7.46 | 最高 海南 8.75
```

## 项目结构

```
src/oilprice/
├── __init__.py      # 包入口
├── __main__.py      # python -m oilprice 支持
├── main.py          # CLI 入口和主流程
├── config.py        # .env 配置加载
├── scraper.py       # 油价数据抓取与解析
├── prediction.py    # 基于国际油价的调价预测算法
├── formatter.py     # 消息内容格式化
└── notifier.py      # 企业微信消息推送

tests/
├── conftest.py       # 测试 fixtures 和模拟数据
├── test_config.py    # 配置模块测试
├── test_scraper.py   # 抓取模块测试
├── test_prediction.py # 预测算法测试
├── test_formatter.py # 格式化模块测试
└── test_notifier.py  # 通知模块测试
```

## 开发与测试

```bash
# 运行所有测试
poetry run pytest tests/ -v

# 代码格式化
poetry run black src/ tests/
poetry run isort src/ tests/

# 本地构建可执行文件（需要 nuitka）
poetry run python -m nuitka --onefile --output-dir=dist --output-filename=oilprice ./src/main.py
```

## 发布新版本

推送 `v*` 格式的 tag 即可自动触发 CI/CD 流程：

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions 会自动完成：
1. 运行全部测试
2. 使用 Nuitka 构建 Windows 和 Linux 的 onefile 可执行文件
3. 创建 GitHub Release 并上传构建产物

构建完成后可在 [Releases 页面](../../releases) 下载对应平台的可执行文件。

## 企业微信配置指南

1. 登录 [企业微信管理后台](https://work.weixin.qq.com/)
2. 进入 **应用管理** → **自建** → 创建应用
3. 获取以下信息：
   - **Corp ID**: 企业信息页面 → 企业ID
   - **Secret**: 应用详情页 → Secret
   - **Agent ID**: 应用详情页 → AgentId
4. 将信息填入 `.env` 文件

## License

MIT