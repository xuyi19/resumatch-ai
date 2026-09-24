<template>
  <div>
    <!-- 页头 -->
    <div class="flex items-end justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold text-ink">求职总览</h1>
        <p class="text-xs text-ink-faint mt-1">
          {{ today }} · 简历、诊断与模拟面试进展一屏掌握
        </p>
      </div>
      <button @click="$router.push('/app/analyze')"
        class="px-4 py-2 text-sm font-medium rounded-lg bg-accent text-white
          hover:bg-accent-hover transition-colors">
        + 发起诊断
      </button>
    </div>

    <LoadingBlock v-if="loading" text="统计加载中…" />

    <!-- 加载失败：显式可见可重试（不静默吞错） -->
    <div v-else-if="loadError"
      class="bg-warn/10 border border-warn/40 rounded-lg px-5 py-4 flex items-center justify-between">
      <span class="text-sm text-warn">统计数据加载失败（服务可能未就绪）</span>
      <button @click="loadAll" class="text-sm font-medium text-warn hover:text-ink transition-colors">
        重试
      </button>
    </div>

    <template v-else>
      <!-- 统计卡 -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <button v-for="card in cards" :key="card.label" @click="card.to && $router.push(card.to)"
          class="bg-panel border border-line rounded-lg p-5 text-left hover:border-accent/50
            transition-colors group">
          <div class="text-xs text-ink-faint mb-2">{{ card.label }}</div>
          <div class="flex items-baseline gap-1.5">
            <span class="text-3xl font-semibold font-mono" :class="card.accent ? 'text-accent' : 'text-ink'">
              {{ card.value }}
            </span>
            <span v-if="card.unit" class="text-xs text-ink-sub">{{ card.unit }}</span>
          </div>
          <div v-if="card.sub" class="text-xs text-ink-faint mt-1.5">{{ card.sub }}</div>
        </button>
      </div>

      <!-- 空态引导 -->
      <div v-if="!stats.diagnosis_total && !stats.resume_count"
        class="bg-panel border border-line rounded-lg p-12 text-center mb-6">
        <div class="text-4xl mb-4">🧭</div>
        <div class="text-lg font-semibold text-ink mb-2">从一份简历开始</div>
        <p class="text-sm text-ink-sub max-w-md mx-auto">
          上传或创建简历、粘贴意向岗位 JD，AI 将给出六维评分、差距分析与改写建议；
          之后可在岗位市场锁定目标、用 AI 面试官实战演练。
        </p>
      </div>

      <!-- 继续进行 -->
      <div v-if="stats.ongoing_diagnoses.length || stats.ongoing_interviews.length" class="mb-6">
        <h2 class="text-sm font-semibold text-ink mb-3">⏳ 继续进行</h2>
        <div class="grid md:grid-cols-2 gap-3">
          <button v-for="d in stats.ongoing_diagnoses" :key="d.task_id"
            @click="$router.push(`/app/result/${d.task_id}`)"
            class="flex items-center gap-3 bg-panel border border-warn/40 rounded-lg px-4 py-3
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
            class="flex items-center gap-3 bg-panel border border-accent/40 rounded-lg px-4 py-3
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

      <!-- 最近记录双列 -->
      <div class="grid md:grid-cols-2 gap-4">
        <!-- 最近诊断 -->
        <div class="bg-panel border border-line rounded-lg p-5">
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
              class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-inset
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
        <div class="bg-panel border border-line rounded-lg p-5">
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
              class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-inset
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

const loading = ref(true)
const loadError = ref(false)
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

const cards = computed(() => [
  { label: '简历库', value: stats.value.resume_count, unit: '份', to: '/app/resumes' },
  {
    label: '诊断', value: stats.value.diagnosis_total, unit: '次', to: '/app/history',
    sub: stats.value.diagnosis_avg_score != null ? `平均 ${stats.value.diagnosis_avg_score} 分` : '',
  },
  {
    label: '模拟面试', value: stats.value.interview_total, unit: '场', to: '/app/interview',
    sub: stats.value.interview_avg_score != null ? `均分 ${stats.value.interview_avg_score}/10` : '',
  },
  {
    label: '最近成绩', accent: true,
    value: stats.value.latest_interview_score != null
      ? `${stats.value.latest_interview_score}/10`
      : (stats.value.latest_diagnosis?.score != null ? stats.value.latest_diagnosis.score : '—'),
    sub: stats.value.latest_interview_score != null
      ? '最近一次面试评分'
      : (stats.value.latest_diagnosis?.score != null ? '最近一次诊断综合分' : '暂无成绩'),
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
