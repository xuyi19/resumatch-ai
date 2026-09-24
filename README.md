# 知岗 ResuMatch-AI

> 中文名：**知岗** ｜ 英文名：**ResuMatch-AI**
> 知岗，意在**读懂岗位所求，认清自身所长**——从「改简历」到「过面试」的全流程 AI 求职助手：简历诊断 → 对答式优化 → 岗位匹配 → 模拟面试实战评分，一个应用全部搞定

求职投递里常见的困境，是求职者仅凭主观感受撰写简历，难以精准捕捉招聘 JD 背后的核心诉求，导致简历内容与岗位要求错位，投递石沉大海。

本项目基于 LangGraph 多智能体架构，打造简历与岗位 JD 智能匹配诊断工具。系统自动解析简历文本，抽取岗位核心能力要求，从多维度量化简历适配程度，定位能力短板，挖掘被忽略的个人亮点，并依据岗位需求针对性优化简历，生成可直接导出的文档。

不同于简单的文本润色工具，**知岗是求职者的岗位需求分析师**。它以岗位 JD 作为标尺，客观比对简历与岗位之间的差距，抹平求职者和招聘方之间的信息差，让简历不再是经历的堆砌，而是对岗位需求的有效回应。

- 上传简历、粘贴目标岗位 JD，AI 六维评分并逐条指出与岗位的差距（每条引用简历原文佐证）
- 改完简历一键重诊对比进度；岗位市场锁定目标岗位
- 最后让 AI 面试官来一场多轮自由对话的模拟面试，拿到总分、每题得分与四维雷达，导出 Word 报告复盘

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=flat-square&logo=fastapi)
![Vue](https://img.shields.io/badge/Vue-3.5-4FC08D?style=flat-square&logo=vuedotjs)
![LangGraph](https://img.shields.io/badge/LangGraph-1.2-7F77DD?style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-WAL-4479A1?style=flat-square&logo=sqlite)

---

## 目录

- [项目简介](#项目简介)
- [核心特性](#核心特性)
- [界面演示](#界面演示)
- [技术栈](#技术栈)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [桌面版（免安装分发）](#桌面版免安装分发)
- [网站部署模式](#网站部署模式)
- [项目结构](#项目结构)
- [API 一览](#api-一览)

---

## 项目简介

写简历靠感觉、投岗位靠海投、面试靠运气——知岗把这条链路变成**可量化、可复盘的闭环**：

1. **诊断**：上传简历（PDF/DOCX/TXT）+ 粘贴 JD，LangGraph 多节点诊断链输出六维评分、差距清单（RAG 证据接地，每条差距引用简历原文 `[R3]`）与改写建议；信息不足时 AI 动态追问（人在回路）
2. **优化**：按建议改写后用 10 套模板导出 Word（支持嵌入证件照），或在编辑器里直接创作；重诊一遍，分数/雷达/差距三重对比，改到哪进步到哪一目了然
3. **岗位**：岗位市场按简历一键匹配推荐（附推荐理由），也支持手动导入公司比对
4. **面试**：AI 面试官基于简历 + JD 生成 6 题题单，多轮自由对话（可被追问、可补充、可提前收尾），答完出总分 + 每题得分 + 四维雷达，导出 Word 面试报告

不做岗位爬取 —— 岗位数据来自 AI 生成与示例数据，JD 完全由用户掌控；全部数据本机 SQLite 按会话隔离，桌面版免安装双击即用。

## 核心特性

- **工作台总览**：简历数、诊断次数与均分、面试场次与均分、最近成绩一屏掌握；进行中的诊断/面试一键继续
- **多格式简历解析**：支持 PDF / DOCX / TXT，DOCX 会一并提取表格内容，避免表格式简历丢信息
- **JD 粘贴即用**：无爬虫依赖，从 BOSS / 智联 / 拉勾复制 JD 直接粘贴；最近使用的 JD 自动记忆，二次诊断免重贴
- **LangGraph 诊断链**：解析简历 ∥ 解析岗位 → 六维评分 → 差距分析 → 改写建议，实时进度可视化
- **RAG 证据接地**：简历/JD 条目级分块检索，差距与建议必须引用简历原文（`[R3]`），无据自动标「推断」——消融实验证明贡献 +8 分且消除无据推断（见 [`docs/ResuMatch-AI-技术说明文档.md`](docs/ResuMatch-AI-技术说明文档.md) 第 13 章）
- **动态多轮追问（人在回路）**：AI 基于信息缺口动态生成 0-3 个追问（LangGraph interrupt 暂停 → 前端问题卡片 → 回答后恢复续跑），失败可断点重试，跨重启可恢复
- **对答式深度优化**：AI 追问补充经历细节后生成定制优化简历，支持一键优化 / 逐题问答两种模式
- **10 套简历模板 + 证件照**：经典居中 / 侧栏双栏 / 商务蓝等 10 套，导出 Word 自动排入证件照；编辑器实时预览（与导出版式一致）+ 纯前端简历快速体检（零 LLM 秒级反馈）
- **我的简历库**：多份简历统一管理——重命名 / 批量删除 / PDF 原文件在线预览 / 最近诊断分速览，一键对任一简历发起诊断
- **岗位市场**：按简历意向一键获取岗位（AI 生成 / 示例数据）→ LLM 匹配度排序推荐（附推荐理由）→ 点选即填入 JD 直接诊断；支持手动导入公司比对
- **AI 模拟面试**：基于简历 + JD 生成 6 题题单（技术基础/项目深挖/岗位匹配/情景行为），与 AI 面试官**多轮自由对话**（可被追问、可补充、可提前收尾），答完出总评——总分 + 每题得分 + 四类维度雷达，支持独立发起（无需先诊断）、会话恢复、Word 报告导出
- **重诊对比 + 差距清单**：改完简历重诊，分数/雷达/差距三重对比；差距条目可标记「已解决」，对比视图联动高亮
- **诊断报告 / 面试报告导出 Word**：报告可存档、可打印、可发给导师
- **数据与隐私**：全部数据本机 SQLite 按会话隔离，设置页一键清空
- **双形态交付**：桌面 exe（免安装双击即用）+ 网站（匿名会话、无需注册）；亮 / 暗双主题；界面按运行形态自适应

## 界面演示

**工作台总览** —— /app 默认页：简历 / 诊断 / 面试进展一屏掌握，进行中的任务一键继续

![工作台总览](docs/images/dashboard.png)

| 发起诊断 | 诊断报告（六维雷达 + 证据接地） |
|---|---|
| ![发起诊断](docs/images/analyze.png) | ![诊断报告](docs/images/result.png) |

| 模拟面试（独立发起 + 多轮对话） | 简历库（批量管理 + 原文件预览） |
|---|---|
| ![模拟面试](docs/images/interview.png) | ![简历库](docs/images/resumes.png) |

| 诊断历史（重诊对比） | 设置（自带 API Key） |
|---|---|
| ![诊断历史](docs/images/history.png) | ![设置](docs/images/settings.png) |

## 技术栈

**后端**
- FastAPI + Uvicorn —— 异步 Web 框架
- LangGraph + langchain-openai —— 诊断工作流编排 + interrupt 人在回路，兼容 DeepSeek / 通义 / 智谱等 OpenAI 协议模型
- RAG-lite 证据检索 —— 条目级分块 + 纯 Python 余弦/IDF 关键词检索（零向量库依赖，embedding 不可用自动降级），证据接地可解释、抗幻觉
- SQLite（aiosqlite + WAL）—— 单文件库，免安装、支持并发读写
- PyMuPDF / python-docx —— 简历解析与 Word 生成（多模板 + 证件照排版）

**前端**
- Vue 3 (`<script setup>`) + Vue Router（hash 模式）
- Vite + Tailwind CSS
- ECharts —— 六维雷达图
- Axios

## 系统架构

```mermaid
flowchart TD
    A["简历上传<br/>PDF / DOCX → 文本"] --> D
    B["用户粘贴 JD 文本"] --> E
    R["evidence.py<br/>条目级分块 + RAG 检索"] -.-> F & G

    subgraph LG["LangGraph 诊断链"]
        direction LR
        D["parser<br/>结构解析"] --- E["job_analyze<br/>岗位解析"]
        E --> F["scorer<br/>六维评分<br/>按维度检索证据"]
        F --> G["gap<br/>差距分析<br/>差距必须引用 [R*] 原文"]
        G --> C["clarify<br/>动态追问 0-3 问<br/>interrupt 暂停"]
        C -->|用户回答后 Command(resume)| H["rewriter<br/>改写建议"]
        H --> I2["refine<br/>自省精修"]
    end

    I2 --> I["结果落库 SQLite<br/>历史可回看"]
    I --> J["对答式优化<br/>optimizer"]
    J --> K["简历编辑器<br/>10 套模板 + 证件照 + docx 实时预览"]
    K --> L["导出 Word / PDF"]
```

**RAG 证据接地**：诊断开始时把简历/JD 切成条目级证据块（`R1/J1…` 稳定 id），评分/差距/改写节点按需检索 Top-K 证据块注入 prompt；LLM 输出的证据引用经 `filter_valid_ids` 校验（防幻觉 id），无据差距自动标「推断」。embedding 服务不可用时自动降级 IDF 加权关键词检索（BM25-lite）。

**动态追问（人在回路）**：差距分析后 `clarify_plan` 节点按信息缺口生成 0-3 个问题，经 LangGraph `interrupt()` 暂停图执行并推送前端；用户答题后 `POST /live/clarify/{task_id}` 携 `Command(resume)` 恢复续跑改写与精修，全程状态由 checkpointer 保管（任务终态自动释放）。

**AI 模拟面试（LangGraph 之外的第二条对话链）**：`/interview/start` 按简历+JD+诊断差距生成 6 题题单；`/interview/chat/{task_id}` 多轮自由对话——候选人随时发言，面试官 LLM 以 `{reply, advance}` 结构化回应（可追问/点评，判断回答充分则收尾进下一题），末题自动汇总总评（总分 + 每题得分）；完整对话流存 `Conversation.chat_log`，会话跨重启可恢复，支持独立发起（`/app/interview`，无需先跑诊断）。

**任务进度**通过内存任务表实时推送（前端轮询 `/live/status`），诊断结果落库 SQLite `diagnosis_records`；服务重启时启动补偿会把残留的 running 记录标记为失败，前端自动回落历史接口恢复结果。桌面版由 `run.py` 看门狗守护：浏览器进程退出 **且** 页面心跳（每 20s `/meta/heartbeat`）消失超时后才收尾服务，防误杀。

**数据隔离**：所有业务表带 `owner_id` 列。本机/桌面形态固定 `local`；网站形态通过 HttpOnly 匿名会话 cookie 区分用户，老库由 `ensure_schema_columns()` 启动时自动补列迁移。

## 快速开始

### 环境要求

| 项目 | 版本 | 说明 |
|---|---|---|
| Python | 3.11+ | 推荐 conda / venv 隔离 |
| Node.js | 20+ | Vite 8 要求 |
| LLM API Key | — | 任意 OpenAI 协议兼容服务（DeepSeek 等） |

### 1. 配置后端

在 `backend/` 目录下创建 `.env`（该文件已在 `.gitignore` 中，不会被提交）：

```ini
DEBUG=True

# 任意 OpenAI 协议兼容模型
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

数据库为内置 SQLite（`backend/data/resumatch.db`），启动时自动建表，无需安装任何数据库。

### 2. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 3. 一键启动（推荐）

```bash
python run.py           # 项目根目录：自动拉起后端(8000) + 前端(5173)并弹浏览器
                        # 看门狗守护：浏览器关闭且心跳超时后自动收尾服务
# 或仅手动启动后端
uvicorn app.main:app --reload --port 8000
```

启动后访问 `http://127.0.0.1:8000/docs` 查看交互式 API 文档。

### 4. 启动前端（手动方式，run.py 已拉起则跳过）

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173`。Vite 已配置 `/api` 代理到后端，无需额外配置跨域。

### 5. 运行测试

```bash
cd backend
python -m pytest tests/ -q
```

## 桌面版（免安装分发）

不想装 Python / Node 也能用：项目可打包为**免安装桌面版**，双击即用，适合发给同学、考官或作为毕设现场演示。

```bash
cd backend
python build_desktop.py    # 任意 shell 可跑，产物在 release/ResuMatch-AI-桌面版/
```

- **pywebview 原生窗口**：默认窗口模式运行（Edge WebView2），异常时自动回退浏览器；`--no-browser` / `--browser` 可强制
- **无黑窗控制台**：`--windowed` 打包，运行日志写到 exe 同级 `data/logs/app.log`
- **单实例锁**：重复启动会自动聚焦已有窗口（识别 ResuMatch 健康响应，不误伤其它应用）
- 默认 **SQLite** 免安装，数据保存在 exe 同级 `data/resumatch.db`
- 大模型 API Key 由使用者在「设置」页填写，也可在 exe 同级放 `config.json` 预置（零配置分发）
- 包体约 55MB（已剔除 torch / Chromium / MySQL 驱动），Windows 10/11 实测通过

> **注意**：必须连同 `_internal` 文件夹一起拷贝，单独复制 `.exe` 无法运行。

## 网站部署模式

设置环境变量 `APP_MODE=web` 即切换为多用户网站形态：

- **匿名会话隔离**：首次访问自动签发 HttpOnly cookie（`rmsid`，30 天有效），无注册登录；也可用 `X-Session-Id` 请求头直调 API
- **每日配额**：使用服务端预置 Key 的诊断默认限 10 次/天（`WEB_DAILY_LIMIT`），用户在设置页自带 Key 则不限
- 简历 / 诊断记录 / 对话历史全部按会话隔离，互不可见

```bash
# 示例：以 web 模式启动
APP_MODE=web uvicorn app.main:app --host 0.0.0.0 --port 8765
```

## 项目结构

```
resumatch-ai/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口、lifespan（建表+老库补列+启动补偿）
│   │   ├── core/
│   │   │   ├── config.py           # pydantic-settings（APP_MODE / 会话 / 配额）
│   │   │   ├── deps.py             # get_owner_id 会话隔离依赖
│   │   │   └── db.py               # 异步引擎、ensure_schema_columns 老库补列
│   │   ├── models/entities.py      # Resume / DiagnosisRecord / Conversation（含面试题单/对话流）
│   │   ├── api/v1/                 # resume / live / history / chat / optimize / settings / health
│   │   │                           # + interview（题单/多轮对话/评分/导出）+ jobs（岗位市场）+ data（清空）
│   │   ├── services/               # resume_service / live_pipeline_service / diagnosis_service / job_market
│   │   ├── agents/                 # LangGraph 诊断工作流
│   │   │   └── nodes/              # parser / job_analyze / scorer / gap / rewriter
│   │   │                           # + refine（自省精修）/ optimizer / interactive_opt
│   │   └── utils/                  # file_parser、docx_generator（10 模板 + 证件照）、report_docx（诊断/面试报告导出）
│   ├── scripts/evaluate.py         # 质量评估脚本（标注集 × 多次运行，产出评估报告）
│   ├── desktop.py                  # pywebview 桌面启动器
│   ├── build_desktop.py            # PyInstaller 打包脚本（one-folder）
│   ├── run.py                      # 一键启动（前后端 + 看门狗心跳守护）
│   ├── tests/                      # pytest 用例（63 例：API / 诊断图 / 面试 / 岗位 / docx 生成）
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api/index.js            # Axios 封装
│       ├── composables/            # useAppMode / useTheme（形态与主题切换）
│       ├── components/             # InterviewPanel（面试面板，结果页与独立页复用）
│       │                           # RadarChart（参数化雷达）/ ResumePreview / EmptyState / LoadingBlock
│       ├── utils/checker.js        # 纯前端简历快速体检规则
│       └── views/                  # Home / Analyze / Result / Editor / Chat / History / Settings
│                                   # + Interview（独立面试）/ ResumeList（简历库）/ Changelog
└── docs/                           # 四件套：改造计划（迭代史）/ 技术说明文档（实现+踩坑+评估）/ 论文准备（知识点+答辩）/ 修改日志
```

## API 一览

启动后完整文档见 `/docs`，主要接口如下：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 健康检查（含数据库连通性） |
| GET | `/api/v1/meta` | 运行形态元信息（桌面版/网页版、配额、版本），前端据此切换界面 |
| POST | `/api/v1/resumes/upload` | 上传简历并解析（≤10MB，按会话隔离） |
| GET | `/api/v1/resumes/{id}` | 查询简历 |
| GET | `/api/v1/resumes/templates` | 简历模板目录（10 套） |
| POST | `/api/v1/resumes/photo` | 上传证件照（JPG/PNG ≤5MB） |
| GET | `/api/v1/resumes/photo/{photo_id}` | 读取证件照 |
| DELETE | `/api/v1/resumes/photo/{photo_id}` | 删除证件照 |
| POST | `/api/v1/resumes/export-docx` | 导出优化简历为 Word（可指定模板与照片） |
| POST | `/api/v1/live/analyze` | 启动诊断：`{resume_id, jd_text, resume_name?, enable_refine?}` |
| GET | `/api/v1/live/stream/{task_id}` | **SSE 实时推送**诊断进度（前端主用） |
| GET | `/api/v1/live/status/{task_id}` | 查询任务进度与结果（内存优先，过期回退 DB） |
| POST | `/api/v1/live/clarify/{task_id}` | 提交动态追问回答，`Command(resume)` 恢复诊断链 |
| GET | `/api/v1/history` | 历史记录列表（按会话隔离） |
| GET/DELETE | `/api/v1/history/{task_id}` | 历史详情 / 删除 |
| POST | `/api/v1/optimize/{task_id}` | 一键优化 |
| POST | `/api/v1/chat/start|reply|finish/{task_id}` | 对答式优化 |
| GET | `/api/v1/chat/history/{task_id}` | 对话历史 |
| GET | `/api/v1/resumes/list` | 简历库列表（含最近诊断分） |
| GET | `/api/v1/resumes/{id}/file` | 简历原文件（inline，供 PDF 预览） |
| POST | `/api/v1/resumes/delete-batch` | 简历库批量删除 |
| POST | `/api/v1/jobs/search` | 岗位市场：获取岗位（AI 生成 / 示例数据） |
| POST | `/api/v1/jobs/recommend` | 按简历 LLM 匹配推荐（附推荐理由） |
| POST | `/api/v1/jobs/import-match` | 手动导入公司比对 |
| POST | `/api/v1/interview/start/{task_id}` | 生成面试题单（regenerate 重出） |
| POST | `/api/v1/interview/start-free` | 独立发起面试（简历 + JD，无需先诊断） |
| GET | `/api/v1/interview/{task_id}` | 恢复面试会话（题单/对话流/总评） |
| POST | `/api/v1/interview/chat/{task_id}` | 多轮自由对话（`{reply, advance}` 收尾推进） |
| GET | `/api/v1/interview/sessions` | 面试会话列表（含总分） |
| POST | `/api/v1/interview/export/{task_id}` | 面试报告导出 Word |
| POST | `/api/v1/history/{task_id}/export-report` | 诊断报告导出 Word |
| DELETE | `/api/v1/data` | 一键清空本会话全部数据 |
| POST | `/api/v1/meta/heartbeat` | 页面心跳（看门狗防误杀） |

**完整流程调用示例**

```bash
# 1. 上传简历
curl -X POST http://127.0.0.1:8000/api/v1/resumes/upload \
  -F "file=@我的简历.pdf"
# → {"id": 1, "filename": "我的简历.pdf", "text_length": 2143}

# 2. 启动诊断（粘贴 JD 文本）
curl -X POST http://127.0.0.1:8000/api/v1/live/analyze \
  -H "Content-Type: application/json" \
  -d '{"resume_id": 1, "jd_text": "岗位职责：负责后端服务开发……任职要求：3 年以上 Python 经验……", "resume_name": "我的简历.pdf"}'
# → {"task_id": "a1b2c3d4e5f6", "status": "pending"}

# 3. 轮询结果
curl http://127.0.0.1:8000/api/v1/live/status/a1b2c3d4e5f6
```

---

## 常见问题

<details>
<summary>8000 端口被占用</summary>

启动脚本会自动顺延到 8001+。控制台会打印实际端口，浏览器访问对应地址即可。
</details>

<details>
<summary>老版本数据库升级</summary>

直接启动即可：`ensure_schema_columns()` 会在启动时自动检查并补齐新增列（如 `owner_id`），历史数据自动归属本机用户，无需手动迁移。
</details>

<details>
<summary>LLM 返回内容不是合法 JSON</summary>

部分模型对结构化输出支持不完善。项目在 `agents/utils.py` 中做了三层兜底：剥离代码块标记 → 正则提取 JSON 片段 → 失败后追加纠错提示重试（最多 3 次）。
</details>

<details>
<summary>桌面版双击闪退</summary>

必须连同 `_internal` 文件夹一起拷贝。若窗口无法创建（缺 WebView2 运行时），程序会自动回退到系统浏览器打开；也可用 `--browser` 参数手动指定。
</details>

更多历史踩坑记录见 [`docs/ResuMatch-AI-技术说明文档.md`](docs/ResuMatch-AI-技术说明文档.md) 第 12 章。

---

## 开发路线

- [x] M1 清理：移除爬虫与 MySQL，SQLite 单文件库
- [x] M2 逻辑修复：resume_id 落库、任务状态持久化、启动补偿、keyword 回填岗位名
- [x] M3 桌面版强化：pywebview 窗口化、单实例锁、打包排除清单、exe 烟测
- [x] M4 网站化：owner 会话隔离、Web 每日配额、证件照、10 套简历模板
- [x] M5 收尾：历史文档重写、模板化前端预览
- [x] M6 SSE 实时进度 + 结果落库 + 自省精修（refine）+ 质量评估脚本
- [x] M7 桌面 exe 强化：任务串台修复、原生窗口、无控制台打包
- [x] M8 启动提速（52.6s → 2.1s）+ 双形态界面（桌面 App 风 / 网页引流）+ 首页重写
- [x] M9 清理回收 1.8GB（历史安装包 / 冗余环境文件）
- [x] M10 编辑器预览保真：docx-preview 直渲真实 Word 文件，预览与导出版式一致
- [x] M11 RAG 证据接地 + 动态多轮追问（interrupt 人在回路）+ 消融/稳定性评估
- [x] M12 检索 IDF 加权（BM25-lite）+ 空池防幻觉指令
- [x] M13~M16 健壮性收敛、导出体验升级、编辑器独立创建简历、任务跨重启恢复
- [x] M17~M22 产品化一期：统一壳 + 亮暗双主题、岗位市场（AI 生成岗位 + LLM 推荐 + 手动导入比对）、报告导出 + 重诊对比、简历库 + 快速体检、失败重试 + 扫描件引导、数据与隐私 + 更新检查
- [x] M23 面试功能落地：AI 出题单 + 模拟面试逐轮点评
- [x] M24~M27 体验深化：多简历管理页、编辑器入库、重复诊断去重、PDF 原文件预览
- [x] M28~M30 版本号单一事实源、岗位数据源精简 + 手动导入公司比对
- [x] M31~M33 独立面试页 + 多轮自由对话（可追问可收尾）+ 面试报告导出 Word
- [x] M34~M35 面试评分量化（总分/每题得分/四类雷达）+ 差距条目标记「已解决」与重诊对比联动
- [x] M36 工作台总览仪表盘（/app 默认页：统计卡 + 进行中任务 + 最近记录）

---

## 免责声明

- 本项目为个人学习与技术研究成果，**不得用于任何商业用途**。
- 简历文件包含个人敏感信息，请勿将数据库文件分发他人；网站部署需自行补充传输加密与数据脱敏。
- LLM 生成的评分与建议仅供参考，不构成任何求职决策依据。

---

## License

[MIT](LICENSE) © 2026
