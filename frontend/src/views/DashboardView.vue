<template>
  <div class="max-w-6xl mx-auto px-6 md:px-10 py-8 md:py-10">
    <!-- 页头 -->
    <div class="flex items-end justify-between mb-8">
      <div>
        <h1 class="text-xl font-semibold tracking-tight">
          <span class="bg-gradient-to-r from-ink to-accent bg-clip-text text-transparent">求职总览</span>
        </h1>
        <div class="h-0.5 w-14 rounded-full bg-gradient-to-r from-accent to-accent-hover/0 mt-1.5"></div>
        <p class="text-xs text-ink-faint mt-1.5">
          {{ today }} · 简历、诊断与模拟面试进展一屏掌握
        </p>
      </div>
    </div>

    <LoadingBlock v-if="loading" text="统计加载中…" />

    <!-- 加载失败：显式可见可重试（不静默吞错） -->
    <div v-else-if="loadError"
      class="bg-warn/10 border border-warn/40 rounded-2xl px-5 py-4 flex items-center justify-between">
      <span class="text-sm text-warn">统计数据加载失败（服务可能未就绪）</span>
      <button @click="loadAll" class="text-sm font-medium text-warn hover:text-ink transition-colors">
        重试
      </button>
    </div>

    <template v-else>
      <!-- M41 Bento 网格总览：Hero 大卡 + 统计小卡（大小不一的便当盒布局） -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-5 mb-8">

        <!-- Hero：问候 + 最近成绩 + 快捷入口 -->
        <div class="col-span-2 row-span-2 rounded-2xl p-6 md:p-7 relative overflow-hidden
          bg-gradient-to-br from-accent to-accent-hover text-white
          border-2 border-ink/80 shadow-[5px_5px_0_0] shadow-ink/25
          flex flex-col justify-between min-h-[200px]">
          <div class="absolute -right-10 -top-12 w-44 h-44 rounded-full bg-white/10"></div>
          <div class="absolute -right-1 top-14 w-24 h-24 rounded-full bg-white/10"></div>
          <div class="relative">
            <div class="text-sm opacity-90">{{ greeting }}，祝求职顺利</div>
            <div class="text-xs opacity-60 mt-1">{{ today }}</div>
          </div>
          <div class="relative">
            <div class="text-xs opacity-75 mb-1">🏆 最近成绩</div>
            <div class="text-4xl md:text-5xl font-semibold font-mono tracking-tight leading-none">
              {{ heroScore.value }}
              <span class="text-sm font-sans font-normal opacity-75">{{ heroScore.unit }}</span>
            </div>
            <div class="text-xs opacity-75 mt-2">{{ heroScore.sub }}</div>
            <div class="flex flex-wrap gap-2.5 mt-5">
              <button @click="$router.push('/app/analyze')" class="px-4 py-2 text-xs font-medium rounded-2xl
                bg-white text-accent hover:bg-white/90 transition-colors shadow-sm">
                + 发起诊断
              </button>
              <button @click="$router.push('/app/interview')" class="px-4 py-2 text-xs font-medium rounded-2xl
                bg-white/15 text-white hover:bg-white/25 border border-white/30 transition-colors">
                🎤 模拟面试
              </button>
            </div>
          </div>
        </div>

        <!-- 统计小卡 -->
        <button v-for="card in cards" :key="card.label" @click="card.to && $router.push(card.to)"
          class="bg-panel border border-line rounded-2xl p-5 text-left hover:border-accent/50
            hover:-translate-y-0.5 hover:shadow-lg transition-all duration-200 group">
          <div class="text-xs text-ink-faint mb-2 flex items-center gap-1.5">
            <span class="text-sm">{{ card.icon }}</span>{{ card.label }}
          </div>
          <div class="flex items-baseline gap-1.5">
            <span class="text-3xl font-semibold font-mono text-ink">{{ card.value }}</span>
            <span v-if="card.unit" class="text-xs text-ink-sub">{{ card.unit }}</span>
          </div>
          <div v-if="card.sub" class="text-xs text-ink-faint mt-1.5">{{ card.sub }}</div>
        </button>
      </div>

      <!-- 空态引导 -->
      <div v-if="!stats.diagnosis_total && !stats.resume_count"
        class="bg-panel border border-line rounded-2xl p-12 text-center mb-8">
        <div class="text-4xl mb-4">🧭</div>
        <div class="text-lg font-semibold text-ink mb-2">从一份简历开始</div>
        <p class="text-sm text-ink-sub max-w-md mx-auto">
          上传或创建简历、粘贴意向岗位 JD，AI 将给出六维评分、差距分析与改写建议；
          之后可在岗位市场锁定目标、用 AI 面试官实战演练。
        </p>
        <div class="flex flex-wrap items-center justify-center gap-3 mt-5">
          <button @click="$router.push('/app/analyze')"
            class="bg-accent text-white px-5 py-2 text-xs font-medium rounded-lg transition-all">
            开始第一份诊断
          </button>
          <button @click="showGuide = true"
            class="px-5 py-2 text-xs font-medium rounded-lg border border-accent/50 text-accent
              hover:bg-accent/10 transition-colors">
            🔄 重看新手引导
          </button>
        </div>
      </div>

      <!-- 继续进行 -->
      <div v-if="stats.ongoing_diagnoses.length || stats.ongoing_interviews.length" class="mb-8">
        <h2 class="text-sm font-semibold text-ink mb-3">⏳ 继续进行</h2>
        <div class="grid md:grid-cols-2 gap-3">
          <button v-for="d in stats.ongoing_diagnoses" :key="d.task_id"
            @click="$router.push(`/app/result/${d.task_id}`)"
            :class="stats.ongoing_diagnoses.length + stats.ongoing_interviews.length === 1 ? 'md:col-span-2' : ''"
            class="flex items-center gap-3 bg-panel border border-warn/40 rounded-2xl px-5 py-3.5
              text-left hover:border-warn transition-colors">
            <span class="text-lg">🩺</span>
            <span class="flex-1 min-w-0">
              <span class="block text-sm text-ink truncate">
                {{ d.keyword || d.resume_name || '未命名诊断' }}
              </span>
              <span class="block text-xs text-ink-faint">{{ statusLabel(d.status) }} · 点击查看进度</span>
            </span>
            <span class="text-xs text-warn shrink-0">{{ statusLabel(d.status) }}</span>
          </button>
          <button v-for="iv in stats.ongoing_interviews" :key="iv.task_id"
            @click="$router.push({ path: '/app/interview', query: { task_id: iv.task_id } })"
            :class="stats.ongoing_diagnoses.length + stats.ongoing_interviews.length === 1 ? 'md:col-span-2' : ''"
            class="flex items-center gap-3 bg-panel border border-accent/40 rounded-2xl px-5 py-3.5
              text-left hover:border-accent transition-colors">
            <span class="text-lg">🎤</span>
            <span class="flex-1 min-w-0">
              <span class="block text-sm text-ink">模拟面试进行中</span>
              <span class="block text-xs text-ink-faint">
                已完成 {{ iv.answered }}/{{ iv.total || '?' }} 题 · 点击继续
              </span>
            </span>
            <span class="text-xs text-accent shrink-0">进行中</span>
          </button>
        </div>
      </div>

      <!-- M38 分数趋势双列 -->
      <div v-if="diagTrendPoints.length || ivTrendPoints.length"
        class="grid md:grid-cols-2 gap-5 mb-8">
        <div class="bg-panel border border-line rounded-2xl p-5">
          <h2 class="text-sm font-semibold text-ink mb-4">📈 诊断分数趋势</h2>
          <div class="h-48">
            <LineChart :points="diagTrendPoints" :max="100" />
          </div>
        </div>
        <div class="bg-panel border border-line rounded-2xl p-5">
          <h2 class="text-sm font-semibold text-ink mb-4">🎤 面试分数趋势</h2>
          <div class="h-48">
            <LineChart :points="ivTrendPoints" :max="10" />
          </div>
        </div>
      </div>

      <!-- M56.4 投递漏斗 -->
      <div v-if="stats.saved_jobs_count" class="bg-panel border border-line rounded-2xl p-5 mb-8">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold text-ink">📮 投递漏斗</h2>
          <button @click="$router.push('/app/jobs')"
            class="text-xs text-ink-faint hover:text-accent transition-colors">管理岗位 →</button>
        </div>
        <div class="grid grid-cols-5 gap-2">
          <div v-for="step in funnelSteps" :key="step.key" class="text-center">
            <div class="text-2xl font-semibold font-mono" :class="step.color">{{ step.count }}</div>
            <div class="text-xs text-ink-faint mt-1">{{ step.label }}</div>
            <div class="h-1.5 rounded-full bg-inset mt-2 overflow-hidden">
              <div class="h-full rounded-full transition-all duration-500"
                :class="step.bar" :style="{ width: funnelPct(step.count) }" />
            </div>
          </div>
        </div>
      </div>

      <!-- M60 求职跟进：applied 逾期提醒 + 面试日程（状态流转后自动消失，无 dismiss） -->
      <div v-if="followups.stale_applies.length || followups.upcoming_interviews.length"
        class="bg-panel border border-line rounded-2xl p-5 mb-8">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold text-ink">📌 求职跟进</h2>
          <span class="text-xs text-ink-faint">投递 {{ followups.days }} 天未流转提醒</span>
        </div>
        <div class="grid md:grid-cols-2 gap-5">
          <!-- 该跟进 -->
          <div>
            <div class="text-xs font-medium text-ink-sub mb-2">该跟进（{{ followups.days }} 天未流转）</div>
            <div v-if="!followups.stale_applies.length" class="text-xs text-ink-faint py-3">
              暂无待跟进 ✓
            </div>
            <div v-else class="space-y-2">
              <div v-for="s in followups.stale_applies" :key="s.id"
                class="flex items-center gap-3 px-3 py-2.5 rounded-2xl border border-warn/30 bg-warn/5">
                <span class="flex-1 min-w-0">
                  <span class="block text-sm text-ink truncate">{{ s.title }}<span v-if="s.company" class="text-ink-faint"> · {{ s.company }}</span></span>
                  <span class="block text-xs text-ink-faint">已投递 {{ s.days }} 天无流转<span v-if="s.city"> · {{ s.city }}</span></span>
                </span>
                <button @click="goFollowUp(s.id)"
                  class="text-xs font-medium text-warn hover:text-ink shrink-0 transition-colors">
                  去跟进 →
                </button>
              </div>
            </div>
          </div>
          <!-- 面试日程 -->
          <div>
            <div class="text-xs font-medium text-ink-sub mb-2">面试日程</div>
            <div v-if="!followups.upcoming_interviews.length" class="text-xs text-ink-faint py-3">
              暂无面试安排
            </div>
            <div v-else class="space-y-2">
              <div v-for="iv in followups.upcoming_interviews" :key="iv.id"
                class="flex items-center gap-3 px-3 py-2.5 rounded-2xl border border-line bg-inset/50">
                <span class="flex-1 min-w-0">
                  <span class="block text-sm text-ink truncate">{{ iv.title }}<span v-if="iv.company" class="text-ink-faint"> · {{ iv.company }}</span></span>
                  <span class="block text-xs text-ink-faint">{{ fmtInterviewDate(iv.next_interview_at) }}</span>
                </span>
                <span class="text-xs shrink-0" :class="interviewDue(iv).cls">{{ interviewDue(iv).text }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- M53 活跃热力图 -->
      <div v-if="hasActivity" class="bg-panel border border-line rounded-2xl p-5 mb-8">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold text-ink">🔥 活跃热力图</h2>
          <span class="text-xs text-ink-faint">近 90 天 · 诊断 / 面试 / 投递</span>
        </div>
        <HeatmapChart :days="stats.activity_heatmap || []" />
      </div>

      <!-- M63 求职周报（接口失败整卡隐藏；接口成功即使全零也显示兜底文案） -->
      <div v-if="weekly" class="bg-panel border border-line rounded-2xl p-5 mb-8">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h2 class="text-sm font-semibold text-ink">📋 求职周报</h2>
          <div class="flex items-center gap-2">
            <button @click="shiftWeek(1)" :disabled="weekOffset >= 8"
              class="text-xs px-2 py-1 rounded-lg border border-line text-ink-sub
                hover:border-accent/60 transition-colors
                disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:border-line">
              ‹ {{ weekOffset === 0 ? '上周' : '更早' }}
            </button>
            <span class="text-xs text-ink-faint">{{ weekly.week_start }} ~ {{ weekly.week_end }}</span>
            <button @click="shiftWeek(-1)" :disabled="weekOffset <= 0"
              class="text-xs px-2 py-1 rounded-lg border border-line text-ink-sub
                hover:border-accent/60 transition-colors
                disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:border-line">
              ›
            </button>
          </div>
        </div>
        <!-- 六指标 + 活跃天数：手机 3 列 / sm 6 列 -->
        <div class="grid grid-cols-3 sm:grid-cols-6 gap-2 mt-4">
          <div v-for="cell in weeklyCells" :key="cell.key"
            class="bg-inset/50 rounded-xl px-2 py-2.5 text-center">
            <div class="text-xs text-ink-faint">{{ cell.icon }} {{ cell.label }}</div>
            <div class="text-2xl font-semibold font-mono text-ink mt-0.5">{{ cell.value }}</div>
            <div class="text-[11px] mt-0.5" :class="deltaCls(cell)">{{ deltaText(cell) }}</div>
          </div>
        </div>
        <ul class="mt-4 space-y-1.5">
          <li v-for="(h, i) in weekly.highlights || []" :key="i" class="text-sm text-ink-sub">{{ h }}</li>
        </ul>
        <div class="flex flex-wrap items-center gap-4 mt-4">
          <button @click="copyWeekly" class="text-xs font-medium text-accent hover:underline transition-colors">
            📋 一键复制
          </button>
          <button @click="exportWeekly" :disabled="exportingWeekly"
            class="text-xs font-medium text-accent hover:underline transition-colors disabled:opacity-50">
            📄 导出 Word
          </button>
          <span class="text-xs text-ink-faint">投递 / 面试 / 刷题 / 诊断 / Offer 自动汇总</span>
        </div>
      </div>

      <!-- 最近记录双列 -->
      <div class="grid md:grid-cols-2 gap-5">
        <!-- 最近诊断 -->
        <div class="bg-panel border border-line rounded-2xl p-5">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-sm font-semibold text-ink">🩺 最近诊断</h2>
            <button @click="$router.push('/app/history')"
              class="text-xs text-ink-faint hover:text-accent transition-colors">全部 →</button>
          </div>
          <div v-if="!recentDiags.length" class="text-xs text-ink-faint py-4 text-center">
            还没有诊断记录
          </div>
          <div v-else class="space-y-2">
            <button v-for="h in recentDiags" :key="h.task_id"
              @click="$router.push(`/app/result/${h.task_id}`)"
              class="w-full flex items-center gap-3 px-3 py-2.5 rounded-2xl hover:bg-inset
                transition-colors text-left">
              <span class="flex-1 min-w-0">
                <span class="block text-sm text-ink truncate">{{ h.keyword || h.resume_name || '未命名' }}</span>
                <span class="block text-xs text-ink-faint">{{ fmtTime(h.created_at) }}</span>
              </span>
              <span v-if="h.score != null"
                class="text-sm font-mono font-semibold shrink-0"
                :class="diagScoreCls(h.score)">{{ h.score }}</span>
              <span v-else class="text-xs text-ink-faint shrink-0">{{ statusLabel(h.status) }}</span>
            </button>
          </div>
        </div>

        <!-- 最近面试 -->
        <div class="bg-panel border border-line rounded-2xl p-5">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-sm font-semibold text-ink">🎤 最近面试</h2>
            <button @click="$router.push('/app/interview')"
              class="text-xs text-ink-faint hover:text-accent transition-colors">全部 →</button>
          </div>
          <div v-if="!recentInterviews.length" class="text-xs text-ink-faint py-4 text-center">
            还没有面试记录 · 去发起一场模拟面试
          </div>
          <div v-else class="space-y-2">
            <button v-for="s in recentInterviews" :key="s.task_id"
              @click="$router.push({ path: '/app/interview', query: { task_id: s.task_id } })"
              class="w-full flex items-center gap-3 px-3 py-2.5 rounded-2xl hover:bg-inset
                transition-colors text-left">
              <span class="flex-1 min-w-0">
                <span class="block text-sm text-ink truncate">
                  {{ s.first_question || s.source }}
                </span>
                <span class="block text-xs text-ink-faint">{{ fmtTime(s.updated_at) }}</span>
              </span>
              <span v-if="s.overall_score != null"
                class="text-sm font-mono font-semibold shrink-0"
                :class="ivScoreCls(s.overall_score)">{{ s.overall_score }}/10</span>
              <span v-else class="text-xs text-ink-faint shrink-0">
                {{ s.answered }}/{{ s.total }} 题
              </span>
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- M55 首次启动引导（fixed 弹层，置于模板根部） -->
    <OnboardingGuide v-if="showGuide" @done="showGuide = false" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import api from '../api'
import { useAppMode } from '../composables/useAppMode'
import LoadingBlock from '../components/LoadingBlock.vue'
import LineChart from '../components/LineChart.vue'
import HeatmapChart from '../components/HeatmapChart.vue'
import OnboardingGuide from '../components/OnboardingGuide.vue'

const route = useRoute()
const router = useRouter()
// M63 周报导出需要区分桌面态（服务端直写）与网页态（blob 下载）
const { isDesktop } = useAppMode()

const loading = ref(true)
const loadError = ref(false)
// M55 首次启动引导弹层显隐
const showGuide = ref(false)
const stats = ref({
  resume_count: 0, diagnosis_total: 0, diagnosis_avg_score: null,
  latest_diagnosis: null, ongoing_diagnoses: [],
  interview_total: 0, interview_finished: 0, interview_avg_score: null,
  latest_interview_score: null, ongoing_interviews: [],
  saved_jobs_count: 0,
  apply_funnel: {},  // M56.4 投递漏斗（stats 缺字段时回退空对象）
  activity_heatmap: [],  // M53 活跃热力图（stats 缺字段时回退空数组）
})
const recentDiags = ref([])
const recentInterviews = ref([])
// M60 求职跟进：逾期 applied + 面试日程（接口失败回退空态，整卡隐藏不阻断总览）
const followups = ref({ days: 7, stale_applies: [], upcoming_interviews: [] })

const today = new Date().toLocaleDateString('zh-CN', {
  year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
})

// M41 Hero 问候语按时段变化
const greeting = computed(() => {
  const h = new Date().getHours()
  return h < 6 ? '夜深了' : h < 12 ? '早上好' : h < 18 ? '下午好' : '晚上好'
})

// Hero 最近成绩：优先面试评分，其次诊断综合分
const heroScore = computed(() => {
  const s = stats.value
  if (s.latest_interview_score != null) {
    return { value: s.latest_interview_score, unit: '/ 10', sub: '最近一次模拟面试评分' }
  }
  if (s.latest_diagnosis?.score != null) {
    return { value: s.latest_diagnosis.score, unit: '/ 100', sub: '最近一次诊断综合分' }
  }
  return { value: '—', unit: '', sub: '完成一次诊断或面试后在这里看到成绩' }
})

// M38 趋势数据（stats 缺字段时回退空数组，兼容旧响应）
const diagTrendPoints = computed(() =>
  (stats.value.diagnosis_trend || []).map(t => ({ x: t.date, y: t.score })))
const ivTrendPoints = computed(() =>
  (stats.value.interview_trend || []).map(t => ({ x: t.date, y: t.score })))

// M56.4 投递漏斗五档（数量 + 进度条配色）
const FUNNEL_STEPS = [
  { key: 'wish', label: '想投', color: 'text-ink-sub', bar: 'bg-ink-faint/50' },
  { key: 'applied', label: '已投递', color: 'text-accent', bar: 'bg-accent' },
  { key: 'interviewing', label: '面试中', color: 'text-warn', bar: 'bg-warn' },
  { key: 'offer', label: 'Offer', color: 'text-ok', bar: 'bg-ok' },
  { key: 'closed', label: '已结束', color: 'text-ink-faint', bar: 'bg-ink-faint/40' },
]
const funnelSteps = computed(() =>
  FUNNEL_STEPS.map((f) => ({ ...f, count: stats.value.apply_funnel?.[f.key] ?? 0 })))
function funnelPct(n) {
  const max = Math.max(...funnelSteps.value.map((s) => s.count), 1)
  return `${Math.max(Math.round((n / max) * 100), n ? 8 : 0)}%`
}

// M53 有任意活跃天才显示热力图卡（新用户避免空格子占版面）
const hasActivity = computed(() =>
  (stats.value.activity_heatmap || []).some((d) => d.count > 0))

const cards = computed(() => [
  { label: '简历库', icon: '📄', value: stats.value.resume_count, unit: '份', to: '/app/resumes' },
  {
    label: '诊断', icon: '🩺', value: stats.value.diagnosis_total, unit: '次', to: '/app/history',
    sub: stats.value.diagnosis_avg_score != null ? `平均 ${stats.value.diagnosis_avg_score} 分` : '',
  },
  {
    label: '模拟面试', icon: '🎤', value: stats.value.interview_total, unit: '场', to: '/app/interview',
    sub: stats.value.interview_avg_score != null ? `均分 ${stats.value.interview_avg_score}/10` : '',
  },
  {
    // M51 收藏并入岗位库：统计卡改读后端 saved_jobs_count，直达岗位库
    label: '岗位库', icon: '⭐', value: stats.value.saved_jobs_count ?? 0, unit: '个', to: '/app/jobs',
    sub: stats.value.saved_jobs_count ? '管理 / 匹配 / 投递追踪' : '收藏或添加岗位统一管理',
  },
])

function statusLabel(s) {
  return { pending: '排队中', running: '进行中', waiting_clarify: '待补充回答', failed: '失败', success: '已完成' }[s] || s
}
function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
    + ' ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
function diagScoreCls(s) {
  return s >= 80 ? 'text-ok' : s >= 60 ? 'text-accent' : 'text-warn'
}
function ivScoreCls(s) {
  return s >= 8 ? 'text-ok' : s >= 6 ? 'text-accent' : 'text-warn'
}

/* ---- M60 求职跟进 ---- */
function goFollowUp(id) {
  // 本地 optimistic 移除：跳转岗位库后本卡不再显示，防重复点击感
  followups.value.stale_applies = followups.value.stale_applies.filter((s) => s.id !== id)
  router.push(`/app/jobs?focus=${id}`)
}
function fmtInterviewDate(iso) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  return `${d.getMonth() + 1}月${d.getDate()}日 ${hm}`
}
function interviewDue(item) {
  if (item.days_left < 0) return { text: `逾期 ${-item.days_left} 天`, cls: 'text-warn' }
  if (item.days_left === 0) return { text: '今天', cls: 'text-accent' }
  return { text: `还有 ${item.days_left} 天`, cls: 'text-ink-faint' }
}

