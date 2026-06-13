"""口语化日期解析模块

将中文口语化日期表达转换为具体的 date 对象。

支持的表达:
- 标准格式: "6月18日"、"6月18号"、"2025-06-18"
- 基准词: 今天/今日、明天/明日/明儿、后天/后儿、大后天、昨天/昨日/昨儿、前天/前儿、大前天
- 时间后缀: 晚/晚上/晚间/夜里、早/早上/上午、中午、下午、凌晨
- 组合表达: 今晚、明晚、昨晚、明早、后天晚上 等
"""

import re
from datetime import date, timedelta

from loguru import logger

# 基准词 → 相对天数偏移
_BASE_DAY_OFFSETS: dict[str, int] = {
    # 今天
    "今天": 0,
    "今日": 0,
    # 明天
    "明天": 1,
    "明日": 1,
    "明儿": 1,
    "明儿个": 1,
    # 后天
    "后天": 2,
    "后儿": 2,
    "后儿个": 2,
    # 大后天
    "大后天": 3,
    # 昨天
    "昨天": -1,
    "昨日": -1,
    "昨儿": -1,
    "昨儿个": -1,
    # 前天
    "前天": -2,
    "前儿": -2,
    "前儿个": -2,
    # 大前天
    "大前天": -3,
}

# 时间后缀 → 是否需要日期进位（当晚24时 = 次日0时）
# "晚/夜里" + "24时/零点" → 进位到次日
# 其他时间后缀仅影响时间段描述，不影响日期
_TIME_SUFFIXES: list[str] = [
    "晚上",
    "晚间",
    "夜里",
    "夜间",
    "晚",
    "早上",
    "上午",
    "早",
    "中午",
    "下午",
    "傍晚",
    "凌晨",
]

# 组合表达词（直接映射到相对天数）
# 例如 "今晚" = 今天，"明晚" = 明天
_COMPOUND_WORDS: dict[str, int] = {
    "今晚": 0,
    "明晚": 1,
    "昨晚": -1,
    "明早": 1,
    "今早": 0,
    "昨早": -1,
}


def _parse_standard_date(text: str, base_date: date) -> date | None:
    """解析标准日期格式

    支持:
    - "X月X日" / "X月X号" (使用 base_date 的年份)
    - "YYYY年X月X日" / "YYYY年X月X号"
    - "YYYY-MM-DD" / "YYYY/MM/DD"

    Args:
        text: 包含日期的文本
        base_date: 基准日期（用于补全年份）

    Returns:
        解析后的日期，失败返回 None
    """
    # YYYY年X月X日 / YYYY年X月X号
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # X月X日 / X月X号（使用 base_date 的年份）
    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", text)
    if m:
        try:
            return date(base_date.year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass

    # YYYY-MM-DD / YYYY/MM/DD
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    return None


def _parse_colloquial_date(text: str, base_date: date) -> date | None:
    """解析口语化日期表达

    优先匹配组合词（如"今晚"），再匹配"基准词+时间后缀"的组合，
    最后匹配单独的基准词。

    Args:
        text: 包含口语化日期的文本
        base_date: 基准日期

    Returns:
        解析后的日期，失败返回 None
    """
    # 1. 优先匹配组合词（今晚、明晚、昨晚 等）
    for word, offset in _COMPOUND_WORDS.items():
        if word in text:
            result = base_date + timedelta(days=offset)
            logger.debug(f"口语化日期匹配: '{word}' → {result}")
            return result

    # 2. 匹配"基准词+时间后缀"组合
    # 先按长度降序排列基准词，避免"前天"被"前"匹配
    sorted_bases = sorted(_BASE_DAY_OFFSETS.items(), key=lambda x: -len(x[0]))
    for word, offset in sorted_bases:
        if word in text:
            result = base_date + timedelta(days=offset)
            logger.debug(f"口语化日期匹配: '{word}' → {result}")
            return result

    return None


def _has_midnight_modifier(text: str) -> bool:
    """检查文本中是否包含午夜时间修饰词

    "24时"、"24:00"、"零点"、"0点" 等表示午夜的表达，
    配合"今晚"使用时意味着日期需要进位到次日。

    Args:
        text: 待检查的文本

    Returns:
        是否包含午夜修饰
    """
    return bool(re.search(r"24\s*[时点:：]?\s*0?0?|零点|0\s*点\s*整?", text))


def resolve_date(text: str, base_date: date | None = None) -> date | None:
    """从文本中解析日期

    按优先级依次尝试:
    1. 标准日期格式（X月X日、YYYY-MM-DD 等）
    2. 口语化日期表达（今晚、明天、后天 等）

    Args:
        text: 包含日期信息的文本（如 "下次油价今晚24时调整"）
        base_date: 基准日期，默认为当天

    Returns:
        解析出的 date 对象，失败返回 None
    """
    if base_date is None:
        base_date = date.today()

    # 1. 优先尝试标准日期格式（更精确）
    result = _parse_standard_date(text, base_date)
    if result is not None:
        logger.debug(f"标准日期解析: '{text}' → {result}")
        return result

    # 2. 尝试口语化表达
    result = _parse_colloquial_date(text, base_date)
    if result is not None:
        return result

    logger.debug(f"日期解析失败: '{text}'")
    return None


def resolve_date_summary(text: str, base_date: date | None = None) -> str:
    """从文本中解析日期并返回格式化的摘要字符串

    用于生成类似 "下次油价6月18日24时调整" 的摘要文本。

    Args:
        text: 包含日期信息的原始文本
        base_date: 基准日期，默认为当天

    Returns:
        格式化的摘要字符串，如 "下次油价6月18日24时调整"；
        解析失败返回 ""
    """
    resolved = resolve_date(text, base_date)
    if resolved is None:
        return ""

    return f"下次油价{resolved.month}月{resolved.day}日24时调整"
