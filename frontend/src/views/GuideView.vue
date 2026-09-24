<template>
  <div class="max-w-4xl mx-auto px-6 md:px-10 py-8 md:py-10">

    <!-- 页头（全站统一规范：渐变标题 + 短横线） -->
    <div class="mb-10">
      <h1 class="text-xl font-semibold tracking-tight">
        <span class="bg-gradient-to-r from-ink to-accent bg-clip-text text-transparent">使用说明</span>
      </h1>
      <div class="h-0.5 w-14 rounded-full bg-gradient-to-r from-accent to-accent-hover/0 mt-1.5"></div>
      <p class="text-xs text-ink-faint mt-1.5">
        从配置到导出的完整指引 · 约 3 分钟读完
      </p>
    </div>

    <!-- 快速上手：三步大卡（说明书封面页） -->
    <div class="grid md:grid-cols-3 gap-5 mb-14">
      <div v-for="(q, i) in quick" :key="q.title"
        class="bg-panel rounded-2xl p-6 flex flex-col">
        <div class="text-4xl font-semibold font-mono text-accent/30 mb-4">
          {{ String(i + 1).padStart(2, '0') }}
        </div>
        <div class="text-sm font-semibold text-ink mb-2">{{ q.title }}</div>
        <p class="text-xs text-ink-sub leading-relaxed flex-1">{{ q.desc }}</p>
        <RouterLink :to="q.to"
          class="inline-flex items-center gap-1 mt-4 text-xs font-medium text-accent
            hover:gap-1.5 transition-all">
          {{ q.link }} <span>→</span>
        </RouterLink>
      </div>
    </div>

    <!-- 章节正文（说明书目录式排版） -->
    <section v-for="ch in chapters" :key="ch.no" class="mb-12">
      <div class="flex items-center gap-3 mb-5">
        <span class="w-8 h-8 shrink-0 rounded-lg flex items-center justify-center
          bg-gradient-to-br from-accent to-accent-hover text-white text-xs font-bold font-mono
          border-2 border-ink/80 shadow-[2px_2px_0_0] shadow-ink/50">
          {{ ch.no }}
        </span>
        <h2 class="text-base font-semibold text-ink whitespace-nowrap">{{ ch.title }}</h2>
        <div class="flex-1 border-t-2 border-line"></div>
      </div>

      <ol class="space-y-3">
        <li v-for="(s, si) in ch.steps" :key="si" class="flex gap-3 items-start">
          <span class="w-5 h-5 shrink-0 mt-0.5 rounded-md bg-inset text-accent text-[10px]
            font-mono font-semibold flex items-center justify-center">
            {{ si + 1 }}
          </span>
          <p class="text-sm leading-relaxed text-ink-sub">
            <span class="font-medium text-ink">{{ s.t }}</span>
            <span v-if="s.d">　{{ s.d }}</span>
            <RouterLink v-if="s.to" :to="s.to"
              class="ml-1.5 text-xs text-accent hover:underline whitespace-nowrap">前往 →</RouterLink>
          </p>
        </li>
      </ol>
    </section>

    <!-- 常见问题（可折叠） -->
    <section class="mb-12">
      <div class="flex items-center gap-3 mb-5">
        <span class="w-8 h-8 shrink-0 rounded-lg flex items-center justify-center
          bg-gradient-to-br from-accent to-accent-hover text-white text-xs font-bold font-mono
          border-2 border-ink/80 shadow-[2px_2px_0_0] shadow-ink/50">?</span>
        <h2 class="text-base font-semibold text-ink whitespace-nowrap">常见问题</h2>
        <div class="flex-1 border-t-2 border-line"></div>
      </div>

      <div class="space-y-2.5">
        <details v-for="f in faqs" :key="f.q" class="group bg-panel rounded-xl
          border border-line px-5 py-4 open:border-accent/40 transition-colors">
          <summary class="flex items-center gap-2.5 cursor-pointer text-sm font-medium text-ink
            list-none [&::-webkit-details-marker]:hidden">
            <span class="w-5 h-5 shrink-0 rounded bg-accent/10 text-accent text-[10px] font-bold
              flex items-center justify-center">Q</span>
            <span class="flex-1">{{ f.q }}</span>
            <span class="text-ink-faint group-open:rotate-90 transition-transform">›</span>
          </summary>
          <p class="text-sm text-ink-sub leading-relaxed mt-3 pl-7.5">{{ f.a }}</p>
        </details>
      </div>
    </section>

    <!-- 底部 CTA -->
    <div class="bg-panel rounded-2xl px-8 py-8 text-center">
      <div class="text-sm font-semibold text-ink mb-1.5">准备好开始了吗？</div>
      <p class="text-xs text-ink-sub mb-5">配置好 AI 服务后，一次完整诊断约 3 分钟</p>
      <RouterLink to="/app/analyze"
        class="inline-block px-6 py-2.5 text-xs font-medium rounded-lg bg-accent text-white
          hover:bg-accent-hover active:scale-[0.98] transition-all">
        发起第一次诊断
      </RouterLink>
    </div>

  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import { useAppMode } from '../composables/useAppMode'

