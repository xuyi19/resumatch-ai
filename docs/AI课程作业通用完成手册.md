# AI 智能体课程作业通用完成手册（Agent 执行版）

> **给谁用**：需要完成「智能体开发实践」类课程大作业的学生，以及被委托执行的 AI 编程助手（Codex / WorkBuddy / Trae / Claude Code 等）。
> **怎么用**：把本文档 + 你的选题（一句话即可）+ 学校答题模板 docx 一起交给 AI 助手，说「按本手册完成项目并生成报告」。手册自包含，无需参考任何示例仓库。
> **可信度**：全流程由「知岗 ResuMatch-AI」项目实战验证——pytest 223 例全绿、报告 docx 10 页逐页目检通过、成功提交。

---

## 0. 评分结构与得分策略（先读）

| 评分项 | 分值 | 得分核心动作 | 对应手册步骤 |
|---|---|---|---|
| 工程规范 | 20 | venv 隔离 + requirements 版本锁定 + 四层目录 + 密钥环境变量 + 全局工具类 | Step 1/2 |
| 知识库 RAG | 18 | Chroma 初始化 + PDF/TXT 分割入库 + 语义检索过滤重排 + 提示词拼接 | Step 3 |
| 多轮智能体 | 32 | BaseMessage 消息体系 + 记忆持久化裁剪 + 提示词模板 + ReAct 双工具 + LCEL 链 | Step 4 |
| 系统支撑 | 22 | 日志分级持久化 + 异常分类 + 输入安全过滤 + 实验对照（附截图）+ 容错调优 | Step 5/6 |
| 项目文档 | 8 | README 部署全流程 + 中文注释 + 架构总结 + 改进方向 | Step 7 |

**策略**：多轮智能体（32 分）是分值大头，ReAct 双工具与记忆持久化必须真实可运行（有测试佐证）；报告占 8 分但评审第一眼看到的是它，第 4 章流水线保证排版不出错。

---

## 1. 统一架构：任意选题的映射方法

本课程作业的本质是同一个骨架换领域皮肤。任何选题只需回答三个问题：

| 选题要素 | 需要什么 | 例子 |
|---|---|---|
| **领域知识文档** | 2~5 份该领域的 PDF/TXT 资料（入库做 RAG） | 医药→药品说明书；法律→法条；招聘→简历与 JD；校园→教务规章 |
| **高频问答场景** | 用户围绕资料提问 | 「这个药和感冒药能同服吗」「这条法条怎么适用」「我适合这个岗位吗」 |
| **计算场景** | 至少一个需要精确数值计算的问题 | 药物剂量换算、赔偿金计算、**薪资倒推/税后计算**、绩点计算 |

**映射规则**：把手册中所有「简历/岗位」字样替换为你的领域名词即可，架构、代码、报告结构完全不变。选题不同只影响三处：①入库的资料内容；②系统提示词里的角色人设一句话；③calculate 工具的示例问题。

---

## 2. 技术栈锁定（不要更换，已验证兼容）

```
Python >= 3.10
fastapi==0.141.1          uvicorn==0.52.4          python-multipart==0.0.32
sqlalchemy==2.0.52        aiosqlite==0.21.0        # SQLite 免安装，评审计分项
pydantic==2.13.5          pydantic-settings==2.15.0
langgraph==1.2.11         # create_react_agent 所在
langchain-openai==1.6.2   # ChatOpenAI + OpenAIEmbeddings（OpenAI 协议，任意厂商即插即用）
chromadb==1.5.9           # 持久化向量库（评审计分项）
pymupdf==1.28.2           # PDF 解析；python-docx==1.2.0（DOCX）
loguru==0.7.3
pytest==9.1.1             pytest-asyncio==1.4.0
```

> embedding 不用本地模型（torch 太重），走 OpenAI 协议 `/embeddings`，兼容 DeepSeek/通义/智谱等；测试用第 6 章的确定性伪向量绕开网络。

---

## 3. 七步执行流程（Agent 逐步执行，每步有验证）

### Step 1 环境与依赖（工程规范 3+4 分）

```bash
conda create -n agent-hw python=3.10 -y && conda activate agent-hw
# 等效标准做法：python -m venv venv
mkdir backend && cd backend && pip install -r requirements.txt
pytest -q   # 验证：装完即可跑（先写 1 个健康检查测试）
```

`requirements.txt` 全部 `==` 锁版本、按用途分组注释（Web/数据库/LLM/向量库/解析/日志/测试）。报告里写「锁版本保证一次装好处处一致」。

### Step 2 四层目录骨架（工程规范 4+4+5 分）

