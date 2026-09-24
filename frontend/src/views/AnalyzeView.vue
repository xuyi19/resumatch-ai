<template>
  <div class="max-w-6xl mx-auto px-6 md:px-10 py-8 md:py-10">
    <div class="mb-8">
      <h1 class="text-2xl font-semibold tracking-tight mb-1.5">
        <span class="bg-gradient-to-r from-ink to-accent bg-clip-text text-transparent">发起诊断</span>
      </h1>
      <div class="h-0.5 w-14 rounded-full bg-gradient-to-r from-accent to-accent-hover/0"></div>
      <p class="text-sm text-ink-sub mt-2">上传或粘贴简历 + 粘贴岗位 JD，AI 生成针对性诊断报告</p>
    </div>

    <div class="grid lg:grid-cols-2 gap-5 items-start">
      <!-- F1：从简历库预选的提示条 -->
      <div v-if="route.query.resume_id" class="lg:col-span-2 flex items-center gap-2
        px-4 py-2.5 rounded-lg bg-accent/10 border border-accent/30 text-sm text-accent">
        <span>已从简历库选择：{{ route.query.resume_name || `简历 #${route.query.resume_id}` }}</span>
        <span class="text-xs text-ink-faint">（提交时将直接复用该简历）</span>
        <RouterLink :to="{ path: '/app/analyze' }"
          class="ml-auto text-xs text-ink-faint hover:text-ink transition-colors">取消</RouterLink>
      </div>

      <!-- ============ 左栏：简历 ============ -->
      <section class="bg-panel border border-line rounded-lg p-5 md:p-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold flex items-center gap-2">
            <span class="w-5 h-5 rounded bg-gradient-to-br from-accent to-accent-hover text-white
              text-[11px] font-mono flex items-center justify-center shadow-sm shadow-accent/30">1</span>
            简历
          </h2>
          <!-- A1：一键填入示例 -->
          <button @click="fillExample"
            class="text-xs text-accent hover:underline"
            title="填入内置示例，30 秒体验完整流程">
            ▶ 填入示例简历
          </button>
        </div>

        <!-- Tab 切换：上传文件 / 粘贴文本 -->
        <div class="inline-flex p-0.5 rounded-md bg-inset border border-line mb-4">
          <button v-for="t in modes" :key="t.value" @click="mode = t.value"
            class="px-3.5 py-1.5 text-xs font-medium rounded-[5px] transition-colors"
            :class="mode === t.value
              ? 'bg-panel text-ink shadow-sm'
              : 'text-ink-sub hover:text-ink'">
            {{ t.label }}
          </button>
        </div>

        <!-- 上传文件 -->
        <label v-if="mode === 'file'" class="block cursor-pointer">
          <input type="file" accept=".pdf,.docx,.doc" class="hidden" @change="onFileChange" />
          <div class="border-2 border-dashed border-accent/30 rounded-xl px-6 py-12 text-center
            bg-accent/[0.04] hover:border-accent hover:bg-accent/10 hover:shadow-lg hover:shadow-accent/10
            active:scale-[0.99] transition-all duration-150">
            <div class="w-12 h-12 mx-auto mb-3 rounded-xl bg-gradient-to-br from-accent/15 to-accent/5
              border border-accent/20 flex items-center justify-center text-2xl">📄</div>
            <div v-if="!file" class="text-sm text-ink-sub">点击选择简历文件</div>
            <div v-else class="text-sm text-accent font-medium font-mono">{{ file.name }}</div>
            <div class="text-xs text-ink-faint mt-2">支持 .pdf .docx .doc，≤ 10MB</div>
          </div>
        </label>

        <!-- 粘贴文本（A1：在线简历 / 纯文本简历入口） -->
        <div v-else>
          <textarea v-model="pasteText" rows="12"
            placeholder="直接粘贴简历全文（从在线简历 / 文本简历复制即可）"
            class="w-full px-3.5 py-3 text-sm bg-inset rounded-lg border border-line
              resize-none focus:outline-none focus:border-accent
              placeholder:text-ink-faint transition-colors" />
          <div class="text-xs text-ink-faint mt-1.5">
            已粘贴 {{ pasteText.length }} 字（建议 200 字以上）
          </div>
        </div>
      </section>

      <!-- ============ 右栏：JD + 提交 ============ -->
      <section class="bg-panel border border-line rounded-lg p-5 md:p-6
        flex flex-col lg:sticky lg:top-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold flex items-center gap-2">
            <span class="w-5 h-5 rounded text-[11px] font-mono
              flex items-center justify-center shadow-sm shadow-accent/30
              bg-gradient-to-br from-accent to-accent-hover text-white">2</span>
            岗位 JD
          </h2>
          <!-- M19：一键获取岗位 -->
          <button @click="jobPanelOpen = !jobPanelOpen"
            class="text-xs text-accent hover:underline">
            ⚡ {{ jobPanelOpen ? '收起岗位面板' : '一键获取岗位' }}
          </button>
        </div>

        <!-- M19：岗位获取面板（三方数据源检索 / 按简历推荐 / M30 手动导入比对） -->
        <div v-if="jobPanelOpen" class="mb-4 p-3.5 rounded-lg border border-line bg-inset">
          <!-- M30：模式 Tab -->
          <div class="flex gap-1 mb-3">
            <button v-for="t in jobTabs" :key="t.value" @click="jobTab = t.value"
              class="px-3 py-1.5 text-xs rounded-md border transition-colors"
              :class="jobTab === t.value
                ? 'bg-accent/10 text-accent border-accent/30 font-medium'
                : 'text-ink-sub border-line hover:border-line-strong'">
              {{ t.label }}
            </button>
          </div>

          <!-- 搜岗位（数据源检索 / 智能推荐） -->
          <div v-if="jobTab === 'search'">
            <div class="flex gap-2">
              <input v-model="jobKeyword" type="text" placeholder="岗位关键词，如：Python 后端"
                class="flex-1 min-w-0 px-3 py-2 text-sm bg-panel rounded-md border border-line
                  focus:outline-none focus:border-accent placeholder:text-ink-faint" />
              <input v-model="jobCity" type="text" placeholder="城市"
                class="w-20 shrink-0 px-3 py-2 text-sm bg-panel rounded-md border border-line
                  focus:outline-none focus:border-accent placeholder:text-ink-faint" />
              <button @click="fetchJobs" :disabled="jobsLoading"
                class="shrink-0 px-3.5 py-2 text-xs font-medium rounded-md
                  bg-accent text-white hover:bg-accent-hover
                  disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                {{ jobsLoading ? '获取中…' : '获取岗位' }}
              </button>
            </div>
            <div class="text-xs text-ink-faint mt-2 leading-relaxed">
              数据源：{{ jobSourceName }} ·
              {{ canRecommend ? '将按当前粘贴的简历智能推荐' : '按关键词搜索（粘贴简历文本后可智能推荐）' }}
              <RouterLink to="/app/settings" class="text-accent hover:underline">配置数据源 ↗</RouterLink>
            </div>
          </div>

          <!-- 导入比对（M30：手动录入目标公司，与简历匹配排序） -->
          <div v-else-if="jobTab === 'import'">
            <div class="flex gap-2">
              <input v-model="impCompany" type="text" placeholder="公司，如：阿里云"
                class="flex-1 min-w-0 px-3 py-2 text-sm bg-panel rounded-md border border-line
                  focus:outline-none focus:border-accent placeholder:text-ink-faint" />
              <input v-model="impTitle" type="text" placeholder="岗位，如：Java 开发"
                class="flex-1 min-w-0 px-3 py-2 text-sm bg-panel rounded-md border border-line
                  focus:outline-none focus:border-accent placeholder:text-ink-faint" />
              <button @click="addImported"
                class="shrink-0 px-3.5 py-2 text-xs font-medium rounded-md
                  bg-accent text-white hover:bg-accent-hover transition-colors">
                添加
              </button>
            </div>
            <div class="flex gap-2 mt-2">
              <input v-model="impCity" type="text" placeholder="城市（可选）"
                class="w-28 px-3 py-2 text-sm bg-panel rounded-md border border-line
                  focus:outline-none focus:border-accent placeholder:text-ink-faint" />
              <input v-model="impSalary" type="text" placeholder="薪资（可选）"
                class="w-32 px-3 py-2 text-sm bg-panel rounded-md border border-line
                  focus:outline-none focus:border-accent placeholder:text-ink-faint" />
            </div>

            <div v-if="importedList.length" class="mt-2.5 flex flex-wrap gap-1.5">
              <span v-for="(c, i) in importedList" :key="i"
                class="inline-flex items-center gap-1 pl-2.5 pr-1 py-1 rounded-md text-xs
                  bg-panel border border-line group">
                <span class="truncate max-w-[200px]" :title="`${c.company} · ${c.title}`">
                  {{ c.company }} · {{ c.title }}<template v-if="c.city">（{{ c.city }}）</template>
                </span>
                <button @click="removeImported(i)" title="移除"
                  class="w-4 h-4 shrink-0 rounded flex items-center justify-center
                    text-ink-faint hover:text-bad transition-colors">×</button>
              </span>
            </div>

            <div class="flex items-center gap-3 mt-3">
              <button @click="matchImported" :disabled="jobsLoading || !importedList.length"
                class="px-3.5 py-2 text-xs font-medium rounded-md
                  bg-accent text-white hover:bg-accent-hover
                  disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                {{ jobsLoading ? '比对中…' : `与简历比对（${importedList.length}）` }}
              </button>
              <span class="text-xs text-ink-faint">
                {{ canRecommend ? '将逐家计算匹配分并排序' : '需先在左侧粘贴简历文本（≥100 字）' }}
              </span>
            </div>
          </div>

          <!-- M51：收藏夹已并入岗位库（localStorage 收藏由岗位库页迁移引导接管） -->

          <!-- 结果区（搜岗位 / 导入比对两种模式共用） -->
          <div v-if="jobsError" class="mt-3 p-2.5 rounded-md text-xs bg-bad/10 border border-bad/30 text-bad">
            {{ jobsError }}
          </div>
          <div v-else-if="jobsLoading" class="mt-3 text-xs text-ink-faint py-4 text-center">
            正在获取岗位…
          </div>
          <div v-else-if="jobList.length" class="mt-3 space-y-2 max-h-80 overflow-y-auto pr-1">
            <div v-for="j in jobList" :key="j.id" class="p-3 rounded-md border border-line bg-panel">
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <div class="text-sm font-medium truncate">{{ j.title }}</div>
                  <div class="text-xs text-ink-faint mt-0.5 truncate font-mono">
                    {{ j.company || '—' }} · {{ j.city || '—' }} · {{ j.salary || '薪资面议' }}
                  </div>
                </div>
                <div class="flex items-center gap-2 shrink-0">
                  <span v-if="j.score != null"
                    class="px-1.5 py-0.5 rounded text-[11px] font-mono"
                    :class="j.score >= 70 ? 'bg-ok/10 text-ok' : j.score >= 40 ? 'bg-warn/10 text-warn' : 'bg-inset text-ink-faint'">
                    {{ j.score }}分
                  </span>
                </div>
              </div>
              <div v-if="j.reason" class="text-xs text-ink-sub mt-1.5">{{ j.reason }}</div>
              <div class="flex items-center gap-3 mt-2">
                <button @click="useJob(j)" class="text-xs text-accent hover:underline">
                  用此岗位诊断 →
                </button>
                <button @click="addToLibrary(j)" :disabled="inLibrary.has(j.id)"
                  class="text-xs transition-colors"
                  :class="inLibrary.has(j.id) ? 'text-ink-faint cursor-default' : 'text-accent hover:underline'">
                  {{ inLibrary.has(j.id) ? '✓ 已入库' : '＋ 入库' }}
                </button>
                <a v-if="j.url" :href="j.url" target="_blank" rel="noopener"
                  class="text-xs text-ink-faint hover:text-accent">原文 ↗</a>
                <span class="text-[11px] text-ink-faint ml-auto shrink-0">{{ j.source }}</span>
              </div>
            </div>
          </div>
          <div v-else class="mt-3 text-xs text-ink-faint py-4 text-center">
            {{ jobTab === 'search' ? '输入关键词后点击「获取岗位」' : '录入目标公司后点击「与简历比对」' }}
          </div>
          <div v-if="jobsNotice" class="text-xs text-warn mt-2">{{ jobsNotice }}</div>
        </div>

        <textarea v-model="jdText" rows="10"
          placeholder="粘贴目标岗位的 JD 文本&#10;&#10;可以从 BOSS、智联、拉勾等平台复制岗位描述，直接粘贴到此处。"
          class="w-full px-3.5 py-3 text-sm bg-inset rounded-lg border border-line
            resize-none focus:outline-none focus:border-accent
            placeholder:text-ink-faint transition-colors" />
        <div class="text-xs text-ink-faint mt-1.5">
          已输入 {{ jdText.length }} 字（至少 20 字）
        </div>

        <!-- F2：最近使用的 JD 一键复用 -->
        <div v-if="recentJds.length" class="mt-4">
          <div class="text-xs text-ink-faint mb-2">最近使用</div>
          <div class="flex flex-wrap gap-1.5">
            <span v-for="(j, i) in recentJds" :key="j.ts"
              class="inline-flex items-center gap-1 pl-2.5 pr-1 py-1 rounded-md text-xs
                bg-inset border border-line max-w-[240px] group">
              <button @click="useRecentJd(j)" :title="j.text"
                class="truncate text-ink-sub group-hover:text-accent transition-colors">
                {{ j.title }}
              </button>
              <button @click="removeRecentJd(i)" title="删除该记录"
                class="w-4 h-4 shrink-0 rounded flex items-center justify-center
                  text-ink-faint hover:text-bad transition-colors">×</button>
            </span>
          </div>
        </div>

        <!-- 提交 -->
        <div class="mt-6 pt-5 border-t border-line">
          <button @click="startAnalyze" :disabled="loading || !canSubmit"
            class="w-full py-3 rounded-lg text-sm font-medium
              bg-accent text-white hover:bg-accent-hover
              disabled:opacity-40 disabled:cursor-not-allowed
              active:scale-[0.99] transition-all duration-150">
            {{ loading ? '启动中…' : '🚀 开始诊断' }}
          </button>
          <div class="text-center text-xs text-ink-faint mt-3 font-mono">
            诊断约需 60-90 秒 · 全程实时流式进度
          </div>
        </div>
      </section>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import api from '../api'
