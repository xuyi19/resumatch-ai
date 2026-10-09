<template>
  <div class="max-w-6xl mx-auto px-6 md:px-10 py-8 md:py-10">

    <!-- 页头（全站统一规范：渐变标题 + 短横线） -->
    <div class="flex items-end justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold tracking-tight">
          <span class="bg-gradient-to-r from-ink to-accent bg-clip-text text-transparent">⚖️ Offer 比较</span>
        </h1>
        <div class="h-0.5 w-14 rounded-full bg-gradient-to-r from-accent to-accent-hover/0 mt-1.5"></div>
        <p class="text-xs text-ink-faint mt-1.5">
          手握多个 Offer？加权量化 + 雷达对比 + 一句话结论——纯本地计算不外传
        </p>
      </div>
      <div class="flex items-center gap-2">
        <span v-if="offers.length && selectedIds.length < 2" class="text-[11px] text-ink-faint hidden sm:inline">
          勾选至少 2 个
        </span>
        <button @click="runCompare" :disabled="selectedIds.length < 2 || comparing"
          :title="selectedIds.length < 2 ? '先在卡片左上角勾选 2~6 个 Offer' : '对比所选 Offer'"
          class="px-4 py-2 text-xs font-medium rounded-lg border border-accent/50 text-accent
            hover:bg-accent/10 active:scale-[0.98] transition-all disabled:opacity-40 disabled:cursor-not-allowed">
          {{ comparing ? '计算中…' : `⚖️ 对比所选 (${selectedIds.length}/6)` }}
        </button>
        <button @click="openForm()"
          class="px-4 py-2 text-xs font-medium rounded-lg bg-accent text-white
            hover:bg-accent-hover active:scale-[0.98] transition-all">
          ＋ 录入 Offer
        </button>
      </div>
    </div>

    <!-- 录入 / 编辑弹窗（保存后不收起，连续录入） -->
    <Teleport to="body">
      <div v-if="formOpen" @click.self="closeForm"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/40">
        <div class="bg-panel border-2 border-ink/80 shadow-[3px_3px_0_0] shadow-ink/20 rounded-2xl w-full max-w-2xl max-h-[88vh]
          overflow-y-auto p-5 md:p-6">
          <div class="flex items-center justify-between gap-3 mb-4">
            <div class="text-sm font-semibold">
              {{ editingId != null ? '✏️ 编辑 Offer' : '＋ 录入 Offer' }}
              <span class="ml-2 text-xs font-normal text-ink-faint">带 * 必填，其余可留空</span>
            </div>
            <button @click="closeForm"
              class="text-lg leading-none text-ink-sub hover:text-ink shrink-0">×</button>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <input v-model="form.company" maxlength="60" placeholder="公司名称 *"
              class="px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
                focus:border-accent placeholder:text-ink-faint transition-colors" />
            <input v-model="form.title" maxlength="60" placeholder="岗位名称 *"
              class="px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
                focus:border-accent placeholder:text-ink-faint transition-colors" />
            <input v-model="form.city" maxlength="20" placeholder="城市（如：杭州）"
              class="px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
                focus:border-accent placeholder:text-ink-faint transition-colors" />
          </div>

          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <label class="block">
              <span class="text-[11px] text-ink-faint">月薪（K 元）*</span>
              <input v-model.number="form.monthly_salary" type="number" min="1" max="500" placeholder="如：20"
                class="w-full mt-0.5 px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
                  focus:border-accent placeholder:text-ink-faint transition-colors" />
            </label>
            <label class="block">
              <span class="text-[11px] text-ink-faint">年薪含几个月（12~18）</span>
              <input v-model.number="form.salary_months" type="number" min="12" max="18"
                class="w-full mt-0.5 px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
                  focus:border-accent transition-colors" />
            </label>
            <label class="block">
              <span class="text-[11px] text-ink-faint">单程通勤（分钟，0~240）</span>
              <input v-model.number="form.commute_minutes" type="number" min="0" max="240"
                class="w-full mt-0.5 px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
                  focus:border-accent transition-colors" />
            </label>
          </div>

          <!-- 五险/发展/稳定：五档按钮（1=最低 5=顶格） -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <div v-for="rate in RATE_FIELDS" :key="rate.key">
              <span class="text-[11px] text-ink-faint">{{ rate.label }}（1~5）</span>
              <div class="flex items-center gap-1 mt-0.5">
                <button v-for="n in 5" :key="n" @click="form[rate.key] = n"
                  class="flex-1 py-1.5 text-xs rounded-md border transition-all active:scale-[0.95]"
                  :class="form[rate.key] >= n
                    ? 'bg-accent border-accent text-white'
                    : 'bg-inset border-line text-ink-sub hover:border-accent/50'">{{ n }}</button>
              </div>
            </div>
          </div>

          <textarea v-model="form.notes" rows="2" maxlength="500"
            placeholder="备注（如：leader 面谈感受、加班传闻、期权细节…）"
            class="w-full px-3.5 py-2.5 text-sm bg-inset rounded-lg border border-line resize-y
              leading-relaxed focus:outline-none focus:border-accent
              placeholder:text-ink-faint transition-colors"></textarea>

          <div class="flex items-center gap-3 mt-3">
            <button @click="saveForm" :disabled="formSaving"
              class="px-5 py-2 text-xs font-medium rounded-lg bg-accent text-white
                hover:bg-accent-hover active:scale-[0.98] transition-all disabled:opacity-50">
              {{ formSaving ? '保存中…' : editingId != null ? '保存修改' : '保存（可连续录入）' }}
            </button>
            <button @click="closeForm"
              class="px-4 py-2 text-xs text-ink-sub hover:text-ink transition-colors">取消</button>
          </div>
        </div>
      </div>
    </Teleport>

    <LoadingBlock v-if="loading" text="Offer 列表加载中…" />
    <div v-else-if="loadError" class="bg-warn/10 border border-warn/40 rounded-2xl px-5 py-4
      flex items-center justify-between">
      <span class="text-sm text-warn">Offer 列表加载失败</span>
      <button @click="loadAll" class="text-sm font-medium text-warn hover:text-ink transition-colors">重试</button>
    </div>

    <template v-else>
      <!-- 空态 -->
      <div v-if="!offers.length" class="bg-panel rounded-2xl p-12 text-center">
        <div class="text-4xl mb-4">⚖️</div>
        <div class="text-lg font-semibold mb-2">还没有录入 Offer</div>
        <p class="text-sm text-ink-sub max-w-md mx-auto">
          手握多个 Offer 时把它们录进来，按薪资、通勤、五险、发展、稳定五个维度加权打分，
          雷达图直观对比 + 一句话结论帮你拍板——纯本地计算，数据不外传。
        </p>
        <button @click="openForm()"
          class="px-5 py-2 text-xs font-medium rounded-lg bg-accent text-white
            hover:bg-accent-hover transition-colors mt-5">＋ 录入第一个 Offer</button>
      </div>

      <template v-else>
        <!-- 对比结果区（出现在卡片网格上方） -->
        <div v-if="compareResult" class="bg-panel border-2 border-ink/80 shadow-[3px_3px_0_0] shadow-ink/20 rounded-2xl p-5 mb-6">
          <div class="flex items-center justify-between gap-3 mb-3">
            <div class="text-sm font-semibold">⚖️ 对比结果</div>
            <button @click="compareResult = null"
              class="text-xs text-ink-sub hover:text-ink transition-colors">收起对比</button>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
            <!-- 多系列雷达图 -->
            <div class="h-72 md:border-r border-line/60 md:pr-5">
              <RadarChart :series="radarSeries" :dims="RADAR_DIMS" :max="100" />
            </div>

            <!-- 排名列表 -->
            <div class="flex flex-col justify-center">
              <div v-for="it in compareResult.items" :key="it.id"
                class="flex items-center gap-3 py-2.5" :class="it.rank > 1 ? 'border-t border-line/60' : ''">
                <span class="w-6 h-6 rounded-md text-xs font-bold flex items-center justify-center shrink-0"
                  :class="it.rank === 1 ? 'bg-accent text-white' : 'bg-inset text-ink-sub'">{{ it.rank }}</span>
                <div class="flex-1 min-w-0">
                  <div class="text-sm font-semibold text-ink truncate" :title="`${it.company} · ${it.title}`">
                    {{ it.company }} · {{ it.title }}
                  </div>
                  <div class="text-xs text-ink-faint mt-0.5">
                    年薪包 {{ fmtWan(it.annual) }} 万<template v-if="it.city"> · {{ it.city }}</template>
                  </div>
                </div>
                <div class="text-xl font-bold tabular-nums shrink-0"
                  :class="it.rank === 1 ? 'text-accent' : 'text-ink'">{{ it.total }}</div>
              </div>
            </div>
          </div>

          <!-- 一句话结论（确定性模板，非 AI） -->
          <div class="mt-4 bg-inset border border-line rounded-xl px-4 py-3">
            <div class="text-[11px] text-ink-faint mb-1">⚖️ 一句话结论（本地模板生成，非 AI）</div>
            <p class="text-sm text-ink-sub leading-relaxed">{{ compareResult.conclusion }}</p>
          </div>

          <div class="text-[11px] text-ink-faint mt-2.5">{{ weightLegend }}</div>
        </div>

        <!-- 卡片网格 -->
        <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div v-for="o in offers" :key="o.id"
            class="bg-panel border-2 border-ink/80 shadow-[3px_3px_0_0] shadow-ink/15 rounded-lg p-5 flex flex-col
              hover:-translate-y-0.5 hover:shadow-[4px_4px_0_0] hover:shadow-ink/25 transition-all"
            :class="isSelected(o.id) ? 'ring-2 ring-accent/60 border-accent/60' : ''">
            <!-- 头部：勾选框 + 公司·岗位 + 更新时间 -->
            <div class="flex items-start gap-2 mb-2">
              <button @click="toggleSelect(o)" :title="isSelected(o.id) ? '取消勾选' : '勾选加入对比'"
                class="w-5 h-5 mt-0.5 rounded border flex items-center justify-center text-[11px] shrink-0 transition-all"
                :class="isSelected(o.id)
                  ? 'bg-accent border-accent text-white'
                  : 'border-line-strong text-transparent hover:border-accent'">✓</button>
              <div class="min-w-0 flex-1">
                <div class="text-sm font-semibold text-ink truncate" :title="`${o.company} · ${o.title}`">
                  {{ o.company }} · {{ o.title }}
                </div>
                <div v-if="o.city" class="text-xs text-ink-faint mt-0.5 truncate">📍 {{ o.city }}</div>
              </div>
              <span class="text-[10px] font-mono text-ink-faint shrink-0 mt-0.5">{{ fmtTime(o.updated_at) }}</span>
            </div>

            <!-- 年薪包大数字 -->
            <div class="flex items-baseline gap-2 mb-2.5">
              <span class="text-2xl font-bold text-accent tabular-nums">{{ fmtWan(o.annual) }}</span>
              <span class="text-xs text-ink-faint">万年薪包（月薪 {{ o.monthly_salary }}K × {{ o.salary_months }} 个月）</span>
            </div>

            <!-- 通勤/五险/发展/稳定徽标 -->
            <div class="flex items-center gap-1.5 flex-wrap mb-2.5">
              <span v-for="b in badges(o)" :key="b.label"
                class="px-1.5 py-0.5 rounded text-[11px] bg-inset text-ink-sub">{{ b.label }} {{ b.value }}</span>
            </div>

            <!-- 备注（两行截断） -->
            <p v-if="o.notes" class="text-xs text-ink-faint leading-relaxed line-clamp-2 mb-4 flex-1"
              :title="o.notes">{{ o.notes }}</p>
            <p v-else class="text-xs text-ink-faint/60 italic mb-4 flex-1">暂无备注</p>

            <!-- 操作区 -->
            <div class="mt-auto flex items-center gap-2.5 pt-3 border-t border-line/60">
              <button @click="openEdit(o)" title="编辑 Offer"
                class="text-xs text-ink-sub hover:text-accent transition-colors shrink-0">✏️ 编辑</button>
              <span class="flex-1" />
              <button @click="remove(o)" title="删除 Offer"
                class="text-xs text-ink-sub hover:text-bad transition-colors shrink-0">🗑 删除</button>
            </div>
          </div>
        </div>
      </template>
    </template>

  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import api from '../api'