```
backend/app/
├── core/
│   ├── config.py        # 配置层：pydantic-settings 读 .env（BASE_DIR/LLM 参数/DATA_DIR）
│   ├── knowledge.py     # rag 知识库层：Chroma 封装 + split_text + search（Step 3）
│   ├── input_guard.py   # 安全层：三层输入过滤（Step 5）
│   └── db.py            # SQLite 异步引擎 + 建表
├── agents/
│   └── qa_agent.py      # agent 层：提示词模板常量 + ReAct 双工具 + 六步链路（Step 4）
├── api/v1/agent_qa.py   # 路由层：只做入参校验与响应
├── models/entities.py   # ORM 实体
├── utils/file_parser.py # 全局工具：PDF/DOCX/TXT 统一解析
└── tests/               # 与源码同构
```

报告话术：**config 配置层 / prompt 提示词层（agents 内模板常量）/ rag 知识库层（core/knowledge.py）/ agent 智能体业务层（agents/）** 四层与评分细则逐字对应。

密钥安全（4 分）：`.env` 进 `.gitignore`；**不内置任何 Key**——后端只读环境变量兜底，运行时 Key 由用户设置传入（`llm_config` 三要素：base_url/api_key/model）；缺失返回 400 中文提示；日志永不回显密钥。

全局工具类（5 分）：loguru 日志（控制台分级 + `logs/` 文件持久化）、异常分流（`ValueError→400 / 业务异常→400 / 未知→502`，对外只给友好 detail）、ChatOpenAI 统一构造、file_parser 统一解析（含扫描版 PDF 检测：文本 <50 字且多为图片页时明确报「请先 OCR」）。

### Step 3 RAG 三件套（18 分全项）

**3.1 Chroma 初始化**：`chromadb.PersistentClient(path=DATA_DIR/knowledge)` 落盘；每用户独立 collection `kb_{owner_id}`（cosine）；进程内单例 `get_knowledge_base()`；提供 stats/clear 接口。

**3.2 分割与入库**：`split_text(text, chunk_size=500, overlap=80)` 递归分割，分隔优先级：双换行段→单行→句号→分号→逗号→硬切；相邻块保留重叠。入库链：文件→分块→批量向量化→`collection.upsert`，metadata 记 source 文件名供溯源。上传接口做后缀白名单（.pdf/.txt/.md）+ 20MB 限制 + 超长截断 20 万字符。

**3.3 检索过滤重排**：`search(query, k=4)` = 向量化 → `collection.query` top-k → `max_distance=0.85` 余弦阈值过滤 → 查询词面命中（CJK 特征）重排。**降级链**：embedding 异常时退化为 `collection.get` 全量 + 词面打分——「检索不可用但问答可用」。

**3.4 提示词拼接**：检索结果格式化为「【知识库参考资料】块 N（来源：文件名）正文」注入系统提示词 `{rag_block}` 占位；约束「必须优先依据资料作答并标注来源，未覆盖时如实说明」。

### Step 4 ReAct 多轮智能体（32 分全项，得分大头）

**4.1 消息体系（8 分）**：全程 BaseMessage（HumanMessage/AIMessage）；历史以 `Sequence[BaseMessage]` 传递；`create_react_agent(model=llm, tools=[...], prompt=system_str)` 的输入 `{"messages": history + [HumanMessage(content=q)]}` 即 MessagesPlaceholder 语义的「系统→历史→当前问题」分层注入。

**4.2 记忆持久化与裁剪（6 分）**：表 `agent_messages(owner_id, session_id, role, content, created_at)` 双索引；`save_turn` 每轮写 human+ai 两条；`load_history` 倒序取最近 `MAX_HISTORY_MESSAGES=12` 条再正序回放。

**4.3 提示词模板（6 分）**：`_SYSTEM_TMPL` 分层 = 角色人设（按选题换一句话）→ `{rag_block}` → 工具使用规约 → 引用与防注入约束。

