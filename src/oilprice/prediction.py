"""油价调整预测生成模块

基于国际油价波动和中国油价调整规则，自动生成油价调整预测信息。

中国成品油定价机制:
- 每10个工作日调整一次国内成品油价格
- 调整依据国际原油（布伦特、迪拜、WTI）加权平均价格变化
- 调整幅度不足每吨50元时，不作调整（搁浅）

定价链: 国际原油价格(美元/桶) → 汇率转换 → 原油成本(元/吨) → 炼油加工 → 税费 → 零售价(元/升)
"""

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import requests
from loguru import logger

from .scraper import AdjustmentInfo

# 请求配置
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.sina.com.cn",
}
_TIMEOUT = 15

# 新浪财经国际期货行情 API
_SINA_HQ_URL = "https://hq.sinajs.cn/list=hf_OIL,hf_CL"

# 新浪财经汇率 API（美元兑人民币）
_SINA_FX_URL = "https://hq.sinajs.cn/list=fx_susdcny"

# 新浪财经期货日K线数据 API（获取历史收盘价）
# 按优先级尝试多个接口地址，兼容不同环境
_SINA_KLINE_URL_PATTERNS = [
    # 优先: IndexService 接口（广泛验证可用于国际期货 hf_OIL/hf_CL）
    (
        "https://stock2.finance.sina.com.cn/futures/api/json.php/"
        "IndexService.getInnerFuturesDailyKLine?symbol={symbol}"
    ),
    # 备用: InnerFuturesNewService jsonp 格式
    (
        "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/"
        "var%20_result=/InnerFuturesNewService.getDailyKLine?symbol={symbol}"
    ),
]

# Yahoo Finance Chart API（获取国际期货历史收盘价，全球可用、稳定可靠）
_YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# Yahoo Finance 品种映射
_YAHOO_SYMBOLS = {
    "布伦特": "BZ=F",  # ICE Brent Crude Oil Futures
    "WTI": "CL=F",  # NYMEX WTI Crude Oil Futures
}

# 已知调价参考日期（计算起点）
_REFERENCE_DATE = date(2025, 1, 17)

# ===== 中国成品油定价机制常量 =====

# 原油转换: 1吨原油 ≈ 7.33桶
BARRELS_PER_TON = 7.33

# 汽油密度转换: 1吨92#汽油 ≈ 1351升
LITERS_PER_TON_GASOLINE = 1351

# 炼油出油率（原油到汽油的转化率，约40%~50%）
GASOLINE_YIELD_RATE = 0.45

# 税率
VAT_RATE = 0.13  # 增值税 13%
CONSUMPTION_TAX_PER_LITER = 1.52  # 汽油消费税（元/升，固定税额，不随油价变动）
URBAN_MAINTENANCE_TAX_RATE = 0.07  # 城市维护建设税（增值税的7%）
EDUCATION_SURCHARGE_RATE = 0.03  # 教育费附加（增值税的3%）
LOCAL_EDUCATION_SURCHARGE_RATE = 0.02  # 地方教育费附加（增值税的2%）

# 附加税合计系数（基于增值税额）
_SURCHARGE_RATE = (
    URBAN_MAINTENANCE_TAX_RATE + EDUCATION_SURCHARGE_RATE + LOCAL_EDUCATION_SURCHARGE_RATE
)

# 调价阈值: 变化不足50元/吨时搁浅不调整
ADJUSTMENT_THRESHOLD_PER_TON = 50

# 默认美元兑人民币汇率（当API不可用时使用）
_DEFAULT_EXCHANGE_RATE = 7.20


@dataclass
class CrudeOilPrice:
    """国际原油价格"""

    name: str  # 品种名称（如 "布伦特"、"WTI"）
    price: float  # 当前价格（美元/桶）
    change_pct: float | None  # 日涨跌幅百分比
    prev_close: float | None = None  # 前收盘价（美元/桶）


