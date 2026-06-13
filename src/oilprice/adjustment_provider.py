"""油价调整信息多数据源框架

提供可扩展的数据源接口和管理器，支持按优先级从多个网站获取油价调整预测信息。

架构:
- AdjustmentProvider: 抽象接口，每个数据源实现一个 Provider
- ProviderManager: 按优先级尝试多个 Provider，返回第一个成功的结果
- 已实现的 Provider:
  - QiyoujiageProvider: 汽油价格网 (qiyoujiage.com)
  - AutohomeProvider: 汽车之家 (autohome.com.cn)
  - CngoldProvider: 金投网 (cngold.org)
"""

import re
from abc import ABC, abstractmethod
from datetime import date

import requests
from bs4 import BeautifulSoup
from loguru import logger

from .date_resolver import resolve_date, resolve_date_summary
from .scraper import AdjustmentInfo

# 统一请求头
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

_REQUEST_TIMEOUT = 15


def _fetch_page(url: str) -> BeautifulSoup | None:
    """获取并解析网页"""
    try:
        response = requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
        response.raise_for_status()
        response.encoding = "utf-8"
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        logger.error(f"请求 {url} 失败: {e}")
        return None


class AdjustmentProvider(ABC):
    """油价调整信息数据源抽象接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称（用于日志）"""
        ...

    @abstractmethod
    def fetch(self) -> AdjustmentInfo | None:
        """获取油价调整预测信息

        Returns:
            AdjustmentInfo 或 None（获取失败时）
        """
        ...


