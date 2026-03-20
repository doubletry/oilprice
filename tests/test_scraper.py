"""数据抓取模块测试"""

from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from oilprice.scraper import (
    AdjustmentInfo,
    OilPrice,
    parse_adjustment_from_qiyoujiage,
    parse_prices_from_autohome,
    scrape_oil_prices,
)
from tests.conftest import (
    AUTOHOME_HTML,
    QIYOUJIAGE_HTML,
    QIYOUJIAGE_HTML_DOWN,
    QIYOUJIAGE_HTML_EMPTY,
    QIYOUJIAGE_HTML_OLD,
    QIYOUJIAGE_HTML_OLD_DOWN,
    QIYOUJIAGE_HTML_SHELVED,
)


class TestParsePricesFromAutohome:
    """测试汽车之家油价解析"""

    def test_parse_valid_table(self):
        """正常解析油价表格"""
        soup = BeautifulSoup(AUTOHOME_HTML, "html.parser")
        prices = parse_prices_from_autohome(soup)

        assert len(prices) == 3
        assert prices[0].province == "北京"
        assert prices[0].price_92 == "7.64"
        assert prices[0].price_95 == "8.13"
        assert prices[0].price_98 == "9.63"
        assert prices[0].price_0 == "7.34"

    def test_parse_guangdong(self):
        """验证广东数据"""
        soup = BeautifulSoup(AUTOHOME_HTML, "html.parser")
        prices = parse_prices_from_autohome(soup)

        gd = next(p for p in prices if p.province == "广东")
        assert gd.price_92 == "7.66"
        assert gd.price_95 == "8.29"

    def test_empty_table(self):
        """空表格返回空列表"""
        html = "<html><body><table><tr><th>地区</th></tr></table></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        prices = parse_prices_from_autohome(soup)
        assert prices == []

    def test_no_table(self):
        """页面无表格返回空列表"""
        soup = BeautifulSoup("<html><body><p>无数据</p></body></html>", "html.parser")
        prices = parse_prices_from_autohome(soup)
        assert prices == []


class TestParseAdjustmentFromQiyoujiage:
    """测试汽油价格网调价信息解析"""

    def test_parse_new_format_up(self):
        """解析新格式: 预计上调油价XXX元/吨"""
        soup = BeautifulSoup(QIYOUJIAGE_HTML, "html.parser")
        info = parse_adjustment_from_qiyoujiage(soup)

        assert info is not None
        assert "3月23日" in info.summary
        assert "调整" in info.summary
        assert "预计上调油价" in info.detail
        assert "1900元/吨" in info.detail
        assert "1.44元/升-1.72元/升" in info.detail

    def test_parse_new_format_down(self):
        """解析新格式: 预计下调油价XXX元/吨"""
        soup = BeautifulSoup(QIYOUJIAGE_HTML_DOWN, "html.parser")
        info = parse_adjustment_from_qiyoujiage(soup)

        assert info is not None
        assert "4月1日" in info.summary
        assert "预计下调油价" in info.detail
        assert "200元/吨" in info.detail

    def test_parse_old_format_up(self):
        """解析旧格式: 油价上涨X.XX元/升"""
        soup = BeautifulSoup(QIYOUJIAGE_HTML_OLD, "html.parser")
        info = parse_adjustment_from_qiyoujiage(soup)

        assert info is not None
        assert "3月20日" in info.summary
        assert "上涨" in info.detail
        assert "0.55元/升" in info.detail

    def test_parse_old_format_down(self):
        """解析旧格式: 油价下跌X.XX元/升"""
        soup = BeautifulSoup(QIYOUJIAGE_HTML_OLD_DOWN, "html.parser")
        info = parse_adjustment_from_qiyoujiage(soup)

        assert info is not None
        assert "4月1日" in info.summary
        assert "下跌" in info.detail
        assert "0.15元/升" in info.detail

    def test_parse_shelved(self):
        """解析搁浅/不调整"""
        soup = BeautifulSoup(QIYOUJIAGE_HTML_SHELVED, "html.parser")
        info = parse_adjustment_from_qiyoujiage(soup)

        assert info is not None
        assert "4月15日" in info.summary
        assert "不调整" in info.detail or "搁浅" in info.detail

    def test_no_adjustment_info(self):
        """无调价信息返回 None"""
        soup = BeautifulSoup(QIYOUJIAGE_HTML_EMPTY, "html.parser")
        info = parse_adjustment_from_qiyoujiage(soup)
        assert info is None

    def test_page_without_containers(self):
        """页面缺少目标容器返回 None"""
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        info = parse_adjustment_from_qiyoujiage(soup)
        assert info is None


def _mock_autohome_soup():
    """返回模拟的汽车之家 BeautifulSoup 页面"""
    return BeautifulSoup(AUTOHOME_HTML, "html.parser")


def _mock_qiyoujiage_soup():
    """返回模拟的汽油价格网 BeautifulSoup 页面"""
    return BeautifulSoup(QIYOUJIAGE_HTML, "html.parser")


_FAKE_PREDICTION = AdjustmentInfo(
    summary="下次油价3月31日24时调整",
    detail="国际油价呈上涨趋势，预计油价上调约0.10元/升",
)


class TestScrapeOilPrices:
    """测试 scrape_oil_prices"""

    @patch("oilprice.scraper.fetch_page")
    def test_normal_flow(self, mock_fetch):
        """正常流程: 获取油价和调价信息"""
        mock_fetch.side_effect = [_mock_autohome_soup(), _mock_qiyoujiage_soup()]

        result = scrape_oil_prices()

        assert result.adjustment is not None
        assert len(result.prices) > 0

    @patch("oilprice.scraper.fetch_page")
    def test_qiyoujiage_unavailable(self, mock_fetch):
        """汽油价格网不可用时仅返回油价"""
        mock_fetch.side_effect = [_mock_autohome_soup(), None]

        result = scrape_oil_prices()

        assert result.adjustment is None
        assert len(result.prices) > 0

    @patch("oilprice.scraper.fetch_page")
    def test_autohome_failure_raises(self, mock_fetch):
        """汽车之家访问失败时抛出异常"""
        mock_fetch.return_value = None

        with pytest.raises(RuntimeError, match="无法访问汽车之家"):
            scrape_oil_prices()

    @patch("oilprice.scraper.fetch_page")
    def test_autohome_empty_prices_raises(self, mock_fetch):
        """汽车之家解析不到油价时抛出异常"""
        empty_soup = BeautifulSoup(
            "<html><body><table><tr><th>地区</th></tr></table></body></html>",
            "html.parser",
        )
        mock_fetch.return_value = empty_soup

        with pytest.raises(RuntimeError, match="无法从汽车之家解析"):
            scrape_oil_prices()
