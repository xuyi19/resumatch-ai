<template>
  <div class="min-h-screen py-12">
    <div class="max-w-6xl mx-auto px-6">

      <!-- ============ 对比视图（A3） ============ -->
      <template v-if="mode === 'compare'">
        <div class="flex items-center justify-between mb-8">
          <div>
            <h1 class="text-3xl font-semibold text-ink mb-2">Before / After 对比</h1>
            <p class="text-sm text-ink-sub">两次诊断雷达叠加 · 分数与差距变化 · 建议对照</p>
          </div>
          <button @click="exitCompare"
            class="px-4 py-2 text-sm font-medium rounded-lg
              bg-panel border border-line text-ink-sub
              hover:border-line-strong hover:text-ink transition-colors">
            ← 返回列表
          </button>
        </div>

        <LoadingBlock v-if="compareLoading" text="加载对比数据..." />

        <template v-else-if="beforeRec && afterRec">
          <!-- 概览卡：综合分 / 差距条数变化 -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div class="bg-panel border border-line rounded-lg p-5">
              <div class="text-xs text-ink-sub uppercase tracking-wider mb-2">综合分变化</div>
              <div class="flex items-baseline gap-3 font-mono">
                <span class="text-xl text-ink-faint">{{ beforeScore ?? '—' }}</span>
                <span class="text-ink-faint">→</span>
                <span class="text-3xl font-semibold text-accent">{{ afterScore ?? '—' }}</span>
                <span v-if="scoreDelta !== null" class="text-sm font-semibold"
                      :class="scoreDelta >= 0 ? 'text-ok' : 'text-bad'">
                  {{ scoreDelta >= 0 ? '+' : '' }}{{ scoreDelta }}
                </span>
              </div>
              <div class="text-xs text-ink-faint mt-2">
                {{ beforeRec.keyword || '未命名岗位' }} · {{ formatTime(beforeRec.created_at) }}
                <br />
                {{ afterRec.keyword || '未命名岗位' }} · {{ formatTime(afterRec.created_at) }}
              </div>
            </div>
            <div class="bg-panel border border-line rounded-lg p-5">
              <div class="text-xs text-ink-sub uppercase tracking-wider mb-2">差距条数变化</div>
              <div class="flex items-baseline gap-3 font-mono">
                <span class="text-xl text-ink-faint">{{ beforeGaps.length }}</span>
                <span class="text-ink-faint">→</span>
                <span class="text-3xl font-semibold"
                      :class="gapDelta <= 0 ? 'text-ok' : 'text-warn'">{{ afterGaps.length }}</span>
                <span class="text-sm font-semibold"
                      :class="gapDelta <= 0 ? 'text-ok' : 'text-warn'">
                  {{ gapDelta > 0 ? '+' : '' }}{{ gapDelta }}
                </span>
              </div>
              <div class="text-xs text-ink-faint mt-2">负数（减少）通常意味着改进</div>
            </div>
            <div class="bg-panel border border-line rounded-lg p-5">
              <div class="text-xs text-ink-sub uppercase tracking-wider mb-2">简历 / 记录</div>
              <div class="text-sm text-ink mb-1 truncate">
                {{ beforeRec.resume_name || afterRec.resume_name || '未命名简历' }}
              </div>
              <div class="text-xs text-ink-faint font-mono">
                {{ beforeRec.task_id }} → {{ afterRec.task_id }}
              </div>
            </div>
          </div>

          <!-- 雷达叠加 -->
          <div class="bg-panel border border-line rounded-lg p-6 mb-6">
            <h2 class="text-base font-semibold text-ink mb-4">六维雷达叠加</h2>
            <div style="height: 400px">
              <RadarChart :series="compareRadarSeries" />
            </div>
          </div>

          <!-- F4 差距对照：Before 中用户标记「已解决」的条目（报告页打勾，localStorage）绿色高亮 -->
          <div class="bg-panel border border-line rounded-lg p-6 mb-6">
            <div class="flex items-center gap-2 mb-4">
              <h2 class="text-base font-semibold text-ink">差距对照</h2>
              <span v-if="beforeDoneCount" class="text-xs px-2 py-0.5 rounded-md bg-ok/10 text-ok">
                Before 已解决 {{ beforeDoneCount }}/{{ beforeGaps.length }}
              </span>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <div class="text-xs font-medium text-ink-sub uppercase tracking-wider mb-3">
                  Before（{{ beforeGaps.length }} 条）
                </div>
                <ul class="space-y-2.5">
                  <li v-for="(g, i) in beforeGaps" :key="'bg' + i"
                      class="text-sm p-3 rounded-lg border"
                      :class="isBeforeGapDone(g)
                        ? 'bg-ok/5 border-ok/40 text-ink-faint'
                        : 'bg-inset border-line text-ink-sub'">
                    <span v-if="isBeforeGapDone(g)"
                      class="inline-flex items-center gap-1 text-xs text-ok font-semibold mr-1.5">
                      ✓ 已解决</span>
                    <span :class="isBeforeGapDone(g) ? 'line-through' : ''">{{ g.description }}</span>
                  </li>
                  <li v-if="!beforeGaps.length" class="text-sm text-ink-faint">无差距</li>
                </ul>
              </div>
              <div>
                <div class="text-xs font-medium text-accent uppercase tracking-wider mb-3">
                  After（{{ afterGaps.length }} 条）
                </div>
                <ul class="space-y-2.5">
                  <li v-for="(g, i) in afterGaps" :key="'ag' + i"
                      class="text-sm text-ink-sub p-3 rounded-lg bg-inset border border-line">
                    <span class="text-xs font-semibold text-warn mr-1.5">{{ g.severity || '△' }}</span>{{ g.description }}
                  </li>
                  <li v-if="!afterGaps.length" class="text-sm text-ink-faint">无差距（清零 🎉）</li>
                </ul>
              </div>
            </div>
          </div>

          <!-- 建议对照 -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="bg-panel border border-line rounded-lg p-5">
              <div class="text-xs font-medium text-ink-sub uppercase tracking-wider mb-3">
                Before · 改写建议（{{ beforeSuggestions.length }} 条）
              </div>
              <ul class="space-y-3">
                <li v-for="(s, i) in beforeSuggestions" :key="'b' + i"
                    class="text-sm text-ink-sub p-3 rounded-lg bg-inset border border-line">
                  <div class="text-xs text-ink-faint mb-1">{{ s.target }}</div>
                  {{ s.rewritten }}
                </li>
                <li v-if="!beforeSuggestions.length" class="text-sm text-ink-faint">无建议</li>
              </ul>
            </div>
            <div class="bg-panel border border-line rounded-lg p-5">
              <div class="text-xs font-medium text-accent uppercase tracking-wider mb-3">
                After · 改写建议（{{ afterSuggestions.length }} 条）
              </div>
              <ul class="space-y-3">
                <li v-for="(s, i) in afterSuggestions" :key="'a' + i"
                    class="text-sm text-ink p-3 rounded-lg bg-accent/5 border-l-2 border-accent">
                  <div class="text-xs text-ink-faint mb-1">{{ s.target }}</div>
                  {{ s.rewritten }}
                </li>
                <li v-if="!afterSuggestions.length" class="text-sm text-ink-faint">无建议</li>
              </ul>
            </div>
          </div>
        </template>

        <EmptyState v-else-if="!compareLoading"
          title="无法对比" desc="所选记录缺少完整结果">
        </EmptyState>
      </template>

      <!-- ============ 列表视图（D4） ============ -->
      <template v-else>
        <!-- 标题 -->
        <div class="mb-6">
          <h1 class="text-3xl font-semibold text-ink mb-2">历史记录</h1>
          <p class="text-sm text-ink-sub">查看过往的诊断任务，点击查看可恢复完整结果</p>
        </div>

        <div class="bg-panel border border-line rounded-lg p-6">

          <!-- 工具行：状态筛选 + 排序 + 搜索 + 对比 -->
          <div class="flex items-center gap-2 flex-wrap mb-4">
            <div class="inline-flex gap-1 p-1 rounded-lg bg-inset border border-line">
              <button v-for="f in statusFilters" :key="f.key"
                @click="statusFilter = f.key"
                class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors"
                :class="statusFilter === f.key
                  ? 'bg-accent/10 text-accent'
                  : 'text-ink-sub hover:text-ink'">
                {{ f.label }}
              </button>
            </div>

            <button @click="newestFirst = !newestFirst"
              class="px-3 py-1.5 text-xs font-medium rounded-lg bg-inset border border-line
                text-ink-sub hover:text-ink transition-colors"
              :title="newestFirst ? '当前：最新在前' : '当前：最早在前'">
              {{ newestFirst ? '↓ 最新在前' : '↑ 最早在前' }}
            </button>

            <input v-model="searchText" placeholder="搜索岗位 / 简历名..."
              class="px-3 py-1.5 text-xs rounded-lg bg-inset border border-line
                focus:outline-none focus:border-accent transition-colors w-48" />

            <span class="flex-1" />

            <span class="text-xs text-ink-faint">
              已选 {{ selected.length }}/2
            </span>
            <button @click="enterCompare" :disabled="selected.length !== 2"
              class="px-4 py-1.5 text-xs font-medium rounded-lg transition-colors
                disabled:opacity-40 disabled:cursor-not-allowed"
              :class="selected.length === 2
                ? 'bg-accent text-white hover:bg-accent-hover'
                : 'bg-inset border border-line text-ink-faint'">
              对比
            </button>
          </div>

          <!-- 加载中 -->
          <LoadingBlock v-if="loading" text="加载中..." />

          <!-- 空状态 -->
          <EmptyState v-else-if="!records.length"
            title="还没有诊断记录"
            desc="上传简历，开始你的第一次诊断">
            <RouterLink to="/app/analyze"
              class="inline-block px-6 py-2.5 text-sm font-medium rounded-lg
                bg-accent text-white hover:bg-accent-hover transition-colors">
              新建诊断
            </RouterLink>
          </EmptyState>

          <!-- 筛选后为空 -->
          <EmptyState v-else-if="!filteredRecords.length"
            title="没有匹配的记录" desc="试试调整筛选条件或关键词">
          </EmptyState>

          <!-- 紧凑行列表 -->
          <div v-else class="space-y-2">
            <div v-for="r in filteredRecords" :key="r.task_id"
              class="flex items-center gap-3 px-3 py-2.5 rounded-lg
                bg-inset border border-line
                hover:border-line-strong transition-colors">

              <!-- 勾选（仅成功记录可参与对比） -->
              <input v-if="r.status === 'success'" type="checkbox"
                :checked="selected.includes(r.task_id)"
                @change="toggleSelect(r.task_id)"
                class="w-3.5 h-3.5 accent-[rgb(var(--c-accent))] shrink-0 cursor-pointer" />
              <span v-else class="w-3.5 shrink-0" />

              <!-- 状态点 -->
              <div :class="statusDot(r.status)" class="w-2.5 h-2.5 rounded-full shrink-0"></div>

              <!-- 信息（一行式） -->
              <button @click="viewDetail(r.task_id)"
                class="flex-1 min-w-0 text-left flex items-center gap-3">
                <span class="font-medium text-ink text-sm truncate max-w-[220px]">
                  {{ r.keyword || '未命名岗位' }}
                </span>
                <span class="text-xs text-ink-faint truncate hidden sm:inline">
                  {{ r.resume_name || '未命名简历' }}
                </span>
                <!-- 综合分 -->
                <span v-if="r.score != null"
                  class="text-sm font-semibold text-accent font-mono shrink-0">
                  {{ r.score }}
                </span>
              </button>

              <!-- 重诊标识 -->
              <span v-if="r.parent_task_id"
                title="由「用当前简历重新诊断」发起"
                class="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent shrink-0">
                重诊
              </span>

              <!-- 时间 -->
              <span class="text-xs text-ink-faint font-mono shrink-0 hidden md:inline">
                {{ formatTime(r.created_at) }}
              </span>

              <!-- 状态标签 -->
              <span :class="statusClass(r.status)"
                class="px-2 py-0.5 rounded text-[11px] font-medium shrink-0">
                {{ statusText(r.status) }}
              </span>

              <!-- 操作 -->
              <div class="flex items-center gap-1 shrink-0">
                <button @click="viewDetail(r.task_id)"
                  class="px-2.5 py-1 text-xs font-medium rounded-lg
                    text-accent hover:bg-accent/10 transition-colors">
                  查看
                </button>
                <button @click="confirmDelete(r.task_id)"
                  class="px-2.5 py-1 text-xs font-medium rounded-lg
                    text-ink-faint hover:text-bad hover:bg-bad/10 transition-colors">
                  删除
                </button>
              </div>
            </div>
          </div>

        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import api from '../api'
