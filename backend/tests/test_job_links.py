"""M56.1 平台深链纯函数测试：无 DB、无网络，仅校验 URL 拼装规则。"""

from app.utils.job_links import build_apply_links


def test_links_basic_known_city():
    """收录城市 → 四平台齐全，Boss/智联带对应城市码，query 含岗位名+公司。"""
    links = build_apply_links("Python 后端", "字节跳动", "北京")
    assert set(links) == {"boss", "zhilian", "liepin", "nowcoder"}
    assert links["boss"].startswith("https://www.zhipin.com/web/geek/job?query=")
    assert "city=101010100" in links["boss"]
    assert links["zhilian"].startswith("https://sou.zhaopin.com/?kw=")
    assert "jl=530" in links["zhilian"]
    assert links["liepin"].startswith("https://www.liepin.com/zhaopin/?key=")
    assert links["nowcoder"].startswith("https://www.nowcoder.com/search/all?query=")
    # query 参数 URL 编码后包含空格分隔的岗位名与公司名
    from urllib.parse import unquote

    q = unquote(links["boss"].split("query=")[1].split("&")[0])
    assert q == "Python 后端 字节跳动"


def test_links_unknown_city_falls_back():
    """未收录城市：Boss 用全国码，智联省略城市参数。"""
    links = build_apply_links("数据分析", "某公司", "绍兴")
    assert "city=100010000" in links["boss"]  # 全国码
    assert "jl=" not in links["zhilian"]
    assert "kw=" in links["zhilian"]


def test_links_empty_city():
    """无城市输入同样降级为全国搜索，不炸。"""
    links = build_apply_links("产品经理")
    assert "city=100010000" in links["boss"]
    assert "jl=" not in links["zhilian"]


def test_links_city_suffix_and_variants():
    """「杭州市 / 杭州·西湖区」等写法都能命中城市码。"""
    for city in ("杭州市", "杭州·西湖区", "浙江杭州"):
        links = build_apply_links("测试开发", "", city)
        assert "city=101210100" in links["boss"], city
        assert "jl=653" in links["zhilian"], city


def test_links_chinese_and_space_encoded():
    """中文与空格需 URL 编码，保证链接可安全跳转。"""
    links = build_apply_links("算法工程师", "美团", "成都")
    assert "%" in links["boss"] and " " not in links["boss"]
    assert "%" in links["liepin"] and " " not in links["liepin"]
