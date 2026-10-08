<template>
  <div class="max-w-6xl mx-auto px-6 md:px-8 py-12 md:py-16">

    <!-- ============ 答题 / 战报回看：activeTaskId 非空时渲染答题区 ============ -->
    <div v-if="activeTaskId">
      <div class="flex items-center gap-3 mb-6">
        <button @click="backToList"
          class="text-xs text-ink-faint hover:text-accent transition-colors">
          ← 返回大厅
        </button>
      </div>

      <div v-if="loadingSession"
        class="max-w-3xl mx-auto bg-panel border border-line rounded-lg p-10 text-center
          text-sm text-ink-faint">加载中…</div>

      <div v-else class="max-w-3xl mx-auto">

        <!-- 得分战报卡（交卷后） -->
        <div v-if="report"
          class="bg-panel border border-line rounded-lg p-6 md:p-8 mb-6 text-center">
          <div class="text-xs text-ink-sub mb-3">本场战报 · {{ direction || '未填方向' }}</div>
          <div class="flex items-end justify-center gap-2 mb-2">
            <span class="text-5xl font-bold leading-none bg-gradient-to-r from-accent to-accent-hover
              bg-clip-text text-transparent">{{ report.score }}</span>
            <span class="text-sm text-ink-faint mb-1">分</span>
          </div>
          <p class="text-xs text-ink-faint">
            正确 {{ report.correct_count }} / {{ report.total }} 题
            · 正确率 {{ report.total ? Math.round((report.correct_count / report.total) * 100) : 0 }}%
          </p>
        </div>

        <!-- 进度 -->
        <div class="flex items-center justify-between mb-4 text-xs text-ink-faint">
          <span>共 {{ quizQuestions.length }} 题 · 已答 {{ answeredCount }}</span>
          <span>{{ finished ? '本场已交卷' : (direction || '') }}</span>
        </div>

        <!-- 逐题卡片 -->
        <div class="space-y-4 mb-8">
          <div v-for="(q, qi) in quizQuestions" :key="q.id"
            class="bg-panel border border-line rounded-lg p-5">
            <div class="flex items-start gap-2.5 mb-3">
              <span class="text-xs font-mono text-ink-faint mt-0.5 shrink-0">{{ qi + 1 }}.</span>
              <p class="text-sm text-ink leading-relaxed flex-1">{{ q.stem }}</p>
              <span v-if="finished" class="text-xs font-mono shrink-0"
                :class="q.correct === true ? 'text-ok' : q.correct === false ? 'text-bad' : 'text-warn'">
                {{ q.correct === true ? '✓' : q.correct === false ? '✗' : '? 待自评' }}
              </span>
            </div>

            <!-- 选择/逻辑/数量题：radio 选项（A/B/C/D 前缀） -->
            <div v-if="q.options && q.options.length" class="space-y-2">
              <label v-for="(opt, oi) in q.options" :key="oi"
                class="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg border text-sm
                  cursor-pointer transition-colors"
                :class="optionCls(q, oi)">
                <input type="radio" :name="q.id" :value="oi" v-model="pickedMap[q.id]"
                  :disabled="finished" class="accent-accent shrink-0" />
                <span class="font-mono text-xs text-ink-faint shrink-0">{{ letter(oi) }}</span>
                <span class="text-ink leading-relaxed">{{ opt }}</span>
              </label>
            </div>

            <!-- 编程思路题：textarea -->
            <textarea v-else v-model="pickedMap[q.id]" rows="5" :disabled="finished"
              placeholder="用文字描述你的解题思路：核心数据结构/算法、关键步骤、复杂度…"
              class="w-full px-4 py-3 rounded-lg bg-inset border border-line text-sm text-ink
                placeholder:text-ink-faint focus:border-accent focus:outline-none
                transition-colors resize-y leading-relaxed disabled:opacity-70"></textarea>

            <!-- 交卷后：正确答案 + AI 点评 + 解析折叠 -->
            <div v-if="finished" class="mt-3 pt-3 border-t border-line space-y-2">
              <p class="text-xs">
                <span class="text-ink-faint">正确答案：</span>
                <span class="text-ok">{{ answerText(q) }}</span>
              </p>
              <p v-if="q.comment" class="text-xs leading-relaxed">
                <span class="text-ink-faint">AI 点评：</span>
                <span class="text-ink-sub">{{ q.comment }}</span>
              </p>
              <button @click="toggleAnalysis(q.id)"
                class="text-xs text-accent hover:underline">
                {{ showAnalysis[q.id] ? '收起解析 ▲' : '查看解析 ▼' }}
              </button>
              <p v-if="showAnalysis[q.id]"
                class="text-xs text-ink-sub leading-relaxed bg-inset rounded-lg p-3">
                {{ q.analysis || '（暂无解析）' }}
              </p>
            </div>
          </div>
        </div>

        <!-- 交卷 / 再练一组 -->
        <div v-if="!finished" class="flex justify-end">
          <button @click="confirmSubmit" :disabled="submitting"
            class="px-8 py-3 text-sm font-medium rounded-lg bg-accent text-white
              hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed
              transition-colors">
            {{ submitting ? 'AI 正在批卷…' : '交卷' }}
          </button>
        </div>
        <div v-else class="flex justify-end">
          <button @click="backToList"
            class="px-8 py-3 text-sm font-medium rounded-lg bg-accent text-white
              hover:bg-accent-hover transition-colors">
            再练一组
          </button>
        </div>
      </div>
    </div>

    <!-- ============ 大厅：页头 + 发起表单 + 最近练习 + 错题本 ============ -->
    <div v-else>

      <div class="text-center mb-10">
        <div class="inline-flex items-center justify-center w-16 h-16 rounded-lg mb-5
          bg-accent/10 border border-line">
          <span class="text-3xl">📝</span>
        </div>
        <h1 class="text-3xl font-semibold mb-2 tracking-tight">
          <span class="bg-gradient-to-r from-ink to-accent bg-clip-text text-transparent">刷题工坊</span>
        </h1>
        <div class="h-0.5 w-14 rounded-full bg-gradient-to-r from-accent to-accent-hover/0"></div>
        <p class="text-sm text-ink-sub max-w-xl mx-auto mt-4">
          填写岗位方向（可选绑 JD），AI 出题官按真实笔试题型配比出卷——
          技术选择 / 行测逻辑 / 数量关系 / 编程思路，交卷即出解析与战报，错题自动进错题本。
        </p>
      </div>

      <!-- 发起刷题 -->
      <div class="bg-panel border border-line rounded-lg p-6 md:p-8 mb-10 max-w-3xl mx-auto">
        <div class="space-y-5">
          <div>
            <label class="block text-xs font-medium text-ink-sub mb-2">岗位方向 <span class="text-warn">*</span></label>
            <input v-model="form.direction" maxlength="40"
              placeholder="如：Python 后端 / 产品经理 / 数据分析"
              class="w-full px-4 py-3 rounded-lg bg-inset border border-line text-sm text-ink
                placeholder:text-ink-faint focus:border-accent focus:outline-none
                transition-colors" />
          </div>

          <div>
            <div class="flex items-center justify-between mb-2 gap-2 flex-wrap">
              <label class="block text-xs font-medium text-ink-sub">绑定岗位 JD（可选）</label>
              <div class="flex items-center gap-2">
                <!-- M64 岗位库选取：一键带入库内岗位 JD（空库时引导去添加） -->
                <select v-if="libJobs.length" v-model="libJobId" @change="applyLibraryJob"
                  class="px-2.5 py-1.5 rounded-lg bg-inset border border-line text-xs text-ink-sub
                    focus:border-accent focus:outline-none transition-colors max-w-[220px]">
                  <option value="">从岗位库选取…</option>
                  <option v-for="j in libJobs" :key="j.id" :value="String(j.id)">
                    {{ j.company || '公司待定' }} · {{ j.title }}
                  </option>
                </select>
                <RouterLink v-else to="/app/jobs"
                  class="text-xs text-accent hover:underline whitespace-nowrap">
                  从岗位库选取（先去添加岗位）→
                </RouterLink>
                <span class="text-xs font-mono"
                  :class="jdLength <= 6000 ? 'text-ink-faint' : 'text-warn'">
                  {{ jdLength }}/6000
                </span>
              </div>
            </div>
            <textarea v-model="form.jdText" rows="5" maxlength="6000"
              placeholder="粘贴 JD 后出题更贴合岗位考察点；不填则按岗位方向出题"
              class="w-full px-4 py-3 rounded-lg bg-inset border border-line text-sm text-ink
                placeholder:text-ink-faint focus:border-accent focus:outline-none
                transition-colors resize-y leading-relaxed"></textarea>
          </div>

          <div>
            <label class="block text-xs font-medium text-ink-sub mb-2">题量</label>
            <select v-model.number="form.count"
              class="w-full px-4 py-3 rounded-lg bg-inset border border-line text-sm text-ink
                focus:border-accent focus:outline-none transition-colors">
              <option :value="5">5 题 · 快速热身</option>
              <option :value="8">8 题 · 标准练习</option>
              <option :value="10">10 题</option>
              <option :value="15">15 题</option>
              <option :value="20">20 题 · 全真模拟</option>
            </select>
          </div>

          <div class="flex items-center justify-between">
            <p class="text-xs text-ink-faint">出题约需 20-60 秒，由已配置的大模型生成</p>
            <button @click="generateQuiz" :disabled="!canStart || generating"
              class="px-8 py-3 text-sm font-medium rounded-lg bg-accent text-white
                hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed
                transition-colors">
              {{ generating ? 'AI 正在出题…' : '开始刷题' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 最近的练习 -->
      <div class="max-w-3xl mx-auto">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-base font-semibold text-ink">最近的练习</h2>
          <button @click="loadSessions" :disabled="loadingSessions"
            class="text-xs text-ink-faint hover:text-accent transition-colors">
            {{ loadingSessions ? '刷新中…' : '刷新' }}
          </button>
        </div>

        <div v-if="!sessions.length && !loadingSessions"
          class="bg-panel border border-line rounded-lg p-10 text-center">
          <div class="text-3xl mb-3">📝</div>
          <div class="text-sm font-medium text-ink mb-1.5">还没有练习记录</div>
          <p class="text-xs text-ink-faint max-w-xs mx-auto leading-relaxed">
            从上方填写岗位方向发起第一组刷题；也可以绑定岗位库里的 JD 定向练习
          </p>
        </div>

        <div v-else class="space-y-3">
          <div v-for="s in sessions" :key="s.task_id"
            class="bg-panel border border-line rounded-lg p-5 cursor-pointer
              hover:border-accent transition-colors group"
            @click="enterSession(s.task_id)">
            <div class="flex items-center gap-2.5 flex-wrap">
              <span class="text-xs px-2 py-0.5 rounded-md bg-accent/10 text-accent">
                {{ s.direction || '未填方向' }}
              </span>
              <span class="text-xs px-2 py-0.5 rounded-md"
                :class="s.status === 'finished' ? 'bg-ok/10 text-ok' : 'bg-warn/10 text-warn'">
                {{ s.status === 'finished' ? '已完成' : '进行中' }}
              </span>
              <span class="text-xs text-ink-faint">{{ s.total }} 题</span>
              <span v-if="s.score != null" class="text-xs font-mono font-medium"
                :class="s.score >= 80 ? 'text-ok' : s.score >= 60 ? 'text-accent' : 'text-warn'">
                {{ s.score }} 分
              </span>
              <span class="ml-auto text-xs text-ink-faint font-mono">
                {{ (s.updated_at || '').slice(0, 16).replace('T', ' ') }}
              </span>
              <!-- hover 删除（阻止冒泡避免误触恢复） -->
              <button @click.stop="confirmDelete(s.task_id)" title="删除此会话"
                class="opacity-0 group-hover:opacity-100 text-xs text-ink-faint
                  hover:text-warn transition-all shrink-0">删除</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 错题本（折叠区） -->
      <div class="max-w-3xl mx-auto mt-10">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-base font-semibold text-ink">错题本</h2>
          <button @click="wrongOpen = !wrongOpen"
            class="text-xs text-ink-faint hover:text-accent transition-colors">
            {{ wrongOpen ? '收起' : `展开（${wrongItems.length}）` }}
          </button>
        </div>

        <div v-if="wrongOpen">
          <div v-if="!wrongItems.length"
            class="bg-panel border border-line rounded-lg p-8 text-center">
            <div class="text-2xl mb-2">🎉</div>
            <p class="text-xs text-ink-faint">暂无错题——继续保持！</p>
          </div>
          <div v-else class="space-y-3">
            <div v-for="w in wrongItems" :key="w.task_id + '-' + w.qid"
              class="bg-panel border border-line rounded-lg p-5">
              <div class="flex items-center gap-2 mb-2 flex-wrap">
                <span class="text-xs px-2 py-0.5 rounded-md bg-bad/10 text-bad">
                  {{ qtypeLabel(w.qtype) }}
                </span>
                <span class="text-xs px-2 py-0.5 rounded-md bg-inset text-ink-sub">
                  {{ w.direction || '未填方向' }}
                </span>
                <span class="ml-auto text-xs text-ink-faint font-mono">
                  {{ (w.updated_at || '').slice(0, 16).replace('T', ' ') }}
                </span>
              </div>
              <button @click="toggleWrong(w.task_id + '-' + w.qid)"
                class="text-sm text-ink text-left leading-relaxed hover:text-accent
                  transition-colors w-full">
                {{ w.stem }}
              </button>
              <div v-if="wrongExpanded[w.task_id + '-' + w.qid]"
                class="mt-3 pt-3 border-t border-line space-y-1.5">
                <p class="text-xs">
                  <span class="text-ink-faint">正确答案：</span>
                  <span class="text-ok">{{ answerText(w) }}</span>
                </p>
                <p class="text-xs leading-relaxed">
                  <span class="text-ink-faint">解析：</span>
                  <span class="text-ink-sub">{{ w.analysis || '（暂无解析）' }}</span>
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import api from '../api'

const route = useRoute()
const router = useRouter()

// 当前激活会话：支持 /app/quiz?task_id=xxx 直接恢复（刷新不丢）
const activeTaskId = ref(route.query.task_id || '')

/* ---- 大厅状态 ---- */
const sessions = ref([])
const loadingSessions = ref(false)
const generating = ref(false)
const libJobs = ref([])
const libJobId = ref('')
const form = reactive({ direction: '', jdText: '', count: 8 })
const jdLength = computed(() => form.jdText.trim().length)
const canStart = computed(() =>
  form.direction.trim().length >= 1 &&
  form.direction.trim().length <= 40 &&
  jdLength.value <= 6000)

/* ---- 答题状态 ---- */
const loadingSession = ref(false)
const submitting = ref(false)
const direction = ref('')
const quizQuestions = ref([])
const pickedMap = reactive({})
const report = ref(null)
const showAnalysis = reactive({})
const wrongExpanded = reactive({})

const finished = computed(() => report.value !== null)
const answeredCount = computed(() =>
  quizQuestions.value.filter((q) => {
    const v = pickedMap[q.id]
    return v !== undefined && v !== null && v !== ''
  }).length)

function letter(i) {
  return String.fromCharCode(65 + i)
}

function qtypeLabel(t) {
  return { choice: '技术选择', logic: '行测逻辑', math: '数量关系', code: '编程思路' }[t] || '题目'
}

// answer 展示：选择题下标 → 「B. 选项文本」；编程题直接展示要点文本
function answerText(q) {
  if (typeof q.answer === 'number' && q.options && q.options[q.answer] !== undefined) {
    return `${letter(q.answer)}. ${q.options[q.answer]}`
  }
  return String(q.answer ?? '—')
}

function optionCls(q, oi) {
  if (finished.value) {
    // 交卷后：正确项标绿、选错的标红
    if (typeof q.answer === 'number' && oi === q.answer) return 'border-ok bg-ok/10'
    if (pickedMap[q.id] === oi && q.correct === false) return 'border-bad bg-bad/10'
    return 'border-line opacity-70'
  }
  return pickedMap[q.id] === oi
    ? 'border-accent bg-accent/5'
    : 'border-line hover:border-accent'
}

function toggleAnalysis(qid) {
  showAnalysis[qid] = !showAnalysis[qid]
}

function toggleWrong(key) {
  wrongExpanded[key] = !wrongExpanded[key]
}

/* ---- 会话进入/恢复 ---- */
function enterSession(taskId) {
  activeTaskId.value = taskId
  router.replace({ query: { task_id: taskId } })
  loadQuizSession(taskId)
}

function backToList() {
  activeTaskId.value = ''
  router.replace({ query: {} })
  resetQuizState()
  loadSessions()
}

function resetQuizState() {
  quizQuestions.value = []
  report.value = null
  direction.value = ''
  Object.keys(pickedMap).forEach((k) => delete pickedMap[k])
  Object.keys(showAnalysis).forEach((k) => delete showAnalysis[k])
}

async function loadQuizSession(taskId) {
  loadingSession.value = true
  resetQuizState()
  try {
    const res = await api.quizGet(taskId)
    const body = res.data
    if (!body.exists) {
      Message.warning('会话不存在或已被删除')
      activeTaskId.value = ''
      router.replace({ query: {} })
      return
    }
    direction.value = body.direction || ''
    if (body.status === 'finished') {
      // 已完成：完整题 + 判定结果合并渲染
      const byQid = {}
      for (const a of body.answers || []) byQid[a.qid] = a
      quizQuestions.value = (body.questions || []).map((q) => ({
        ...q,
        picked: byQid[q.id]?.picked ?? null,
        correct: byQid[q.id]?.correct ?? null,
        comment: byQid[q.id]?.comment || '',
      }))
      report.value = body.report || null
      // 回填作答（optionCls 判定错选项标红依赖 pickedMap）+ 错题默认展开解析
      for (const q of quizQuestions.value) {
        if (q.picked !== null && q.picked !== undefined) pickedMap[q.id] = q.picked
        if (q.correct !== true) showAnalysis[q.id] = true
      }
    } else {
      quizQuestions.value = (body.questions || []).map((q) => ({ ...q }))
    }
  } catch (e) {
    Message.error('加载会话失败：' + (e?.response?.data?.detail || e.message))
    activeTaskId.value = ''
    router.replace({ query: {} })
  } finally {
    loadingSession.value = false
  }
}

/* ---- 发起刷题 ---- */
async function generateQuiz() {
  if (!canStart.value || generating.value) return
  generating.value = true
  try {
    const res = await api.quizGenerate({
      direction: form.direction.trim(),
      jd_text: form.jdText.trim(),
      count: form.count,
      llm_config: _llmCfg(),
    })
    Message.success('题目已生成，开始作答')
    enterSession(res.data.task_id)
  } catch (e) {
    Message.error(e.response?.data?.detail || '出题失败，请重试')
  } finally {
    generating.value = false
  }
}

// M64 岗位库选取：一键带入库内岗位 JD
function applyLibraryJob() {
  if (!libJobId.value) return
  const j = libJobs.value.find((x) => String(x.id) === libJobId.value)
  if (!j) return
  if (!j.jd || j.jd.trim().length < 20) {
    Message.warning('该岗位缺少完整 JD，请先到岗位库编辑补全')
    libJobId.value = ''
    return
  }
  form.jdText = j.jd.slice(0, 6000)
  Message.success(`已带入「${j.company || ''} ${j.title}」的 JD`)
}

/* ---- 交卷 ---- */
function confirmSubmit() {
  const unanswered = quizQuestions.value.length - answeredCount.value
  if (unanswered > 0) {
    Modal.warning({
      title: `还有 ${unanswered} 题未作答`,
      content: '未作答的题目将按错误计分，确定交卷？',
      hideCancel: false,
      okText: '交卷',
      cancelText: '再看看',
      onOk: submitQuiz,
    })
  } else {
    submitQuiz()
  }
}

async function submitQuiz() {
  if (submitting.value) return
  submitting.value = true
  try {
    const res = await api.quizSubmit(activeTaskId.value, {
      answers: { ...pickedMap },
      llm_config: _llmCfg(),
    })
    const d = res.data
    quizQuestions.value = d.results || []
    report.value = {
      score: d.score, correct_count: d.correct_count, total: d.total, wrong_ids: d.wrong_ids,
    }
    // 错题默认展开解析
    for (const q of quizQuestions.value) {
      if (q.correct !== true) showAnalysis[q.id] = true
    }
    Message.success('交卷完成，战报已生成')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (e) {
    Message.error(e.response?.data?.detail || '交卷失败')
  } finally {
    submitting.value = false
  }
}

/* ---- 列表 / 错题本 ---- */
async function loadSessions() {
  loadingSessions.value = true
  try {
    const res = await api.quizSessions()
    sessions.value = Array.isArray(res.data) ? res.data : []
  } catch (e) { /* 忽略，列表展示为空 */ }
  loadingSessions.value = false
}

const wrongItems = ref([])
const wrongOpen = ref(false)

async function loadWrongbook() {
  try {
    const res = await api.quizWrongbook()
    wrongItems.value = res.data.items || []
  } catch (e) { /* 错题本失败静默 */ }
}

// M37 同款：确认弹窗后删除
function confirmDelete(taskId) {
  Modal.warning({
    title: '确认删除',
    content: '删除后该场练习记录不可恢复，确定继续？',
    hideCancel: false,
    okText: '删除',
    cancelText: '取消',
    onOk: async () => {
      try {
        await api.quizDeleteSession(taskId)
        Message.success('已删除')
        loadSessions()
        loadWrongbook()
      } catch (e) {
        Message.error('删除失败：' + (e?.response?.data?.detail || e.message))
      }
    },
  })
}

function _llmCfg() {
  try {
    const c = JSON.parse(localStorage.getItem('llm_config') || '{}')
    return c.api_key ? c : null
  } catch (e) { return null }
}

onMounted(() => {
  loadSessions()
  loadWrongbook()
  loadLibraryJobs()
  // 支持 /app/quiz?task_id=xxx 深链恢复
  if (activeTaskId.value) loadQuizSession(activeTaskId.value)
})

async function loadLibraryJobs() {
  try {
    const res = await api.listLibraryJobs()
    libJobs.value = res.data.items || []
  } catch (e) { /* 岗位库不可用时不显示下拉，静默 */ }
}
</script>
