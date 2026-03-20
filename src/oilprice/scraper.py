"""油价数据抓取模块

数据源:
- 主数据源: 汽车之家 (autohome.com.cn/oil/) — 获取全国各省实时油价
- 补充数据源: 汽油价格网 (qiyoujiage.com) — 获取油价调整预测信息
- 备选方案: 自动生成预测 — 基于国际油价和调价周期生成调价预测
"""

import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
from loguru import logger

# 统一请求头，模拟浏览器访问
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# 数据源 URL
AUTOHOME_OIL_URL = "https://www.autohome.com.cn/oil/"
QIYOUJIAGE_URL = "http://www.qiyoujiage.com/"

# 请求超时时间（秒）
REQUEST_TIMEOUT = 15


@dataclass
class OilPrice:
    """单个省份的油价数据"""

    province: str  # 省份名称
    price_92: str  # 92# 汽油价格
    price_95: str  # 95# 汽油价格
    price_98: str  # 98# 汽油价格
    price_0: str  # 0# 柴油价格


@dataclass
class AdjustmentInfo:
    """油价调整预测信息"""

    summary: str  # 调价摘要，如 "下次油价3月20日24时调整"
    detail: str  # 调价详情，如 "油价上涨0.55元/升"


@dataclass
class OilPriceData:
    """完整的油价数据"""

    prices: list[OilPrice]  # 各省份油价列表
    adjustment: AdjustmentInfo | None  # 来自汽油价格网的调价信息


def fetch_page(url: str) -> BeautifulSoup | None:
    """获取并解析网页

    Args:
        url: 目标 URL

    Returns:
        BeautifulSoup 对象，失败返回 None
    """
    try:
        response = requests.get(url, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        response.encoding = "utf-8"
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        logger.error(f"请求 {url} 失败: {e}")
        return None


def parse_prices_from_autohome(soup: BeautifulSoup) -> list[OilPrice]:
    """从汽车之家页面解析全国各省油价

    汽车之家的油价表格结构:
    | 地区 | 92#汽油 | 95#汽油 | 98#汽油 | 0#柴油 |

    Args:
        soup: 汽车之家油价页面的 BeautifulSoup 对象

    Returns:
        各省油价列表
    """
    prices = []
    table = soup.find("table")
    if not table:
        logger.error("汽车之家: 未找到油价表格")
        return prices

    rows = table.find_all("tr")
    # 跳过表头行
    for row in rows[1:]:
        cells = [td.text.strip() for td in row.find_all("td")]
        if len(cells) >= 5:
            prices.append(
                OilPrice(
                    province=cells[0],
                    price_92=cells[1],
                    price_95=cells[2],
                    price_98=cells[3],
                    price_0=cells[4],
                )
            )

    if not prices:
        logger.warning("汽车之家: 表格中未解析到任何油价数据")

    return prices


def parse_adjustment_from_qiyoujiage(soup: BeautifulSoup) -> AdjustmentInfo | None:
    """从汽油价格网解析油价调整预测信息

    解析 #all / #rightTop / #left 区域中的调价通知文本。
    兼容多种历史格式:
    - 新格式: "目前预计上调油价1900元/吨(1.44元/升-1.72元/升)"
    - 旧格式: "油价上涨0.55元/升-0.67元/升(每吨汽柴油价格分别上调695元和670元)"
    - 搁浅: "目前预计油价搁浅不调整" / "油价不调整"

    Args:
        soup: 汽油价格网页面的 BeautifulSoup 对象

    Returns:
        调价信息，解析失败返回 None
    """
    # 尝试从多个容器中获取调价文本
    for container_id in ["all", "rightTop", "left"]:
        container = soup.find(id=container_id)
        if not container:
            continue

        text = container.get_text(separator=" ", strip=True)
        if not text:
            continue

        # 提取调价日期信息: "下次油价X月X日24时调整"
        date_match = re.search(r"(下次油价\S+调整)", text)
        summary = date_match.group(1) if date_match else ""

        # 提取调价幅度（按优先级尝试多种格式）
        detail = _extract_adjustment_detail(text)

        if summary or detail:
            return AdjustmentInfo(
                summary=summary or "调价日期未知",
                detail=detail or "调价幅度未知",
            )

    logger.warning("汽油价格网: 未解析到油价调整信息")
    return None


def _extract_adjustment_detail(text: str) -> str:
    """从文本中提取油价调价幅度详情

    按优先级依次尝试匹配:
    1. 预计上调/下调油价XXX元/吨(X.XX元/升-X.XX元/升)
    2. 预计油价搁浅/不调整
    3. 油价上涨/下跌X.XX元/升...(每吨...)
    4. 油价不调整
    5. 兜底: "调整"后到标点之间含价格关键词的文本

    Args:
        text: 页面文本

    Returns:
        调价幅度描述，未匹配返回空字符串
    """
    patterns = [
        # 新格式: "目前预计上调油价1900元/吨(1.44元/升-1.72元/升)"
        r"((?:目前)?预计[上下]调油价\d+元/吨(?:\([^)]*\))?)",
        # 搁浅: "目前预计油价搁浅不调整(搁浅)"
        r"((?:目前)?预计油价(?:搁浅)?不?调整(?:\([^)]*\))?)",
        # 旧格式: "油价上涨0.55元/升-0.67元/升(每吨汽柴油价格分别上调695元和670元)"
        r"(油价(?:上涨|下跌)\d+\.?\d*元/升[^，。）]*(?:\([^)]*\))?)",
        # 纯文字: "油价不调整"
        r"(油价不调整)",
        # 兜底: "调整"后到标点之间含价格单位的文本
        r"(?:调整\s*)((?:目前)?[^，。]+(?:元/吨|元/升|搁浅|不调整)[^，。]*)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip()
    return ""


def _try_generate_prediction() -> AdjustmentInfo | None:
    """[Deprecated] 已废弃，保留以兼容旧代码"""
    return None


def scrape_oil_prices() -> OilPriceData:
    """抓取完整的油价数据

    从汽车之家获取实时油价，从汽油价格网获取调价预测。

    Returns:
        OilPriceData 完整油价数据

    Raises:
        RuntimeError: 无法获取任何油价数据时抛出
    """
    # 1. 从汽车之家获取实时油价（主数据源）
    logger.info("正在从汽车之家获取实时油价...")
    autohome_soup = fetch_page(AUTOHOME_OIL_URL)
    if not autohome_soup:
        raise RuntimeError("无法访问汽车之家油价页面")

    prices = parse_prices_from_autohome(autohome_soup)
    if not prices:
        raise RuntimeError("无法从汽车之家解析油价数据")

    logger.info(f"成功获取 {len(prices)} 个省份的油价数据")

    adjustment = None

    # 2. 从汽油价格网获取调价预测
    logger.info("正在从汽油价格网获取调价预测信息...")
    qiyoujiage_soup = fetch_page(QIYOUJIAGE_URL)
    if qiyoujiage_soup:
        adjustment = parse_adjustment_from_qiyoujiage(qiyoujiage_soup)
        if adjustment:
            logger.info(f"调价信息: {adjustment.summary} {adjustment.detail}")
        else:
            logger.warning("未能获取调价预测信息")
    else:
        logger.warning("无法访问汽油价格网")

    return OilPriceData(prices=prices, adjustment=adjustment)