import EmptyState from '../components/EmptyState.vue'
import LoadingBlock from '../components/LoadingBlock.vue'
import RadarChart from '../components/RadarChart.vue'

const router = useRouter()
const records = ref([])
const loading = ref(false)

/* ---- D4：筛选 / 排序 / 搜索 ---- */
const statusFilter = ref('all')
const newestFirst = ref(true)
const searchText = ref('')

const statusFilters = [
  { key: 'all', label: '全部' },
  { key: 'success', label: '成功' },
  { key: 'failed', label: '失败' },
  { key: 'incomplete', label: '进行中/其他' },
]

const filteredRecords = computed(() => {
  const kw = searchText.value.trim().toLowerCase()
  let list = records.value.filter(r => {
    if (statusFilter.value === 'success' && r.status !== 'success') return false
    if (statusFilter.value === 'failed' && r.status !== 'failed') return false
    if (statusFilter.value === 'incomplete' &&
        ['success', 'failed'].includes(r.status)) return false
    if (kw) {
      const hay = `${r.keyword || ''} ${r.resume_name || ''}`.toLowerCase()
      if (!hay.includes(kw)) return false
    }
    return true
  })
  list = [...list].sort((a, b) => {
    const ta = a.created_at || '', tb = b.created_at || ''
    return newestFirst.value ? tb.localeCompare(ta) : ta.localeCompare(tb)
  })
  return list
})

