# ⛽ OilPrice - 油价监控推送工具

查询全国实时油价，并通过企业微信应用推送到微信。

## 功能特性

- **实时油价查询** — 从汽车之家获取全国 31 个省份的 92#、95#、98# 汽油及 0# 柴油价格
- **油价调整预测** — 从汽油价格网获取下次调价日期和预计涨跌幅度
- **算法预测** — 基于完整定价链算法，结合国际原油价格、汇率、炼油成本和税费，独立计算预计零售价变动
- **多数据源支持** — 优先使用 Yahoo Finance 获取国际原油历史 K 线数据，新浪财经作为备用数据源
- **企业微信推送** — 通过企业微信应用以文本卡片形式推送到个人微信
- **全国对比** — 展示 92# 汽油全国最高/最低价格省份

## 数据源

| 数据源 | 网站 | 用途 |
|--------|------|------|
| 汽车之家 | [autohome.com.cn/oil](https://www.autohome.com.cn/oil/) | 全国各省实时油价（主数据源） |
| 汽油价格网 | [qiyoujiage.com](http://www.qiyoujiage.com/) | 油价调整预测信息（补充数据源） |
| Yahoo Finance | [finance.yahoo.com](https://finance.yahoo.com/) | 国际原油历史 K 线数据（算法预测主数据源） |
| 新浪财经 | [finance.sina.com.cn](https://finance.sina.com.cn/) | 国际原油实时行情、K 线数据（备用）、美元兑人民币汇率 |

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
  (来源:汽油价格网)

🔮 下次油价3月20日24时调整
  国际油价(布伦特71.20美元/桶(↑2.35%)，WTI67.80美元/桶(↑1.98%))呈上涨趋势，汇率7.22，较上轮调价变动约+180元/吨，预计油价上调约0.15元/升
  (来源:算法预测)

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
├── prediction.py    # 国际油价获取与算法预测（定价链计算）
├── formatter.py     # 消息内容格式化（含来源标签）
└── notifier.py      # 企业微信消息推送

tests/
├── conftest.py       # 测试 fixtures 和模拟数据
├── test_config.py    # 配置模块测试
├── test_scraper.py   # 抓取模块测试
├── test_prediction.py # 预测模块测试
├── test_formatter.py # 格式化模块测试
└── test_notifier.py  # 通知模块测试
```

## 算法预测说明

本工具内置完整的中国成品油定价链算法，基于国际原油价格独立计算预计零售价变动：

```
国际原油价格(美元/桶) → 汇率转换 → 原油成本(元/吨) → 炼油加工 → 税费 → 零售价(元/升)
```

**定价链参数：**

| 参数 | 值 | 说明 |
|------|------|------|
| 桶/吨转换 | 7.33 桶/吨 | 1 吨原油 ≈ 7.33 桶 |
| 汽油密度 | 1351 升/吨 | 92# 汽油密度转换 |
| 炼油出油率 | 45% | 原油到汽油的转化率 |
| 增值税 | 13% | |
| 消费税 | 1.52 元/升 | 固定税额，不随油价变动 |
| 城建税 | 增值税的 7% | |
| 教育费附加 | 增值税的 3% | |
| 地方教育费附加 | 增值税的 2% | |
| 调价阈值 | 50 元/吨 | 变动不足此值时搁浅不调 |

**价格变动计算优先级：**

1. **窗口变动**（优先）— 当前价格 vs 上轮调价基准价，基于 Yahoo Finance / 新浪财经历史 K 线数据
2. **当日变动**（回退）— 无法获取历史数据时，使用当日涨跌幅估算

**数据源优先级（K 线数据）：**

1. Yahoo Finance Chart API — 全球稳定可靠
2. 新浪财经 K 线 API — 多接口回退（IndexService → InnerFuturesNewService）

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