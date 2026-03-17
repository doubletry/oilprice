"""数据抓取模块测试"""

from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from oilprice.scraper import (
    AdjustmentInfo,
    OilPrice,
    _try_generate_prediction,
    parse_adjustment_from_qiyoujiage,
    parse_prices_from_autohome,
    scrape_oil_prices,
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
    """测试 scrape_oil_prices 不同预测模式"""

    @patch("oilprice.scraper.fetch_page")
    def test_qiyoujiage_mode_only_scrapes(self, mock_fetch):
        """qiyoujiage 模式仅使用汽油价格网"""
        mock_fetch.side_effect = [_mock_autohome_soup(), _mock_qiyoujiage_soup()]

        result = scrape_oil_prices("qiyoujiage")

        assert result.adjustment is not None
        assert result.prediction is None
        assert len(result.prices) > 0

    @patch("oilprice.scraper._try_generate_prediction", return_value=_FAKE_PREDICTION)
    @patch("oilprice.scraper.fetch_page")
    def test_custom_mode_only_uses_algorithm(self, mock_fetch, mock_predict):
        """custom 模式仅使用自定义算法"""
        mock_fetch.return_value = _mock_autohome_soup()

        result = scrape_oil_prices("custom")

        assert result.adjustment is None
        assert result.prediction is not None
        assert "上涨趋势" in result.prediction.detail
        mock_predict.assert_called_once()

    @patch("oilprice.scraper._try_generate_prediction", return_value=_FAKE_PREDICTION)
    @patch("oilprice.scraper.fetch_page")
    def test_both_mode_fetches_both(self, mock_fetch, mock_predict):
        """both 模式同时获取两个来源"""
        mock_fetch.side_effect = [_mock_autohome_soup(), _mock_qiyoujiage_soup()]

        result = scrape_oil_prices("both")

        assert result.adjustment is not None
        assert result.prediction is not None
        mock_predict.assert_called_once()

    @patch("oilprice.scraper.fetch_page")
    def test_fallback_mode_uses_qiyoujiage_when_available(self, mock_fetch):
        """fallback 模式优先使用汽油价格网"""
        mock_fetch.side_effect = [_mock_autohome_soup(), _mock_qiyoujiage_soup()]

        result = scrape_oil_prices("fallback")

        assert result.adjustment is not None
        assert result.prediction is None

    @patch("oilprice.scraper._try_generate_prediction", return_value=_FAKE_PREDICTION)
    @patch("oilprice.scraper.fetch_page")
    def test_fallback_mode_uses_algorithm_when_scrape_fails(
        self, mock_fetch, mock_predict
    ):
        """fallback 模式: 汽油价格网失败时回退到自定义算法"""
        mock_fetch.side_effect = [_mock_autohome_soup(), None]

        result = scrape_oil_prices("fallback")

        # 汽油价格网失败 → adjustment 保持 None，prediction 来自算法
        assert result.adjustment is None
        assert result.prediction is not None
        mock_predict.assert_called_once()

    @patch("oilprice.scraper._try_generate_prediction", return_value=None)
    @patch("oilprice.scraper.fetch_page")
    def test_fallback_mode_both_fail(self, mock_fetch, mock_predict):
        """fallback 模式: 两个来源都失败"""
        mock_fetch.side_effect = [_mock_autohome_soup(), None]

        result = scrape_oil_prices("fallback")

        assert result.adjustment is None
        assert result.prediction is None

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