import LoadingBlock from '../components/LoadingBlock.vue'
import RadarChart from '../components/RadarChart.vue'

/* ---- 常量：五档自评字段 / 雷达维度 / 默认权重（与后端 DEFAULT_WEIGHTS 一致） ---- */
const RATE_FIELDS = [
  { key: 'insurance', label: '五险一金' },
  { key: 'development', label: '发展前景' },
  { key: 'stability', label: '稳定性' },
]
const SCORE_KEYS = ['salary', 'commute', 'insurance', 'development', 'stability']
const RADAR_DIMS = ['薪资', '通勤', '五险', '发展', '稳定']
const WEIGHT_LABELS = { salary: '薪资', commute: '通勤', insurance: '五险', development: '发展', stability: '稳定' }
const DEFAULT_WEIGHTS = { salary: 40, commute: 15, insurance: 15, development: 20, stability: 10 }
// 雷达多系列配色（CSS 变量名 / rgb 串，RadarChart.colorOf 两种都支持）
const SERIES_COLORS = ['--c-accent', '--c-ok', '--c-warn', '--c-bad', '--c-ink-sub', '147 51 234']

const loading = ref(true)
const loadError = ref(false)
const offers = ref([])
const selectedIds = ref([])
const comparing = ref(false)
const compareResult = ref(null)

