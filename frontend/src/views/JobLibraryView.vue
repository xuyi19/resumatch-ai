<template>
  <div class="max-w-6xl mx-auto px-6 md:px-10 py-8 md:py-10">

    <!-- 页头（全站统一规范：渐变标题 + 短横线） -->
    <div class="flex items-end justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold tracking-tight">
          <span class="bg-gradient-to-r from-ink to-accent bg-clip-text text-transparent">岗位库</span>
        </h1>
        <div class="h-0.5 w-14 rounded-full bg-gradient-to-r from-accent to-accent-hover/0 mt-1.5"></div>
        <p class="text-xs text-ink-faint mt-1.5">
          统一管理心仪岗位 · 粘贴 JD 建档 · 一键与简历批量匹配
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button @click="toggleImport()"
          class="px-4 py-2 text-xs font-medium rounded-lg border border-accent/50 text-accent
            hover:bg-accent/10 active:scale-[0.98] transition-all">
          {{ importOpen ? '收起导入' : '⇪ 批量导入' }}
        </button>
        <button @click="toggleForm()"
          class="px-4 py-2 text-xs font-medium rounded-lg bg-accent text-white
            hover:bg-accent-hover active:scale-[0.98] transition-all">
          {{ formOpen ? '收起' : '＋ 添加岗位' }}
        </button>
      </div>
    </div>

    <!-- 批量导入：粘贴混排文本 → AI 解析 → 勾选入库 -->
    <div v-if="importOpen" class="bg-panel rounded-2xl p-5 md:p-6 mb-6">
      <div class="text-sm font-semibold mb-1">批量导入岗位</div>
      <p class="text-xs text-ink-faint mb-3">
        粘贴一个或多个岗位的混排文本（招聘网站复制的 JD、岗位列表等），AI 自动提取岗位信息，确认后入库。
        不同岗位之间建议用空行分隔，解析更准。
      </p>
      <textarea v-model="rawImportText" rows="8" maxlength="60000"
        placeholder="例如从 BOSS 直聘批量复制的多个岗位描述，或各处收集的 JD 文本……"
        class="w-full px-3.5 py-3 text-sm bg-inset rounded-lg border border-line resize-y
          focus:outline-none focus:border-accent placeholder:text-ink-faint transition-colors"></textarea>
      <div class="flex items-center gap-3 mt-3">
        <button @click="parseBatch" :disabled="parsing || rawImportText.trim().length < 30"
          class="px-5 py-2 text-xs font-medium rounded-lg bg-accent text-white
            hover:bg-accent-hover active:scale-[0.98] transition-all disabled:opacity-40">
          {{ parsing ? 'AI 解析中…' : parsed.length ? '重新解析' : 'AI 解析预览' }}
        </button>
        <button @click="closeImport"
          class="px-4 py-2 text-xs text-ink-sub hover:text-ink transition-colors">关闭</button>
      </div>

      <div v-if="parseDegraded" class="mt-3 px-4 py-3 rounded-xl text-xs bg-warn/10 border border-warn/40 text-warn">
        {{ parseDegradedReason }}
      </div>

      <!-- 解析预览（勾选） -->
      <div v-if="parsed.length" class="mt-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-ink-sub">解析出 {{ parsed.length }} 个岗位 · 已全选，可取消勾选</span>
          <button @click="toggleSelectAll"
            class="text-xs text-accent hover:underline">{{ allSelected ? '全不选' : '全选' }}</button>
        </div>
        <div class="space-y-2 max-h-80 overflow-y-auto pr-1">
          <label v-for="(j, i) in parsed" :key="i"
            class="flex items-start gap-2.5 px-3 py-2.5 rounded-lg bg-inset cursor-pointer
              hover:bg-accent/5 transition-colors"
            :class="!j._sel && 'opacity-50'">
            <input type="checkbox" v-model="j._sel" class="mt-0.5 w-4 h-4 accent-accent shrink-0" />
            <div class="min-w-0">
              <div class="text-xs font-medium truncate">
                {{ j.title || '（无岗位名）' }}
                <span v-if="j.company" class="font-normal text-ink-faint ml-1.5">{{ j.company }}</span>
                <span v-if="j.city || j.salary" class="font-normal text-ink-faint ml-1.5">{{ [j.city, j.salary].filter(Boolean).join(' · ') }}</span>
              </div>
              <div class="text-[11px] text-ink-faint mt-0.5 line-clamp-2">{{ j.jd || '（无 JD）' }}</div>
            </div>
          </label>
        </div>
        <div class="flex items-center gap-3 mt-4">
          <button @click="importSelected" :disabled="importing || !selectedCount"
            class="px-5 py-2 text-xs font-medium rounded-lg bg-accent text-white
              hover:bg-accent-hover active:scale-[0.98] transition-all disabled:opacity-40">
            {{ importing ? '导入中…' : `导入选中（${selectedCount}）· 自动跳过重复` }}
          </button>
        </div>
      </div>
    </div>

    <!-- 添加 / 编辑表单 -->
    <div v-if="formOpen" class="bg-panel rounded-2xl p-5 md:p-6 mb-6">
      <div class="text-sm font-semibold mb-4">
        {{ editingId != null ? '编辑岗位' : '添加岗位' }}
        <span class="ml-2 text-xs font-normal text-ink-faint">带 * 必填，其余可留空</span>
      </div>

      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
        <input v-model="form.title" maxlength="80" placeholder="岗位名 *"
          class="px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
            focus:border-accent transition-colors" />
        <input v-model="form.company" maxlength="60" placeholder="公司"
          class="px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
            focus:border-accent transition-colors" />
        <input v-model="form.city" maxlength="20" placeholder="城市"
          class="px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
            focus:border-accent transition-colors" />
        <input v-model="form.salary" maxlength="40" placeholder="薪资（如 25-40K）"
          class="px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
            focus:border-accent transition-colors" />
      </div>
      <textarea v-model="form.jd" rows="6" maxlength="20000"
        placeholder="粘贴岗位 JD 全文（可从 BOSS / 智联 / 拉勾等平台复制岗位描述）&#10;JD 越完整，匹配推荐与面试出题越准"
        class="w-full px-3.5 py-3 text-sm bg-inset rounded-lg border border-line resize-y
          focus:outline-none focus:border-accent placeholder:text-ink-faint transition-colors"></textarea>
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

    <!-- 匹配操作条 -->
    <div v-if="jobs.length" class="bg-panel rounded-2xl px-5 py-4 mb-5
      flex flex-wrap items-center gap-3">
      <span class="text-xs text-ink-sub shrink-0">与简历匹配：</span>
      <select v-model="selectedResumeId"
        class="px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
          focus:border-accent transition-colors min-w-0 max-w-[280px]">
        <option value="">选择简历…</option>
        <option v-for="r in resumes" :key="r.id" :value="r.id">
          {{ r.filename }}
        </option>
      </select>
      <button @click="runMatch" :disabled="matching || !selectedResumeId"
        class="px-4 py-2 text-xs font-medium rounded-lg border border-accent text-accent
          hover:bg-accent/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
        {{ matching ? 'AI 匹配中…' : matchDone ? '重新匹配' : '开始匹配' }}
      </button>
      <button @click="clearMatch"
        class="px-3 py-2 text-xs text-ink-faint hover:text-ink transition-colors">清除结果</button>
      <span class="w-px h-4 bg-line shrink-0 mx-1" />
      <button @click="runGenerate" :disabled="generating || !selectedResumeId"
        :title="selectedResumeId ? 'AI 根据选中简历生成适合的岗位并入库' : '先选择一份简历'"
        class="px-4 py-2 text-xs font-medium rounded-lg border border-accent/50 text-accent
          hover:bg-accent/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
        {{ generating ? 'AI 生成中…' : '✨ AI 生成岗位入库' }}
      </button>
      <span v-if="!matchDone && !matching" class="text-[11px] text-ink-faint ml-auto hidden md:block">
        {{ hasFilters
          ? `对筛选出的 ${filteredJobs.length}/${jobs.length} 个岗位打匹配分（0-100）`
          : `对全部 ${jobs.length} 个岗位打匹配分（0-100）并给推荐理由` }}
      </span>
    </div>

    <!-- 搜索与筛选栏 -->
    <div v-if="jobs.length" class="bg-panel rounded-2xl px-5 py-3 mb-5 flex flex-wrap items-center gap-2.5">
      <div class="relative flex-1 min-w-[190px]">
        <svg class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
        </svg>
        <input v-model="keyword" type="text" placeholder="搜索岗位名 / 公司 / 城市…"
          class="w-full pl-9 pr-3 py-2 text-sm bg-inset rounded-lg border border-line
            focus:outline-none focus:border-accent placeholder:text-ink-faint transition-colors" />
      </div>
      <select v-model="sourceFilter"
        class="px-3 py-2 text-xs bg-inset rounded-lg border border-line text-ink-sub
          focus:outline-none focus:border-accent transition-colors">
        <option value="">全部来源</option>
        <option value="manual">手动添加</option>
        <option value="ai_gen">AI 生成</option>
        <option value="ai">面板入库</option>
        <option value="sample">示例岗位</option>
      </select>
      <select v-if="cityOptions.length" v-model="cityFilter"
        class="px-3 py-2 text-xs bg-inset rounded-lg border border-line text-ink-sub
          focus:outline-none focus:border-accent transition-colors max-w-[140px]">
        <option value="">全部城市</option>
        <option v-for="c in cityOptions" :key="c" :value="c">{{ c }}</option>
      </select>
      <select v-model="statusFilter"
        class="px-3 py-2 text-xs bg-inset rounded-lg border border-line text-ink-sub
          focus:outline-none focus:border-accent transition-colors">
        <option value="">全部状态</option>
        <option v-for="(s, key) in STATUS" :key="key" :value="key">{{ s.label }}</option>
      </select>
      <button v-if="hasFilters" @click="clearFilters"
        class="px-3 py-2 text-xs text-ink-faint hover:text-ink transition-colors">清除筛选</button>
      <span class="text-[11px] font-mono text-ink-faint ml-auto shrink-0">
        {{ filteredJobs.length }}/{{ jobs.length }}
      </span>
      <span class="w-px h-4 bg-line shrink-0" />
      <button @click="toggleSelMode" :title="selMode ? '退出管理模式' : '进入管理模式，勾选岗位批量删除'"
        class="px-3 py-2 text-xs font-medium rounded-lg border transition-colors shrink-0"
        :class="selMode ? 'bg-accent text-white border-accent' : 'border-line text-ink-sub hover:border-accent/60 hover:text-accent'">
        {{ selMode ? '✓ 完成' : '☐ 批量管理' }}
      </button>
      <button v-if="selMode" @click="toggleSelectAllCards"
        class="px-3 py-2 text-xs text-ink-sub hover:text-ink transition-colors">
        {{ allCardsSelected ? '全不选' : '全选' }}
      </button>
    </div>

    <!-- 管理模式浮动操作条 -->
    <Teleport to="body">
      <Transition enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 translate-y-4" leave-active-class="transition duration-150 ease-in"
        leave-to-class="opacity-0 translate-y-4">
        <div v-if="selMode && selCount"
          class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-4
            bg-float rounded-xl px-5 py-3 border border-line-strong shadow-lg">
          <span class="text-sm text-ink-sub">已选 <b class="text-ink">{{ selCount }}</b> 个岗位</span>
          <span class="w-px h-5 bg-line" />
          <!-- M49 批量设置投递状态 -->
          <select @change="batchSetStatus($event.target.value); $event.target.value = ''"
            class="px-3 py-2 text-xs bg-inset rounded-lg border border-line text-ink-sub
              focus:outline-none focus:border-accent transition-colors cursor-pointer">
            <option value="" disabled selected>设为状态…</option>
            <option v-for="(s, key) in STATUS" :key="key" :value="key">{{ s.label }}</option>
          </select>
          <span class="w-px h-5 bg-line" />
          <button @click="batchRemove" :disabled="batchRemoving"
            class="px-4 py-2 text-xs font-medium rounded-lg bg-bad text-white
              hover:opacity-90 active:scale-[0.98] transition-all disabled:opacity-40">
            {{ batchRemoving ? '删除中…' : '🗑 批量删除' }}
          </button>
          <button @click="toggleSelMode"
            class="px-3 py-2 text-xs text-ink-sub hover:text-ink transition-colors">取消</button>
        </div>
      </Transition>
    </Teleport>

    <!-- 降级提示 -->
    <div v-if="matchDegraded" class="mb-5 px-4 py-3 rounded-xl text-xs
      bg-warn/10 border border-warn/40 text-warn">
      AI 精排不可用，已按关键词重合度排序——可在设置页配置 API Key 后重新匹配获得更准的排序。
    </div>

    <!-- 岗位列表 -->
    <LoadingBlock v-if="loading" text="岗位库加载中…" />
    <div v-else-if="loadError" class="bg-warn/10 border border-warn/40 rounded-2xl px-5 py-4
      flex items-center justify-between">
      <span class="text-sm text-warn">岗位库加载失败</span>
      <button @click="loadAll" class="text-sm font-medium text-warn hover:text-ink transition-colors">重试</button>
    </div>

    <template v-else>
      <div v-if="!jobs.length && !formOpen && !importOpen" class="bg-panel rounded-2xl p-12 text-center">
        <div class="text-4xl mb-4">💼</div>
        <div class="text-lg font-semibold mb-2">从一份 JD 开始建库</div>
        <p class="text-sm text-ink-sub max-w-md mx-auto">
          把心仪岗位的 JD 粘贴进来统一管理；之后选一份简历即可批量匹配出分，
          也可以直接「用此岗位诊断 / 面试」。
        </p>
        <div class="flex items-center justify-center gap-3 mt-5">
          <button @click="openForm()"
            class="px-5 py-2 text-xs font-medium rounded-lg bg-accent text-white
              hover:bg-accent-hover transition-colors">＋ 添加第一个岗位</button>
          <button @click="fillSamples" :disabled="fillingSamples"
            class="px-5 py-2 text-xs font-medium rounded-lg border border-accent/50 text-accent
              hover:bg-accent/10 transition-colors disabled:opacity-40">
            {{ fillingSamples ? '填充中…' : '🧪 填充 6 个示例岗位' }}
          </button>
        </div>
      </div>

      <!-- 筛选无结果（库非空但过滤后为空） -->
      <div v-else-if="hasFilters && !filteredJobs.length"
        class="bg-panel rounded-2xl p-10 text-center">
        <div class="text-3xl mb-3">🔍</div>
        <div class="text-sm text-ink-sub mb-1">没有符合筛选条件的岗位</div>
        <p class="text-xs text-ink-faint mb-4">换个关键词，或清除筛选查看全部 {{ jobs.length }} 个岗位</p>
        <button @click="clearFilters"
          class="px-4 py-2 text-xs font-medium rounded-lg border border-accent/50 text-accent
            hover:bg-accent/10 transition-colors">清除筛选</button>
      </div>

      <div v-else class="space-y-2.5">
        <div v-for="j in displayJobs" :key="j.id"
          class="bg-panel rounded-xl px-4 py-3 border border-line hover:border-line-strong
            hover:shadow-md transition-all"
          :class="selMode && selIds.has(j.id) && 'ring-2 ring-accent/50 border-accent/40'">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0 flex items-center gap-2 flex-wrap">
              <!-- 管理模式复选框 -->
              <input v-if="selMode" type="checkbox" :checked="selIds.has(j.id)"
                @change="toggleCardSel(j.id)"
                class="w-4 h-4 accent-accent shrink-0 cursor-pointer" />
              <span class="text-sm font-semibold shrink-0">{{ j.title }}</span>
              <span class="text-xs text-ink-sub truncate max-w-[180px]">{{ j.company || '公司待定' }}</span>
              <span v-if="j.city" class="px-1.5 py-0.5 rounded text-[11px] bg-inset text-ink-sub shrink-0">{{ j.city }}</span>
              <span v-if="j.salary" class="px-1.5 py-0.5 rounded text-[11px] bg-ok/10 text-ok font-mono shrink-0">{{ j.salary }}</span>
              <span class="px-1.5 py-0.5 rounded text-[11px] bg-inset text-ink-faint shrink-0">{{ sourceLabel(j.source) }}</span>
              <!-- M49 投递状态徽标：点击直接切换 -->
              <select :value="j.status || 'wish'" @change="setStatus(j, $event.target.value)" @click.stop
                :title="'投递状态：' + (STATUS[j.status || 'wish']?.label || '') + '，点击切换'"
                class="px-1.5 py-0.5 rounded text-[11px] font-medium shrink-0 border-0 cursor-pointer
                  appearance-none focus:outline-none focus:ring-1 focus:ring-accent -mr-1"
                :class="STATUS[j.status || 'wish']?.cls">
                <option v-for="(s, key) in STATUS" :key="key" :value="key">{{ s.label }}</option>
              </select>
            </div>
            <!-- 匹配分徽标 -->
            <div v-if="matchMap[j.id]" class="flex items-center gap-2 shrink-0">
              <span class="text-[10px] text-ink-faint max-w-[120px] truncate">{{ matchMap[j.id].reason }}</span>
              <div class="px-2 py-0.5 rounded-lg text-sm font-mono font-semibold"
                :class="matchMap[j.id].score >= 70 ? 'bg-ok/10 text-ok'
                  : matchMap[j.id].score >= 40 ? 'bg-warn/10 text-warn' : 'bg-inset text-ink-faint'">
                {{ matchMap[j.id].score }} 分
              </div>
            </div>
            <span v-else class="text-[10px] text-ink-faint shrink-0 mt-1 font-mono">{{ fmtTime(j.created_at) }}</span>
          </div>

          <!-- JD 摘要（默认单行截断，点击展开；无 JD 显示占位） -->
          <p v-if="j.jd" class="text-xs text-ink-faint mt-1.5 leading-relaxed cursor-pointer"
            :class="expandedId === j.id ? 'whitespace-pre-wrap text-ink-sub' : 'truncate'"
            :title="expandedId === j.id ? '点击收起' : '点击展开'"
            @click="expandedId = expandedId === j.id ? null : j.id">{{ j.jd }}</p>
          <p v-else class="text-xs text-ink-faint/60 mt-1.5 italic">暂无 JD 描述 · 编辑补充后可用于诊断/面试</p>

          <!-- 操作行 -->
          <div class="flex items-center gap-3 mt-2 pt-2 border-t border-line/60">
            <button @click="diagnoseWith(j)" class="text-xs text-accent hover:underline">🩺 用此岗位诊断</button>
            <button @click="interviewWith(j)" class="text-xs text-accent hover:underline">🎤 用此岗位面试</button>
            <span class="flex-1" />
            <button v-if="!selMode" @click="openEdit(j)" title="编辑岗位"
              class="text-xs text-ink-sub hover:text-accent transition-colors">✏️ 编辑</button>
            <button v-if="!selMode" @click="remove(j)" title="删除岗位"
              class="text-xs text-ink-sub hover:text-bad transition-colors">🗑 删除</button>
          </div>
        </div>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import api from '../api'
