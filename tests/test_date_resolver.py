"""口语化日期解析模块测试"""

from datetime import date

import pytest

from oilprice.date_resolver import (
    resolve_date,
    resolve_date_summary,
    _parse_standard_date,
    _parse_colloquial_date,
    _has_midnight_modifier,
)


class TestParseStandardDate:
    """测试标准日期格式解析"""

    def test_month_day_cn(self):
        """X月X日格式"""
        result = _parse_standard_date("下次油价6月18日24时调整", date(2025, 6, 13))
        assert result == date(2025, 6, 18)

    def test_month_day_cn_with_hao(self):
        """X月X号格式"""
        result = _parse_standard_date("下次油价6月18号24时调整", date(2025, 6, 13))
        assert result == date(2025, 6, 18)

    def test_year_month_day_cn(self):
        """YYYY年X月X日格式"""
        result = _parse_standard_date("下次油价2025年6月18日调整", date(2025, 6, 13))
        assert result == date(2025, 6, 18)

    def test_iso_format(self):
        """YYYY-MM-DD格式"""
        result = _parse_standard_date("2025-06-18调整", date(2025, 6, 13))
        assert result == date(2025, 6, 18)

    def test_slash_format(self):
        """YYYY/MM/DD格式"""
        result = _parse_standard_date("2025/06/18调整", date(2025, 6, 13))
        assert result == date(2025, 6, 18)

    def test_no_date_returns_none(self):
        """无日期返回 None"""
        result = _parse_standard_date("暂无调价信息", date(2025, 6, 13))
        assert result is None

    def test_uses_base_date_year(self):
        """X月X日格式使用基准日期的年份"""
        result = _parse_standard_date("下次油价3月20日调整", date(2025, 1, 17))
        assert result == date(2025, 3, 20)


class TestHasMidnightModifier:
    """测试午夜修饰词检测"""

    def test_24_shi(self):
        assert _has_midnight_modifier("今晚24时调整") is True

    def test_24_dian(self):
        assert _has_midnight_modifier("今晚24点调整") is True

    def test_24_colon_00(self):
        assert _has_midnight_modifier("今晚24:00调整") is True

    def test_ling_dian(self):
        assert _has_midnight_modifier("明早零点调整") is True

    def test_no_modifier(self):
        assert _has_midnight_modifier("明天调整") is False

    def test_9_shi(self):
        assert _has_midnight_modifier("明天9时调整") is False