import { RouterLink } from 'vue-router'
import { EXAMPLE_RESUME, EXAMPLE_JD } from '../data/example'
import { useKeyGuide } from '../composables/useKeyGuide'
import { JOB_SOURCES, loadJobSource } from '../data/jobSources'

const route = useRoute()
const router = useRouter()
const guide = useKeyGuide()

const modes = [
  { label: '上传文件', value: 'file' },
  { label: '粘贴文本', value: 'paste' },
]

const mode = ref('file')
const file = ref(null)
const pasteText = ref('')
const jdText = ref('')
const loading = ref(false)

/* ---- F2：JD 最近 5 条（localStorage） ---- */
const JD_KEY = 'resumatch_jd_recent'
const recentJds = ref(loadRecentJds())

function loadRecentJds() {
  try {
    return JSON.parse(localStorage.getItem(JD_KEY) || '[]').slice(0, 5)
  } catch (e) {
    return []
  }
}

function saveRecentJd(text) {
  const t = text.trim()
  if (!t) return
  const items = loadRecentJds().filter((j) => j.text !== t)
  const title = (t.split('\n')[0] || '').trim().slice(0, 24) || '未命名岗位'
  items.unshift({ title, text: t, ts: Date.now() })
  recentJds.value = items.slice(0, 5)
  try {
    localStorage.setItem(JD_KEY, JSON.stringify(recentJds.value))
  } catch (e) {}
}

