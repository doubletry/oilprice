"""油价调整预测模块测试"""

from datetime import date
from unittest.mock import patch

import pytest

from oilprice.prediction import (
    ADJUSTMENT_THRESHOLD_PER_TON,
    BARRELS_PER_TON,
    GASOLINE_YIELD_RATE,
    LITERS_PER_TON_GASOLINE,
    VAT_RATE,
    CrudeOilPrice,
    _add_working_days,
    _calculate_retail_price_impact,
    fetch_crude_oil_prices,
    fetch_exchange_rate,
    fetch_reference_crude_prices,
    generate_prediction,
    get_next_adjustment_date,
    get_previous_adjustment_date,
)


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
        today = date.today()
        result = get_next_adjustment_date(today)
        assert result >= today


class TestGetPreviousAdjustmentDate:
    """测试上一次调价日期计算"""

    def test_before_reference_date(self):
        """基准日之前返回 None"""
        result = get_previous_adjustment_date(date(2025, 1, 10))
        assert result is None

    def test_on_reference_date(self):
        """基准日当天返回 None（没有更早的调价日）"""
        result = get_previous_adjustment_date(date(2025, 1, 17))
        assert result is None

    def test_day_after_reference(self):
        """基准日后一天，上次调价日 = 基准日"""
        result = get_previous_adjustment_date(date(2025, 1, 18))
        assert result == date(2025, 1, 17)

    def test_mid_cycle(self):
        """周期中间，上次调价日 = 周期起始日"""
        # Between Jan 17 and Jan 31
        result = get_previous_adjustment_date(date(2025, 1, 25))
        assert result == date(2025, 1, 17)

    def test_on_next_adjustment_date(self):
        """下一个调价日当天，上次调价日 = 上一周期"""
        # Jan 31 is adjustment date, previous is Jan 17
        result = get_previous_adjustment_date(date(2025, 1, 31))
        assert result == date(2025, 1, 17)

    def test_second_cycle(self):
        """第二个周期内的上次调价日"""
        # After Jan 31, previous adjustment = Jan 31
        result = get_previous_adjustment_date(date(2025, 2, 5))
        assert result == date(2025, 1, 31)

    def test_result_is_before_today(self):
        """上次调价日一定在 today 之前"""
        today = date(2025, 6, 15)
        result = get_previous_adjustment_date(today)
        assert result is not None
        assert result < today


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
        # prev_close should be stored
        assert brent.prev_close == 73.80
        assert wti.prev_close == 70.00

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


class TestFetchExchangeRate:
    """测试汇率获取"""

    @patch("oilprice.prediction.requests.get")
    def test_parse_normal_rate(self, mock_get):
        """正常解析汇率（直接格式）"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = (
            'var hq_str_fx_susdcny="7.2644,7.2580,7.2700,7.2500,'
            '0,0,0,7.2500,2025-03-14,10:30:00";'
        )
        rate = fetch_exchange_rate()
        assert 7.0 < rate < 8.0
        assert rate == pytest.approx(7.2644)

    @patch("oilprice.prediction.requests.get")
    def test_parse_hundredths_format(self, mock_get):
        """解析百倍格式（726.44 → 7.2644）"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = (
            'var hq_str_fx_susdcny="726.44,725.80,727.00,725.00,'
            '0,0,0,725.00,2025-03-14,10:30:00";'
        )
        rate = fetch_exchange_rate()
        assert 7.0 < rate < 8.0
        assert rate == pytest.approx(7.2644)

    @patch("oilprice.prediction.requests.get")
    def test_network_error_returns_default(self, mock_get):
        """网络错误返回默认汇率"""
        import requests

        mock_get.side_effect = requests.ConnectionError("Connection refused")
        rate = fetch_exchange_rate()
        assert rate == 7.20

    @patch("oilprice.prediction.requests.get")
    def test_empty_response_returns_default(self, mock_get):
        """空响应返回默认汇率"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = ""
        rate = fetch_exchange_rate()
        assert rate == 7.20

    @patch("oilprice.prediction.requests.get")
    def test_malformed_response_returns_default(self, mock_get):
        """格式错误的响应返回默认汇率"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "invalid data"
        rate = fetch_exchange_rate()
        assert rate == 7.20


