<template>
  <div>

    <!-- 子区切换：面试准备 / 模拟面试 -->
    <div class="flex justify-center mb-8">
      <div class="inline-flex gap-2 p-1.5 rounded-lg bg-inset border border-line">
        <button v-for="sec in sections" :key="sec.key"
                @click="section = sec.key"
                class="px-5 py-2.5 text-sm font-medium rounded-md transition-colors"
                :class="section === sec.key
            ? 'bg-accent/10 text-accent'
            : 'text-ink-sub hover:text-ink'">
          {{ sec.icon }} {{ sec.label }}
        </button>
      </div>
    </div>

    <!-- 会话恢复状态：onMount 的 GET 失败必须可见可重试（静默吞错会表现为「Tab 卡死」） -->
    <div v-if="interview.restoring" class="text-center text-xs text-ink-faint py-4">
      正在恢复面试会话…
    </div>
    <div v-else-if="interview.restoreError"
         class="mb-4 flex items-center justify-between bg-warn/10 border border-warn/40
           rounded-lg px-4 py-2.5">
      <span class="text-xs text-warn">面试会话加载失败（服务可能未就绪或已中断）</span>
      <button @click="retryRestore"
        class="text-xs font-medium text-warn hover:text-ink transition-colors">重试</button>
    </div>

    <!-- ============ 面试准备：题单 ============ -->
    <div v-show="section === 'prep'">

      <!-- 空态：生成题单 -->
      <div v-if="!interview.plan.length" class="bg-panel border border-line rounded-lg p-16 text-center">
        <div class="inline-flex items-center justify-center w-24 h-24 rounded-lg mb-6
          bg-inset border border-line">
          <span class="text-4xl">🎤</span>
        </div>
        <div class="text-lg font-semibold text-ink mb-2">面试准备</div>
        <p class="text-sm text-ink-sub max-w-md mx-auto mb-6">
          基于简历与目标岗位，AI 面试官生成 6 道针对性面试题
          （技术基础 / 项目深挖 / 岗位匹配 / 情景行为），附考察点与回答思路。
        </p>
        <button @click="genInterview" :disabled="interview.loading"
          class="px-6 py-2.5 text-sm font-medium rounded-lg bg-accent text-white
            hover:bg-accent-hover disabled:opacity-50 transition-colors">
          {{ interview.loading ? 'AI 出题中…' : '生成面试题单' }}
        </button>
      </div>

      <!-- 题单列表 -->
      <div v-else class="space-y-3">
        <div class="flex items-center justify-between mb-4">
          <div class="text-sm text-ink-sub">
            共 <span class="font-mono text-accent">{{ interview.plan.length }}</span> 题
            · 结合简历与岗位要求重点考察
          </div>
          <button @click="regenerateNext = true; genInterview()" :disabled="interview.loading"
              class="text-xs text-ink-faint hover:text-accent transition-colors">
              {{ interview.loading ? '生成中…' : '重新出题' }}
            </button>
        </div>
        <div v-for="(q, i) in interview.plan" :key="q.id"
             class="bg-panel border border-line rounded-lg p-5">
          <div class="flex items-center gap-2.5 mb-3">
            <span class="w-6 h-6 rounded-md bg-inset border border-line flex items-center
              justify-center text-xs text-accent font-mono shrink-0">{{ i + 1 }}</span>
            <span class="text-xs px-2 py-0.5 rounded-md bg-accent/10 text-accent">{{ q.category }}</span>
            <span v-if="q.focus" class="text-xs text-ink-faint ml-auto">考察点：{{ q.focus }}</span>
          </div>
          <div class="text-sm text-ink leading-relaxed">{{ q.question }}</div>
          <details v-if="q.hint" class="mt-3 group">
            <summary class="text-xs text-ink-faint cursor-pointer hover:text-accent
              transition-colors select-none">💡 查看回答思路</summary>
            <div class="mt-2 pl-3 border-l-2 border-line text-xs text-ink-sub leading-relaxed">
              {{ q.hint }}
            </div>
          </details>
        </div>
      </div>
    </div>

    <!-- ============ 模拟面试：多轮自由对话（M32） ============ -->
    <div v-show="section === 'mock'">

      <!-- 未出题 → 引导先生成 -->
      <div v-if="!interview.plan.length" class="bg-panel border border-line rounded-lg p-16 text-center">
        <div class="inline-flex items-center justify-center w-24 h-24 rounded-lg mb-6
          bg-inset border border-line">
          <span class="text-4xl">🎬</span>
        </div>
        <div class="text-lg font-semibold text-ink mb-2">模拟面试</div>
        <p class="text-sm text-ink-sub max-w-md mx-auto mb-6">
          与 AI 面试官像真实面试一样多轮对话：可被追问、可随时补充，回答充分后自动进入下一题，
          6 题答完出整体总评。请先生成面试题单。
        </p>
        <button @click="section = 'prep'"
          class="px-6 py-2.5 text-sm font-medium rounded-lg bg-accent text-white
            hover:bg-accent-hover transition-colors">
          去生成题单
        </button>
      </div>

      <!-- 对话进行中 -->
      <div v-else class="bg-panel border border-line rounded-lg p-5 md:p-7">

        <!-- 顶部：进度 + 进度条 -->
        <div class="text-sm text-ink-sub mb-2">
          第 <span class="font-mono text-accent">{{ Math.min(interview.currentIndex + 1, interview.plan.length) }}</span>
          / {{ interview.plan.length }} 题
          <span v-if="currentQuestion" class="text-ink-faint">· {{ currentQuestion.category }}</span>
        </div>
        <div class="h-1 rounded-full bg-inset border border-line overflow-hidden mb-4">
          <div class="h-full bg-accent transition-all duration-500"
            :style="{ width: `${(Math.min(interview.currentIndex, interview.plan.length) / interview.plan.length) * 100}%` }"></div>
        </div>

        <!-- 总评 -->
        <div v-if="interview.summary" class="mb-6">
          <div class="flex items-center gap-2 mb-3">
            <span class="text-base font-semibold text-ink">🏁 模拟面试总评</span>
            <span class="text-xs px-2 py-0.5 rounded-md bg-ok/10 text-ok">
              已完成 {{ interview.plan.length }}/{{ interview.plan.length }}</span>
            <button @click="exportReport" :disabled="exporting"
              class="ml-auto text-xs px-3 py-1.5 rounded-md border border-line
                text-ink-sub hover:text-accent hover:border-accent/50
                disabled:opacity-50 transition-colors">
              {{ exporting ? '导出中…' : '📄 导出面试报告' }}
            </button>
          </div>
          <div class="bg-inset border border-line rounded-lg p-5 space-y-4">
            <p class="text-sm text-ink leading-relaxed">{{ interview.summary.overall }}</p>
            <div class="grid md:grid-cols-3 gap-4">
              <div>
                <div class="text-xs text-ok font-medium mb-1.5">✓ 亮点</div>
                <ul class="space-y-1 text-xs text-ink-sub leading-relaxed list-disc pl-4">
                  <li v-for="(s, i) in interview.summary.strengths" :key="i">{{ s }}</li>
                </ul>
              </div>
              <div>
                <div class="text-xs text-warn font-medium mb-1.5">△ 待改进</div>
                <ul class="space-y-1 text-xs text-ink-sub leading-relaxed list-disc pl-4">
                  <li v-for="(w, i) in interview.summary.weaknesses" :key="i">{{ w }}</li>
                </ul>
              </div>
              <div>
                <div class="text-xs text-accent font-medium mb-1.5">→ 建议</div>
                <ul class="space-y-1 text-xs text-ink-sub leading-relaxed list-disc pl-4">
                  <li v-for="(sg, i) in interview.summary.suggestions" :key="i">{{ sg }}</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        <!-- 聊天流 -->
        <div ref="chatBoxRef" class="space-y-4 max-h-[460px] overflow-y-auto pr-1 mb-4">
          <div v-for="(m, i) in interview.chatLog" :key="i">
            <!-- 面试官 -->
            <div v-if="m.role === 'interviewer'" class="flex items-start gap-2.5">
              <span class="w-7 h-7 rounded-md bg-accent/15 text-accent flex items-center
                justify-center text-sm shrink-0">🧑‍💼</span>
              <div class="min-w-0 max-w-[85%]">
                <div class="text-xs text-ink-faint mb-1">
                  面试官<template v-if="qInfo(m.qid)">
                    · 第 {{ qInfo(m.qid).no }} 题 · {{ qInfo(m.qid).category }}</template>
                </div>
                <div class="inline-block rounded-lg rounded-tl-none border px-4 py-2.5"
                  :class="isQuestionMsg(m) ? 'bg-accent/5 border-accent/30' : 'bg-inset border-line'">
                  <span class="text-sm text-ink leading-relaxed whitespace-pre-wrap">{{ m.content }}</span>
                </div>
              </div>
            </div>
            <!-- 候选人 -->
            <div v-else class="flex justify-end">
              <div class="max-w-[85%] rounded-lg rounded-tr-none bg-accent/10 border border-accent/30
                px-4 py-2.5 text-sm text-ink leading-relaxed whitespace-pre-wrap">
                <span class="text-xs text-accent font-medium mr-2">我</span>{{ m.content }}
              </div>
            </div>
          </div>
          <!-- 思考中指示 -->
          <div v-if="interview.submitting" class="flex items-center gap-2 pl-10">
            <span class="w-7 h-7 rounded-md bg-accent/15 text-accent flex items-center
              justify-center text-sm shrink-0">🧑‍💼</span>
            <span class="text-xs text-ink-faint">面试官正在思考…</span>
          </div>
        </div>

        <!-- 输入区 -->
        <div v-if="!interview.summary">
          <details v-if="currentQuestion?.hint" class="mb-2.5">
            <summary class="text-xs text-ink-faint cursor-pointer hover:text-accent
              transition-colors select-none">💡 查看本题回答思路</summary>
            <div class="mt-1.5 pl-3 border-l-2 border-line text-xs text-ink-sub leading-relaxed">
              {{ currentQuestion.hint }}
            </div>
          </details>
          <textarea v-model="interview.answer" rows="3" :disabled="interview.submitting"
            @keydown.enter.exact.prevent="sendChat(false)"
            placeholder="像真实面试一样作答，可分点展开；面试官可能追问，也可随时补充。回答充分后面试官会带你进入下一题"
            class="w-full px-4 py-3 rounded-lg bg-inset border border-line text-sm text-ink
              placeholder:text-ink-faint focus:border-accent focus:outline-none
              transition-colors resize-y"></textarea>
          <div class="flex items-center justify-between mt-3">
            <button @click="sendChat(true)" :disabled="interview.submitting"
              class="text-xs text-ink-faint hover:text-accent transition-colors
                disabled:opacity-40 disabled:cursor-not-allowed">
              本题回答完毕，进入下一题 →
            </button>
            <button @click="sendChat(false)" :disabled="interview.submitting || !interview.answer.trim()"
              class="px-5 py-2 text-sm font-medium rounded-lg bg-accent text-white
                hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed
                transition-colors">
              {{ interview.submitting ? '面试官思考中…' : '发送' }}
            </button>
          </div>
        </div>
        <div v-else class="text-center text-xs text-ink-faint py-2">
          本场面试已结束，总评已生成。可到「面试准备」重新出题再练一场。
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { reactive, ref, computed, watch, nextTick, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import api from '../api'

const props = defineProps({
  taskId: { type: String, required: true },
})

// 默认进入模拟面试（有题单时直接开答）；无题单时两区都有引导
const section = ref('mock')

const sections = [
  { key: 'prep', label: '面试准备', icon: '🎤' },
  { key: 'mock', label: '模拟面试', icon: '🎬' },
]

// ===== M23/M31/M32 面试功能：题单 + 多轮自由对话（诊断内嵌 / 独立页复用） =====
const interview = reactive({
  loading: false,
  plan: [],          // [{id, category, question, focus, hint}]
  currentIndex: 0,
  chatLog: [],       // M32 完整对话流 [{role: interviewer|candidate, qid, content}]
  summary: null,     // 总评 {overall, strengths, weaknesses, suggestions}
  answer: '',        // 当前输入
  submitting: false,
  loaded: false,     // 已从后端恢复过（避免重复请求）
  restoring: false,  // 会话恢复请求进行中
  restoreError: false, // 恢复失败（服务不可达等）——显式展示并允许重试
})

const currentQuestion = computed(() => interview.plan[interview.currentIndex] || null)

// 消息 qid → 题号/分类（题干与追问/点评都挂在对应题下）
function qInfo(qid) {
  const i = interview.plan.findIndex(q => q.id === qid)
  return i < 0 ? null : { no: i + 1, category: interview.plan[i].category }
}

// 题干消息（内容与题单原文一致）→ 高亮样式
function isQuestionMsg(m) {
  const q = interview.plan.find(x => x.id === m.qid)
  return !!q && q.question === m.content
}

function _llmCfg() {
  try {
    const c = JSON.parse(localStorage.getItem('llm_config') || '{}')
    return c.api_key ? c : null
  } catch (e) { return null }
}

let regenerateNext = false  // 「重新出题」时置位，请求携带 regenerate 强制重出

async function genInterview() {
  interview.loading = true
  const regenerate = regenerateNext
  regenerateNext = false
  try {
    const res = await api.interviewStart(props.taskId, _llmCfg(), regenerate)
    applyInterviewState(res.data)
    Message.success(regenerate ? '已重新出题' : '面试题单已生成')
  } catch (e) {
    Message.error(e.response?.data?.detail || '生成面试题失败')
  } finally {
    interview.loading = false
  }
}

function applyInterviewState(d = {}) {
  interview.plan = d.questions || []
  interview.currentIndex = d.current_index || 0
  interview.chatLog = d.chat_log || []
  interview.summary = d.summary || null
  interview.answer = ''
  interview.loaded = true
}

async function ensureInterviewLoaded() {
  if (interview.loaded) return
  interview.restoring = true
  interview.restoreError = false
  try {
    const res = await api.interviewGet(props.taskId)
    if (res.data.exists) applyInterviewState(res.data)
  } catch (e) {
    // 服务未就绪/中断等网络异常：显式报错而不是当成「无会话」
    interview.restoreError = true
  } finally {
    interview.restoring = false
    interview.loaded = true
  }
}

function retryRestore() {
  interview.loaded = false
  ensureInterviewLoaded()
}

// ===== M32 多轮自由对话：随时发言，面试官回应并判断是否收尾进下一题 =====
async function sendChat(forceAdvance = false) {
  if (interview.submitting) return
  const content = forceAdvance ? '（本题回答完毕，请进入下一题）' : interview.answer.trim()
  if (!content) return
  interview.submitting = true
  // 乐观 UI：自己的消息立即上屏（LLM 回应常需数十秒，避免「点了没反应」）；失败回滚
  const optimistic = forceAdvance ? null : {
    role: 'candidate', qid: interview.plan[interview.currentIndex]?.id, content,
  }
  if (optimistic) {
    interview.chatLog = [...interview.chatLog, optimistic]
    interview.answer = ''
  }
  try {
    const res = await api.interviewChat(props.taskId, content, forceAdvance, _llmCfg())
    interview.chatLog = res.data.chat_log || []
    interview.currentIndex = res.data.next_index ?? interview.currentIndex
    if (res.data.summary) interview.summary = res.data.summary
    if (res.data.finished) Message.success('模拟面试完成，已生成总评')
  } catch (e) {
    if (optimistic) {
      interview.chatLog = interview.chatLog.filter(m => m !== optimistic)
      interview.answer = content  // 恢复输入，避免丢字
    }
    Message.error(e.response?.data?.detail || '发送失败')
  } finally {
    interview.submitting = false
  }
}

// M33 面试报告导出 Word（blob 下载）
const exporting = ref(false)
async function exportReport() {
  if (exporting.value) return
  exporting.value = true
  try {
    const res = await api.interviewExport(props.taskId)
    const url = URL.createObjectURL(new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }))
    const a = document.createElement('a')
    a.href = url
    a.download = `模拟面试报告_${Date.now()}.docx`
    a.click()
    URL.revokeObjectURL(url)
    Message.success('面试报告已导出')
  } catch (e) {
    Message.error(e.response?.data?.detail || '导出失败')
  } finally {
    exporting.value = false
  }
}

// 聊天流自动滚动到底部
const chatBoxRef = ref(null)
watch(() => interview.chatLog.length, async () => {
  await nextTick()
  const el = chatBoxRef.value
  if (el) el.scrollTop = el.scrollHeight
})

onMounted(() => {
  ensureInterviewLoaded()
})
</script>