**4.4 双工具（6 分）**：
- `@tool calculate`：先归一化全角/中文运算符（，,×x），再 **AST 白名单求值**——仅放行数字常量、BinOp(+−*%/＊＊//)、UnaryOp(±)，其余一律拒绝（防 `__import__` 注入）；表达式为空返回错误文案不抛异常。
- `build_document_summarizer(owner_id, llm_config)`：**闭包工具**绑定用户身份，只读该用户知识库片段交模型归纳——数据隔离话术加分。
- 从 `AIMessage.tool_calls` 提取 `tool_trace` 随答案返回（「用了什么工具」可视化）。

**4.5 六步链路（6 分）**：`answer_question()` = ① sanitize_input → ② kb.search（失败降级空）→ ③ 拼 rag_block → ④ load_history → ⑤ `create_react_agent(...).ainvoke` → ⑥ save_turn 并返回 `{answer, tool_trace, rag_sources}`。

### Step 5 安全与异常（22 分的 9 分）

`input_guard.sanitize_input(text, max_len=8000)` 三层：① 剔除控制字符 + 长度截断；② 六类注入正则（指令覆盖/角色重置/越狱话术/套取系统提示/输出劫持/数据外带，中英双语约 10 条）；③ 违规词库。命中返回 `GuardResult(ok=False, reason)`，接口 400 并说明命中规则，不进模型。

异常分类四类：模型鉴权→400；向量库（KnowledgeError）→400；文档解析（ValueError）→400 带处理建议；未知→502。全局 handler 保证结构化 `{detail}`，不泄露堆栈。

### Step 6 测试与实验对照（22 分的 8 分）

**测试分层**（pytest，`asyncio_mode=auto`）：
- 单元：guard 3 例（正常/注入/截断）、split_text 2 例、_safe_eval 2 例；
- Chroma 2 例：**用确定性伪向量**（`_fake_embed = md5 hash 16 维 + 关键词 6 维`，monkeypatch `_embed_texts`），无需网络；
- E2E 3 例：历史回放条数（1→3）、持久化行数、guard 400、owner 隔离。
- 目标：≥20 例全绿，截图 `pytest -q` 输出作为报告图 3。

**实验对照（报告必附截图与分析）**：
- 纯 LLM VS RAG：同一问题，无 RAG 幻觉/无出处 vs 有 RAG 可回链原文（如有消融数据写具体数字：综合分 74→82、证据引用率 100%、虚构 23%→0%）；
- 无工具 VS 有工具：心算易错不可复核 vs calculate 精确且 tool_trace 可见。
- 配图：图 1 = Chroma 检索真实输出；图 2 = guard 拦截 400；图 3 = pytest 全绿。

### Step 7 README 与报告生成 → 见第 4 章流水线

README 必含：简介/环境要求/依赖安装/配置说明/启动流程/测试方法/接口一览（REST 路径+参数+响应示例）。报告用第 4 章流水线按学校模板生成。

---

## 4. 报告生成流水线（核心复用资产，照做零排版事故）

**原理**：docx = ZIP + XML。解包答题模板 → 定位 24 个小项标题锚点段 → 段后插入正文 XML → 插图（media+rels+Content_Types 三件套）→ 重打包 → Word COM 转 PDF 目检。

### 4.1 解包与锚点提取

```python
# 解包
import zipfile; zipfile.ZipFile('模板.docx').extractall('kt_template')
# 全部段落与文本
import re
xml = open('kt_template/word/document.xml', encoding='utf-8').read()
paras = re.findall(r'<w:p\b.*?</w:p>', xml, re.S)   # \b 保证不误配 <w:pPr
ptext = lambda p: ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', p))
```

### 4.2 正文段 XML 模板（宋体小四首行缩进 2 字符）

```python
FONTS = '<w:rFonts w:ascii="宋体" w:eastAsia="宋体" w:hAnsi="宋体" w:hint="eastAsia"/>'
SZ24  = '<w:sz w:val="24"/><w:szCs w:val="24"/>'   # 24 half-pt = 12pt 小四
def body_p(text):
    t = escape(text)  # xml.sax.saxutils.escape
    return (f'<w:p><w:pPr><w:ind w:firstLineChars="200" w:firstLine="480"/>'
            f'<w:rPr>{FONTS}{SZ24}</w:rPr></w:pPr>'
            f'<w:r><w:rPr>{FONTS}{SZ24}</w:rPr><w:t xml:space="preserve">{t}</w:t></w:r></w:p>')
# 图注：同上但 <w:jc w:val="center"/>、sz=21、加 <w:b/>
```

### 4.3 插图三件套

1. PNG 拷入 `word/media/imageN.png`；
2. `word/_rels/document.xml.rels` 的 `</Relationships>` 前追加 `<Relationship Id="rId900" Type=".../image" Target="media/image2.png"/>`；
3. `[Content_Types].xml` 若无则加 `<Default Extension="png" ContentType="image/png"/>`；
4. 正文插入 `<w:drawing>`（`<wp:inline>` 需内联声明 `xmlns:wp`，`<a:graphic>`/`<pic:pic>` 同理内联 `xmlns:a`/`xmlns:pic`；`<a:blip r:embed="rId900"/>`；宽度 14.2cm≈`cx=5112000` EMU，高按像素比例）。

**插入算法**：收集所有 `{锚点: [正文段, (图, 图注)]}` → 对每个锚点定位 `xml.index(锚点段块)+len` 得插入点 → **按位置降序逐个插入**（避免偏移失效）。

### 4.4 打包与目检

```python
# 打包：[Content_Types].xml 先写入，其余按 os.walk 相对路径
# 目检（有 MS Word 时）：
import win32com.client
w = win32com.client.DispatchEx('Word.Application'); w.Visible = False
d = w.Documents.Open(docx, ReadOnly=True); d.SaveAs2(pdf, FileFormat=17)
pages = d.ComputeStatistics(2); d.Close(False); w.Quit()
# 再用 pymupdf 逐页渲染 PNG 人工目检（90dpi 足够）
```

### 4.5 踩坑清单（每条都真实踩过）

| 坑 | 解法 |
|---|---|
| 正则误配 `<w:pPr>` | 用 `<w:p\b.*?</w:p>`（`\b` 挡住字母后续） |
| 多处插入位置漂移 | 收集后按位置**降序**插入 |
| python-docx `paragraphs` 少段落 | 它不读表格内段落——全文校验回退 XML 正则提取 |
| 锚点文本跨多个 `<w:t>` run | 按「含锚点的完整 `<w:p>` 块」定位，不按裸文本替换 |
| 题目占位替换 | 模板题目常是单 run 整串文本，直接字符串 replace 最稳 |
| PowerShell 无 heredoc | `git commit -F 临时文件` |
| Word COM 打开慢 | `DispatchEx` 独立进程 + `ReadOnly=True` + `Close(False)` |

**交付前人工核对**：题目已替换 / 24 锚点全有正文 / 图注居中 / 封面个人信息留白待填 / 末页无多余空白页。

---

## 5. 验收清单（全部打勾才交付）

- [ ] `pytest -q` 全绿（≥20 例），截图留存
- [ ] 无 Key 时接口返回 400 中文提示而非 500 崩溃（这本身就是容错得分点）
- [ ] guard 拦截演示可复现（真实 HTTP 调用截图）
- [ ] Chroma 检索演示可复现（入库→查询→distance 输出截图）
- [ ] 报告五节锚点全覆盖、3 张图嵌入且图注编号连续
- [ ] README 部署步骤新机器可照做
- [ ] `.env` 不在 git 内、源码无任何硬编码 Key

---

## 6. 无 API Key 的演示与测试策略（缺 Key 也能交差）

1. **guard 拦截是真演示**：不需要 Key 即可真实 HTTP 调用展示 400 拦截（注入样本命中规则输出）；
2. **Chroma 用确定性伪向量真跑**：md5-hash+关键词维度的 `_fake_embed`，入库/检索/重排全程真实（distance 数值真实可截图），仅 embedding 换成确定函数——测试与演示都不联网；
3. **pytest 覆盖正常链路**：E2E 用假 agent（记录收到的 messages 断言历史回放）替换 `create_react_agent`，无需真实 LLM；
4. 报告如实写：「演示截图为确定性向量环境，生产配置 Key 后自动切换真实 embedding」。

---

## 7. 技术增强分析：考核技术如何反哺真实项目

以 ResuMatch-AI（多智能体简历诊断系统）为例，考核模块五项技术反哺价值从高到低：

| # | 技术 | 反哺点 | 收益 | 改动量 |
|---|---|---|---|---|
| 1 | **input_guard 三层过滤** | 挂到诊断/面试/自由对话入口——目前主项目只有长度与类型防线，简历文本或 JD 里藏「忽略之前指令」类注入无代码层硬拦截（仅提示词层守则） | 安全短板补齐；简历是外部输入，风险真实存在 | 小（一个函数调用） |
| 2 | **Chroma PersistentClient** | 主项目 RAG 是「任务内临时索引」（每次诊断重建）；考核版落盘+按用户隔离，可升级为**用户级长期知识库**：沉淀历史诊断结论、面试复盘、常见问题，诊断时与任务内索引合并检索 | 诊断引用跨会话经验；新增「随时问我的求职知识库」功能 | 中 |
| 3 | **确定性伪向量测试法** | 主项目 RAG 测试依赖真 embedding 或跳过；`_fake_embed` 让检索逻辑单测离线确定性跑 | RAG 回归测试可进 CI，不怕厂商限流 | 小 |
| 4 | **检索降级链** | embedding 失败→全量取回+词面打分的模式，可移植到主项目非关键检索链路（面试题库、岗位关键词匹配），LLM 故障时基础功能不瘫 | 可用性提升 | 小 |
| 5 | **agent_messages 记忆模式** | owner+session 双索引+倒序裁剪回放，可统一主项目面试 chat_log（现为 JSON 整存，无法按条裁剪） | 长面试 token 可控、可按条审计 | 中（迁移） |
| 6 | **ReAct 工具化** | 主项目诊断链是固定图工作流（正确选择，不宜推翻）；但「岗位库查询/匹配度计算」可包装为工具挂进问答智能体，让查询类问题免走全链 | 派生轻量入口，不动主架构 | 中 |

**结论**：1、3、4 是「小改动高收益」，建议直接做；2 是最有想象力的功能升级；5、6 视需求。反过来也成立——这份手册之所以可信，正因为每项技术都先在真实项目里跑通才沉淀进作业。

---

*手册版本 v1.0（2026-10-16）· 由知岗 ResuMatch-AI 考核实战提炼 · 允许自由转发给任何 AI 助手执行*