import LoadingBlock from '../components/LoadingBlock.vue'

const router = useRouter()

const loading = ref(true)
const loadError = ref(false)
const jobs = ref([])
const resumes = ref([])
const selectedResumeId = ref('')

const formOpen = ref(false)
const editingId = ref(null)
const formSaving = ref(false)
const form = reactive({ title: '', company: '', city: '', salary: '', jd: '' })

const matching = ref(false)
const matchDone = ref(false)
const matchDegraded = ref(false)
const matchMap = reactive({})   // id -> {score, reason}
const expandedId = ref(null)

/* ---- M49 投递状态 ---- */
const STATUS = {
  wish: { label: '💧 想投', cls: 'bg-inset text-ink-sub' },
  applied: { label: '📨 已投递', cls: 'bg-accent/10 text-accent' },
  interviewing: { label: '🎯 面试中', cls: 'bg-warn/10 text-warn' },
  offer: { label: '🎉 Offer', cls: 'bg-ok/10 text-ok' },
  closed: { label: '🏁 已结束', cls: 'bg-bad/10 text-bad' },
}
const statusFilter = ref('')

async function setStatus(j, status) {
  const prev = j.status || 'wish'
  if (status === prev) return
  try {
    await api.updateJobStatus(j.id, status)
    j.status = status
  } catch (e) {
    Message.error(e.response?.data?.detail || '状态更新失败')
    j.status = prev
  }
}

