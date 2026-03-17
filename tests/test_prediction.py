"""油价调整预测模块测试"""

from datetime import date
from unittest.mock import patch

import pytest

from oilprice.prediction import (CrudeOilPrice, _add_working_days,
                                 fetch_crude_oil_prices, generate_prediction,
                                 get_next_adjustment_date)


class TestAddWorkingDays:
    """测试工作日计算"""

    def test_simple_weekdays(self):
        """周一起加5个工作日 → 下周一"""
        # 2025-01-20 is Monday
        result = _add_working_days(date(2025, 1, 20), 5)
        assert result == date(2025, 1, 27)  # Next Monday

    def test_skip_weekend(self):
        """跨周末计算"""
        # 2025-01-17 is Friday, add 1 working day → Monday
        result = _add_working_days(date(2025, 1, 17), 1)
        assert result == date(2025, 1, 20)

    def test_ten_working_days(self):
        """10个工作日 = 2周"""
        # 2025-01-17 (Fri) + 10 working days → 2025-01-31 (Fri)
        result = _add_working_days(date(2025, 1, 17), 10)
        assert result == date(2025, 1, 31)

    def test_zero_days(self):
        """加0个工作日返回起始日期"""
        result = _add_working_days(date(2025, 3, 10), 0)
        assert result == date(2025, 3, 10)


class TestGetNextAdjustmentDate:
    """测试调价日期计算"""

    def test_reference_date_is_returned(self):
        """基准日当天返回基准日"""
        result = get_next_adjustment_date(date(2025, 1, 17))
        assert result == date(2025, 1, 17)

    def test_before_reference_date(self):
        """基准日之前返回基准日"""
        result = get_next_adjustment_date(date(2025, 1, 10))
        assert result == date(2025, 1, 17)

    def test_next_cycle(self):
        """基准日后一天，返回下一个调价日"""
        result = get_next_adjustment_date(date(2025, 1, 18))
        # 10 working days after Jan 17 = Jan 31
        assert result == date(2025, 1, 31)

    def test_returns_future_date(self):
        """返回的日期不早于 today"""
        today = date(2025, 6, 15)
        result = get_next_adjustment_date(today)
        assert result >= today

    def test_result_is_weekday(self):
        """调价日应为工作日"""
        result = get_next_adjustment_date(date(2025, 8, 1))
        assert result.weekday() < 5  # Monday-Friday

    def test_default_uses_today(self):
        """不传参数使用系统日期"""
        result = get_next_adjustment_date()
        assert result >= date.today()


class TestFetchCrudeOilPrices:
    """测试国际原油价格获取"""

    @patch("oilprice.prediction.requests.get")
    def test_parse_sina_response(self, mock_get):
        """正常解析新浪财经API响应"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = (
            'var hq_str_hf_OIL="74.90,75.50,74.00,75.60,0,0,0,73.80,2025-03-14";\n'
            'var hq_str_hf_CL="71.20,72.00,70.50,72.10,0,0,0,70.00,2025-03-14";'
        )

        prices = fetch_crude_oil_prices()

        assert len(prices) == 2
        brent = next(p for p in prices if p.name == "布伦特")
        wti = next(p for p in prices if p.name == "WTI")
        assert brent.price == 74.90
        assert wti.price == 71.20
        # Change pct: (74.90 - 73.80) / 73.80 * 100 ≈ 1.49
        assert brent.change_pct is not None
        assert brent.change_pct > 0

    @patch("oilprice.prediction.requests.get")
    def test_network_error_returns_empty(self, mock_get):
        """网络错误返回空列表"""
        import requests

        mock_get.side_effect = requests.ConnectionError("Connection refused")
        prices = fetch_crude_oil_prices()
        assert prices == []

    @patch("oilprice.prediction.requests.get")
    def test_empty_response(self, mock_get):
        """空响应返回空列表"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = ""
        prices = fetch_crude_oil_prices()
        assert prices == []

    @patch("oilprice.prediction.requests.get")
    def test_malformed_response(self, mock_get):
        """格式错误的响应不崩溃"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "invalid data without quotes"
        prices = fetch_crude_oil_prices()
        assert prices == []


class TestGeneratePrediction:
    """测试预测生成"""

    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_prediction_with_rising_prices(self, mock_fetch):
        """油价上涨时生成上调预测"""
        mock_fetch.return_value = [
            CrudeOilPrice(name="布伦特", price=78.50, change_pct=2.5),
            CrudeOilPrice(name="WTI", price=75.20, change_pct=2.0),
        ]

        result = generate_prediction(date(2025, 3, 15))

        assert "调整" in result.summary
        assert "上涨趋势" in result.detail or "上调" in result.detail
        assert "布伦特" in result.detail
        assert "WTI" in result.detail

    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_prediction_with_falling_prices(self, mock_fetch):
        """油价下跌时生成下调预测"""
        mock_fetch.return_value = [
            CrudeOilPrice(name="布伦特", price=68.00, change_pct=-3.0),
        ]

        result = generate_prediction(date(2025, 3, 15))

        assert "下跌趋势" in result.detail or "下调" in result.detail

    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_prediction_with_small_change(self, mock_fetch):
        """波动较小时预测搁浅"""
        mock_fetch.return_value = [
            CrudeOilPrice(name="布伦特", price=74.00, change_pct=0.1),
        ]

        result = generate_prediction(date(2025, 3, 15))

        assert "搁浅" in result.detail or "波动较小" in result.detail

    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_prediction_without_crude_prices(self, mock_fetch):
        """无法获取国际油价时仍提供调价日期"""
        mock_fetch.return_value = []

        result = generate_prediction(date(2025, 3, 15))

        assert "调整" in result.summary
        assert "暂无" in result.detail

    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_prediction_summary_contains_date(self, mock_fetch):
        """预测摘要包含调价日期"""
        mock_fetch.return_value = []

        result = generate_prediction(date(2025, 1, 20))

        # Next adjustment after Jan 20 should be Jan 31
        assert "1月31日" in result.summary
        assert "24时调整" in result.summary

    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_prediction_with_no_change_pct(self, mock_fetch):
        """有价格但无涨跌幅时显示价格"""
        mock_fetch.return_value = [
            CrudeOilPrice(name="布伦特", price=74.50, change_pct=None),
        ]

        result = generate_prediction(date(2025, 3, 15))

        assert "布伦特" in result.detail
        assert "74.50" in result.detail
