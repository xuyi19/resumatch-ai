"""M61 投递前体检：JD 关键词提取与简历覆盖比对。

纯函数、零外部状态、零 LLM 调用——本地词库匹配 + 英文词补充 + jieba 中文补充
（jieba 缺失时自动降级，词库与英文路径照常工作）。命中判定与计数共用同一套
归一化规则，保证「提取出的词」与「简历比对」口径一致。
"""

from __future__ import annotations

import re

# ============================================================
# 技能词库：(展示名, [别名...])。别名覆盖大小写/空格/中英混写变体；
# 展示名自身也参与匹配（自动并入别名集合）。
# ============================================================
SKILL_LEXICON: list[tuple[str, list[str]]] = [
    # ---------- 编程语言 ----------
    ("Python", ["python", "python3"]),
    ("Java", ["java", "jdk", "jvm"]),
    ("Go", ["golang", "go语言", "go 语言"]),
    ("C++", ["c++", "cpp"]),
    ("C", ["c语言"]),
    ("C#", ["c#", "csharp"]),
    (".NET", [".net", "dotnet", "asp.net", ".net core", "netcore"]),
    ("JavaScript", ["javascript", "js", "es6"]),
    ("TypeScript", ["typescript", "ts"]),
    ("Rust", ["rust"]),
    ("PHP", ["php"]),
    ("Scala", ["scala"]),
    ("R", ["r语言", "rstudio", "ggplot"]),
    ("Kotlin", ["kotlin"]),
    ("Ruby", ["ruby", "rails"]),
    ("Swift", ["swift"]),
    ("Objective-C", ["objective-c", "objc"]),
    ("Shell", ["shell", "bash"]),
    ("SQL", ["sql"]),
    ("Dart", ["dart"]),
    ("Lua", ["lua"]),
    ("Perl", ["perl"]),
    ("MATLAB", ["matlab"]),
    ("Groovy", ["groovy"]),
    ("VBA", ["vba"]),
    # ---------- 后端框架 ----------
    ("Spring Boot", ["springboot", "spring boot", "spring"]),
    ("Spring Cloud", ["springcloud", "spring cloud"]),
    ("Django", ["django"]),
    ("FastAPI", ["fastapi", "fast api"]),
    ("Flask", ["flask"]),
    ("Tornado", ["tornado"]),
    ("Node.js", ["node.js", "nodejs", "node"]),
    ("NestJS", ["nestjs"]),
    ("Express", ["express"]),
    ("Koa", ["koa"]),
    ("Gin", ["gin"]),
    ("gRPC", ["grpc"]),
    ("MyBatis", ["mybatis", "mybatis-plus"]),
    ("Netty", ["netty"]),
    ("Dubbo", ["dubbo"]),
    ("Laravel", ["laravel"]),
    ("ThinkPHP", ["thinkphp"]),
    ("Hibernate", ["hibernate", "jpa"]),
    # ---------- 前端 ----------
    ("Vue", ["vue", "vuejs", "vue.js", "vue3", "vue2"]),
    ("React", ["react", "reactjs", "react.js", "react native"]),
    ("Angular", ["angular", "angularjs"]),
    ("微信小程序", ["小程序", "微信小程序", "miniprogram"]),
    ("uni-app", ["uniapp", "uni-app"]),
    ("Taro", ["taro"]),
    ("Next.js", ["next.js", "nextjs"]),
    ("Nuxt", ["nuxt"]),
    ("Element Plus", ["element-plus", "elementplus", "element ui", "elementui"]),
    ("Ant Design", ["antdesign", "ant design", "antd"]),
    ("jQuery", ["jquery"]),
    ("HTML", ["html", "html5"]),
    ("CSS", ["css", "css3"]),
    ("Sass", ["sass", "scss"]),
    ("Webpack", ["webpack"]),
    ("Vite", ["vite"]),
    ("Electron", ["electron"]),
    ("Flutter", ["flutter"]),
    ("Tailwind CSS", ["tailwind", "tailwindcss"]),
    ("Axios", ["axios"]),
    # ---------- 数据库 / 大数据 ----------
    ("MySQL", ["mysql"]),
    ("Redis", ["redis"]),
    ("MongoDB", ["mongodb", "mongo"]),
    ("PostgreSQL", ["postgresql", "postgres", "pgsql"]),
    ("Oracle", ["oracle"]),
    ("SQL Server", ["sqlserver", "sql server", "mssql"]),
    ("Elasticsearch", ["elasticsearch", "es"]),
    ("Kafka", ["kafka"]),
    ("RabbitMQ", ["rabbitmq"]),
    ("RocketMQ", ["rocketmq"]),
    ("Spark", ["spark"]),
    ("Flink", ["flink"]),
    ("Hive", ["hive"]),
    ("Hadoop", ["hadoop", "hdfs", "mapreduce"]),
    ("ClickHouse", ["clickhouse"]),
    ("HBase", ["hbase"]),
    ("数据仓库", ["数仓", "数据仓库", "data warehouse"]),
    ("TiDB", ["tidb"]),
    ("Doris", ["doris"]),
    ("Presto", ["presto", "trino"]),
    ("Memcached", ["memcached"]),
    ("Cassandra", ["cassandra"]),
    ("Neo4j", ["neo4j"]),
    # ---------- 云与运维 ----------
    ("Docker", ["docker", "容器"]),
    ("Kubernetes", ["k8s", "kubernetes"]),
    ("Linux", ["linux", "centos", "ubuntu"]),
    ("AWS", ["aws", "amazon web services", "ec2", "s3"]),
    ("阿里云", ["阿里云", "aliyun"]),
    ("腾讯云", ["腾讯云", "tencent cloud"]),
    ("Azure", ["azure"]),
    ("GCP", ["gcp", "google cloud"]),
    ("Terraform", ["terraform"]),
    ("CI/CD", ["ci/cd", "cicd", "持续集成", "持续交付", "持续部署"]),
    ("Jenkins", ["jenkins"]),
    ("GitLab", ["gitlab"]),
    ("GitHub Actions", ["github actions", "github action"]),
    ("Ansible", ["ansible"]),
    ("Nginx", ["nginx"]),
    ("Prometheus", ["prometheus"]),
    ("Grafana", ["grafana"]),
    ("ELK", ["elk", "logstash", "kibana"]),
    ("Istio", ["istio"]),
    ("DevOps", ["devops"]),
    ("SRE", ["sre"]),
    ("Git", ["git"]),
    # ---------- AI 与数据科学 ----------
    ("PyTorch", ["pytorch", "torch"]),
    ("TensorFlow", ["tensorflow"]),
    ("机器学习", ["机器学习", "machine learning"]),
    ("深度学习", ["深度学习", "deep learning"]),
    ("LLM", ["llm", "大模型", "large language model"]),
    ("RAG", ["rag", "检索增强"]),
    ("Pandas", ["pandas"]),
    ("NumPy", ["numpy"]),
    ("scikit-learn", ["scikit-learn", "sklearn"]),
    ("NLP", ["nlp", "自然语言处理"]),
    ("OpenCV", ["opencv"]),
    ("计算机视觉", ["计算机视觉", "图像识别"]),
    ("LangChain", ["langchain", "langgraph"]),
    ("Agent", ["agent", "智能体"]),
    ("强化学习", ["强化学习", "reinforcement learning"]),
    ("数据挖掘", ["数据挖掘", "data mining"]),
    ("数据分析", ["数据分析", "data analysis"]),
    ("推荐系统", ["推荐系统", "推荐算法"]),
    ("模型微调", ["微调", "sft", "lora"]),
    ("AIGC", ["aigc"]),
    ("OCR", ["ocr"]),
    ("Hugging Face", ["huggingface", "hugging face", "transformers"]),
    # ---------- 软性高频词 ----------
    ("高并发", ["高并发"]),
    ("分布式", ["分布式"]),
    ("微服务", ["微服务"]),
    ("性能优化", ["性能优化", "调优"]),
    ("单元测试", ["单元测试", "单测"]),
    ("敏捷开发", ["敏捷", "scrum"]),
    ("跨部门沟通", ["跨部门", "跨团队"]),
    ("项目管理", ["项目管理", "pmp"]),
    ("需求分析", ["需求分析"]),
    ("系统设计", ["系统设计", "架构设计"]),
    ("高可用", ["高可用"]),
    ("中间件", ["中间件"]),
    ("多线程", ["多线程", "并发编程"]),
    ("计算机网络", ["计算机网络", "tcp/ip", "tcp"]),
    ("数据结构", ["数据结构"]),
    ("算法", ["算法"]),
    ("设计模式", ["设计模式"]),
    ("消息队列", ["消息队列", "mq"]),
    ("负载均衡", ["负载均衡"]),
    ("缓存", ["缓存"]),
    ("容灾", ["容灾", "灾备"]),
    ("代码审查", ["代码审查", "code review"]),
    ("英语", ["英语", "英文", "六级", "cet-6"]),
    ("Excel", ["excel"]),
    ("PPT", ["ppt", "powerpoint"]),
]