/* ---- M63 求职周报 ---- */
// 周报聚合数据：null = 未加载 / 接口失败（整卡隐藏）；接口成功即使全零也显示
const weekly = ref(null)
const weekOffset = ref(0)  // 0 = 本周，1 = 上周…最多 8
const weeklyLoading = ref(false)
const exportingWeekly = ref(false)

const WEEKLY_CELLS = [
  { key: 'applications', icon: '📮', label: '投递' },
  { key: 'interviews', icon: '🎤', label: '面试' },
  { key: 'quizzes', icon: '🧠', label: '刷题' },
  { key: 'diagnoses', icon: '📄', label: '诊断' },
  { key: 'jobs_added', icon: '⭐', label: '入库' },
  { key: 'offers', icon: '🎉', label: 'Offer' },
]

const weeklyCells = computed(() => {
  if (!weekly.value) return []
  const m = weekly.value.metrics || {}
  const cells = WEEKLY_CELLS.map((c) => ({ ...c, ...(m[c.key] || {}) }))
  cells.push({ key: 'active_days', icon: '🗓', label: '活跃天', ...(weekly.value.active_days || {}) })
  return cells
})

// 环变小字：prev=0 且本周有值 → 「新增」；+3 绿 / -2 红 / 0 灰「持平」
function deltaText(c) {
  if (!c.prev && c.value > 0) return '新增'
  if (c.delta === 0) return '持平'
  return c.delta > 0 ? `+${c.delta}` : `${c.delta}`
}
function deltaCls(c) {
  if (c.delta > 0) return 'text-ok'
  if (c.delta < 0) return 'text-warn'
  return 'text-ink-faint'
}