function useRecentJd(j) {
  jdText.value = j.text
}

function removeRecentJd(i) {
  recentJds.value.splice(i, 1)
  try {
    localStorage.setItem(JD_KEY, JSON.stringify(recentJds.value))
  } catch (e) {}
}

/* ---- A1：示例一键填入 ---- */
function fillExample() {
  mode.value = 'paste'
  pasteText.value = EXAMPLE_RESUME
  jdText.value = EXAMPLE_JD
  Message.success('已填入示例简历与 JD，点击「开始诊断」即可体验')
}

const canSubmit = computed(() => {
  const resumeOk =
    mode.value === 'file' ? !!file.value : pasteText.value.trim().length >= 50
  return resumeOk && jdText.value.trim().length >= 20
})

function onFileChange(e) {
  file.value = e.target.files[0] || null
}

async function startAnalyze() {
  // A5：未配置 Key 先引导，不发请求
  await guide.refresh()
  if (guide.state.needGuide) {
    guide.showGuide()
    Message.warning('请先配置 AI 服务（API Key）')
    return
  }

  const fromLibrary = !!route.query.resume_id
  // F1：简历库预选时简历侧已就绪，只校验 JD
  if (!fromLibrary && !canSubmit.value) {
    Message.warning(
      mode.value === 'file'
        ? '请上传简历并粘贴至少 20 字的岗位 JD'
        : '请粘贴完整简历（≥50 字）并填写至少 20 字的岗位 JD',
    )
    return
  }
  if (fromLibrary && jdText.value.trim().length < 20) {
    Message.warning('请填写至少 20 字的岗位 JD')
    return
  }

  loading.value = true
  try {
    // 1. 简历入库（F1：从简历库预选则直接复用，跳过上传）/ 文件上传 / 文本直存
    let resumeId = route.query.resume_id ? Number(route.query.resume_id) : null
    let resumeName = String(route.query.resume_name || '')
    if (resumeId) {
      loading.value = false
    } else if (mode.value === 'file') {
      const up = await api.uploadResume(file.value)
      resumeId = up.data.id
      resumeName = file.value?.name || ''
    } else {
      const up = await api.uploadResumeText({
        filename: '粘贴的简历.txt',
        text: pasteText.value.trim(),
      })
      resumeId = up.data.id
      resumeName = '粘贴的简历.txt'
      if (up.data?.duplicated) {
        Message.info('简历库中已有内容相同的简历，已直接复用（未新建记录）')
      }
    }

    // 2. 构建请求
    let cfg = {}
    try { cfg = JSON.parse(localStorage.getItem('llm_config') || '{}') } catch (e) {}

    const body = {
      resume_id: resumeId,
      jd_text: jdText.value.trim(),
      resume_name: resumeName,
    }
    if (cfg.api_key) body.llm_config = cfg

    // 3. 启动 + F2 记录 JD
    saveRecentJd(jdText.value)
    const res = await api.startLiveAnalyze(body)
    router.push(`/app/result/${res.data.task_id}`)
  } catch (e) {
    console.error(e)
    // 409：已有进行中的任务——引导前往（可继续追问或放弃）
    const activeId = e.response?.headers?.['x-active-task']
    if (e.response?.status === 409 && activeId) {
      Modal.confirm({
        title: '已有进行中的诊断任务',
        content: '可前往该任务继续（回答追问/查看进度），或在其页面放弃后重新发起。',
        okText: '前往该任务',
        cancelText: '留在此页',
        onOk: () => router.push(`/app/result/${activeId}`),
      })
    } else {
      Message.error('失败：' + (e.response?.data?.detail || e.message))
    }
    loading.value = false
  }
}