/* ---- A3：勾选两条对比 ---- */
const selected = ref([])
const mode = ref('list')
const compareLoading = ref(false)
const beforeRec = ref(null)
const afterRec = ref(null)

function toggleSelect(taskId) {
  const idx = selected.value.indexOf(taskId)
  if (idx >= 0) selected.value.splice(idx, 1)
  else if (selected.value.length < 2) selected.value.push(taskId)
  else {
    // 已满 2 条：替换最早勾选的（队列语义）
    selected.value.shift()
    selected.value.push(taskId)
  }
}

async function enterCompare() {
  if (selected.value.length !== 2) return
  mode.value = 'compare'
  compareLoading.value = true
  try {
    const [a, b] = await Promise.all([
      api.getHistoryDetail(selected.value[0]),
      api.getHistoryDetail(selected.value[1]),
    ])
    // 按 created_at 排出 before / after
    const recs = [a.data, b.data].sort((x, y) =>
      (x.created_at || '').localeCompare(y.created_at || ''))
    beforeRec.value = recs[0]
    afterRec.value = recs[1]
  } catch (e) {
    Message.error('加载对比数据失败：' + e.message)
    mode.value = 'list'
  } finally {
    compareLoading.value = false
  }
}

function exitCompare() {
  mode.value = 'list'
  beforeRec.value = null
  afterRec.value = null
}