async function loadWeekly() {
  weeklyLoading.value = true
  try {
    const res = await api.getWeeklyReport(weekOffset.value)
    weekly.value = res.data
  } catch (e) {
    console.warn('[dashboard] 周报加载失败', e)
    weekly.value = null
  } finally {
    weeklyLoading.value = false
  }
}

async function shiftWeek(d) {
  const next = weekOffset.value + d
  if (next < 0 || next > 8) return
  weekOffset.value = next
  await loadWeekly()
}

// 一键复制纯文本：标题行 + 亮点 + 指标表
const weeklyText = computed(() => {
  if (!weekly.value) return ''
  const lines = [
    `知岗 · 求职周报（${weekly.value.week_start} ~ ${weekly.value.week_end}）`,
    ...(weekly.value.highlights || []),
    '',
  ]
  for (const c of weeklyCells.value) {
    lines.push(`${c.icon} ${c.label}\t本周 ${c.value}\t上周 ${c.prev}\t${deltaText(c)}`)
  }
  return lines.join('\n')
})

async function copyWeekly() {
  try {
    await navigator.clipboard.writeText(weeklyText.value)
    Message.success('周报已复制到剪贴板')
  } catch {
    Message.error('复制失败，请手动选择文本复制')
  }
}

async function exportWeekly() {
  exportingWeekly.value = true
  try {
    // 桌面形态（M71）：统一保存到「导出位置」设置的目录「周报」子目录
    if (isDesktop.value) {
      const res = await api.exportWeeklyReportToPath({
        week_offset: weekOffset.value, save_path: 'auto',
      })
      Message.success(`周报已保存到：${res.data?.saved_to || res.data?.save_path || ''}`)
      return
    }
    const res = await api.exportWeeklyReport({ week_offset: weekOffset.value })
    const url = URL.createObjectURL(new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }))
    const a = document.createElement('a')
    a.href = url
    a.download = `求职周报_${weekly.value.week_start}_${weekly.value.week_end}.docx`
    a.click()
    URL.revokeObjectURL(url)
    Message.success('周报已导出（见浏览器下载目录）')
  } catch (e) {
    Message.error(e.response?.data?.detail || '导出失败')
  } finally {
    exportingWeekly.value = false
  }
}