class TestFetchReferenceCrudePrices:
    """测试历史基准价获取"""

    @patch("oilprice.prediction.requests.get")
    def test_parse_kline_dict_format(self, mock_get):
        """正常解析JSONP字典格式的K线数据"""
        # 模拟 JSONP 响应（字典格式）
        jsonp_data = (
            'var _result=(['
            '{"d":"2025-01-15","o":"73.00","h":"73.80","l":"72.50","c":"73.50","v":"1000"},'
            '{"d":"2025-01-16","o":"73.50","h":"74.20","l":"73.00","c":"74.00","v":"1100"},'
            '{"d":"2025-01-17","o":"74.00","h":"74.80","l":"73.50","c":"74.50","v":"1200"}'
            ']);'
        )
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = jsonp_data

        result = fetch_reference_crude_prices(date(2025, 1, 17))

        assert result is not None
        # Should find prices for both varieties (same mock used for both API calls)
        assert len(result) > 0
        for name, price in result.items():
            assert price == 74.50  # Close price on Jan 17

    @patch("oilprice.prediction.requests.get")
    def test_finds_nearest_trading_day(self, mock_get):
        """参考日期非交易日时，使用最近交易日的收盘价"""
        # Jan 18 is Saturday, should match Jan 17 (Friday)
        jsonp_data = (
            'var _result=(['
            '{"d":"2025-01-16","o":"73.50","h":"74.20","l":"73.00","c":"73.80","v":"1100"},'
            '{"d":"2025-01-17","o":"74.00","h":"74.80","l":"73.50","c":"74.50","v":"1200"}'
            ']);'
        )
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = jsonp_data

        result = fetch_reference_crude_prices(date(2025, 1, 18))

        assert result is not None
        for name, price in result.items():
            assert price == 74.50  # Jan 17 is closest to Jan 18

    @patch("oilprice.prediction.requests.get")
    def test_rejects_distant_dates(self, mock_get):
        """距离参考日期超过5天时不使用"""
        jsonp_data = (
            'var _result=(['
            '{"d":"2025-01-10","o":"73.00","h":"73.80","l":"72.50","c":"73.50","v":"1000"}'
            ']);'
        )
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = jsonp_data

        # ref_date is Jan 20, but data only has Jan 10 (10 days away > 5 day threshold)
        result = fetch_reference_crude_prices(date(2025, 1, 20))

        assert result is None

    @patch("oilprice.prediction.requests.get")
    def test_network_error_returns_none(self, mock_get):
        """网络错误返回 None"""
        import requests

        mock_get.side_effect = requests.ConnectionError("Connection refused")
        result = fetch_reference_crude_prices(date(2025, 1, 17))
        assert result is None

    @patch("oilprice.prediction.requests.get")
    def test_empty_response_returns_none(self, mock_get):
        """空响应返回 None"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "var _result=([]);"
        result = fetch_reference_crude_prices(date(2025, 1, 17))
        assert result is None

    @patch("oilprice.prediction.requests.get")
    def test_malformed_jsonp_returns_none(self, mock_get):
        """JSONP格式异常返回 None"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "invalid data without brackets"
        result = fetch_reference_crude_prices(date(2025, 1, 17))
        assert result is None


class TestCalculateRetailPriceImpact:
    """测试零售价影响计算（定价链）"""

    def test_positive_change(self):
        """原油价格上涨 → 零售价上涨"""
        change_per_ton, change_per_liter = _calculate_retail_price_impact(
            crude_change_usd=1.0, exchange_rate=7.20
        )
        assert change_per_ton > 0
        assert change_per_liter > 0

    def test_negative_change(self):
        """原油价格下跌 → 零售价下跌"""
        change_per_ton, change_per_liter = _calculate_retail_price_impact(
            crude_change_usd=-1.0, exchange_rate=7.20
        )
        assert change_per_ton < 0
        assert change_per_liter < 0

    def test_zero_change(self):
        """原油价格不变 → 零售价不变"""
        change_per_ton, change_per_liter = _calculate_retail_price_impact(
            crude_change_usd=0.0, exchange_rate=7.20
        )
        assert change_per_ton == 0
        assert change_per_liter == 0

    def test_exchange_rate_affects_result(self):
        """汇率越高，同样的美元变动对人民币影响越大"""
        _, liter_low = _calculate_retail_price_impact(1.0, exchange_rate=6.50)
        _, liter_high = _calculate_retail_price_impact(1.0, exchange_rate=7.50)
        assert liter_high > liter_low

    def test_calculation_chain_values(self):
        """验证定价链各环节计算正确性"""
        crude_change_usd = 1.0
        exchange_rate = 7.20

        change_per_ton, change_per_liter = _calculate_retail_price_impact(
            crude_change_usd, exchange_rate
        )

        # 手动验证: 1美元/桶 × 7.33桶/吨 × 7.20元/美元 = 52.776 元/吨原油
        expected_crude_cny = crude_change_usd * BARRELS_PER_TON * exchange_rate
        assert expected_crude_cny == pytest.approx(52.776)

        # 除以出油率: 52.776 / 0.45 ≈ 117.28 元/吨汽油
        expected_gasoline = expected_crude_cny / GASOLINE_YIELD_RATE
        assert change_per_ton == pytest.approx(expected_gasoline, rel=0.01)

        # 零售价应大于0且在合理范围内
        assert 0.05 < change_per_liter < 0.20

    def test_one_dollar_change_reasonable(self):
        """1美元/桶变动对应的零售价变动在合理范围内（约0.08-0.12元/升）"""
        _, change_per_liter = _calculate_retail_price_impact(1.0, 7.20)
        assert 0.05 < abs(change_per_liter) < 0.20


