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

        assert "3月23日" in desc
        assert "上调" in desc
        assert "来源:汽油价格网" in desc

    def test_adjustment_before_price(self, sample_oil_data):
        """调价预测在油价之前展示"""
        _, desc = format_message(sample_oil_data, "广东")

        adj_pos = desc.index("📢")
        price_pos = desc.index("📍")
        assert adj_pos < price_pos

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

    def test_no_national_comparison(self, sample_oil_data):
        """不包含全国油价对比"""
        _, desc = format_message(sample_oil_data, "广东")

        assert "最低" not in desc
        assert "最高" not in desc

    def test_format_with_prediction(self, sample_prices):
        """消息中包含调价信息及来源标识"""
        from oilprice.scraper import AdjustmentInfo, OilPriceData

        adjustment = AdjustmentInfo(
            summary="下次油价3月23日24时调整",
            detail="目前预计上调油价1900元/吨(1.44元/升-1.72元/升)",
        )
        data = OilPriceData(
            prices=sample_prices, adjustment=adjustment,
        )
        _, desc = format_message(data, "广东")

        assert "📢" in desc
        assert "3月23日" in desc
        assert "上调" in desc
        assert "来源:汽油价格网" in desc

    def test_html_tags_in_description(self, sample_oil_data):
        """描述内容使用企业微信 text_card HTML 标签"""
        _, desc = format_message(sample_oil_data, "广东")

        assert "<div" in desc


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
