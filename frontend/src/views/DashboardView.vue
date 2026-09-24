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
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'
import LoadingBlock from '../components/LoadingBlock.vue'
import LineChart from '../components/LineChart.vue'
import { loadFavorites } from '../utils/favorites'

const loading = ref(true)
const loadError = ref(false)
// M41 收藏岗位数（localStorage，进入页面即读）
const favCount = ref(loadFavorites().length)
const stats = ref({
  resume_count: 0, diagnosis_total: 0, diagnosis_avg_score: null,
  latest_diagnosis: null, ongoing_diagnoses: [],
  interview_total: 0, interview_finished: 0, interview_avg_score: null,
  latest_interview_score: null, ongoing_interviews: [],
})
const recentDiags = ref([])
const recentInterviews = ref([])

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
    label: '收藏岗位', icon: '⭐', value: favCount.value, unit: '个', to: '/app/analyze',
    sub: favCount.value ? '在岗位市场查看与管理' : '去岗位市场收藏心仪岗位',
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

async function loadAll() {
  loading.value = true
  loadError.value = false
  try {
    // 统计 + 最近诊断 + 最近面试三路并发
    const [statsRes, histRes, ivRes] = await Promise.all([
      api.getStats(),
      api.getHistory({ limit: 5 }),
      api.interviewSessions(),
    ])
    stats.value = statsRes.data
    recentDiags.value = histRes.data.items || []
    recentInterviews.value = (ivRes.data.items || []).slice(0, 5)
  } catch (e) {
    console.warn('[dashboard] 统计加载失败', e)
    loadError.value = true
  } finally {
    loading.value = false
  }
}
onMounted(loadAll)
</script>
