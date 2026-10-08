"""M56.1 平台深链直达：按岗位名+公司+城市生成招聘平台官方搜索页 URL。

纯函数、零网络请求——只做「带搜索词打开官方页」的 URL 拼装，不抓取平台数据、
不代用户提交（M56 定位红线）。城市码沿用各平台公开惯例：Boss 与天气行政代码
一致，智联为其自有编码体系；未收录城市降级（Boss 用全国码 / 智联不带城市参数），
保证深链永远可用。
"""

from __future__ import annotations

from urllib.parse import quote

# Boss 直聘城市码（与天气行政代码一致，可按需扩展）
BOSS_CITY_CODES: dict[str, str] = {
    "北京": "101010100",
    "上海": "101020100",
    "广州": "101280100",
    "深圳": "101280600",
    "杭州": "101210100",
    "成都": "101270100",
    "武汉": "101200100",
    "西安": "101110100",
    "南京": "101190100",
    "苏州": "101190400",
    "天津": "101030100",
    "重庆": "101040100",
    "长沙": "101250100",
    "郑州": "101180100",
    "合肥": "101220100",
    "福州": "101230101",
    "厦门": "101230201",
    "济南": "101120101",
    "青岛": "101120201",
    "大连": "101070201",
    "沈阳": "101070101",
    "哈尔滨": "101050101",
    "昆明": "101290101",
    "无锡": "101190201",
    "宁波": "101210401",
    "东莞": "101281601",
    "佛山": "101281000",
}
_BOSS_NATIONWIDE = "100010000"  # Boss 全国码

# 智联自有城市码（仅收录高置信常用城市，未命中省略 jl 参数走全国）
ZHILIAN_CITY_CODES: dict[str, str] = {
    "北京": "530",
    "上海": "538",
    "广州": "763",
    "深圳": "765",
    "杭州": "653",
    "南京": "635",
    "苏州": "639",
    "成都": "801",
    "武汉": "736",
    "西安": "854",
    "天津": "531",
    "重庆": "551",
}


def _city_code(city: str, table: dict[str, str]) -> str:
    """从「杭州市 / 杭州·西湖区 / 浙江杭州」等写法中匹配城市码，未命中返回空串。"""
    c = (city or "").strip()
    if not c:
        return ""
    for name, code in table.items():
        if name in c:
            return code
    return ""


def build_apply_links(title: str, company: str = "", city: str = "") -> dict[str, str]:
    """生成 Boss/智联/猎聘/牛客 四平台搜索深链。

    query = 岗位名 + 公司名（并入提高直达命中率）；城市匹配不到时
    Boss 用全国码、智联省略城市参数，深链保持可用。
    """
    q = " ".join(x for x in [(title or "").strip(), (company or "").strip()] if x)
    qs = quote(q)

    boss_city = _city_code(city, BOSS_CITY_CODES) or _BOSS_NATIONWIDE
    zl_city = _city_code(city, ZHILIAN_CITY_CODES)
    zl_city_param = f"&jl={zl_city}" if zl_city else ""

    return {
        "boss": f"https://www.zhipin.com/web/geek/job?query={qs}&city={boss_city}",
        "zhilian": f"https://sou.zhaopin.com/?kw={qs}{zl_city_param}",
        "liepin": f"https://www.liepin.com/zhaopin/?key={qs}",
        "nowcoder": f"https://www.nowcoder.com/search/all?query={qs}",
    }