# 停用词：过滤泛化词（仅作用于英文/中文补充路径，词库本身是人工筛过的）
STOPWORDS: set[str] = {
    # 中文泛化词
    "岗位职责", "任职要求", "优先", "熟悉", "精通", "负责", "参与", "公司", "团队",
    "经验", "相关", "较强", "良好", "能力", "工作", "岗位", "候选", "者", "以上", "等",
    "加分", "加分项", "了解", "掌握", "具有", "具备", "进行", "完成", "使用", "开发",
    "设计", "实现", "维护", "优化", "支持", "包括", "以下", "要求", "优先考虑", "人员",
    # 英文泛化词
    "the", "and", "with", "for", "you", "your", "our", "will", "are", "have", "has",
    "from", "this", "that", "not", "can", "who", "all", "any", "per", "or", "of", "in",
    "on", "to", "at", "by", "as", "is", "be", "we", "us", "an", "it", "its", "etc",
    "eg", "ie", "via", "using", "use", "used", "new", "more", "than", "over", "other",
    "years", "year", "experience", "development", "engineer", "engineers", "manager",
    "team", "teams", "work", "working", "job", "role", "position", "company", "bonus",
    "plus", "good", "strong", "ability", "skill", "skills", "related", "familiar",
    "proficient", "master", "responsible", "participate", "candidate", "candidates",
}

