<template>
  <Teleport to="body">
    <div v-if="job" @click.self="$emit('close')"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/40">
      <div class="bg-panel border-2 border-ink/80 shadow-[3px_3px_0_0] shadow-ink/20 rounded-2xl
        w-full max-w-2xl max-h-[88vh] overflow-y-auto p-5 md:p-6">
        <!-- 头部 -->
        <div class="flex items-start justify-between gap-3 mb-4">
          <div class="min-w-0">
            <div class="text-sm font-semibold truncate">🧩 匹配分解「{{ job.title }}」</div>
            <div class="text-xs text-ink-faint mt-0.5 truncate">
              {{ job.company || '公司待定' }}<span v-if="job.city"> · {{ job.city }}</span>
            </div>
          </div>
          <button @click="$emit('close')" class="text-lg leading-none text-ink-sub hover:text-ink shrink-0">×</button>
        </div>

        <!-- 简历选择 + 开始分析 -->
        <div class="flex items-center gap-2 flex-wrap">
          <select v-model="resumeId"
            class="px-2.5 py-1.5 text-xs bg-inset rounded-lg border border-line
              focus:outline-none focus:border-accent transition-colors min-w-0 max-w-[220px]">
            <option value="">选择简历…</option>
            <option v-for="r in resumes" :key="r.id" :value="r.id">{{ r.filename }}</option>
          </select>
          <button @click="runMatrix" :disabled="loading || !resumeId"
            class="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-accent text-white
              hover:bg-accent-hover active:scale-[0.98] transition-all disabled:opacity-40">
            {{ loading ? 'AI 分析中…' : (result ? '重新分析' : '开始分析') }}
          </button>
        </div>
        <p v-if="!resumes.length" class="text-[11px] text-ink-faint mt-1.5">
          还没有简历，先去 <router-link to="/app/resumes" class="text-accent hover:underline">简历库</router-link> 上传或创建一份。
        </p>

        <!-- 加载态 -->
        <div v-if="loading" class="mt-5 py-8 text-center">
          <div class="text-sm text-ink-sub">AI 正在逐条拆解 JD 并在简历中定位证据…</div>
          <div class="text-[11px] text-ink-faint mt-1.5">通常需要十几秒，请稍候</div>
        </div>

        <!-- 结果 -->
        <template v-else-if="result">
          <!-- 分数横幅 -->
          <div class="mt-4 rounded-xl border border-line bg-inset/60 px-4 py-3.5">
            <div class="flex items-center gap-3.5">
              <div class="text-3xl font-semibold font-mono shrink-0" :class="scoreCls">{{ result.score }}</div>
              <div class="flex-1 min-w-0">
                <div class="h-3 rounded-full border-2 border-ink/70 bg-panel overflow-hidden">
                  <div class="h-full bg-accent transition-all duration-500" :style="{ width: result.score + '%' }"></div>
                </div>
                <div class="text-[11px] text-ink-faint mt-1.5 flex items-center gap-2.5 flex-wrap">
                  <span class="text-ok">✓ 匹配 {{ result.counts.hit }}</span>
                  <span class="text-warn">◐ 部分匹配 {{ result.counts.partial }}</span>
                  <span class="text-ink-faint">✗ 缺失 {{ result.counts.miss }}</span>
                  <span>共 {{ result.counts.total }} 条要求</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 矩阵行 -->
          <div class="mt-3 space-y-2">
            <div v-for="(r, i) in result.rows" :key="'mr-' + i"
              class="border rounded-lg px-3.5 py-3" :class="rowBorderCls(r.verdict)">
              <div class="flex items-start gap-2.5">
                <span class="text-sm font-semibold shrink-0 mt-0.5" :class="rowTextCls(r.verdict)">{{ rowIcon(r.verdict) }}</span>
                <div class="flex-1 min-w-0">
                  <div class="text-xs font-medium text-ink leading-relaxed">{{ r.requirement }}</div>
                  <div class="flex items-center gap-1.5 mt-1.5 flex-wrap">
                    <span class="px-1.5 py-0.5 rounded text-[10px] bg-inset text-ink-faint shrink-0">
                      {{ catLabel(r.category) }} · 权重 {{ r.weight }}
                    </span>
                  </div>
                  <!-- 证据引用块：逐字摘自简历原文 -->
                  <div v-if="r.evidence"
                    class="mt-2 border-l-2 rounded-r px-2.5 py-1.5 text-[11px] text-ink-sub leading-relaxed bg-inset/70"
                    :class="r.verdict === 'hit' ? 'border-ok/50' : 'border-warn/50'">
                    <span class="text-ink-faint">简历证据：</span>「{{ r.evidence }}」
                  </div>
                  <p v-if="r.gap" class="text-[11px] text-warn mt-1.5 leading-relaxed">💡 {{ r.gap }}</p>
                </div>
              </div>
            </div>
          </div>

          <!-- M61 关键词覆盖（确定性比对，与 AI 矩阵互为印证） -->
          <div class="mt-4 border-t border-line pt-3.5">
            <div class="flex items-center gap-2.5">
              <span class="text-[11px] font-semibold text-ink-sub shrink-0">关键词覆盖</span>
              <div class="flex-1 h-2.5 rounded-full border-2 border-ink/70 bg-panel overflow-hidden">
                <div class="h-full bg-accent transition-all duration-500" :style="{ width: kw.coverage + '%' }"></div>
              </div>
              <span class="text-[11px] font-mono shrink-0"
                :class="kw.coverage >= 70 ? 'text-ok' : kw.coverage >= 40 ? 'text-warn' : 'text-ink-faint'">
                {{ kw.coverage }}%
              </span>
            </div>
            <div v-if="kw.hits.length" class="flex flex-wrap gap-1.5 mt-2">
              <span v-for="w in kw.hits" :key="'kw-h-' + w"
                class="px-1.5 py-0.5 rounded text-[11px] text-ok bg-ok/10 border border-ok/30">{{ w }}</span>
            </div>
            <div v-if="kw.missing.length" class="flex flex-wrap gap-1.5 mt-1.5">
              <span v-for="w in kw.missing" :key="'kw-m-' + w"
                class="px-1.5 py-0.5 rounded text-[11px] text-warn bg-warn/10 border border-warn/30">{{ w }}</span>
            </div>
          </div>

          <p class="text-[11px] text-ink-faint mt-3.5 leading-relaxed">
            证据均逐字摘自简历原文；未能回溯到原文的条目已降级为「部分匹配」并标注——AI 只解读不编造。
            匹配分仅供参考，投递决策请结合实际。
          </p>
        </template>

        <!-- 错误态 -->
        <div v-else-if="error" class="mt-5 rounded-xl border border-warn/40 bg-warn/10 px-4 py-3.5">
          <p class="text-xs text-warn leading-relaxed">{{ error }}</p>
          <button v-if="needKey" @click="goSettings"
            class="mt-2.5 px-3.5 py-1.5 text-xs font-medium rounded-lg border border-accent/50 text-accent
              hover:bg-accent/10 transition-colors">去设置页配置 API Key</button>
        </div>

        <!-- 空态 -->
        <p v-else class="text-[11px] text-ink-faint mt-4 leading-relaxed">
          选一份简历点「开始分析」，AI 把 JD 拆成具体要求，逐条在简历中定位原文证据，给出可解释的匹配矩阵与加权分。
        </p>

        <!-- 底部 -->
        <div class="flex justify-end mt-4 pt-3 border-t border-line">
          <button @click="$emit('close')" class="px-4 py-2 text-xs text-ink-sub hover:text-ink transition-colors">关闭</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import api from '../api'