def _add_working_days(start: date, days: int) -> date:
    """从起始日期起计算第 N 个工作日

    仅跳过周末（周六日），不处理法定节假日。
    实际调价日可能因节假日偏差 1-3 天。

    Args:
        start: 起始日期
        days: 工作日天数

    Returns:
        第 N 个工作日的日期
    """
    current = start
    counted = 0
    while counted < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # 周一至周五
            counted += 1
    return current


def get_next_adjustment_date(today: date | None = None) -> date:
    """计算下次油价调整日期

    基于已知基准日（2025-01-17）和10个工作日周期推算。
    实际日期可能因法定节假日偏差 1-3 天。

    Args:
        today: 当前日期，默认使用系统日期

    Returns:
        下次调价日期
    """
    if today is None:
        today = date.today()

    current = _REFERENCE_DATE
    while current < today:
        current = _add_working_days(current, 10)

    return current


def get_previous_adjustment_date(today: date | None = None) -> date | None:
    """计算上一次油价调整日期

    基于已知基准日（2025-01-17）和10个工作日周期推算。

    Args:
        today: 当前日期，默认使用系统日期

    Returns:
        上一次调价日期，如果在基准日当天或之前返回 None
    """
    if today is None:
        today = date.today()

    current = _REFERENCE_DATE
    prev = None
    while current < today:
        prev = current
        current = _add_working_days(current, 10)

    return prev


def fetch_crude_oil_prices() -> list[CrudeOilPrice]:
    """从新浪财经获取国际原油价格

    获取布伦特原油和 WTI 原油的实时行情数据。

    Returns:
        原油价格列表，获取失败返回空列表
    """
    try:
        response = requests.get(_SINA_HQ_URL, headers=_HEADERS, timeout=_TIMEOUT)
        response.raise_for_status()
        response.encoding = "gbk"

        prices = []
        for line in response.text.strip().split(";"):
            line = line.strip()
            if not line or '"' not in line:
                continue

            try:
                data_str = line.split('"')[1]
                fields = data_str.split(",")
                if not fields or not fields[0]:
                    continue

                current_price = float(fields[0])

                # 判断原油品种
                if "hf_OIL" in line:
                    name = "布伦特"
                elif "hf_CL" in line:
                    name = "WTI"
                else:
                    continue

                # 尝试计算日涨跌幅（基于前收盘价）
                change_pct = None
                prev_close_price = None
                if len(fields) > 7 and fields[7]:
                    try:
                        prev_close_price = float(fields[7])
                        if prev_close_price > 0:
                            change_pct = round(
                                (current_price - prev_close_price)
                                / prev_close_price
                                * 100,
                                2,
                            )
                    except ValueError:
                        logger.exception(f"{name}解析前收盘价失败，字段值: {fields[7]}")

                prices.append(
                    CrudeOilPrice(
                        name=name,
                        price=current_price,
                        change_pct=change_pct,
                        prev_close=prev_close_price,
                    )
                )
            except (IndexError, ValueError):
                logger.exception(f"解析原油价格行失败: {line[:100]}")
                continue

        if prices:
            logger.info(f"获取到 {len(prices)} 个原油品种价格")
        else:
            logger.warning("新浪财经API未返回有效原油价格数据")

        return prices

    except requests.RequestException:
        logger.exception("获取国际原油价格失败")
        return []