const isSelected = (id) => selectedIds.value.includes(id)

/* ---- 数据加载 ---- */
async function loadAll() {
  loading.value = true
  loadError.value = false
  try {
    const res = await api.listOffers()
    offers.value = res.data.items || []
    // 已删除的勾选清理
    const alive = new Set(offers.value.map((o) => o.id))
    selectedIds.value = selectedIds.value.filter((id) => alive.has(id))
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

/* ---- 勾选（对比模式）：任何勾选变化都作废旧对比结果 ---- */
function toggleSelect(o) {
  compareResult.value = null
  const i = selectedIds.value.indexOf(o.id)
  if (i >= 0) {
    selectedIds.value.splice(i, 1)
    return
  }
  if (selectedIds.value.length >= 6) {
    Message.warning('最多对比 6 个 Offer')
    return
  }
  selectedIds.value.push(o.id)
}

/* ---- 对比 ---- */
async function runCompare() {
  if (selectedIds.value.length < 2) {
    Message.warning('至少勾选两个 Offer')
    return
  }
  comparing.value = true
  try {
    const res = await api.compareOffers({ ids: [...selectedIds.value] })
    compareResult.value = res.data
  } catch (e) {
    Message.error(e.response?.data?.detail || '对比失败')
  } finally {
    comparing.value = false
  }
}

const radarSeries = computed(() => (compareResult.value?.items || []).map((it, i) => ({
  name: it.company,
  values: SCORE_KEYS.map((k) => it.scores[k]),
  color: SERIES_COLORS[i % SERIES_COLORS.length],
})))

const weightLegend = computed(() => {
  const parts = Object.keys(DEFAULT_WEIGHTS)
    .map((k) => `${WEIGHT_LABELS[k]} ${DEFAULT_WEIGHTS[k]}%`)
    .join(' · ')
  return `权重：${parts}（默认）`
})

/* ---- 新建 / 编辑（保存不收起，连续录入） ---- */
const formOpen = ref(false)
const editingId = ref(null)
const formSaving = ref(false)
const FORM_EMPTY = {
  company: '', title: '', city: '', monthly_salary: null,
  salary_months: 12, commute_minutes: 45, insurance: 3, development: 3, stability: 3, notes: '',
}
const form = reactive({ ...FORM_EMPTY })

function resetForm() {
  Object.assign(form, FORM_EMPTY)
}

function openForm() {
  resetForm()
  editingId.value = null
  formOpen.value = true
}

function openEdit(o) {
  editingId.value = o.id
  Object.assign(form, {
    company: o.company || '', title: o.title || '', city: o.city || '',
    monthly_salary: o.monthly_salary, salary_months: o.salary_months,
    commute_minutes: o.commute_minutes, insurance: o.insurance,
    development: o.development, stability: o.stability, notes: o.notes || '',
  })
  formOpen.value = true
}

function closeForm() {
  formOpen.value = false
  resetForm()
  editingId.value = null
}

async function saveForm() {
  const company = form.company.trim()
  const title = form.title.trim()
  if (!company || !title) {
    Message.warning('公司与岗位为必填')
    return
  }
  const monthly = Number(form.monthly_salary)
  if (!monthly || monthly < 1 || monthly > 500) {
    Message.warning('月薪需在 1~500 K 之间')
    return
  }
  formSaving.value = true
  try {
    const payload = {
      company,
      title,
      city: form.city.trim(),
      monthly_salary: monthly,
      salary_months: form.salary_months,
      commute_minutes: form.commute_minutes,
      insurance: form.insurance,
      development: form.development,
      stability: form.stability,
      notes: form.notes.trim(),
    }
    if (editingId.value != null) {
      const res = await api.updateOffer(editingId.value, payload)
      cardsReplace(res.data)
      Message.success('已保存修改')
    } else {
      const res = await api.createOffer(payload)
      offers.value.unshift(res.data)
      Message.success('已保存 Offer，可继续录入')
    }
    // 连续录入惯例：清空表单、弹窗不收起；数据变了旧对比结果作废
    resetForm()
    editingId.value = null
    compareResult.value = null
  } catch (e) {
    Message.error(e.response?.data?.detail || '保存失败')
  } finally {
    formSaving.value = false
  }
}

function cardsReplace(rec) {
  offers.value = offers.value.filter((x) => x.id !== rec.id)
  offers.value.unshift(rec)
}

/* ---- 删除 ---- */
function remove(o) {
  Modal.warning({
    title: '确认删除该 Offer？',
    content: `「${o.company} · ${o.title}」将从列表删除。`,
    okText: '删除',
    okButtonProps: { status: 'danger' },
    cancelText: '取消',
    hideCancel: false,
    onOk: async () => {
      try {
        await api.deleteOffer(o.id)
        offers.value = offers.value.filter((x) => x.id !== o.id)
        selectedIds.value = selectedIds.value.filter((id) => id !== o.id)
        compareResult.value = null
        Message.success('已删除')
      } catch (e) {
        Message.error(e.response?.data?.detail || '删除失败')
      }
    },
  })
}

/* ---- 展示杂项 ---- */
function fmtWan(annualK) {
  const v = (annualK || 0) / 10
  return Number.isInteger(v) ? String(v) : v.toFixed(1)
}

function badges(o) {
  return [
    { label: '通勤', value: `${o.commute_minutes}min` },
    { label: '五险', value: o.insurance },
    { label: '发展', value: o.development },
    { label: '稳定', value: o.stability },
  ]
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}-${String(d.getDate()).padStart(2, '0')}`
}

function onEscKey(e) {
  if (e.key === 'Escape' && formOpen.value) closeForm()
}

onMounted(async () => {
  await loadAll()
  window.addEventListener('keydown', onEscKey)
})

onUnmounted(() => window.removeEventListener('keydown', onEscKey))
</script>
