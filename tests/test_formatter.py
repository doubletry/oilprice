"""消息格式化模块测试"""

from oilprice.formatter import format_message, get_province_cn


class TestFormatMessage:
    """测试消息格式化"""

    def test_format_with_province(self, sample_oil_data):
        """格式化含指定省份的消息"""
        title, desc = format_message(sample_oil_data, "广东")

        assert "广东" in title
        assert "今日油价" in title
        assert "7.66" in desc  # 92# 价格
        assert "8.29" in desc  # 95# 价格
        assert "10.29" in desc  # 98# 价格
        assert "7.30" in desc  # 0# 柴油

    def test_format_with_adjustment(self, sample_oil_data):
        """消息中包含调价信息及来源标识"""
        _, desc = format_message(sample_oil_data, "广东")

        assert "3月20日" in desc
        assert "上涨" in desc
        assert "来源:汽油价格网" in desc

    def test_format_without_adjustment(self, sample_oil_data_no_adjustment):
        """无调价信息时不报错"""
        title, desc = format_message(sample_oil_data_no_adjustment, "广东")

        assert "广东" in title
        assert "7.66" in desc
        assert "调整" not in desc

    def test_format_province_not_found(self, sample_oil_data):
        """省份不存在时显示警告"""
        title, desc = format_message(sample_oil_data, "不存在省")

        assert "全国" in title
        assert "未找到" in desc

    def test_format_price_comparison(self, sample_oil_data):
        """消息中包含全国最低/最高油价"""
        _, desc = format_message(sample_oil_data, "广东")

        assert "最低" in desc
        assert "最高" in desc
        assert "新疆" in desc  # 92# 最低
        assert "海南" in desc  # 92# 最高

    def test_format_with_prediction(self, sample_prices):
        """消息中包含自定义算法预测及来源标识"""
        from oilprice.scraper import AdjustmentInfo, OilPriceData

        prediction = AdjustmentInfo(
            summary="下次油价4月1日24时调整",
            detail="国际油价呈上涨趋势，预计油价上调约0.10元/升",
        )
        data = OilPriceData(
            prices=sample_prices, adjustment=None, prediction=prediction
        )
        _, desc = format_message(data, "广东")

        assert "🔮" in desc
        assert "4月1日" in desc
        assert "上涨" in desc
        assert "来源:算法预测" in desc

    def test_format_with_both(self, sample_prices):
        """同时包含调价信息和自定义预测，各有来源标识"""
        from oilprice.scraper import AdjustmentInfo, OilPriceData

        adjustment = AdjustmentInfo(
            summary="下次油价3月20日24时调整",
            detail="油价上涨0.55元/升",
        )
        prediction = AdjustmentInfo(
            summary="下次油价3月20日24时调整",
            detail="国际油价呈上涨趋势，预计油价上调约0.10元/升",
        )
        data = OilPriceData(
            prices=sample_prices, adjustment=adjustment, prediction=prediction
        )
        _, desc = format_message(data, "广东")

        assert "📢" in desc
        assert "🔮" in desc
        assert "0.55" in desc
        assert "国际油价" in desc
        assert "来源:汽油价格网" in desc
        assert "来源:算法预测" in desc


class TestGetProvinceCn:
    """测试省份名称转换"""

    def test_english_to_chinese(self):
        assert get_province_cn("guangdong") == "广东"
        assert get_province_cn("beijing") == "北京"
        assert get_province_cn("shanghai") == "上海"

    def test_case_insensitive(self):
        assert get_province_cn("GuangDong") == "广东"
        assert get_province_cn("BEIJING") == "北京"

    def test_chinese_input(self):
        """已是中文直接返回"""
        assert get_province_cn("广东") == "广东"
        assert get_province_cn("北京") == "北京"

    def test_unknown_province(self):
        """未知省份返回原值"""
        assert get_province_cn("unknown") == "unknown"