const { isWeb, meta, quotaEnabled } = useAppMode()

/* ---- 快速上手三步 ---- */
const quick = [
  {
    title: '配置 AI 服务',
    desc: '在设置页选择大模型厂商，粘贴 API Key。也支持 Ollama 本地模型，无需联网 Key。',
    link: '去设置',
    to: '/settings',
  },
  {
    title: '发起诊断',
    desc: '上传简历或用编辑器创建，粘贴意向岗位 JD，点击开始，进度逐节点实时展示。',
    link: '去诊断',
    to: '/app/analyze',
  },
  {
    title: '查看并导出报告',
    desc: '六维评分、差距清单、STAR 改写建议，改完可导出 Word 或打印成 PDF。',
    link: '看历史',
    to: '/app/history',
  },
]

/* ---- 章节 ---- */
const chapters = [
  {
    no: '01',
    title: '准备工作：配置 AI 服务',
    steps: [
      { t: '打开「设置」页', d: '选择厂商（智谱 / DeepSeek / 通义千问 / Kimi / 豆包 / OpenAI 等），接口地址自动填入。', to: '/settings' },
      { t: '粘贴 API Key', d: '到厂商开放平台控制台创建 Key，粘贴后保存。Key 只保存在本机，不上传任何服务器。' },
      { t: '没有 Key？', d: '可选 Ollama 本地模型（免费，需本机安装 Ollama 并拉取模型）；Web 模式也可使用站点预置 Key。' },
      {
        t: quotaEnabled.value ? `每日免费额度 ${meta.value.daily_limit} 次` : '免费额度',
        d: quotaEnabled.value
          ? '使用站点预置 Key 每日可免费诊断，在侧栏可查看剩余额度；填自己的 Key 则不限次数。'
          : '桌面端使用自己的 Key，额度由厂商控制；侧栏可查看配额说明。',
      },
    ],
  },
  {
    no: '02',
    title: '管理简历',
    steps: [
      { t: '在线创建', d: '「创建简历」编辑器逐段填写基本信息、经历、技能，自动保存进简历库。', to: '/app/editor' },
      { t: '上传文件', d: '「简历库」支持上传 PDF / DOCX，多份简历并存、可批量删除、可在线预览原文件。', to: '/app/resumes' },
      { t: '改写与导出', d: '诊断报告中的改写建议可一键生成优化简历，10 套模板任选，导出可投递的 Word 文件。' },
    ],
  },
  {
    no: '03',
    title: '岗位与发起诊断',
    steps: [
      { t: '粘贴岗位 JD', d: '发起诊断页直接粘贴 JD 全文，内容越全，匹配分析越准。', to: '/app/analyze' },
      { t: '还没想好岗位？', d: '展开岗位面板「一键获取」：AI 根据简历生成匹配岗位（推荐），或使用示例数据体验流程。' },
      { t: '收藏心仪岗位', d: '岗位卡右上角 ♡ 一键收藏（保留 JD 快照，上限 50 条），之后可一键「用此岗位诊断 / 面试」。' },
      { t: '开始诊断', d: '点击开始后多智能体流水线并行运转，进度流式推送；AI 追问补充信息时按提示回答即可。' },
    ],
  },
  {
    no: '04',
    title: '读懂诊断报告',
    steps: [
      { t: '总分与六维雷达', d: '匹配度、量化、结构等六个维度逐一打分，雷达图直观呈现强弱项。' },
      { t: '差距清单', d: '逐条列出与岗位要求的差距；完成后点条目左侧 △ 变 ✓ 标记「已解决」，刷新不丢。' },
      { t: 'STAR 改写建议', d: '把平淡的经历描述改写成有情境、有行动、有量化的表达，可直接抄进简历。' },
      { t: '导出', d: '报告页「导出 Word」一键存档；浏览器打印可选择「另存为 PDF」。' },
    ],
  },
  {
    no: '05',
    title: '模拟面试',
    steps: [
      { t: '两个入口', d: '诊断报告页的「模拟面试」Tab，或侧栏「模拟面试」独立发起，均可基于简历 + JD 出题。', to: '/app/interview' },
      { t: '多轮自由对话', d: '像真实面试一样追问与作答；本题答完点「收尾进入下一题」，也可「强制收尾」跳过。' },
      { t: '量化评分', d: '结束后自动生成总评：总分 + 每题评分 + 能力雷达（满分 10 分制）。' },
      { t: '面试报告', d: '总评区「导出面试报告」存为 Word；历史会话可随时恢复继续练或删除。' },
    ],
  },
  {
    no: '06',
    title: '工作台总览',
    steps: [
      { t: '一屏掌握', d: '总览页汇总简历、诊断、面试数据，诊断与面试分数趋势一目了然。', to: '/app/dashboard' },
      { t: '继续进行', d: '未完成的诊断 / 面试任务在「继续进行」区一键回到现场，中途关页面也不丢进度。' },
      { t: '主题切换', d: '侧栏底部太阳 / 月亮按钮切换亮暗主题，偏好自动记住。' },
    ],
  },
]