const beforeScores = computed(() =>
  beforeRec.value?.result?.diagnosis?.scores || {})
const afterScores = computed(() =>
  afterRec.value?.result?.diagnosis?.scores || {})

const beforeScore = computed(() => beforeScores.value.overall ?? null)
const afterScore = computed(() => afterScores.value.overall ?? null)
const scoreDelta = computed(() =>
  beforeScore.value != null && afterScore.value != null
    ? afterScore.value - beforeScore.value : null)

const beforeGaps = computed(() => beforeRec.value?.result?.diagnosis?.gaps || [])
const afterGaps = computed(() => afterRec.value?.result?.diagnosis?.gaps || [])

// ---- F4：对比视图联动报告页的差距标记（gap_done_{task_id}，key 与 ResultView 一致） ----
function gapKey(g) {
  return `${g.dimension || ''}|${g.description || ''}`
}
const beforeDoneKeys = computed(() => {
  try {
    return new Set(JSON.parse(localStorage.getItem(`gap_done_${beforeRec.value?.task_id}`) || '[]'))
  } catch (e) { return new Set() }
})
const beforeDoneCount = computed(() =>
  beforeGaps.value.filter(g => beforeDoneKeys.value.has(gapKey(g))).length)
function isBeforeGapDone(g) { return beforeDoneKeys.value.has(gapKey(g)) }
const gapDelta = computed(() => afterGaps.value.length - beforeGaps.value.length)

