<template>
  <div class="max-w-6xl mx-auto px-6 md:px-10 py-8 md:py-10">

    <!-- 页头（全站统一规范：渐变标题 + 短横线） -->
    <div class="flex items-end justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold tracking-tight">
          <span class="bg-gradient-to-r from-ink to-accent bg-clip-text text-transparent">✨ 素材库</span>
        </h1>
        <div class="h-0.5 w-14 rounded-full bg-gradient-to-r from-accent to-accent-hover/0 mt-1.5"></div>
        <p class="text-xs text-ink-faint mt-1.5">
          项目与成就的 STAR 结构化档案——面试答题、简历优化、求职信三处复用
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button @click="openGen()"
          class="px-4 py-2 text-xs font-medium rounded-lg border border-accent/50 text-accent
            hover:bg-accent/10 active:scale-[0.98] transition-all">
          ✨ AI 生成
        </button>
        <button @click="openForm()"
          class="px-4 py-2 text-xs font-medium rounded-lg bg-accent text-white
            hover:bg-accent-hover active:scale-[0.98] transition-all">
          ＋ 新建素材
        </button>
      </div>
    </div>

    <!-- AI 生成弹窗：粘贴项目描述 → 提炼 STAR 草稿 → 回填编辑弹窗核对保存 -->
    <Teleport to="body">
      <div v-if="genOpen" @click.self="closeGen"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/40">
        <div class="bg-panel border border-line rounded-2xl w-full max-w-2xl max-h-[88vh]
          overflow-y-auto p-5 md:p-6 shadow-lg">
          <div class="flex items-center justify-between gap-3 mb-3">
            <div class="text-sm font-semibold">✨ AI 生成素材草稿</div>
            <button @click="closeGen"
              class="text-lg leading-none text-ink-sub hover:text-ink shrink-0">×</button>
          </div>
          <p class="text-xs text-ink-faint mb-3">
            粘贴项目描述 / 经历文本（简历项目段落、复盘笔记等），AI 提炼成 STAR 结构草稿并回填到编辑表单；
            AI 只基于你提供的内容提炼，不会编造细节与数据，生成后请核对修改再保存。
          </p>
          <textarea v-model="genText" rows="9" maxlength="4000"
            placeholder="例如：&#10;我负责订单系统的性能优化项目，当时大促峰值流量激增，核心接口 P99 超过 800ms。我主导引入本地缓存、读写分离与慢 SQL 治理，最终 P99 降到 120ms，故障率下降 90%。"
            class="w-full px-3.5 py-3 text-sm bg-inset rounded-lg border border-line resize-y leading-relaxed
              focus:outline-none focus:border-accent placeholder:text-ink-faint transition-colors"></textarea>
          <div class="flex items-center gap-3 mt-3">
            <button @click="runGenerate" :disabled="generating || genText.trim().length < 30"
              class="px-5 py-2 text-xs font-medium rounded-lg bg-accent text-white
                hover:bg-accent-hover active:scale-[0.98] transition-all disabled:opacity-40">
              {{ generating ? '生成中…' : '✨ 生成草稿' }}
            </button>
            <span class="text-[11px] text-ink-faint">
              至少 30 字{{ genText.trim().length ? ` · 已输入 ${genText.trim().length} 字` : '' }}
            </span>
            <button @click="closeGen"
              class="px-4 py-2 text-xs text-ink-sub hover:text-ink transition-colors ml-auto">关闭</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 新建 / 编辑弹窗（保存后不收起，连续录入） -->
    <Teleport to="body">
      <div v-if="formOpen" @click.self="closeForm"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/40">
        <div class="bg-panel border border-line rounded-2xl w-full max-w-2xl max-h-[88vh]
          overflow-y-auto p-5 md:p-6 shadow-lg">
          <div class="flex items-center justify-between gap-3 mb-4">
            <div class="text-sm font-semibold">
              {{ editingId != null ? '✏️ 编辑素材' : '＋ 新建素材' }}
              <span class="ml-2 text-xs font-normal text-ink-faint">带 * 必填，其余可留空</span>
            </div>
            <button @click="closeForm"
              class="text-lg leading-none text-ink-sub hover:text-ink shrink-0">×</button>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <input v-model="form.title" maxlength="60" placeholder="项目 / 成就标题 *"
              class="px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
                focus:border-accent placeholder:text-ink-faint transition-colors" />
            <input v-model="form.role" maxlength="40" placeholder="我的角色（如：后端负责人）"
              class="px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
                focus:border-accent placeholder:text-ink-faint transition-colors" />
            <input v-model="form.tags" maxlength="200" placeholder="标签（逗号分隔，如：Python,高并发）"
              class="px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
                focus:border-accent placeholder:text-ink-faint transition-colors" />
          </div>

          <div class="space-y-3">
            <textarea v-for="sec in SECTIONS" :key="sec.key" v-model="form[sec.field]"
              :rows="sec.rows" maxlength="2000" :placeholder="sec.placeholder"
              class="w-full px-3.5 py-2.5 text-sm bg-inset rounded-lg border border-line resize-y
                leading-relaxed focus:outline-none focus:border-accent
                placeholder:text-ink-faint transition-colors"></textarea>
          </div>

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

    <LoadingBlock v-if="loading" text="素材库加载中…" />
    <div v-else-if="loadError" class="bg-warn/10 border border-warn/40 rounded-2xl px-5 py-4
      flex items-center justify-between">
      <span class="text-sm text-warn">素材库加载失败</span>
      <button @click="loadAll" class="text-sm font-medium text-warn hover:text-ink transition-colors">重试</button>
    </div>

    <template v-else>
      <!-- 空态 -->
      <div v-if="!cards.length" class="bg-panel rounded-2xl p-12 text-center">
        <div class="text-4xl mb-4">✨</div>
        <div class="text-lg font-semibold mb-2">还没有素材卡</div>
        <p class="text-sm text-ink-sub max-w-md mx-auto">
          把做过的项目与成就按「情境-任务-行动-结果」整理成 STAR 卡片统一归档；
          面试答题、简历优化、求职信都能直接引用，也可以让 AI 从项目描述一键提炼草稿。
        </p>
        <div class="flex items-center justify-center gap-3 mt-5">
          <button @click="openForm()"
            class="px-5 py-2 text-xs font-medium rounded-lg bg-accent text-white
              hover:bg-accent-hover transition-colors">＋ 新建第一张素材卡</button>
          <button @click="openGen()"
            class="px-5 py-2 text-xs font-medium rounded-lg border border-accent/50 text-accent
              hover:bg-accent/10 transition-colors">✨ AI 生成草稿</button>
        </div>
      </div>

      <!-- 卡片网格 -->
      <div v-else class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="c in cards" :key="c.id"
          class="bg-panel border border-line rounded-lg p-5 flex flex-col
            hover:border-accent/50 hover:shadow-md transition-all">
          <!-- 头部：标题 + 角色 + 更新时间 -->
          <div class="flex items-start gap-2 mb-2">
            <div class="min-w-0 flex-1">
              <div class="text-sm font-semibold text-ink truncate" :title="c.title">{{ c.title }}</div>
              <div v-if="c.role" class="text-xs text-ink-faint mt-0.5 truncate">👤 {{ c.role }}</div>
            </div>
            <span class="text-[10px] font-mono text-ink-faint shrink-0 mt-0.5">{{ fmtTime(c.updated_at) }}</span>
          </div>

          <!-- 标签 chips -->
          <div v-if="tagList(c).length" class="flex items-center gap-1.5 flex-wrap mb-2.5">
            <span v-for="t in tagList(c)" :key="t"
              class="px-1.5 py-0.5 rounded text-[11px] bg-accent/10 text-accent">{{ t }}</span>
          </div>

          <!-- STAR 四段摘要（默认两行截断，点击展开/收起全文） -->
          <div class="space-y-1.5 mb-4 cursor-pointer flex-1"
            :title="expandedId === c.id ? '点击收起' : '点击展开全文'"
            @click="expandedId = expandedId === c.id ? null : c.id">
            <template v-if="hasStarContent(c)">
              <div v-for="sec in SECTIONS" :key="sec.key" v-show="c[sec.field]"
                class="flex items-start gap-1.5">
                <span class="shrink-0 w-4 h-4 rounded text-[10px] font-mono flex items-center
                  justify-center bg-inset text-ink-faint mt-0.5">{{ sec.key }}</span>
                <p class="text-xs leading-relaxed flex-1 min-w-0 whitespace-pre-line"
                  :class="expandedId === c.id ? 'text-ink-sub' : 'line-clamp-2 text-ink-faint'">{{ c[sec.field] }}</p>
              </div>
            </template>
            <p v-else class="text-xs text-ink-faint/60 italic">暂无 STAR 内容 · 点 ✏️ 编辑补充四段描述</p>
          </div>

          <!-- 操作区 -->
          <div class="mt-auto flex items-center gap-2.5 pt-3 border-t border-line/60">
            <button @click="copyCard(c)" class="text-xs text-accent hover:underline shrink-0">📋 复制</button>
            <button @click="openEdit(c)" title="编辑素材"
              class="text-xs text-ink-sub hover:text-accent transition-colors shrink-0">✏️ 编辑</button>
            <span class="flex-1" />
            <button @click="remove(c)" title="删除素材"
              class="text-xs text-ink-sub hover:text-bad transition-colors shrink-0">🗑 删除</button>
          </div>
        </div>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import api from '../api'