# 英文补充词正则：字母开头，允许字母数字与 +#./-（覆盖 c++ / c# / ci/cd / vue.js）
_EN_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#./-]{1,24}")
# 疑似域名/链接碎片 token（URL 已先剔除，这里兜底过滤 .com/.cn 等）
_SITE_SUFFIX_RE = re.compile(r"\.(com|cn|net|org|io|html|php|asp)\b")


def _normalize(text: str) -> str:
    """归一化：lowercase + 全角转半角 + 多空格合一。"""
    if not text:
        return ""
    text = text.lower()
    out = []
    for ch in text:
        code = ord(ch)
        if code == 0x3000:  # 全角空格
            ch = " "
        elif 0xFF01 <= code <= 0xFF5E:  # 全角 ASCII 区
            ch = chr(code - 0xFEE0)
        out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _count_in(norm_text: str, alias: str) -> int:
    """alias 在归一化文本中的出现次数。

    纯 ASCII 字母数字且长度 ≤4 的短别名（js/go/k8s/ai…）用词边界正则计数，
    防止「js」误吃「json」、「go」误吃「golang」这类子串误报；其余按普通
    子串计数（spring 命中 springboot、c++ 等含符号别名本就无边界问题）。
    """
    if not alias:
        return 0
    if len(alias) <= 4 and alias.isascii() and alias.isalnum():
        return len(re.findall(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", norm_text))
    return norm_text.count(alias)


# 模块加载时预归一化词库（重复调用 extract/check 不再做字符串变换）
_ALL_ALIASES: set[str] = set()          # 全部归一化别名 + 展示名（英文补充去重用）
_DISPLAY_ALIASES: dict[str, tuple[str, ...]] = {}  # 归一化展示名 -> 归一化别名元组
for _display, _aliases in SKILL_LEXICON:
    _nd = _normalize(_display)
    _na = tuple(dict.fromkeys(
        [a for a in (_normalize(x) for x in _aliases) if a] + [_nd]
    ))
    _ALL_ALIASES.update(_na)
    _DISPLAY_ALIASES[_nd] = _na


def _jieba_tags(text: str) -> list[str]:
    """jieba 关键词提取（import 放函数内）：jieba 缺失/失败一律返回空列表降级。"""
    try:
        import jieba
        import jieba.analyse  # noqa: F401

        try:
            jieba.setLogLevel(60)  # 压掉首建词典的「Building prefix dict」日志
        except Exception:
            pass
        return list(jieba.analyse.extract_tags(text, topK=15))
    except Exception:  # ImportError / 运行期异常（如打包缺词典文件）统一降级
        return []


def extract_jd_keywords(jd: str, max_terms: int = 30) -> list[dict]:
    """从 JD 提取高频关键词：词库匹配 → 英文补充 → 中文补充 → 合并去重。

    返回 [{"word": 展示名, "count": JD 出现次数}, ...]，按 count 降序。
    """
    norm_jd = _normalize(jd)
    if not norm_jd:
        return []

    # 1) 词库匹配：任一别名出现即候选，count 取别名间最大值
    candidates: list[dict] = []
    seen_norms: set[str] = set()
    for display, aliases in SKILL_LEXICON:
        nd = _normalize(display)
        count = max(_count_in(norm_jd, a) for a in _DISPLAY_ALIASES[nd])
        if count > 0:
            candidates.append({"word": display, "count": count, "_norm": nd})
            seen_norms.add(nd)
            seen_norms.update(_DISPLAY_ALIASES[nd])

    # 2) 英文补充：独立英文 token 出现 ≥2 次（剔除 URL 碎片、停用词、词库已覆盖词）
    clean_jd = re.sub(r"https?://\S+", " ", norm_jd)
    freq: dict[str, int] = {}
    for token in _EN_TOKEN_RE.findall(clean_jd):
        if _SITE_SUFFIX_RE.search(token) or token in STOPWORDS or token in _ALL_ALIASES:
            continue
        freq[token] = freq.get(token, 0) + 1
    for token, n in freq.items():
        if n >= 2:
            candidates.append({"word": token, "count": n, "_norm": token})
            seen_norms.add(token)

    # 3) 中文补充：jieba 关键词（缺失自动降级）；纯 ASCII 交给上面两条路径
    for tag in _jieba_tags(norm_jd):
        if len(tag) < 2 or tag in STOPWORDS or tag.isascii():
            continue
        nt = _normalize(tag)
        if nt in seen_norms:
            continue
        count = norm_jd.count(nt)
        if count > 0:
            candidates.append({"word": tag, "count": count, "_norm": nt})
            seen_norms.add(nt)

    # 4) 展示名归一化去重（同 norm 取 count 大者）→ count 降序 → 截断
    merged: dict[str, dict] = {}
    for c in candidates:
        prev = merged.get(c["_norm"])
        if not prev or c["count"] > prev["count"]:
            merged[c["_norm"]] = c
    result = sorted(merged.values(), key=lambda c: -c["count"])[:max_terms]
    return [{"word": c["word"], "count": c["count"]} for c in result]


def check_coverage(keywords: list[dict], resume_text: str) -> dict:
    """关键词覆盖比对：展示名或任一别名命中（同一套归一化/边界口径）即 hits。

    返回 {"coverage": 0~100 整数, "hits": [...], "missing": [...]}，
    hits/missing 均保持 keywords 原顺序（count 降序）。
    """
    norm_resume = _normalize(resume_text)
    hits: list[str] = []
    missing: list[str] = []
    for kw in keywords or []:
        word = str(kw.get("word") or "").strip()
        if not word:
            continue
        nd = _normalize(word)
        aliases = _DISPLAY_ALIASES.get(nd) or (nd,)
        matched = any(_count_in(norm_resume, a) > 0 for a in aliases)
        (hits if matched else missing).append(word)
    total = len(hits) + len(missing)
    coverage = round(len(hits) * 100 / total) if total else 0
    return {"coverage": coverage, "hits": hits, "missing": missing}
