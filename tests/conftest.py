"""测试通用 fixtures"""

import pytest

from oilprice.scraper import AdjustmentInfo, OilPrice, OilPriceData


@pytest.fixture
def sample_prices():
    """多省份油价样本数据"""
    return [
        OilPrice(province="北京", price_92="7.64", price_95="8.13", price_98="9.63", price_0="7.34"),
        OilPrice(province="广东", price_92="7.66", price_95="8.29", price_98="10.29", price_0="7.30"),
        OilPrice(province="上海", price_92="7.60", price_95="8.09", price_98="10.09", price_0="7.28"),
        OilPrice(province="海南", price_92="8.75", price_95="9.29", price_98="9.49", price_0="7.38"),
        OilPrice(province="新疆", price_92="7.46", price_95="7.98", price_98="0", price_0="7.08"),
    ]


@pytest.fixture
def sample_adjustment():
    """油价调整样本数据"""
    return AdjustmentInfo(
        summary="下次油价3月23日24时调整",
        detail="目前预计上调油价1900元/吨(1.44元/升-1.72元/升)",
    )


@pytest.fixture
def sample_oil_data(sample_prices, sample_adjustment):
    """完整油价数据"""
    return OilPriceData(prices=sample_prices, adjustment=sample_adjustment)


@pytest.fixture
def sample_oil_data_no_adjustment(sample_prices):
    """无调价信息的油价数据"""
    return OilPriceData(prices=sample_prices, adjustment=None)


# 汽车之家油价页面的 HTML 模拟数据
AUTOHOME_HTML = """
<html>
<head><title>今日油价查询</title></head>
<body>
<table class="form_table__qzSm4">
  <tr><th>地区</th><th>92#汽油</th><th>95#汽油</th><th>98#汽油</th><th>0#柴油</th></tr>
  <tr><td>北京</td><td>7.64</td><td>8.13</td><td>9.63</td><td>7.34</td></tr>
  <tr><td>广东</td><td>7.66</td><td>8.29</td><td>10.29</td><td>7.30</td></tr>
  <tr><td>上海</td><td>7.60</td><td>8.09</td><td>10.09</td><td>7.28</td></tr>
</table>
</body>
</html>
"""

# 汽油价格网的 HTML 模拟数据（新格式）
QIYOUJIAGE_HTML = """
<html>
<body>
<div id="all">
  下次油价3月23日24时调整，
  目前预计上调油价1900元/吨(1.44元/升-1.72元/升)，大家相互转告油价继续大涨。
</div>
<div id="rightTop">
  柴油价格 油价
  下次油价3月23日24时调整
  目前预计上调油价1900元/吨(1.44元/升-1.72元/升)，大家相互转告油价继续大涨。
</div>
</body>
</html>
"""

# 汽油价格网的 HTML 模拟数据（旧格式）
QIYOUJIAGE_HTML_OLD = """
<html>
<body>
<div id="all">
  下次油价3月20日24时调整， 油价上涨0.55元/升-0.67元/升(每吨汽柴油价格分别上调695元和670元)，
  大家相互转告油价又涨了。
</div>
</body>
</html>
"""

# 无调价信息的 HTML
QIYOUJIAGE_HTML_EMPTY = """
<html><body><div id="all">暂无数据</div></body></html>
"""

# 油价下调格式
QIYOUJIAGE_HTML_DOWN = """
<html>
<body>
<div id="all">
  下次油价4月1日24时调整 目前预计下调油价200元/吨(0.15元/升-0.18元/升)，大家相互转告油价下跌了。
</div>
</body>
</html>
"""

# 油价搁浅/不调整格式
QIYOUJIAGE_HTML_SHELVED = """
<html>
<body>
<div id="all">
  下次油价4月15日24时调整 目前预计油价搁浅不调整
</div>
</body>
</html>
"""

# 旧格式：油价下跌
QIYOUJIAGE_HTML_OLD_DOWN = """
<html>
<body>
<div id="all">
  下次油价4月1日24时调整， 油价下跌0.15元/升-0.18元/升(每吨汽柴油价格分别下调200元和195元)
</div>
</body>
</html>
"""
