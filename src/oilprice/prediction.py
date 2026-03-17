"""油价调整预测生成模块

基于国际油价波动和中国油价调整规则，自动生成油价调整预测信息。

中国成品油定价机制:
- 每10个工作日调整一次国内成品油价格
- 调整依据国际原油（布伦特、迪拜、WTI）加权平均价格变化
- 调整幅度不足每吨50元时，不作调整（搁浅）

定价链: 国际原油价格(美元/桶) → 汇率转换 → 原油成本(元/吨) → 炼油加工 → 税费 → 零售价(元/升)
"""

from dataclasses import dataclass
from datetime import date, timedelta

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
                        pass

                prices.append(
                    CrudeOilPrice(
                        name=name,
                        price=current_price,
                        change_pct=change_pct,
                        prev_close=prev_close_price,
                    )
                )
            except (IndexError, ValueError) as e:
                logger.debug(f"解析原油价格行失败: {e}")
                continue

        if prices:
            logger.info(f"获取到 {len(prices)} 个原油品种价格")
        else:
            logger.warning("新浪财经API未返回有效原油价格数据")

        return prices

    except requests.RequestException as e:
        logger.warning(f"获取国际原油价格失败: {e}")
        return []


def fetch_exchange_rate() -> float:
    """从新浪财经获取美元兑人民币汇率

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
        if not fields or not fields[0]:
            logger.warning("汇率API未返回有效数据")
            return _DEFAULT_EXCHANGE_RATE

        rate = float(fields[0])
        # 新浪汇率API可能返回百倍数值（如 726.44 表示 7.2644）
        if rate > 100:
            rate = rate / 100
        logger.info(f"当前美元兑人民币汇率: {rate:.4f}")
        return rate

    except (requests.RequestException, ValueError, IndexError) as e:
        logger.warning(f"获取汇率失败，使用默认值 {_DEFAULT_EXCHANGE_RATE}: {e}")
        return _DEFAULT_EXCHANGE_RATE


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

    使用完整定价链计算:
    国际原油价格(美元/桶) → 汇率转换 → 加工成本 → 税费 → 零售价(元/升)

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

    # 1. 计算下次调价日期
    next_date = get_next_adjustment_date(today)
    summary = f"下次油价{next_date.month}月{next_date.day}日24时调整"

    # 2. 获取国际油价
    crude_prices = fetch_crude_oil_prices()

    if not crude_prices:
        detail = "暂无国际油价数据，请关注后续调价通知"
        return AdjustmentInfo(summary=summary, detail=detail)

    # 3. 获取实时汇率
    exchange_rate = fetch_exchange_rate()

    # 4. 计算原油价格变动（美元/桶）
    price_parts = []
    total_change_usd = 0.0
    change_count = 0

    for cp in crude_prices:
        desc = f"{cp.name}{cp.price:.2f}美元/桶"
        if cp.change_pct is not None:
            arrow = "↑" if cp.change_pct > 0 else "↓" if cp.change_pct < 0 else "→"
            desc += f"({arrow}{abs(cp.change_pct):.2f}%)"

            # 计算绝对变动（美元/桶）
            if cp.prev_close is not None and cp.prev_close > 0:
                change_usd = cp.price - cp.prev_close
            else:
                change_usd = cp.price * (cp.change_pct / 100)

            total_change_usd += change_usd
            change_count += 1
        price_parts.append(desc)

    price_str = "，".join(price_parts)

    if change_count > 0:
        avg_change_usd = total_change_usd / change_count

        # 5. 通过完整定价链计算零售价影响
        gasoline_change_per_ton, retail_change_per_liter = (
            _calculate_retail_price_impact(avg_change_usd, exchange_rate)
        )

        # 6. 根据阈值判断调价方向
        if abs(gasoline_change_per_ton) < ADJUSTMENT_THRESHOLD_PER_TON:
            detail = (
                f"国际油价({price_str})，"
                f"汇率{exchange_rate:.2f}，"
                f"折合变动约{gasoline_change_per_ton:+.0f}元/吨"
                f"(不足{ADJUSTMENT_THRESHOLD_PER_TON}元/吨)，"
                f"预计本轮油价搁浅不调整"
            )
        elif avg_change_usd > 0:
            detail = (
                f"国际油价({price_str})呈上涨趋势，"
                f"汇率{exchange_rate:.2f}，"
                f"折合变动约{gasoline_change_per_ton:+.0f}元/吨，"
                f"预计油价上调约{abs(retail_change_per_liter):.2f}元/升"
            )
        else:
            detail = (
                f"国际油价({price_str})呈下跌趋势，"
                f"汇率{exchange_rate:.2f}，"
                f"折合变动约{gasoline_change_per_ton:+.0f}元/吨，"
                f"预计油价下调约{abs(retail_change_per_liter):.2f}元/升"
            )
    else:
        detail = f"国际油价: {price_str}，汇率{exchange_rate:.2f}"

    return AdjustmentInfo(summary=summary, detail=detail)