class QiyoujiageProvider(AdjustmentProvider):
    """汽油价格网数据源

    解析 http://www.qiyoujiage.com/ 页面中的调价信息。
    增强版：支持口语化日期解析（今晚、明晚、昨晚 等）。
    """

    @property
    def name(self) -> str:
        return "汽油价格网"

    def fetch(self) -> AdjustmentInfo | None:
        soup = _fetch_page("http://www.qiyoujiage.com/")
        if not soup:
            return None
        return self._parse(soup)

    def _parse(self, soup: BeautifulSoup) -> AdjustmentInfo | None:
        """解析汽油价格网调价信息"""
        for container_id in ["all", "rightTop", "left"]:
            container = soup.find(id=container_id)
            if not container:
                continue

            text = container.get_text(separator=" ", strip=True)
            if not text:
                continue

            # 提取调价日期信息
            summary = self._extract_summary(text)
            # 提取调价幅度
            detail = self._extract_detail(text)

            if summary or detail:
                return AdjustmentInfo(
                    summary=summary or "调价日期未知",
                    detail=detail or "调价幅度未知",
                )

        logger.warning("汽油价格网: 未解析到油价调整信息")
        return None

    def _extract_summary(self, text: str) -> str:
        """提取调价日期摘要，支持口语化日期"""
        # 先尝试标准格式
        date_match = re.search(r"(下次油价\S+调整)", text)
        if date_match:
            raw = date_match.group(1)
            # 尝试解析其中的日期
            resolved_summary = resolve_date_summary(raw)
            if resolved_summary:
                return resolved_summary
            # 如果原始文本中已包含标准日期，直接返回
            return raw

        # 尝试更宽泛的匹配
        # 例如: "油价今晚24时调整"、"油价明天调整"
        broad_match = re.search(
            r"油价\s*(今晚|明晚|昨晚|明天|后天|今天|昨天)\S*调整", text
        )
        if broad_match:
            resolved_summary = resolve_date_summary(text)
            if resolved_summary:
                return resolved_summary

        return ""

    def _extract_detail(self, text: str) -> str:
        """提取调价幅度详情"""
        patterns = [
            # 新格式: "目前预计上调油价1900元/吨(1.44元/升-1.72元/升)"
            r"((?:目前)?预计[上下]调油价\d+元/吨(?:\([^)]*\))?)",
            # 搁浅: "目前预计油价搁浅不调整"
            r"((?:目前)?预计油价(?:搁浅)?不?调整(?:\([^)]*\))?)",
            # 旧格式: "油价上涨0.55元/升-0.67元/升(每吨...)"
            r"(油价(?:上涨|下跌|上调|下调)\d+\.?\d*元/升[^，。）]*(?:\([^)]*\))?)",
            # 预计下调/上调幅度: "目前预计下调270元/吨(0.21元/升-0.24元/升)"
            r"((?:目前)?预计[上下]调\d+元/吨(?:\([^)]*\))?)",
            # 纯文字: "油价不调整"
            r"(油价不调整)",
            # 兜底
            r"(?:调整\s*)((?:目前)?[^，。]+(?:元/吨|元/升|搁浅|不调整)[^，。]*)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return m.group(1).strip()
        return ""


class AutohomeProvider(AdjustmentProvider):
    """汽车之家数据源

    从汽车之家油价页面提取调价预测信息。
    汽车之家页面通常包含简短的调价预测摘要。
    """

    @property
    def name(self) -> str:
        return "汽车之家"

    def fetch(self) -> AdjustmentInfo | None:
        soup = _fetch_page("https://www.autohome.com.cn/oil/")
        if not soup:
            return None
        return self._parse(soup)

    def _parse(self, soup: BeautifulSoup) -> AdjustmentInfo | None:
        """从汽车之家页面提取调价信息"""
        # 汽车之家的调价信息通常在页面描述区域或 meta 标签中
        # 尝试从页面文本中搜索调价相关内容
        text = soup.get_text(separator=" ", strip=True)

        # 匹配调价模式
        patterns = [
            r"(下次油价\S+调整)",
            r"(油价[上下]调\d+\.?\d*元/升)",
            r"(预计[上下]调\d+元/吨)",
            r"(油价搁浅不?调整)",
        ]

        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                raw = m.group(1)
                # 尝试解析日期
                resolved_summary = resolve_date_summary(raw)
                summary = resolved_summary if resolved_summary else raw

                # 尝试提取幅度
                detail = self._extract_detail(text)
                return AdjustmentInfo(
                    summary=summary,
                    detail=detail or "请关注后续调价通知",
                )

        logger.debug("汽车之家: 未找到调价预测信息")
        return None

    def _extract_detail(self, text: str) -> str:
        """提取调价幅度"""
        patterns = [
            r"((?:目前)?预计[上下]调\d+元/吨(?:\([^)]*\))?)",
            r"(油价(?:上涨|下跌|上调|下调)\d+\.?\d*元/升[^，。]*)",
            r"((?:目前)?预计油价(?:搁浅)?不?调整)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return m.group(1).strip()
        return ""


class CngoldProvider(AdjustmentProvider):
    """金投网数据源

    从金投网 (cngold.org) 获取油价调整预测信息。
    金投网是国内知名的财经数据网站，数据较稳定。
    """

    @property
    def name(self) -> str:
        return "金投网"

    def fetch(self) -> AdjustmentInfo | None:
        # 尝试多个可能的 URL
        urls = [
            "https://www.cngold.org/crude/oiladjust.html",
            "https://oil.cngold.org/oiladjust.html",
            "https://www.cngold.org/crude/",
        ]
        for url in urls:
            soup = _fetch_page(url)
            if soup:
                result = self._parse(soup)
                if result:
                    return result
        logger.warning("金投网: 所有 URL 均未获取到有效数据")
        return None

    def _parse(self, soup: BeautifulSoup) -> AdjustmentInfo | None:
        """解析金投网调价信息"""
        text = soup.get_text(separator=" ", strip=True)

        # 匹配调价模式
        date_pattern = re.search(
            r"下次油价?\s*(\S{1,20})\s*调整", text
        )
        detail_pattern = re.search(
            r"((?:目前)?预计[上下]调\d+元/吨[^，。]*)", text
        )
        if not detail_pattern:
            detail_pattern = re.search(
                r"((?:目前)?预计油价搁浅不?调整)", text
            )

        if date_pattern or detail_pattern:
            summary = ""
            if date_pattern:
                raw = date_pattern.group(0)
                resolved = resolve_date_summary(raw)
                summary = resolved if resolved else raw

            detail = detail_pattern.group(1).strip() if detail_pattern else ""

            if summary or detail:
                return AdjustmentInfo(
                    summary=summary or "调价日期未知",
                    detail=detail or "调价幅度未知",
                )

        logger.debug("金投网: 未解析到调价信息")
        return None


class ProviderManager:
    """数据源管理器

    按优先级依次尝试多个数据源，返回第一个成功的结果。
    """

    def __init__(self, providers: list[AdjustmentProvider] | None = None):
        """初始化管理器

        Args:
            providers: 数据源列表，按优先级排列。
                       默认使用 [汽油价格网, 汽车之家, 金投网]
        """
        if providers is None:
            providers = [
                QiyoujiageProvider(),
                AutohomeProvider(),
                CngoldProvider(),
            ]
        self._providers = providers

    def fetch(self) -> AdjustmentInfo | None:
        """按优先级尝试获取油价调整信息

        Returns:
            第一个成功获取的 AdjustmentInfo，全部失败返回 None
        """
        for provider in self._providers:
            try:
                logger.info(f"正在从 {provider.name} 获取调价信息...")
                result = provider.fetch()
                if result:
                    logger.info(
                        f"{provider.name} 获取成功: {result.summary} | {result.detail}"
                    )
                    return result
                else:
                    logger.warning(f"{provider.name} 未返回有效数据")
            except Exception:
                logger.exception(f"{provider.name} 获取异常")

        logger.warning("所有数据源均未能获取调价信息")
        return None
