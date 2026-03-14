"""数据抓取模块测试"""

import pytest
from bs4 import BeautifulSoup

from oilprice.scraper import (
    parse_adjustment_from_qiyoujiage,
    parse_prices_from_autohome,
)
from tests.conftest import AUTOHOME_HTML, QIYOUJIAGE_HTML, QIYOUJIAGE_HTML_EMPTY


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

    def test_parse_adjustment_info(self):
        """正常解析调价信息"""
        soup = BeautifulSoup(QIYOUJIAGE_HTML, "html.parser")
        info = parse_adjustment_from_qiyoujiage(soup)

        assert info is not None
        assert "3月20日" in info.summary
        assert "调整" in info.summary
        assert "上涨" in info.detail

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