import LoadingBlock from '../components/LoadingBlock.vue'

/* ---- STAR 四段定义（卡片摘要与编辑表单共用） ---- */
const SECTIONS = [
  { key: 'S', name: '情境', field: 'situation', rows: 4,
    placeholder: 'S · 情境：项目背景是什么？当时面临什么问题或挑战？' },
  { key: 'T', name: '任务', field: 'task', rows: 3,
    placeholder: 'T · 任务：你承担了什么任务 / 目标？' },
  { key: 'A', name: '行动', field: 'action', rows: 4,
    placeholder: 'A · 行动：你具体做了什么？用了什么方法？' },
  { key: 'R', name: '结果', field: 'result', rows: 3,
    placeholder: 'R · 结果：产出了什么成果？尽量用数据量化' },
]

const loading = ref(true)
const loadError = ref(false)
const cards = ref([])
const expandedId = ref(null)

/* ---- 数据加载 ---- */
async function loadAll() {
  loading.value = true
  loadError.value = false
  try {
    const res = await api.listStarCards()
    cards.value = res.data.items || []
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

/* ---- 新建 / 编辑 ---- */
const formOpen = ref(false)
const editingId = ref(null)
const formSaving = ref(false)
const form = reactive({ title: '', role: '', tags: '', situation: '', task: '', action: '', result: '' })

const FORM_EMPTY = { title: '', role: '', tags: '', situation: '', task: '', action: '', result: '' }

function resetForm() {
  Object.assign(form, FORM_EMPTY)
}

function openForm() {
  resetForm()
  editingId.value = null
  formOpen.value = true
}

function openEdit(c) {
  editingId.value = c.id
  Object.assign(form, {
    title: c.title || '', role: c.role || '', tags: c.tags || '',
    situation: c.situation || '', task: c.task || '', action: c.action || '', result: c.result || '',
  })
  formOpen.value = true
}

function closeForm() {
  formOpen.value = false
  resetForm()
  editingId.value = null
}

async function saveForm() {
  const title = form.title.trim()
  if (!title) {
    Message.warning('标题必填')
    return
  }
  formSaving.value = true
  try {
    const payload = {
      title,
      role: form.role.trim(),
      tags: form.tags.trim(),
      situation: form.situation.trim(),
      task: form.task.trim(),
      action: form.action.trim(),
      result: form.result.trim(),
    }
    if (editingId.value != null) {
      const res = await api.updateStarCard(editingId.value, payload)
      // 刷新列表：被更新的卡按 updated_at 排到最前
      cards.value = cards.value.filter((x) => x.id !== editingId.value)
      cards.value.unshift(res.data)
      Message.success('已保存修改')
    } else {
      const res = await api.createStarCard(payload)
      cards.value.unshift(res.data)
      Message.success('已保存素材卡，可继续录入')
    }
    // 连续录入惯例：清空表单、弹窗不收起
    resetForm()
    editingId.value = null
  } catch (e) {
    Message.error(e.response?.data?.detail || '保存失败')
  } finally {
    formSaving.value = false
  }
}

/* ---- 删除 ---- */
function remove(c) {
  Modal.warning({
    title: '确认删除该素材卡？',
    content: `「${c.title}」将从素材库删除。`,
    okText: '删除',
    okButtonProps: { status: 'danger' },
    cancelText: '取消',
    hideCancel: false,
    onOk: async () => {
      try {
        await api.deleteStarCard(c.id)
        cards.value = cards.value.filter((x) => x.id !== c.id)
        Message.success('已删除')
      } catch (e) {
        Message.error(e.response?.data?.detail || '删除失败')
      }
    },
  })
}

/* ---- 复制：拼纯文本（标题/角色/标签/四段全文） ---- */
function tagList(c) {
  return (c.tags || '').split(',').map((t) => t.trim()).filter(Boolean)
}

function hasStarContent(c) {
  return SECTIONS.some((s) => c[s.field])
}

function cardPlainText(c) {
  const parts = [`【${c.title}】`]
  if (c.role) parts.push(`我的角色：${c.role}`)
  if (tagList(c).length) parts.push(`标签：${tagList(c).join(' / ')}`)
  for (const sec of SECTIONS) {
    if (c[sec.field]) parts.push(`${sec.key}（${sec.name}）：${c[sec.field]}`)
  }
  return parts.join('\n')
}

async function copyCard(c) {
  try {
    await navigator.clipboard.writeText(cardPlainText(c))
    Message.success('素材卡已复制到剪贴板')
  } catch {
    Message.error('复制失败，请手动选择文本复制')
  }
}

/* ---- AI 生成草稿：粘贴描述 → 提炼 STAR → 回填编辑弹窗 ---- */
const genOpen = ref(false)
const genText = ref('')
const generating = ref(false)

function openGen() {
  genText.value = ''
  genOpen.value = true
}

function closeGen() {
  genOpen.value = false
  genText.value = ''
}

async function runGenerate() {
  if (genText.value.trim().length < 30) {
    Message.warning('项目描述太短（至少 30 字）')
    return
  }
  generating.value = true
  try {
    const res = await api.generateStarDraft({ text: genText.value.trim(), llm_config: null })
    const d = res.data.draft || {}
    // 生成 → 检查修改 → 保存的动线：回填编辑弹窗并打开它
    resetForm()
    editingId.value = null
    Object.assign(form, {
      title: d.title || '', role: d.role || '', tags: d.tags || '',
      situation: d.situation || '', task: d.task || '', action: d.action || '', result: d.result || '',
    })
    genOpen.value = false
    genText.value = ''
    formOpen.value = true
    Message.success('草稿已生成，请核对修改后保存')
  } catch (e) {
    Message.error(e.response?.data?.detail || 'AI 生成失败')
  } finally {
    generating.value = false
  }
}

/* ---- 杂项 ---- */
function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}-${String(d.getDate()).padStart(2, '0')}`
}

function onEscKey(e) {
  if (e.key !== 'Escape') return
  if (genOpen.value) closeGen()
  else if (formOpen.value) closeForm()
}

onMounted(async () => {
  await loadAll()
  window.addEventListener('keydown', onEscKey)
})

onUnmounted(() => window.removeEventListener('keydown', onEscKey))
</script>