const beforeSuggestions = computed(() =>
  beforeRec.value?.result?.diagnosis?.suggestions || [])
const afterSuggestions = computed(() =>
  afterRec.value?.result?.diagnosis?.suggestions || [])

const DIM_KEYS = ['completeness', 'quantification', 'star_structure',
  'skill_match', 'achievement', 'readability']

const compareRadarSeries = computed(() => [
  { name: `Before ${beforeScore.value ?? ''}`, values: DIM_KEYS.map(k => beforeScores.value[k]?.score || 0), color: '--c-ink-faint' },
  { name: `After ${afterScore.value ?? ''}`, values: DIM_KEYS.map(k => afterScores.value[k]?.score || 0), color: '--c-accent' },
])

async function loadHistory() {
  loading.value = true
  try {
    const res = await api.getHistory({ limit: 50 })
    records.value = res.data.items || []
    // 清掉已不存在的勾选
    const ids = new Set(records.value.map(r => r.task_id))
    selected.value = selected.value.filter(id => ids.has(id))
  } catch (e) {
    Message.error('加载失败：' + e.message)
  } finally {
    loading.value = false
  }
}

function viewDetail(taskId) {
  router.push(`/app/result/${taskId}`)
}

function confirmDelete(taskId) {
  Modal.warning({
    title: '确认删除',
    content: '删除后不可恢复，确定继续？',
    hideCancel: false,
    okText: '删除',
    cancelText: '取消',
    onOk: async () => {
      try {
        await api.deleteHistory(taskId)
        Message.success('已删除')
        loadHistory()
      } catch (e) {
        Message.error('删除失败：' + e.message)
      }
    },
  })
}

function statusDot(status) {
  return {
    success: 'bg-ok',
    failed: 'bg-bad',
    running: 'bg-accent',
    pending: 'bg-ink-faint',
  }[status] || 'bg-ink-faint'
}

function statusClass(status) {
  return {
    success: 'bg-ok/10 text-ok',
    failed: 'bg-bad/10 text-bad',
    running: 'bg-accent/10 text-accent',
    pending: 'bg-inset text-ink-sub',
  }[status] || 'bg-inset text-ink-sub'
}

function statusText(status) {
  return {
    success: '成功',
    failed: '失败',
    running: '进行中',
    pending: '排队',
  }[status] || status
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

onMounted(loadHistory)
</script>