/* ================================ M19：一键获取岗位 ================================ */

const jobPanelOpen = ref(false)
const jobKeyword = ref('')
const jobCity = ref('')
const jobsLoading = ref(false)
const jobList = ref([])
const jobsError = ref('')
const jobsNotice = ref('')

/* ---- M30：导入比对（手动录入目标公司，localStorage 持久化） ---- */
const jobTabs = computed(() => [
  { label: '搜岗位', value: 'search' },
  { label: '导入比对', value: 'import' },
])
const jobTab = ref('search')
const IMPORT_KEY = 'resumatch_imported_companies'
const impCompany = ref('')
const impTitle = ref('')
const impCity = ref('')
const impSalary = ref('')
const importedList = ref(loadImported())

/* M51：localStorage 收藏夹已并入岗位库——岗位卡「＋ 入库」直达，旧数据由岗位库页迁移引导接管 */

function loadImported() {
  try {
    return JSON.parse(localStorage.getItem(IMPORT_KEY) || '[]').slice(0, 20)
  } catch (e) {
    return []
  }
}

function persistImported() {
  try {
    localStorage.setItem(IMPORT_KEY, JSON.stringify(importedList.value))
  } catch (e) {}
}

function addImported() {
  const company = impCompany.value.trim()
  const title = impTitle.value.trim()
  if (!company || !title) {
    Message.warning('公司和岗位都要填')
    return
  }
  if (importedList.value.length >= 20) {
    Message.warning('最多导入 20 家，先移除一些再添加')
    return
  }
  importedList.value.push({
    company, title,
    city: impCity.value.trim(),
    salary: impSalary.value.trim(),
    jd: '',
  })
  persistImported()
  impCompany.value = ''
  impTitle.value = ''
  impCity.value = ''
  impSalary.value = ''
}

