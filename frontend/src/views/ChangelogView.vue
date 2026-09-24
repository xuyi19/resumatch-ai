<template>
  <div class="min-h-screen py-12">
    <div class="max-w-3xl mx-auto px-6">

      <div class="mb-12">
        <div class="flex items-center gap-3 mb-2">
          <h1 class="text-3xl font-semibold text-ink">更新日志</h1>
          <span v-if="meta.version" class="px-2.5 py-1 rounded-lg text-xs font-mono
            bg-accent/10 text-accent border border-accent/20">当前 v{{ meta.version }}</span>
        </div>
        <p class="text-sm text-ink-sub">知岗 ResuMatch-AI 的版本历史与发布说明</p>
      </div>

      <div class="relative pl-8">
        <div class="absolute left-[5px] top-2 bottom-2 w-px bg-line-strong/60"></div>

        <div v-for="log in logs" :key="log.version"
          class="relative mb-12 last:mb-0">

          <div class="absolute -left-8 top-1.5 w-3 h-3 rounded-full bg-accent ring-4 ring-accent/15"></div>

          <div class="flex items-baseline gap-4 mb-4 flex-wrap">
            <div class="text-xl font-semibold text-ink font-mono">{{ log.version }}</div>
            <div class="text-sm text-ink-sub font-mono">{{ log.date }}</div>
            <span v-if="log.current" class="px-2 py-0.5 rounded-md text-xs font-medium
              bg-ok/10 text-ok border border-ok/25">当前版本</span>
          </div>

          <div v-if="log.title" class="text-base font-medium text-ink-sub mb-4">
            {{ log.title }}
          </div>

          <div class="space-y-3">
            <div v-for="(item, j) in log.items" :key="j"
              class="flex gap-3 items-start">
              <span :class="tagClass(item.type)"
                class="shrink-0 mt-0.5 px-2.5 py-1 rounded-lg text-xs font-medium">
                {{ item.type }}
              </span>
              <span class="text-sm text-ink-sub leading-relaxed">{{ item.text }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="mt-16 text-center">
        <RouterLink to="/"
          class="inline-block px-6 py-3 text-sm font-medium rounded-lg
            bg-panel border border-line text-ink-sub
            hover:border-line-strong hover:text-ink
            transition-colors">
          返回首页
        </RouterLink>
      </div>

    </div>
  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import { useAppMode } from '../composables/useAppMode'

const { meta } = useAppMode()

const logs = [
  {
    version: 'v0.10.0',
    date: '2026-09-24',
    title: 'AI 面试官实战 + 工作台总览',
    current: true,
    items: [
      { type: '新增', text: '模拟面试多轮自由对话：可追问、可补充、可跳过，AI 面试官按真实面试节奏回应' },
      { type: '新增', text: '面试评分量化：总分 + 每题得分 + 四维能力雷达图，会话列表直接比较各场成绩' },
      { type: '新增', text: '面试报告导出 Word：完整问答记录与总评，便于复盘存档' },
      { type: '新增', text: '工作台总览仪表盘（默认页）：统计卡、分数趋势折线、进行中任务、最近记录' },
      { type: '新增', text: '岗位收藏夹：♡ 收藏心仪岗位，一键带 JD 发起诊断或模拟面试' },
      { type: '优化', text: '总览页 Bento 布局改版：Hero 欢迎卡 + 便当盒卡片网格；全站品牌光晕与卡片柔影' },
      { type: '优化', text: '面试会话可删除管理；进行中的诊断与面试在工作台一键继续' },
      { type: '修复', text: '修复批量删除简历失败、面试强制收尾占位文案污染对话流等问题' },
    ],
  },
  {
    version: 'v0.9.0',
    date: '2026-09-23',
    title: '岗位市场 + 简历库 + 报告闭环',
    items: [
      { type: '新增', text: '岗位市场：粘贴 JD 一键获取在招岗位，按简历智能推荐（官方数据接口）' },
      { type: '新增', text: '诊断报告导出 Word；两次诊断自动对比（Before/After 综合分与差距变化）' },
      { type: '新增', text: '简历库独立页：多简历管理、重命名/预览/删除/批量删除，重复上传自动拦截复用' },
      { type: '新增', text: '简历库 PDF 原版式预览（浏览器内直渲）+ 原文件下载' },
      { type: '新增', text: '面试准备（6 题定制题单 + 回答思路）与模拟面试（逐题点评 + 总评）' },
      { type: '新增', text: '失败任务断点续跑（已完成节点不重跑）；追问回答草稿暂存，刷新不丢' },
      { type: '新增', text: '一键清空本机全部数据（隐私合规）' },
      { type: '优化', text: '简历编辑器支持入库保存，从简历库一键发起诊断；一键启动降噪 + 关浏览器自动停服' },
      { type: '修复', text: '修复结果页白屏（变量初始化顺序）等问题' },
    ],
  },
  {
    version: 'v0.8.0',
    date: '2026-09-22',
    title: '全站风格重做：类 Codex 控制台',
    items: [
      { type: '变更', text: '全站视觉重做：统一深色控制台风格，亮 / 暗双主题一键切换（跟随系统记忆）' },
      { type: '变更', text: '页面结构分离：首页 = 产品介绍页，工作台承载功能；桌面端启动直进工作台' },
      { type: '新增', text: '用户 API Key 引导：首次使用三步完成模型接入（预设厂商一键填入 + 连接测试）' },
      { type: '优化', text: 'web 形态压力加固：匿名会话隔离、服务端 Key 每日配额' },
    ],
  },
  {
    version: 'v0.7.0',
    date: '2026-09-21',
    title: '证据接地 RAG + 动态追问',
    items: [
      { type: '新增', text: 'RAG 证据接地：每条差距结论 / 改写建议引用简历原文出处，可点击查看' },
      { type: '新增', text: '动态多轮追问：AI 判定信息不足时先向用户提问，补齐后再继续诊断' },
      { type: '优化', text: '证据检索升级 BM25-lite 加权，区分性关键词（如 Kubernetes）排名提升' },
      { type: '新增', text: '独立简历编辑器：表单 + 实时预览，导出与预览版式完全一致（真实分页）' },
      { type: '新增', text: '跨重启恢复：诊断中断 / 服务重启后重新打开任务可继续，不从头重跑' },
      { type: '新增', text: 'Word 导出历史记录，桌面版可再次定位已保存文件' },
    ],
  },
  {
    version: 'v0.6.0',
    date: '2026-09-18',
    title: '双形态交付 + 实时诊断',
    items: [
      { type: '变更', text: '移除招聘网络爬虫：JD 改为用户粘贴输入，岗位数据走官方数据接口' },
      { type: '新增', text: '网站版 / 桌面 exe 双形态同一套代码，界面按形态自动适配' },
      { type: '新增', text: '诊断实时进度 + 阶段日志（流式推送），不再黑盒等待' },
      { type: '新增', text: 'Word 模板扩充至 8 套，支持嵌入证件照' },
      { type: '优化', text: '启动性能优化（健康检查 52s → 2s），端口占用检测修复' },
    ],
  },
  {
    version: 'v0.5.0',
    date: '2026-09-11',
    title: '简历编辑器 + PDF 导出 + 实时日志',
    items: [
      { type: '新增', text: '简历在线编辑器（左侧表单 + 右侧实时预览）' },
      { type: '新增', text: '浏览器打印导出 PDF，所见即所得，无第三方依赖' },
      { type: '新增', text: 'Word 导出保留，与 PDF 双通道下载' },
      { type: '新增', text: 'Word 模板扩充至 8 套（经典/现代/简约/商务/学术/创意/两栏/紧凑）' },
      { type: '新增', text: '诊断进度页新增实时日志面板与阶段追踪' },
      { type: '新增', text: '独立 API 配置页（/settings），支持连接测试' },
      { type: '新增', text: '顶部导航新增 GitHub / Gitee 仓库入口' },
      { type: '优化', text: '编辑数据自动保存到 localStorage，刷新不丢失' },
      { type: '优化', text: '打印区域与编辑区域彻底分离，避免打印污染' },
      { type: '修复', text: '修复诊断进度页长时间空白无反馈的问题' },
    ],
  },
  {
    version: 'v0.4.0',
    date: '2026-09-10',
    title: '对答式优化 + 多模板 Word',
    items: [
      { type: '新增', text: '对答式优化：AI 追问 3-5 个关键信息，用户补充后精准生成' },
      { type: '新增', text: 'ClarifyModal 弹窗组件，支持必答/选答区分' },
      { type: '新增', text: '优化简历从主流程剥离为独立接口（/optimize/{task_id}）' },
      { type: '新增', text: 'Word 模板扩充至 3 套（经典/现代/简约）' },
      { type: '优化', text: '诊断流程从 5 Agent 优化到 4 Agent，缩短响应时间' },
      { type: '优化', text: '结果页改为 Tab 结构（诊断/优化/面试/模拟面试）' },
    ],
  },
  {
    version: 'v0.3.0',
    date: '2026-09-08',
    title: '历史记录 + 代码清理',
    items: [
      { type: '新增', text: '诊断历史记录持久化，服务重启后仍可查看' },
      { type: '新增', text: '全局错误处理 + 日志落盘（按天切分，错误单独存档）' },
      { type: '新增', text: 'CORS + 安全响应头（X-Frame-Options 等）' },
      { type: '新增', text: '一键启动脚本 start.bat' },
      { type: '变更', text: '数据库索引优化（jobs 表加 city+created / source+created 联合索引）' },
      { type: '优化', text: '删除异步版爬虫、旧 HTML 前端等冗余文件' },
    ],
  },
  {
    version: 'v0.2.0',
    date: '2026-09-05',
    title: '前端重构 + 视觉升级',
    items: [
      { type: '新增', text: 'Vue3 + Vite 前端重构（替代旧 HTML）' },
      { type: '新增', text: '新拟物派设计语言，统一视觉风格' },
      { type: '新增', text: 'ECharts 六维雷达图，可视化简历评分' },
      { type: '变更', text: '首页 / 控制台 / 结果页 / 历史记录 四页面结构' },
      { type: '修复', text: '修复 Vue 路由切换时的白屏问题' },
    ],
  },
  {
    version: 'v0.1.0',
    date: '2026-09-01',
    title: '项目初始化',
    items: [
      { type: '新增', text: '智联招聘实时爬虫（Playwright + 同步模式）' },
      { type: '新增', text: '混合匹配算法（关键词 + 语义向量 + 加权排序）' },
      { type: '新增', text: '4 Agent 诊断流程（解析/评分/差距/改写）' },
      { type: '新增', text: '用户自定义 LLM API（DeepSeek / 智谱 / OpenAI）' },
      { type: '新增', text: '简历上传（PDF/DOCX）+ Word 导出（3 模板）' },
    ],
  },
]

function tagClass(type) {
  const map = {
    '新增': 'bg-ok/10 text-ok',
    '变更': 'bg-accent/10 text-accent',
    '修复': 'bg-warn/10 text-warn',
    '删除': 'bg-bad/10 text-bad',
    '优化': 'bg-accent/10 text-accent',
  }
  return map[type] || 'bg-inset text-ink-sub'
}
</script>