async function batchSetStatus(status) {
  if (!status || !selIds.value.size) return
  try {
    await api.batchUpdateJobStatus([...selIds.value], status)
    jobs.value.forEach((j) => {
      if (selIds.value.has(j.id)) j.status = status
    })
    Message.success(`已将 ${selIds.value.size} 个岗位设为「${STATUS[status].label}」`)
  } catch (e) {
    Message.error(e.response?.data?.detail || '批量更新失败')
  }
}

/* ---- 搜索与筛选（本地过滤，匹配分排序作用于筛选后的子集） ---- */
const keyword = ref('')
const sourceFilter = ref('')
const cityFilter = ref('')

const filteredJobs = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return jobs.value.filter((j) => {
    if (kw && ![j.title, j.company, j.city].some((v) => (v || '').toLowerCase().includes(kw)))
      return false
    if (sourceFilter.value && (j.source || 'manual') !== sourceFilter.value) return false
    if (cityFilter.value && (j.city || '') !== cityFilter.value) return false
    if (statusFilter.value && (j.status || 'wish') !== statusFilter.value) return false
    return true
  })
})

const cityOptions = computed(() =>
  [...new Set(jobs.value.map((j) => (j.city || '').trim()).filter(Boolean))].sort(),
)

const hasFilters = computed(() => !!(keyword.value.trim() || sourceFilter.value || cityFilter.value || statusFilter.value))

