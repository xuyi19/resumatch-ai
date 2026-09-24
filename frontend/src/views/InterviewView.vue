<template>
  <div class="max-w-6xl mx-auto px-6 md:px-8 py-12 md:py-16">

    <!-- ============ 面试进行中：直接渲染面试面板 ============ -->
    <div v-if="activeTaskId">
      <div class="flex items-center gap-3 mb-6">
        <button @click="backToList"
          class="text-xs text-ink-faint hover:text-accent transition-colors">
          ← 返回会话列表
        </button>
      </div>
      <InterviewPanel :task-id="activeTaskId" />
    </div>

    <!-- ============ 会话大厅：发起 + 最近面试 ============ -->
    <div v-else>

      <div class="text-center mb-10">
        <div class="inline-flex items-center justify-center w-16 h-16 rounded-lg mb-5
          bg-accent/10 border border-line">
          <span class="text-3xl">🎤</span>
        </div>
        <h1 class="text-3xl font-semibold mb-2 tracking-tight">
          <span class="bg-gradient-to-r from-ink to-accent bg-clip-text text-transparent">模拟面试</span>
        </h1>
        <div class="h-0.5 w-14 rounded-full bg-gradient-to-r from-accent to-accent-hover/0"></div>
        <p class="text-sm text-ink-sub max-w-xl mx-auto">
          选择一份简历，粘贴意向岗位 JD，AI 面试官即刻出题开考——无需先跑诊断。
          共 6 题（技术基础 / 项目深挖 / 岗位匹配 / 情景行为），逐题点评，答完出总评。
        </p>
      </div>

      <!-- 发起面试 -->
      <div class="bg-panel border border-line rounded-lg p-6 md:p-8 mb-10 max-w-3xl mx-auto">
        <div class="space-y-5">
          <div>
            <label class="block text-xs font-medium text-ink-sub mb-2">选择简历</label>
            <select v-model="form.resumeId"
              class="w-full px-4 py-3 rounded-lg bg-inset border border-line text-sm text-ink
                focus:border-accent focus:outline-none transition-colors">
              <option :value="null" disabled>请选择简历…</option>
              <option v-for="r in resumes" :key="r.id" :value="r.id">
                {{ r.filename }}
              </option>
            </select>
            <p v-if="!resumes.length && !loadingResumes" class="text-xs text-warn mt-2">
              简历库为空，请先到
              <RouterLink to="/app/analyze" class="text-accent hover:underline">发起诊断</RouterLink>
              或
              <RouterLink to="/app/editor" class="text-accent hover:underline">创建简历</RouterLink>
            </p>
          </div>

          <div>
            <div class="flex items-center justify-between mb-2 gap-2 flex-wrap">
              <label class="block text-xs font-medium text-ink-sub">意向岗位 JD</label>
              <div class="flex items-center gap-2">
                <!-- M45 岗位库选取：一键带入库内岗位 JD（空库时引导去添加） -->
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
                  :class="jdLength >= 20 ? 'text-ink-faint' : 'text-warn'">
                  {{ jdLength }}/6000
                </span>
              </div>
            </div>
            <textarea v-model="form.jdText" rows="7" maxlength="6000"
              placeholder="粘贴招聘 JD：岗位职责、任职要求、加分项等。AI 将结合简历与 JD 针对性出题"
              class="w-full px-4 py-3 rounded-lg bg-inset border border-line text-sm text-ink
                placeholder:text-ink-faint focus:border-accent focus:outline-none
                transition-colors resize-y leading-relaxed"></textarea>
          </div>

          <div class="flex items-center justify-between">
            <p class="text-xs text-ink-faint">出题约需 20-40 秒，由已配置的大模型生成</p>
            <button @click="startInterview" :disabled="!canStart || starting"
              class="px-8 py-3 text-sm font-medium rounded-lg bg-accent text-white
                hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed
                transition-colors">
              {{ starting ? 'AI 正在出题…' : '开始面试' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 最近的面试 -->
      <div class="max-w-3xl mx-auto">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-base font-semibold text-ink">最近的面试</h2>
          <button @click="loadSessions" :disabled="loadingSessions"
            class="text-xs text-ink-faint hover:text-accent transition-colors">
            {{ loadingSessions ? '刷新中…' : '刷新' }}
          </button>
        </div>

        <div v-if="!sessions.length && !loadingSessions"
          class="bg-panel border border-line rounded-lg p-10 text-center">
          <div class="text-3xl mb-3">🎤</div>
          <div class="text-sm font-medium text-ink mb-1.5">还没有面试记录</div>
          <p class="text-xs text-ink-faint max-w-xs mx-auto leading-relaxed">
            从上方选择简历与意向岗位 JD，发起第一场模拟面试；也可以只贴 JD 开独立面试
          </p>
        </div>

        <div v-else class="space-y-3">
          <div v-for="s in sessions" :key="s.task_id"
            class="bg-panel border border-line rounded-lg p-5 cursor-pointer
              hover:border-accent transition-colors group"
            @click="resumeSession(s.task_id)">
            <div class="flex items-center gap-2.5 mb-2 flex-wrap">
              <span class="text-xs px-2 py-0.5 rounded-md"
                :class="s.source === '独立面试' ? 'bg-accent/10 text-accent' : 'bg-inset text-ink-sub'">
                {{ s.source }}
              </span>
              <span class="text-xs px-2 py-0.5 rounded-md"
                :class="s.status === 'finished' ? 'bg-ok/10 text-ok' : 'bg-warn/10 text-warn'">
                {{ s.status === 'finished' ? '已完成' : `进行中 ${s.answered}/${s.total}` }}
              </span>
              <!-- M34 列表带总分，可直接横向比较各场成绩 -->
              <span v-if="s.overall_score != null" class="text-xs font-mono font-medium"
                :class="s.overall_score >= 8 ? 'text-ok' : s.overall_score >= 6 ? 'text-accent' : 'text-warn'">
                {{ s.overall_score }} 分
              </span>
              <span v-else-if="s.summary" class="text-xs text-ok">✓ 已出总评</span>
              <span class="ml-auto text-xs text-ink-faint font-mono">
                {{ (s.updated_at || '').slice(0, 16).replace('T', ' ') }}
              </span>
              <!-- M37：删除废弃会话（hover 显示，阻止冒泡避免误触恢复） -->
              <button @click.stop="confirmDelete(s.task_id)" title="删除此会话"
                class="opacity-0 group-hover:opacity-100 text-xs text-ink-faint
                  hover:text-warn transition-all shrink-0">删除</button>
            </div>
            <div class="text-sm text-ink leading-relaxed group-hover:text-accent transition-colors">
              {{ s.first_question || '（题单为空）' }}
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
import InterviewPanel from '../components/InterviewPanel.vue'

const route = useRoute()
const router = useRouter()

// 当前激活会话：支持 /app/interview?task_id=xxx 直接恢复（刷新不丢）
const activeTaskId = ref(route.query.task_id || '')

const resumes = ref([])
const loadingResumes = ref(false)
const sessions = ref([])
const loadingSessions = ref(false)
const starting = ref(false)

const form = reactive({
  resumeId: null,
  jdText: '',
})

const jdLength = computed(() => form.jdText.trim().length)
const canStart = computed(() =>
  form.resumeId !== null && jdLength.value >= 20 && jdLength.value <= 6000)

async function loadResumes() {
  loadingResumes.value = true
  try {
    const res = await api.listResumes()
    resumes.value = res.data.items || []
  } catch (e) { /* 列表失败静默，空态有引导 */ }
  loadingResumes.value = false
}

async function loadSessions() {
  loadingSessions.value = true
  try {
    const res = await api.interviewSessions()
    sessions.value = res.data.items || []
  } catch (e) { /* 忽略，列表展示为空 */ }
  loadingSessions.value = false
}

// M37：删除废弃/无效会话（确认弹窗后删除，与诊断历史删除同款交互）
function confirmDelete(taskId) {
  Modal.warning({
    title: '确认删除',
    content: '删除后该场面试记录不可恢复，确定继续？',
    hideCancel: false,
    okText: '删除',
    cancelText: '取消',
    onOk: async () => {
      try {
        await api.interviewDeleteSession(taskId)
        Message.success('已删除')
        loadSessions()
      } catch (e) {
        Message.error('删除失败：' + (e?.response?.data?.detail || e.message))
      }
    },
  })
}

async function startInterview() {
  if (!canStart.value || starting.value) return
  starting.value = true
  try {
    const cfg = _llmCfg()
    const res = await api.interviewStartFree({
      resume_id: form.resumeId,
      jd_text: form.jdText.trim(),
      llm_config: cfg,
    })
    Message.success('题单已生成，面试开始')
    enterSession(res.data.task_id)
  } catch (e) {
    Message.error(e.response?.data?.detail || '发起面试失败')
  } finally {
    starting.value = false
  }
}

function resumeSession(taskId) {
  enterSession(taskId)
}

function enterSession(taskId) {
  activeTaskId.value = taskId
  // 写入 query，刷新/回退不丢会话
  router.replace({ query: { task_id: taskId } })
}

function backToList() {
  activeTaskId.value = ''
  router.replace({ query: {} })
  loadSessions()
}

function _llmCfg() {
  try {
    const c = JSON.parse(localStorage.getItem('llm_config') || '{}')
    return c.api_key ? c : null
  } catch (e) { return null }
}

onMounted(() => {
  loadResumes()
  loadSessions()
  loadLibraryJobs()
  // M40 收藏岗位一键开面试：AnalyzeView 跳转携带 ?jd=
  const jd = (route.query.jd || '').toString()
  if (jd) {
    form.jdText = jd.slice(0, 6000)
    Message.info('已带入收藏岗位的 JD，选择简历后即可开始面试')
  }
})

/* ---- M45 岗位库选取：一键带入库内岗位 JD ---- */
const libJobs = ref([])
const libJobId = ref('')

async function loadLibraryJobs() {
  try {
    const res = await api.listLibraryJobs()
    libJobs.value = res.data.items || []
  } catch (e) { /* 岗位库不可用时不显示下拉，静默 */ }
}

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
  Message.success(`已带入「${j.company || ''} ${j.title}」的 JD，选择简历后即可开始面试`)
}
</script>