class TestParseColloquialDate:
    """测试口语化日期解析"""

    def test_jin_wan(self):
        """今晚 → 当天"""
        result = _parse_colloquial_date("油价今晚调整", date(2025, 6, 13))
        assert result == date(2025, 6, 13)

    def test_jin_wan_24_shi(self):
        """今晚24时 → 当天（油价惯例: 日期与"24时"同属一天）"""
        result = _parse_colloquial_date("油价今晚24时调整", date(2025, 6, 13))
        assert result == date(2025, 6, 13)

    def test_ming_wan(self):
        """明晚 → 明天"""
        result = _parse_colloquial_date("油价明晚调整", date(2025, 6, 13))
        assert result == date(2025, 6, 14)

    def test_ming_wan_24_shi(self):
        """明晚24时 → 明天（油价惯例）"""
        result = _parse_colloquial_date("油价明晚24时调整", date(2025, 6, 13))
        assert result == date(2025, 6, 14)

    def test_zuo_wan(self):
        """昨晚 → 昨天"""
        result = _parse_colloquial_date("油价昨晚调整", date(2025, 6, 13))
        assert result == date(2025, 6, 12)

    def test_ming_tian(self):
        """明天 → 明天"""
        result = _parse_colloquial_date("油价明天调整", date(2025, 6, 13))
        assert result == date(2025, 6, 14)

    def test_hou_tian(self):
        """后天 → 后天"""
        result = _parse_colloquial_date("油价后天调整", date(2025, 6, 13))
        assert result == date(2025, 6, 15)

    def test_zuo_tian(self):
        """昨天 → 昨天"""
        result = _parse_colloquial_date("油价昨天调整", date(2025, 6, 13))
        assert result == date(2025, 6, 12)

    def test_qian_tian(self):
        """前天 → 前天"""
        result = _parse_colloquial_date("油价前天调整", date(2025, 6, 13))
        assert result == date(2025, 6, 11)

    def test_da_hou_tian(self):
        """大后天"""
        result = _parse_colloquial_date("油价大后天调整", date(2025, 6, 13))
        assert result == date(2025, 6, 16)

    def test_da_qian_tian(self):
        """大前天"""
        result = _parse_colloquial_date("油价大前天调整", date(2025, 6, 13))
        assert result == date(2025, 6, 10)

    def test_ming_zao(self):
        """明早 → 明天"""
        result = _parse_colloquial_date("油价明早调整", date(2025, 6, 13))
        assert result == date(2025, 6, 14)

    def test_jin_zao(self):
        """今早 → 今天"""
        result = _parse_colloquial_date("油价今早调整", date(2025, 6, 13))
        assert result == date(2025, 6, 13)

    def test_ming_er(self):
        """明儿（方言） → 明天"""
        result = _parse_colloquial_date("油价明儿调整", date(2025, 6, 13))
        assert result == date(2025, 6, 14)

    def test_hou_er(self):
        """后儿（方言） → 后天"""
        result = _parse_colloquial_date("油价后儿调整", date(2025, 6, 13))
        assert result == date(2025, 6, 15)

    def test_zuo_er(self):
        """昨儿（方言） → 昨天"""
        result = _parse_colloquial_date("油价昨儿调整", date(2025, 6, 13))
        assert result == date(2025, 6, 12)

    def test_hou_tian_wan_shang(self):
        """后天晚上 → 后天"""
        result = _parse_colloquial_date("油价后天晚上调整", date(2025, 6, 13))
        assert result == date(2025, 6, 15)

    def test_jin_wan_ling_dian(self):
        """今晚零点 → 当天（油价惯例）"""
        result = _parse_colloquial_date("油价今晚零点调整", date(2025, 6, 13))
        assert result == date(2025, 6, 13)

    def test_no_match_returns_none(self):
        """无匹配返回 None"""
        result = _parse_colloquial_date("暂无调价信息", date(2025, 6, 13))
        assert result is None


class TestResolveDate:
    """测试综合日期解析"""

    def test_standard_priority_over_colloquial(self):
        """标准格式优先于口语化表达"""
        result = resolve_date("下次油价6月18日今晚24时调整", date(2025, 6, 13))
        assert result == date(2025, 6, 18)

    def test_colloquial_fallback(self):
        """无标准格式时回退到口语化"""
        result = resolve_date("油价今晚24时调整", date(2025, 6, 13))
        assert result == date(2025, 6, 13)

    def test_real_world_standard(self):
        """真实场景: 标准格式"""
        result = resolve_date("下次油价6月18日24时调整", date(2025, 6, 13))
        assert result == date(2025, 6, 18)

    def test_real_world_colloquial_tonight(self):
        """真实场景: 今晚24时 → 当天（油价惯例: 日期与24时同属一天）"""
        result = resolve_date("油价今晚24时调整", date(2025, 6, 13))
        assert result == date(2025, 6, 13)

    def test_real_world_colloquial_tomorrow(self):
        """真实场景: 明天"""
        result = resolve_date("油价明天24时调整", date(2025, 6, 13))
        assert result == date(2025, 6, 14)

    def test_real_world_colloquial_yesterday(self):
        """真实场景: 昨晚"""
        result = resolve_date("油价昨晚24时调整", date(2025, 6, 13))
        assert result == date(2025, 6, 12)

    def test_no_date_returns_none(self):
        """完全无日期信息返回 None"""
        result = resolve_date("暂无调价信息", date(2025, 6, 13))
        assert result is None

    def test_default_base_date(self):
        """不传基准日期使用当天作为基准"""
        from datetime import timedelta
        result = resolve_date("明天调整")
        today = date.today()
        assert result == today + timedelta(days=1)


class TestResolveDateSummary:
    """测试日期摘要生成"""

    def test_standard_format(self):
        result = resolve_date_summary("下次油价6月18日24时调整")
        assert result == "下次油价6月18日24时调整"

    def test_colloquial_to_summary(self):
        result = resolve_date_summary("油价今晚24时调整", date(2025, 6, 13))
        assert result == "下次油价6月13日24时调整"

    def test_no_date_returns_empty(self):
        result = resolve_date_summary("暂无调价信息")
        assert result == ""
