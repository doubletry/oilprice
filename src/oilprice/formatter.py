"""消息格式化模块 - 将油价数据格式化为企业微信消息内容"""

from datetime import datetime

from .scraper import OilPriceData


def format_message(data: OilPriceData, province: str) -> tuple[str, str]:
    """将油价数据格式化为企业微信 text_card 所需的标题和描述

    Args:
        data: 完整油价数据
        province: 目标省份名称（如 "广东"、"北京"）

    Returns:
        (title, description) 元组
    """
    today = datetime.now().strftime("%Y年%m月%d日")

    # 查找目标省份的油价
    target_price = None
    for price in data.prices:
        if price.province == province:
            target_price = price
            break

    # 构建标题
    if target_price:
        title = f"⛽ {province}今日油价 ({today})"
    else:
        title = f"⛽ 全国今日油价 ({today})"

    # 构建描述内容
    lines = []

    # 本省油价
    if target_price:
        lines.append(f"📍 {province}油价")
        lines.append(f"  92#汽油: {target_price.price_92} 元/升")
        lines.append(f"  95#汽油: {target_price.price_95} 元/升")
        lines.append(f"  98#汽油: {target_price.price_98} 元/升")
        lines.append(f"  0#柴油: {target_price.price_0} 元/升")
    else:
        # 未找到指定省份，显示提示
        lines.append(f"⚠️ 未找到 {province} 的油价数据")

    # 油价调整信息
    if data.adjustment:
        lines.append("")
        lines.append(f"📢 {data.adjustment.summary}")
        lines.append(f"  {data.adjustment.detail}")

    # 全国油价对比（显示最低和最高）
    if len(data.prices) > 1:
        prices_92 = []
        for p in data.prices:
            try:
                val = float(p.price_92)
                prices_92.append((p.province, val))
            except ValueError:
                continue

        if prices_92:
            prices_92.sort(key=lambda x: x[1])
            cheapest = prices_92[0]
            most_expensive = prices_92[-1]
            lines.append("")
            lines.append(
                f"📊 全国92#: 最低 {cheapest[0]} {cheapest[1]:.2f}"
                f" | 最高 {most_expensive[0]} {most_expensive[1]:.2f}"
            )

    description = "\n".join(lines)
    return title, description


# 省份名称映射: 英文 -> 中文
PROVINCE_MAP = {
    "beijing": "北京",
    "tianjin": "天津",
    "hebei": "河北",
    "shanxi": "山西",
    "neimenggu": "内蒙古",
    "liaoning": "辽宁",
    "jilin": "吉林",
    "heilongjiang": "黑龙江",
    "shanghai": "上海",
    "jiangsu": "江苏",
    "zhejiang": "浙江",
    "anhui": "安徽",
    "fujian": "福建",
    "jiangxi": "江西",
    "shandong": "山东",
    "henan": "河南",
    "hubei": "湖北",
    "hunan": "湖南",
    "guangdong": "广东",
    "guangxi": "广西",
    "hainan": "海南",
    "chongqing": "重庆",
    "sichuan": "四川",
    "guizhou": "贵州",
    "yunnan": "云南",
    "xizang": "西藏",
    "shaanxi": "陕西",
    "gansu": "甘肃",
    "qinghai": "青海",
    "ningxia": "宁夏",
    "xinjiang": "新疆",
}


def get_province_cn(province_key: str) -> str:
    """将省份英文标识转为中文名称

    Args:
        province_key: 省份英文标识或直接中文名称

    Returns:
        中文省份名称
    """
    # 如果已经是中文，直接返回
    if any("\u4e00" <= ch <= "\u9fff" for ch in province_key):
        return province_key
    return PROVINCE_MAP.get(province_key.lower(), province_key)
