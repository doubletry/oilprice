"""油价调整预测生成模块

基于国际油价波动和中国油价调整规则，自动生成油价调整预测信息。

中国成品油定价机制:
- 每10个工作日调整一次国内成品油价格
- 调整依据国际原油（布伦特、迪拜、WTI）加权平均价格变化
- 调整幅度不足每吨50元时，不作调整（搁浅）
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

# 已知调价参考日期（计算起点）
_REFERENCE_DATE = date(2025, 1, 17)


@dataclass
class CrudeOilPrice:
    """国际原油价格"""

    name: str  # 品种名称（如 "布伦特"、"WTI"）
    price: float  # 当前价格（美元/桶）
    change_pct: float | None  # 日涨跌幅百分比


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
                if len(fields) > 7 and fields[7]:
                    try:
                        prev_close = float(fields[7])
                        if prev_close > 0:
                            change_pct = round(
                                (current_price - prev_close) / prev_close * 100,
                                2,
                            )
                    except ValueError:
                        pass

                prices.append(
                    CrudeOilPrice(
                        name=name,
                        price=current_price,
                        change_pct=change_pct,
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


def generate_prediction(today: date | None = None) -> AdjustmentInfo:
    """生成油价调整预测信息

    结合调价周期和国际油价数据，自动生成预测。
    即使国际油价获取失败，仍可提供调价日期信息。

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

    # 3. 根据国际油价生成趋势判断
    price_parts = []
    total_change = 0.0
    change_count = 0

    for cp in crude_prices:
        desc = f"{cp.name}{cp.price:.2f}美元/桶"
        if cp.change_pct is not None:
            arrow = "↑" if cp.change_pct > 0 else "↓" if cp.change_pct < 0 else "→"
            desc += f"({arrow}{abs(cp.change_pct):.2f}%)"
            total_change += cp.change_pct
            change_count += 1
        price_parts.append(desc)

    price_str = "，".join(price_parts)

    if change_count > 0:
        avg_change = total_change / change_count
        # 粗略换算: 国际油价每变化1% ≈ 国内零售价变化约0.05元/升
        est_retail = round(abs(avg_change) * 0.05, 2)

        if abs(avg_change) < 0.5:
            detail = f"国际油价({price_str})波动较小，预计本轮油价搁浅不调整"
        elif avg_change > 0:
            detail = (
                f"国际油价({price_str})呈上涨趋势，" f"预计油价上调约{est_retail}元/升"
            )
        else:
            detail = (
                f"国际油价({price_str})呈下跌趋势，" f"预计油价下调约{est_retail}元/升"
            )
    else:
        detail = f"国际油价: {price_str}"

    return AdjustmentInfo(summary=summary, detail=detail)