def fetch_exchange_rate() -> float:
    """从新浪财经获取美元兑人民币汇率

    新浪外汇API返回格式（字段以逗号分隔）:
    "名称/时间,现价,今开,昨收,最高,最低,买价,日期,时间,..."
    注意: fields[0] 可能是名称(如"美元人民币")或时间(如"22:25:02")，
    实际汇率值需要在后续字段中查找。

    Returns:
        美元兑人民币汇率，获取失败返回默认值
    """
    try:
        response = requests.get(_SINA_FX_URL, headers=_HEADERS, timeout=_TIMEOUT)
        response.raise_for_status()
        response.encoding = "gbk"

        text = response.text.strip()
        if '"' not in text:
            logger.warning("汇率API响应格式异常")
            return _DEFAULT_EXCHANGE_RATE

        data_str = text.split('"')[1]
        fields = data_str.split(",")
        if not fields:
            logger.warning("汇率API未返回有效数据")
            return _DEFAULT_EXCHANGE_RATE

        # 遍历字段查找合理的汇率值（应在 1~100 之间，或百倍值 100~1000）
        rate = None
        for field in fields:
            field = field.strip()
            if not field:
                continue
            try:
                val = float(field)
            except ValueError:
                continue
            # 合理汇率范围: 直接值 1~15，或百倍值 100~1500
            if 1.0 <= val <= 15.0:
                rate = val
                break
            elif 100.0 <= val <= 1500.0:
                rate = val / 100
                break

        if rate is None:
            logger.warning(f"汇率API未找到有效汇率值，字段: {fields}")
            return _DEFAULT_EXCHANGE_RATE

        logger.info(f"当前美元兑人民币汇率: {rate:.4f}")
        return rate

    except (requests.RequestException, ValueError, IndexError):
        logger.exception(f"获取汇率失败，使用默认值 {_DEFAULT_EXCHANGE_RATE}")
        return _DEFAULT_EXCHANGE_RATE


def _parse_kline_json(text: str) -> list | None:
    """从K线API响应文本中解析JSON数组

    支持纯JSON和JSONP包装两种响应格式。
    API可能返回 null、空字符串或格式异常的数据。

    Args:
        text: API响应文本

    Returns:
        解析后的K线数据列表，解析失败返回 None
    """
    text = text.strip()

    # 空响应或 null
    if not text or text == "null":
        return None

    # 纯JSON数组: [...]
    if text.startswith("["):
        data = json.loads(text)
        return data if data else None

    # JSONP包装: var _result=([...]); 或类似格式
    start_idx = text.find("[")
    end_idx = text.rfind("]")
    if start_idx < 0 or end_idx < 0:
        return None

    json_str = text[start_idx : end_idx + 1]
    data = json.loads(json_str)
    return data if data else None


def _fetch_kline_from_sina(symbol: str, name: str) -> list | None:
    """从新浪财经获取期货K线数据，尝试多个API接口

    按优先级尝试 _SINA_KLINE_URL_PATTERNS 中的接口地址，
    返回第一个成功解析的K线数据。

    Args:
        symbol: 期货品种代码（如 "hf_OIL"）
        name: 品种中文名称（用于日志）

    Returns:
        K线数据列表，所有接口都失败时返回 None
    """
    for url_tpl in _SINA_KLINE_URL_PATTERNS:
        url = url_tpl.format(symbol=symbol)
        try:
            response = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            response.raise_for_status()
            response.encoding = "utf-8"
            text = response.text.strip()

            data = _parse_kline_json(text)
            if data:
                logger.info(f"{name}新浪K线数据获取成功，共{len(data)}条记录")
                return data
            else:
                logger.debug(
                    f"{name}新浪K线接口返回空数据，尝试下一个接口。"
                    f"URL: {url}，响应前100字符: {text[:100]}"
                )
        except (requests.RequestException, json.JSONDecodeError):
            logger.exception(f"{name}新浪K线接口请求失败: {url}")
            continue

    logger.info(f"新浪财经{name}K线数据获取失败，将尝试Yahoo Finance")
    return None