const props = defineProps({
  job: { type: Object, default: null },
  resumes: { type: Array, default: () => [] },
})
const emit = defineEmits(['close'])

const router = useRouter()
const resumeId = ref('')
const loading = ref(false)
const error = ref('')
const result = ref(null)

// 打开时重置（仅一份简历时自动预选）
watch(() => props.job, (j) => {
  result.value = null
  error.value = ''
  loading.value = false
  resumeId.value = j && props.resumes.length === 1 ? String(props.resumes[0].id) : ''
})

const jdReady = computed(() => ((props.job?.jd || '').trim().length) >= 30)
const kw = computed(() => ({
  coverage: result.value?.keywords?.coverage ?? 0,
  hits: result.value?.keywords?.hits || [],
  missing: result.value?.keywords?.missing || [],
}))
const scoreCls = computed(() => {
  const s = result.value?.score ?? 0
  return s >= 70 ? 'text-ok' : s >= 40 ? 'text-warn' : 'text-ink-faint'
})
// 400「未配置 Key」/ 502「检查模型配置」→ 引导去设置页
const needKey = computed(() => /设置|模型配置/.test(error.value))

const CAT_LABELS = { skill: '硬技能', domain: '领域', exp: '经验', edu: '学历', other: '其他' }
const catLabel = (c) => CAT_LABELS[c] || '其他'
const rowIcon = (v) => (v === 'hit' ? '✓' : v === 'partial' ? '◐' : '✗')
const rowTextCls = (v) => (v === 'hit' ? 'text-ok' : v === 'partial' ? 'text-warn' : 'text-ink-faint')
const rowBorderCls = (v) =>
  v === 'hit' ? 'border-ok/30' : v === 'partial' ? 'border-warn/30' : 'border-line'

function goSettings() {
  emit('close')
  router.push('/settings')
}

async function runMatrix() {
  if (!resumeId.value) {
    Message.warning('先选择一份简历')
    return
  }
  if (!jdReady.value) {
    Message.warning('该岗位暂无有效 JD，先编辑补充 JD 再分析')
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = await api.matchMatrix({
      jd: props.job.jd.trim(),
      resume_id: Number(resumeId.value),
    })
    result.value = res.data
  } catch (e) {
    error.value = e.response?.data?.detail || '分析失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>