function removeImported(i) {
  importedList.value.splice(i, 1)
  persistImported()
}

async function matchImported() {
  if (!canRecommend.value) {
    Message.warning('请先在左侧「粘贴文本」模式录入简历全文（≥100 字）')
    return
  }
  jobsLoading.value = true
  jobsError.value = ''
  jobsNotice.value = ''
  let llmCfg = {}
  try { llmCfg = JSON.parse(localStorage.getItem('llm_config') || '{}') } catch (e) {}
  try {
    const res = await api.importMatchJobs({
      resume_text: pasteText.value.trim().slice(0, 6000),
      items: importedList.value,
      llm_config: llmCfg,
    })
    jobList.value = res.data.items || []
    if (res.data.degraded) jobsNotice.value = res.data.degraded_reason || ''
    if (!jobList.value.length) jobsNotice.value = '未能生成匹配结果，请重试'
  } catch (e) {
    jobsError.value = e.response?.data?.detail || e.message || '比对失败'
  } finally {
    jobsLoading.value = false
  }
}

const jobCfg = loadJobSource()
const jobSourceName = computed(
  () => JOB_SOURCES.find((s) => s.id === (jobCfg.provider || 'mock'))?.name || '示例数据',
)
// 粘贴了足够长的简历文本 → 走智能推荐（粗筛 + LLM 精排），否则纯关键词搜索
const canRecommend = computed(
  () => mode.value === 'paste' && pasteText.value.trim().length >= 100,
)