class TestGeneratePrediction:
    """测试预测生成"""

    @patch("oilprice.prediction.fetch_reference_crude_prices")
    @patch("oilprice.prediction.fetch_exchange_rate")
    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_prediction_with_window_change_rising(self, mock_fetch, mock_fx, mock_ref):
        """有上轮基准价时，使用窗口变动计算上涨预测"""
        mock_fx.return_value = 7.20
        mock_fetch.return_value = [
            CrudeOilPrice(name="布伦特", price=78.50, change_pct=0.5, prev_close=78.11),
            CrudeOilPrice(name="WTI", price=75.20, change_pct=0.3, prev_close=74.97),
        ]
        # 上轮调价基准价低于当前价 → 上涨
        mock_ref.return_value = {"布伦特": 73.00, "WTI": 70.00}

        result = generate_prediction(date(2025, 3, 15))

        assert "调整" in result.summary
        assert "上涨趋势" in result.detail or "上调" in result.detail
        assert "较上轮调价" in result.detail
        assert "汇率" in result.detail
        assert "元/吨" in result.detail
        assert "元/升" in result.detail

    @patch("oilprice.prediction.fetch_reference_crude_prices")
    @patch("oilprice.prediction.fetch_exchange_rate")
    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_prediction_with_window_change_falling(self, mock_fetch, mock_fx, mock_ref):
        """有上轮基准价时，使用窗口变动计算下跌预测"""
        mock_fx.return_value = 7.20
        mock_fetch.return_value = [
            CrudeOilPrice(name="布伦特", price=68.00, change_pct=0.5, prev_close=67.66),
        ]
        # 上轮调价基准价高于当前价 → 下跌
        mock_ref.return_value = {"布伦特": 73.00}

        result = generate_prediction(date(2025, 3, 15))

        assert "下跌趋势" in result.detail or "下调" in result.detail
        assert "较上轮调价" in result.detail

    @patch("oilprice.prediction.fetch_reference_crude_prices")
    @patch("oilprice.prediction.fetch_exchange_rate")
    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_prediction_with_window_change_small(self, mock_fetch, mock_fx, mock_ref):
        """窗口变动较小时预测搁浅"""
        mock_fx.return_value = 7.20
        mock_fetch.return_value = [
            CrudeOilPrice(name="布伦特", price=74.20, change_pct=0.1, prev_close=74.13),
        ]
        # 上轮基准价与当前价接近 → 搁浅
        mock_ref.return_value = {"布伦特": 74.00}

        result = generate_prediction(date(2025, 3, 15))

        assert "搁浅" in result.detail or "不调整" in result.detail
        assert "较上轮调价" in result.detail
        assert "不足" in result.detail or "50" in result.detail

    @patch("oilprice.prediction.fetch_reference_crude_prices")
    @patch("oilprice.prediction.fetch_exchange_rate")
    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_fallback_to_daily_change(self, mock_fetch, mock_fx, mock_ref):
        """无法获取历史数据时回退到当日变动"""
        mock_fx.return_value = 7.20
        mock_ref.return_value = None  # 历史数据不可用
        mock_fetch.return_value = [
            CrudeOilPrice(name="布伦特", price=78.50, change_pct=2.5, prev_close=76.58),
        ]

        result = generate_prediction(date(2025, 3, 15))

        assert "当日" in result.detail
        assert "上涨趋势" in result.detail or "上调" in result.detail

    @patch("oilprice.prediction.fetch_reference_crude_prices")
    @patch("oilprice.prediction.fetch_exchange_rate")
    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_fallback_daily_small_change(self, mock_fetch, mock_fx, mock_ref):
        """当日变动较小时（回退模式）也能预测搁浅"""
        mock_fx.return_value = 7.20
        mock_ref.return_value = None
        mock_fetch.return_value = [
            CrudeOilPrice(name="布伦特", price=74.00, change_pct=0.1, prev_close=73.93),
        ]

        result = generate_prediction(date(2025, 3, 15))

        assert "搁浅" in result.detail or "不调整" in result.detail
        assert "当日" in result.detail

    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_prediction_without_crude_prices(self, mock_fetch):
        """无法获取国际油价时仍提供调价日期"""
        mock_fetch.return_value = []

        result = generate_prediction(date(2025, 3, 15))

        assert "调整" in result.summary
        assert "暂无" in result.detail

    @patch("oilprice.prediction.fetch_reference_crude_prices")
    @patch("oilprice.prediction.fetch_exchange_rate")
    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_prediction_summary_contains_date(self, mock_fetch, mock_fx, mock_ref):
        """预测摘要包含调价日期"""
        mock_fx.return_value = 7.20
        mock_ref.return_value = None
        mock_fetch.return_value = []

        result = generate_prediction(date(2025, 1, 20))

        # Next adjustment after Jan 20 should be Jan 31
        assert "1月31日" in result.summary
        assert "24时调整" in result.summary

    @patch("oilprice.prediction.fetch_reference_crude_prices")
    @patch("oilprice.prediction.fetch_exchange_rate")
    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_prediction_with_no_change_pct(self, mock_fetch, mock_fx, mock_ref):
        """有价格但无涨跌幅且无基准价时显示价格和汇率"""
        mock_fx.return_value = 7.20
        mock_ref.return_value = None
        mock_fetch.return_value = [
            CrudeOilPrice(name="布伦特", price=74.50, change_pct=None),
        ]

        result = generate_prediction(date(2025, 3, 15))

        assert "布伦特" in result.detail
        assert "74.50" in result.detail
        assert "汇率" in result.detail

    @patch("oilprice.prediction.fetch_reference_crude_prices")
    @patch("oilprice.prediction.fetch_exchange_rate")
    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_window_change_overrides_daily_change(self, mock_fetch, mock_fx, mock_ref):
        """窗口变动优先于当日变动:
        当日微涨0.5%但相对上轮调价实际上涨5美元"""
        mock_fx.return_value = 7.20
        mock_fetch.return_value = [
            CrudeOilPrice(
                name="布伦特", price=78.00, change_pct=0.5, prev_close=77.61
            ),
        ]
        # 上轮调价时仅73美元 → 实际窗口涨了5美元
        mock_ref.return_value = {"布伦特": 73.00}

        result = generate_prediction(date(2025, 3, 15))

        # 虽然当日仅涨0.5%，但相对上轮调价涨了约6.85% → 应是上涨趋势
        assert "上涨趋势" in result.detail or "上调" in result.detail
        assert "较上轮调价" in result.detail

    @patch("oilprice.prediction.fetch_reference_crude_prices")
    @patch("oilprice.prediction.fetch_exchange_rate")
    @patch("oilprice.prediction.fetch_crude_oil_prices")
    def test_partial_ref_prices_uses_available(self, mock_fetch, mock_fx, mock_ref):
        """仅部分品种有基准价时，使用有基准价的品种计算窗口变动"""
        mock_fx.return_value = 7.20
        mock_fetch.return_value = [
            CrudeOilPrice(name="布伦特", price=78.00, change_pct=0.5, prev_close=77.61),
            CrudeOilPrice(name="WTI", price=75.00, change_pct=0.3, prev_close=74.78),
        ]
        # 仅布伦特有基准价
        mock_ref.return_value = {"布伦特": 73.00}

        result = generate_prediction(date(2025, 3, 15))

        # 使用布伦特的窗口变动
        assert "较上轮调价" in result.detail
        assert "布伦特" in result.detail