/* ---- FAQ ---- */
const faqs = [
  {
    q: 'API Key 在哪里获取？',
    a: '各大厂商开放平台控制台均可创建（智谱 / DeepSeek / 通义 / Kimi / 豆包 / OpenAI 等），设置页选择厂商后会附指引。完全离线可用 Ollama 本地模型，不需要 Key。',
  },
  {
    q: '我的简历数据安全吗？',
    a: '桌面版所有数据（简历、记录、导出文件）只存本机 data 目录；Web 版按会话隔离，简历与记录仅本会话可见。API Key 只保存在本机，不会上传。',
  },
  {
    q: '免费额度用完了怎么办？',
    a: '在设置页填入自己的 API Key 即不限次数；或切换 Ollama 本地模型完全免费。',
  },
  {
    q: '诊断中途关掉页面，进度会丢吗？',
    a: '不会。回到「总览 → 继续进行」或「诊断历史」，点击未完成任务即可继续；AI 追问的答题现场也会保留。',
  },
  {
    q: '支持哪些简历格式？',
    a: '上传支持 PDF / DOCX；也可以用内置编辑器直接创建，编辑器支持导出 Word。',
  },
  {
    q: '模拟面试的评分标准是什么？',
    a: 'AI 面试官按题目逐一打分（0-10 分），并结合全部回答给出总分与能力雷达；评分维度与岗位 JD 要求挂钩。',
  },
]
</script>