const JOB_ERR_TEXT = {
  invalid_key: 'API Key 无效或未授权，请到设置页检查数据源配置',
  quota: '免费配额已用尽或请求过快，请稍后再试',
  network: '网络连接失败：请检查网络与代理设置',
  maintenance: '数据源暂时维护中，请稍后再试或换用其他数据源',
}

async function fetchJobs() {
  if (!jobKeyword.value.trim()) {
    Message.warning('请输入岗位关键词')
    return
  }
  jobsLoading.value = true
  jobsError.value = ''
  jobsNotice.value = ''
  try {
    const base = {
      provider: jobCfg.provider || 'mock',
      api_key: jobCfg.api_key || '',
      api_id: jobCfg.api_id || '',
      keyword: jobKeyword.value.trim(),
      city: jobCity.value.trim(),
      page: 1,
    }
    let res
    let llmCfg = {}
    try { llmCfg = JSON.parse(localStorage.getItem('llm_config') || '{}') } catch (e) {}
    if (canRecommend.value) {
      res = await api.recommendJobs({
        ...base,
        resume_text: pasteText.value.trim().slice(0, 6000),
        llm_config: llmCfg,
      })
    } else {
      // ai 数据源生成岗位画像需要模型配置；其他数据源忽略该字段
      res = await api.searchJobs({ ...base, llm_config: llmCfg })
    }

    const d = res.data
    if (d.error) {
      jobsError.value = JOB_ERR_TEXT[d.error] || d.message || '获取岗位失败'
      jobList.value = []
      return
    }
    jobList.value = d.items || []
    if (d.fallback) jobsNotice.value = '示例数据无该关键词岗位，已展示全部示例'
    if (d.degraded) jobsNotice.value = d.degraded_reason || ''
    if (canRecommend.value && !jobList.value.length && !jobsNotice.value) {
      jobsNotice.value = '未找到匹配岗位，试试更宽泛的关键词'
    }
  } catch (e) {
    jobsError.value = e.response?.data?.detail || e.message || '获取岗位失败'
  } finally {
    jobsLoading.value = false
  }
}

function useJob(j) {
  const header = `【岗位】${j.title}\n【公司】${j.company || '—'}｜【城市】${j.city || '—'}` +
    (j.salary ? `｜【薪资】${j.salary}` : '')
  jdText.value = `${header}\n\n${j.jd_text}`
  saveRecentJd(jdText.value)
  Message.success('已填入岗位 JD，可继续编辑后开始诊断')
}

/* ---- M45 岗位面板一键入库（saved_jobs 落库，侧栏「岗位库」统一管理） ---- */
const inLibrary = reactive(new Set())

async function addToLibrary(j) {
  try {
    await api.addLibraryJobs([{
      title: j.title,
      company: j.company || '',
      city: j.city || '',
      salary: j.salary || '',
      jd: j.jd_text || '',
      url: j.url || '',
    }], 'ai')
    inLibrary.add(j.id)
    Message.success('已加入岗位库（侧栏「岗位库」可管理与匹配）')
  } catch (e) {
    Message.error(e.response?.data?.detail || '入库失败')
  }
}

/* 岗位库「用此岗位诊断」带 JD 跳入：预填表单 */
function applyQueryJd() {
  const jd = String(route.query.jd || '').trim()
  if (jd.length >= 20) {
    jdText.value = jd
    saveRecentJd(jd)
    Message.success('已填入岗位 JD，可继续编辑后开始诊断')
  }
}

onMounted(applyQueryJd)
</script>
