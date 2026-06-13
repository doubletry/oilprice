"""油价调整信息多数据源框架测试"""

from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from oilprice.adjustment_provider import (
    AutohomeProvider,
    CngoldProvider,
    ProviderManager,
    QiyoujiageProvider,
)
from oilprice.scraper import AdjustmentInfo
from tests.conftest import (
    AUTOHOME_HTML,
    QIYOUJIAGE_HTML,
    QIYOUJIAGE_HTML_DOWN,
    QIYOUJIAGE_HTML_EMPTY,
    QIYOUJIAGE_HTML_OLD,
    QIYOUJIAGE_HTML_OLD_DOWN,
    QIYOUJIAGE_HTML_SHELVED,
    QIYOUJIAGE_HTML_TONIGHT,
    QIYOUJIAGE_HTML_TOMORROW,
    QIYOUJIAGE_HTML_LAST_NIGHT,
    QIYOUJIAGE_HTML_DAY_AFTER_TOMORROW,
)


class TestQiyoujiageProvider:
    """测试汽油价格网 Provider"""

    def test_standard_date_format(self):
        """标准日期格式解析"""
        provider = QiyoujiageProvider()
        soup = BeautifulSoup(QIYOUJIAGE_HTML, "html.parser")
        with patch.object(provider, "fetch", return_value=None):
            result = provider._parse(soup)
        assert result is not None
        assert "3月23日" in result.summary
        assert "预计上调" in result.detail

    def test_old_format(self):
        """旧格式解析"""
        provider = QiyoujiageProvider()
        soup = BeautifulSoup(QIYOUJIAGE_HTML_OLD, "html.parser")
        result = provider._parse(soup)
        assert result is not None
        assert "3月20日" in result.summary
        assert "上涨" in result.detail

    def test_down_format(self):
        """下调格式解析"""
        provider = QiyoujiageProvider()
        soup = BeautifulSoup(QIYOUJIAGE_HTML_DOWN, "html.parser")
        result = provider._parse(soup)
        assert result is not None
        assert "4月1日" in result.summary
        assert "下调" in result.detail

    def test_shelved_format(self):
        """搁浅格式解析"""
        provider = QiyoujiageProvider()
        soup = BeautifulSoup(QIYOUJIAGE_HTML_SHELVED, "html.parser")
        result = provider._parse(soup)
        assert result is not None
        assert "4月15日" in result.summary

    def test_old_down_format(self):
        """旧格式下跌"""
        provider = QiyoujiageProvider()
        soup = BeautifulSoup(QIYOUJIAGE_HTML_OLD_DOWN, "html.parser")
        result = provider._parse(soup)
        assert result is not None
        assert "下跌" in result.detail

    def test_empty_returns_none(self):
        """无数据返回 None"""
        provider = QiyoujiageProvider()
        soup = BeautifulSoup(QIYOUJIAGE_HTML_EMPTY, "html.parser")
        result = provider._parse(soup)
        assert result is None

    def test_tonight_colloquial(self):
        """口语化日期: 今晚24时"""
        provider = QiyoujiageProvider()
        soup = BeautifulSoup(QIYOUJIAGE_HTML_TONIGHT, "html.parser")
        result = provider._parse(soup)
        assert result is not None
        # 今晚24时 应该解析为明天
        assert "调整" in result.summary

    def test_tomorrow_colloquial(self):
        """口语化日期: 明天"""
        provider = QiyoujiageProvider()
        soup = BeautifulSoup(QIYOUJIAGE_HTML_TOMORROW, "html.parser")
        result = provider._parse(soup)
        assert result is not None
        assert "调整" in result.summary

    def test_last_night_colloquial(self):
        """口语化日期: 昨晚"""
        provider = QiyoujiageProvider()
        soup = BeautifulSoup(QIYOUJIAGE_HTML_LAST_NIGHT, "html.parser")
        result = provider._parse(soup)
        assert result is not None
        assert "调整" in result.summary

    def test_day_after_tomorrow_colloquial(self):
        """口语化日期: 后天"""
        provider = QiyoujiageProvider()
        soup = BeautifulSoup(QIYOUJIAGE_HTML_DAY_AFTER_TOMORROW, "html.parser")
        result = provider._parse(soup)
        assert result is not None
        assert "调整" in result.summary


class TestProviderManager:
    """测试数据源管理器"""

    def test_first_provider_succeeds(self):
        """第一个 Provider 成功时直接返回"""
        mock_provider1 = MagicMock(spec=QiyoujiageProvider)
        mock_provider1.name = "汽油价格网"
        mock_provider1.fetch.return_value = AdjustmentInfo(
            summary="下次油价6月18日24时调整",
            detail="预计下调270元/吨",
        )

        mock_provider2 = MagicMock(spec=AutohomeProvider)
        mock_provider2.name = "汽车之家"

        manager = ProviderManager([mock_provider1, mock_provider2])
        result = manager.fetch()

        assert result is not None
        assert "6月18日" in result.summary
        mock_provider1.fetch.assert_called_once()
        mock_provider2.fetch.assert_not_called()

    def test_first_fails_second_succeeds(self):
        """第一个失败时尝试第二个"""
        mock_provider1 = MagicMock(spec=QiyoujiageProvider)
        mock_provider1.name = "汽油价格网"
        mock_provider1.fetch.return_value = None

        mock_provider2 = MagicMock(spec=AutohomeProvider)
        mock_provider2.name = "汽车之家"
        mock_provider2.fetch.return_value = AdjustmentInfo(
            summary="下次油价6月18日24时调整",
            detail="预计下调270元/吨",
        )

        manager = ProviderManager([mock_provider1, mock_provider2])
        result = manager.fetch()

        assert result is not None
        assert "6月18日" in result.summary
        mock_provider1.fetch.assert_called_once()
        mock_provider2.fetch.assert_called_once()

    def test_all_fail_returns_none(self):
        """所有 Provider 都失败返回 None"""
        mock_provider1 = MagicMock(spec=QiyoujiageProvider)
        mock_provider1.name = "汽油价格网"
        mock_provider1.fetch.return_value = None

        mock_provider2 = MagicMock(spec=AutohomeProvider)
        mock_provider2.name = "汽车之家"
        mock_provider2.fetch.return_value = None

        manager = ProviderManager([mock_provider1, mock_provider2])
        result = manager.fetch()

        assert result is None

    def test_exception_in_provider_continues(self):
        """Provider 抛出异常时继续尝试下一个"""
        mock_provider1 = MagicMock(spec=QiyoujiageProvider)
        mock_provider1.name = "汽油价格网"
        mock_provider1.fetch.side_effect = Exception("网络错误")

        mock_provider2 = MagicMock(spec=AutohomeProvider)
        mock_provider2.name = "汽车之家"
        mock_provider2.fetch.return_value = AdjustmentInfo(
            summary="下次油价6月18日24时调整",
            detail="预计下调270元/吨",
        )

        manager = ProviderManager([mock_provider1, mock_provider2])
        result = manager.fetch()

        assert result is not None
        mock_provider2.fetch.assert_called_once()

    def test_default_providers(self):
        """默认 Provider 列表包含 3 个数据源"""
        manager = ProviderManager()
        assert len(manager._providers) == 3