function clearFilters() {
  keyword.value = ''
  sourceFilter.value = ''
  cityFilter.value = ''
  statusFilter.value = ''
}

const displayJobs = computed(() => {
  const base = filteredJobs.value
  if (!matchDone.value) return base
  return [...base].sort(
    (a, b) => (matchMap[b.id]?.score ?? -1) - (matchMap[a.id]?.score ?? -1),
  )
})

const SOURCE_LABELS = { manual: '手动添加', ai: '面板入库', ai_gen: 'AI 生成', sample: '示例岗位' }
const sourceLabel = (s) => SOURCE_LABELS[s] || s

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}-${String(d.getDate()).padStart(2, '0')}`
}

/* ---- 管理模式（批量选择删除） ---- */
const selMode = ref(false)
const selIds = ref(new Set())
const batchRemoving = ref(false)

const selCount = computed(() => selIds.value.size)
const allCardsSelected = computed(
  () => filteredJobs.value.length > 0 && filteredJobs.value.every((j) => selIds.value.has(j.id)),
)

function toggleSelMode() {
  selMode.value = !selMode.value
  if (!selMode.value) selIds.value = new Set()
}

function toggleCardSel(id) {
  const next = new Set(selIds.value)
  next.has(id) ? next.delete(id) : next.add(id)
  selIds.value = next
}

function toggleSelectAllCards() {
  selIds.value = allCardsSelected.value
    ? new Set()
    : new Set(filteredJobs.value.map((j) => j.id))
}

async function batchRemove() {
  const n = selIds.value.size
  Modal.warning({
    title: `确认删除选中的 ${n} 个岗位？`,
    content: '删除后不可恢复（正在进行的诊断/面试不受影响）。',
    okText: '删除',
    okButtonProps: { status: 'danger' },
    cancelText: '取消',
    hideCancel: false,
    onOk: async () => {
      batchRemoving.value = true
      try {
        await api.batchDeleteLibraryJobs([...selIds.value])
        const gone = new Set(selIds.value)
        jobs.value = jobs.value.filter((j) => !gone.has(j.id))
        selIds.value = new Set()
        selMode.value = false
        Message.success(`已删除 ${n} 个岗位`)
      } catch (e) {
        Message.error(e.response?.data?.detail || '批量删除失败')
      } finally {
        batchRemoving.value = false
      }
    },
  })
}

/* ---- 数据加载 ---- */
async function loadAll() {
  loading.value = true
  loadError.value = false
  try {
    const [jobRes, resumeRes] = await Promise.all([api.listLibraryJobs(), api.listResumes()])
    jobs.value = jobRes.data.items || []
    resumes.value = resumeRes.data.items || []
  } catch (e) {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

/* ---- 添加 / 编辑 ---- */
function toggleForm() {
  formOpen.value ? closeForm() : openForm()
}

function openForm() {
  resetForm()
  editingId.value = null
  formOpen.value = true
}

function openEdit(j) {
  editingId.value = j.id
  Object.assign(form, { title: j.title, company: j.company, city: j.city, salary: j.salary, jd: j.jd })
  formOpen.value = true
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function closeForm() {
  formOpen.value = false
  resetForm()
  editingId.value = null
}

function resetForm() {
  Object.assign(form, { title: '', company: '', city: '', salary: '', jd: '' })
}

async function saveForm() {
  const title = form.title.trim()
  if (!title) {
    Message.warning('岗位名必填')
    return
  }
  formSaving.value = true
  try {
    const payload = {
      title,
      company: form.company.trim(),
      city: form.city.trim(),
      salary: form.salary.trim(),
      jd: form.jd.trim(),
    }
    if (editingId.value != null) {
      const res = await api.updateLibraryJob(editingId.value, payload)
      const idx = jobs.value.findIndex((j) => j.id === editingId.value)
      if (idx >= 0) jobs.value.splice(idx, 1, res.data)
      Message.success('已保存修改')
      closeForm()
    } else {
      const res = await api.addLibraryJobs([payload], 'manual')
      jobs.value.unshift(...(res.data.items || []))
      Message.success('已加入岗位库，可继续录入')
      resetForm()  // 连续录入：清空不收起
    }
  } catch (e) {
    Message.error(e.response?.data?.detail || '保存失败')
  } finally {
    formSaving.value = false
  }
}

/* ---- 删除 ---- */
function remove(j) {
  Modal.warning({
    title: '确认删除该岗位？',
    content: `「${j.company || ''} ${j.title}」将从岗位库删除。`,
    okText: '删除',
    cancelText: '取消',
    hideCancel: false,
    onOk: async () => {
      try {
        await api.deleteLibraryJob(j.id)
        jobs.value = jobs.value.filter((x) => x.id !== j.id)
        delete matchMap[j.id]
        Message.success('已删除')
      } catch (e) {
        Message.error(e.response?.data?.detail || '删除失败')
      }
    },
  })
}

/* ---- 匹配推荐 ---- */
async function runMatch() {
  if (!selectedResumeId.value) {
    Message.warning('先选择一份简历')
    return
  }
  matching.value = true
  try {
    // 筛选出子集时只匹配子集（后端按 job_ids 过滤候选池）
    const subset = filteredJobs.value.length < jobs.value.length
    const res = await api.matchLibraryJobs({
      resume_id: Number(selectedResumeId.value),
      job_ids: subset ? filteredJobs.value.map((j) => j.id) : undefined,
      llm_config: null,
    })
    Object.keys(matchMap).forEach((k) => delete matchMap[k])
    for (const it of res.data.items || []) {
      matchMap[it.id] = { score: it.score, reason: it.reason }
    }
    matchDegraded.value = !!res.data.degraded
    matchDone.value = true
    if (res.data.message) Message.info(res.data.message)
    else Message.success(`已为 ${res.data.items?.length ?? 0} 个岗位打分`)
  } catch (e) {
    Message.error(e.response?.data?.detail || '匹配失败')
  } finally {
    matching.value = false
  }
}

function clearMatch() {
  matchDone.value = false
  matchDegraded.value = false
  Object.keys(matchMap).forEach((k) => delete matchMap[k])
}

/* ---- 批量导入：粘贴混排文本 → AI 解析 → 勾选入库 ---- */
const importOpen = ref(false)
const rawImportText = ref('')
const parsing = ref(false)
const parsed = ref([])   // [{title, company, city, salary, jd, _sel}]
const parseDegraded = ref(false)
const parseDegradedReason = ref('')
const importing = ref(false)

const selectedCount = computed(() => parsed.value.filter((j) => j._sel).length)
const allSelected = computed(() => parsed.value.length > 0 && selectedCount.value === parsed.value.length)

function toggleImport() {
  importOpen.value = !importOpen.value
  if (!importOpen.value) {
    rawImportText.value = ''
    parsed.value = []
    parseDegraded.value = false
  }
}

function closeImport() {
  importOpen.value = false
  rawImportText.value = ''
  parsed.value = []
  parseDegraded.value = false
}

function toggleSelectAll() {
  const target = !allSelected.value
  parsed.value.forEach((j) => (j._sel = target))
}

async function parseBatch() {
  if (rawImportText.value.trim().length < 30) {
    Message.warning('文本太短（至少 30 字）')
    return
  }
  parsing.value = true
  try {
    const res = await api.parseBatchImport({ raw_text: rawImportText.value, llm_config: null })
    parsed.value = (res.data.items || []).map((j) => ({ ...j, _sel: true }))
    parseDegraded.value = !!res.data.degraded
    parseDegradedReason.value = res.data.degraded_reason || ''
    if (!parsed.value.length) {
      Message.info(res.data.message || '没有解析出岗位')
    } else {
      Message.success(`解析出 ${parsed.value.length} 个岗位，请确认后导入`)
    }
  } catch (e) {
    Message.error(e.response?.data?.detail || '解析失败')
  } finally {
    parsing.value = false
  }
}

async function importSelected() {
  const items = parsed.value
    .filter((j) => j._sel)
    .map(({ _sel, ...j }) => j)
  if (!items.length) return
  importing.value = true
  try {
    const res = await api.addLibraryJobs(items, 'manual', true)  // 后端自动跳过与库内重复
    const added = res.data.items || []
    jobs.value.unshift(...added)
    const skipped = res.data.skipped || 0
    if (added.length) {
      Message.success(`已导入 ${added.length} 个岗位${skipped ? `，跳过重复 ${skipped} 个` : ''}`)
    } else {
      Message.info(res.data.message || '没有新岗位入库')
    }
    closeImport()
  } catch (e) {
    Message.error(e.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

/* ---- 示例岗位：一键填充体验完整流程（可删除） ---- */
const SAMPLE_JOBS = [
  { title: 'Python 后端开发工程师', company: '字节跳动', city: '北京', salary: '30-50K·16薪',
    jd: '岗位职责：1. 负责内容分发与创作平台后端服务的架构设计与研发；2. 参与高并发、高可用分布式系统建设，保障核心链路稳定性；3. 与算法、前端团队协作完成业务迭代。任职要求：1. 本科及以上学历，3 年以上 Python 开发经验；2. 精通 FastAPI/Flask 至少一种框架，熟悉 MySQL、Redis、Kafka；3. 有大规模分布式系统或高并发订单/内容系统经验者优先。' },
  { title: '前端开发工程师（React 方向）', company: '腾讯', city: '深圳', salary: '25-45K·16薪',
    jd: '岗位职责：1. 负责公司核心 SaaS 产品的前端架构与研发；2. 建设前端工程化体系，优化构建与首屏性能；3. 设计通用组件库，提升团队研发效率。任职要求：1. 熟练掌握 React/TypeScript，理解 Hooks 原理；2. 熟悉 Vite/Webpack 构建链路，有性能调优实战经验；3. 对可视化（ECharts/D3）有经验者优先。' },
  { title: '算法工程师（推荐方向）', company: '美团', city: '北京', salary: '35-60K·15.5薪',
    jd: '岗位职责：1. 负责到店推荐算法的建模与迭代，提升转化与留存；2. 建设 User/Item 表征、排序与重排策略；3. 跟进业界前沿论文并落地。任职要求：1. 硕士及以上学历，计算机/数学相关专业；2. 扎实的机器学习基础，熟悉 PyTorch，有召回/排序实战经验；3. 有 KDD/SIGIR 等论文发表者优先。' },
  { title: '数据分析师（商业化方向）', company: '小红书', city: '上海', salary: '20-35K·14薪',
    jd: '岗位职责：1. 负责商业化广告业务的数据分析，输出增长洞察；2. 搭建指标体系与看板，监控核心漏斗；3. 支持 A/B 实验设计与效果归因。任职要求：1. 本科及以上学历，统计学/计算机相关专业；2. 精通 SQL 与 Python 数据分析，熟悉 Hive/Spark；3. 有互联网广告或增长分析经验者优先。' },
  { title: '测试开发工程师', company: '华为', city: '杭州', salary: '22-38K·14薪',
    jd: '岗位职责：1. 负责云计算产品测试平台与自动化框架建设；2. 设计接口/性能/稳定性测试方案并落地；3. 推动 CI/CD 流水线质量卡点。任职要求：1. 本科及以上学历，2 年以上测试开发经验；2. 精通 Python，熟悉 pytest/locust，了解 Docker 与 K8s；3. 有大型分布式系统测试经验者优先。' },
  { title: '产品经理（AI 应用方向）', company: '蚂蚁集团', city: '杭州', salary: '28-50K·16薪',
    jd: '岗位职责：1. 负责 AI 助手类产品从 0 到 1 的规划与落地；2. 深挖用户场景，设计 Prompt 与 Agent 工作流的产品化方案；3. 协同算法、研发推进迭代并复盘数据。任职要求：1. 本科及以上学历，3 年以上产品经验；2. 对 LLM/Agent 生态有深入理解，用过主流大模型 API；3. 有 AI 产品或工具类产品上线经验者优先。' },
]

const fillingSamples = ref(false)

async function fillSamples() {
  fillingSamples.value = true
  try {
    const res = await api.addLibraryJobs(SAMPLE_JOBS, 'sample')
    jobs.value.unshift(...(res.data.items || []))
    Message.success('已填充 6 个示例岗位，可删除或直接体验匹配/诊断/面试')
  } catch (e) {
    Message.error(e.response?.data?.detail || '填充失败')
  } finally {
    fillingSamples.value = false
  }
}

/* ---- AI 自动入库：按选中简历生成岗位 ---- */
const generating = ref(false)

async function runGenerate() {
  if (!selectedResumeId.value) {
    Message.warning('先选择一份简历')
    return
  }
  generating.value = true
  try {
    const res = await api.generateLibraryJobs({
      resume_id: Number(selectedResumeId.value),
      llm_config: null,
    })
    const added = res.data.items || []
    if (added.length) {
      jobs.value.unshift(...added)
      Message.success(`已生成 ${added.length} 个岗位并入库`)
    } else {
      Message.info(res.data.message || '没有新岗位入库')
    }
  } catch (e) {
    Message.error(e.response?.data?.detail || 'AI 生成失败')
  } finally {
    generating.value = false
  }
}

/* ---- 跳转：诊断 / 面试（带 JD） ---- */
function diagnoseWith(j) {
  if (!j.jd || j.jd.trim().length < 20) {
    Message.warning('该岗位缺少完整 JD，请先编辑补全')
    return
  }
  router.push({ path: '/app/analyze', query: { jd: j.jd } })
}

function interviewWith(j) {
  if (!j.jd || j.jd.trim().length < 20) {
    Message.warning('该岗位缺少完整 JD，请先编辑补全')
    return
  }
  router.push(`/app/interview?jd=${encodeURIComponent(j.jd)}`)
}

function onEscKey(e) {
  if (e.key === 'Escape' && formOpen.value) closeForm()
}

onMounted(() => {
  loadAll()
  window.addEventListener('keydown', onEscKey)
})

onUnmounted(() => window.removeEventListener('keydown', onEscKey))
</script>