async function loadAll() {
  loading.value = true
  loadError.value = false
  try {
    // 统计 + 最近诊断 + 最近面试 + 跟进聚合 四路并发（跟进失败不阻断总览）
    const [statsRes, histRes, ivRes, fuRes] = await Promise.all([
      api.getStats(),
      api.getHistory({ limit: 5 }),
      api.interviewSessions(),
      api.getFollowups().catch(() => null),
    ])
    stats.value = statsRes.data
    recentDiags.value = histRes.data.items || []
    recentInterviews.value = (ivRes.data.items || []).slice(0, 5)
    if (fuRes?.data) followups.value = fuRes.data
  } catch (e) {
    console.warn('[dashboard] 统计加载失败', e)
    loadError.value = true
  } finally {
    loading.value = false
  }
}
onMounted(() => {
  loadAll()
  loadWeekly()  // M63 周报独立加载：失败只隐藏周报卡，不阻断总览
  // M55 首次启动引导：无标记自动弹；?onboarding=1 强制重看（用后即清，防刷新重触发）
  let done = true
  try {
    done = !!localStorage.getItem('onboarding_done')
  } catch (e) { /* 存储不可用时视为已读过，不强行打断 */ }
  if (route.query.onboarding === '1' || !done) showGuide.value = true
  if (route.query.onboarding) router.replace({ query: { ...route.query, onboarding: undefined } })
})
</script>