def _fetch_kline_from_yahoo(name: str) -> list[dict] | None:
    """从 Yahoo Finance Chart API 获取期货日K线数据

    Yahoo Finance 是全球最稳定的免费金融数据源之一。
    API 返回 JSON 格式的时间序列数据。

    Args:
        name: 品种中文名称（"布伦特" 或 "WTI"）

    Returns:
        标准化的K线数据列表 [{"day": "YYYY-MM-DD", "close": "xx.xx"}, ...]，
        获取失败返回 None
    """
    yahoo_symbol = _YAHOO_SYMBOLS.get(name)
    if not yahoo_symbol:
        logger.debug(f"Yahoo Finance 无{name}对应品种映射")
        return None

    url = _YAHOO_CHART_URL.format(symbol=yahoo_symbol)
    params = {
        "range": "1mo",
        "interval": "1d",
        "includePrePost": "false",
    }
    headers = {
        "User-Agent": _HEADERS["User-Agent"],
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        chart = data.get("chart", {})
        results = chart.get("result")
        if not results:
            error = chart.get("error")
            logger.debug(f"Yahoo Finance {name}响应无数据: {error}")
            return None

        result = results[0]
        timestamps = result.get("timestamp")
        quotes = result.get("indicators", {}).get("quote", [{}])
        if not quotes:
            logger.debug(f"Yahoo Finance {name}无quote数据")
            return None

        closes = quotes[0].get("close", [])
        if not timestamps or not closes:
            logger.debug(f"Yahoo Finance {name}无时间或收盘价数据")
            return None

        # 转换为标准化K线格式
        kline_data = []
        for ts, close in zip(timestamps, closes):
            if close is None:
                continue
            # Yahoo Finance 返回 UTC 时间戳
            trade_date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            kline_data.append({"day": trade_date, "close": str(close)})

        if kline_data:
            logger.info(f"{name}Yahoo Finance K线数据获取成功，共{len(kline_data)}条记录")
            return kline_data
        else:
            logger.debug(f"Yahoo Finance {name}解析后无有效K线数据")
            return None

    except (requests.RequestException, json.JSONDecodeError, KeyError):
        logger.exception(f"Yahoo Finance {name}K线数据获取失败")
        return None


def _fetch_kline_data(symbol: str, name: str) -> list | None:
    """获取期货K线数据，按优先级尝试多个数据源

    数据源优先级:
    1. Yahoo Finance Chart API（全球稳定可靠）
    2. 新浪财经K线API（多接口回退）

    Args:
        symbol: 新浪期货品种代码（如 "hf_OIL"）
        name: 品种中文名称（用于日志和Yahoo品种映射）

    Returns:
        K线数据列表，所有数据源都失败时返回 None
    """
    # 优先使用 Yahoo Finance（更稳定可靠）
    yahoo_data = _fetch_kline_from_yahoo(name)
    if yahoo_data:
        return yahoo_data

    # 回退到新浪财经
    sina_data = _fetch_kline_from_sina(symbol, name)
    if sina_data:
        return sina_data

    logger.warning(f"获取{name}历史K线数据失败，所有数据源均不可用")
    return None


def _find_closest_price(
    data: list, ref_date: date, name: str, max_diff_days: int = 5
) -> float | None:
    """从K线数据中查找距离参考日期最近交易日的收盘价

    Args:
        data: K线数据列表（支持多种格式）
        ref_date: 参考日期
        name: 品种中文名称（用于日志）
        max_diff_days: 最大容差天数

    Returns:
        收盘价，未找到合适数据返回 None
    """
    best_price = None
    best_diff = None

    for entry in data:
        try:
            if isinstance(entry, dict):
                # 支持多种key格式: "day"/"date"/"d" 和 "close"/"c"
                entry_date_str = (
                    entry.get("day")
                    or entry.get("date")
                    or entry.get("d", "")
                )
                close_str = entry.get("close") or entry.get("c", "")
            elif isinstance(entry, list) and len(entry) >= 5:
                entry_date_str = str(entry[0])
                close_str = str(entry[4])
            else:
                continue

            if not entry_date_str or not close_str:
                continue

            entry_date = date.fromisoformat(entry_date_str)
            close_price = float(close_str)
            diff = abs((entry_date - ref_date).days)

            if best_diff is None or diff < best_diff:
                best_diff = diff
                best_price = close_price
        except (ValueError, TypeError):
            logger.exception(f"解析{name}K线数据条目失败: {entry}")
            continue

    if best_price is not None and best_diff is not None and best_diff <= max_diff_days:
        return best_price
    return None


def fetch_reference_crude_prices(ref_date: date) -> dict[str, float] | None:
    """获取上次调价日期附近的原油收盘价作为基准价

    按优先级尝试多个数据源获取K线数据:
    1. Yahoo Finance Chart API（全球稳定可靠）
    2. 新浪财经K线API（多接口回退）

    从K线数据中查找距离参考日期最近交易日的收盘价。

    Args:
        ref_date: 参考日期（上次调价日）

    Returns:
        {"布伦特": price, "WTI": price} 字典，获取失败返回 None
    """
    symbols = [("hf_OIL", "布伦特"), ("hf_CL", "WTI")]
    ref_prices: dict[str, float] = {}

    for symbol, name in symbols:
        data = _fetch_kline_data(symbol, name)
        if not data:
            continue

        price = _find_closest_price(data, ref_date, name)
        if price is not None:
            ref_prices[name] = price
            logger.info(f"{name}上轮调价参考价: {price:.2f}美元/桶")

    if ref_prices:
        logger.info(f"获取到 {len(ref_prices)} 个品种的调价基准价")
    else:
        logger.warning("未能获取调价基准价，将使用当日变动数据")

    return ref_prices if ref_prices else None


def _calculate_retail_price_impact(
    crude_change_usd: float,
    exchange_rate: float,
) -> tuple[float, float]:
    """计算原油价格变动对零售汽油价格的影响

    定价链:
    原油变动(美元/桶) → 原油变动(元/吨) → 汽油成本变动(元/吨) → 含税零售变动(元/升)

    Args:
        crude_change_usd: 原油价格变动（美元/桶）
        exchange_rate: 美元兑人民币汇率

    Returns:
        (汽油成本变动_元/吨, 零售价变动_元/升)
    """
    # 1. 原油成本变动（元/吨原油）
    crude_change_cny_per_ton = crude_change_usd * BARRELS_PER_TON * exchange_rate

    # 2. 汽油成本变动（元/吨汽油）— 考虑炼油出油率
    gasoline_change_per_ton = crude_change_cny_per_ton / GASOLINE_YIELD_RATE

    # 3. 含增值税的零售价变动（元/吨）
    retail_change_per_ton = gasoline_change_per_ton * (1 + VAT_RATE)

    # 4. 附加税影响（城建税+教育费附加，基于增值税额）
    vat_amount = gasoline_change_per_ton * VAT_RATE
    surcharge = vat_amount * _SURCHARGE_RATE
    retail_change_per_ton += surcharge

    # 5. 转换为元/升
    retail_change_per_liter = retail_change_per_ton / LITERS_PER_TON_GASOLINE

    return gasoline_change_per_ton, round(retail_change_per_liter, 2)


def generate_prediction(today: date | None = None) -> AdjustmentInfo:
    """生成油价调整预测信息

    使用完整定价链计算当前油价相对于上次调价时的变动:
    国际原油价格(美元/桶) → 汇率转换 → 加工成本 → 税费 → 零售价(元/升)

    价格变动计算优先级:
    1. 优先使用上轮调价基准价（窗口变动，更准确）
    2. 无法获取历史数据时，使用当日涨跌幅（回退方案）

    考虑因素:
    - 国际原油价格（布伦特、WTI）
    - 美元兑人民币汇率
    - 炼油加工出油率
    - 增值税、消费税、附加税
    - 调价阈值（50元/吨）

    Args:
        today: 当前日期，默认使用系统日期

    Returns:
        调价预测信息
    """
    if today is None:
        today = date.today()

    # 1. 计算调价日期
    next_date = get_next_adjustment_date(today)
    prev_date = get_previous_adjustment_date(today)
    summary = f"下次油价{next_date.month}月{next_date.day}日24时调整"

    # 2. 获取国际油价
    crude_prices = fetch_crude_oil_prices()

    if not crude_prices:
        detail = "暂无国际油价数据，请关注后续调价通知"
        return AdjustmentInfo(summary=summary, detail=detail)

    # 3. 获取实时汇率
    exchange_rate = fetch_exchange_rate()

    # 4. 尝试获取上轮调价基准价（用于计算窗口变动）
    ref_prices = fetch_reference_crude_prices(prev_date) if prev_date else None

    # 5. 计算原油价格变动（美元/桶）
    price_parts = []
    total_change_usd = 0.0
    change_count = 0
    using_window_change = False

    for cp in crude_prices:
        if ref_prices and cp.name in ref_prices:
            # 使用窗口变动: 当前价格 vs 上轮调价基准价
            ref_price = ref_prices[cp.name]
            if ref_price > 0:
                change_usd = cp.price - ref_price
                change_pct = (change_usd / ref_price) * 100
                arrow = "↑" if change_usd > 0 else "↓" if change_usd < 0 else "→"
                desc = f"{cp.name}{cp.price:.2f}美元/桶({arrow}{abs(change_pct):.2f}%)"
                total_change_usd += change_usd
                change_count += 1
                using_window_change = True
            else:
                desc = f"{cp.name}{cp.price:.2f}美元/桶"
        elif cp.change_pct is not None:
            # 回退: 使用当日涨跌幅
            arrow = "↑" if cp.change_pct > 0 else "↓" if cp.change_pct < 0 else "→"
            desc = f"{cp.name}{cp.price:.2f}美元/桶({arrow}{abs(cp.change_pct):.2f}%)"
            if cp.prev_close is not None and cp.prev_close > 0:
                change_usd = cp.price - cp.prev_close
            else:
                change_usd = cp.price * (cp.change_pct / 100)
            total_change_usd += change_usd
            change_count += 1
        else:
            desc = f"{cp.name}{cp.price:.2f}美元/桶"
        price_parts.append(desc)

    price_str = "，".join(price_parts)
    change_label = "较上轮调价" if using_window_change else "当日"

    if change_count > 0:
        avg_change_usd = total_change_usd / change_count

        # 6. 通过完整定价链计算零售价影响
        gasoline_change_per_ton, retail_change_per_liter = (
            _calculate_retail_price_impact(avg_change_usd, exchange_rate)
        )

        # 7. 根据阈值判断调价方向
        if abs(gasoline_change_per_ton) < ADJUSTMENT_THRESHOLD_PER_TON:
            detail = (
                f"国际油价({price_str})，"
                f"汇率{exchange_rate:.2f}，"
                f"{change_label}变动约{gasoline_change_per_ton:+.0f}元/吨"
                f"(不足{ADJUSTMENT_THRESHOLD_PER_TON}元/吨)，"
                f"预计本轮油价搁浅不调整"
            )
        elif avg_change_usd > 0:
            detail = (
                f"国际油价({price_str})呈上涨趋势，"
                f"汇率{exchange_rate:.2f}，"
                f"{change_label}变动约{gasoline_change_per_ton:+.0f}元/吨，"
                f"预计油价上调约{abs(retail_change_per_liter):.2f}元/升"
            )
        else:
            detail = (
                f"国际油价({price_str})呈下跌趋势，"
                f"汇率{exchange_rate:.2f}，"
                f"{change_label}变动约{gasoline_change_per_ton:+.0f}元/吨，"
                f"预计油价下调约{abs(retail_change_per_liter):.2f}元/升"
            )
    else:
        detail = f"国际油价: {price_str}，汇率{exchange_rate:.2f}"

    return AdjustmentInfo(summary=summary, detail=detail)
