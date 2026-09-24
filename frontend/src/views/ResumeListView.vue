<template>
  <div class="max-w-6xl mx-auto px-6 md:px-10 py-8 md:py-10">
    <div class="mb-8 flex items-end justify-between flex-wrap gap-3">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight mb-1.5">
          <span class="bg-gradient-to-r from-ink to-accent bg-clip-text text-transparent">简历库</span>
        </h1>
        <div class="h-0.5 w-14 rounded-full bg-gradient-to-r from-accent to-accent-hover/0"></div>
        <p class="text-sm text-ink-sub">统一管理多份简历（不同方向投不同岗位），一键发起诊断</p>
      </div>
      <div class="flex items-center gap-2">
        <!-- 批量删除工具条（选中 >0 时出现） -->
        <button v-if="selected.size" @click="removeBatch"
          class="px-4 py-2 text-sm font-medium rounded-lg border border-bad/50 text-bad
            hover:bg-bad/10 transition-colors">
          删除选中（{{ selected.size }}）
        </button>
        <button v-if="selected.size" @click="selected.clear()"
          class="px-3 py-2 text-sm rounded-lg border border-line text-ink-faint
            hover:text-ink transition-colors">取消选择</button>
        <RouterLink to="/app/editor"
          class="px-4 py-2 text-sm font-medium rounded-lg border border-line text-ink-sub
            hover:border-accent hover:text-accent transition-colors">
          ＋ 新建简历
        </RouterLink>
      </div>
    </div>

    <LoadingBlock v-if="loading" label="加载简历库..." />

    <EmptyState v-else-if="!items.length" type="folder" title="简历库还是空的"
      desc="上传或粘贴一份简历开始使用，也可以直接在编辑器里创建">
      <RouterLink to="/app/analyze"
        class="inline-block px-6 py-2.5 text-sm font-medium rounded-lg bg-accent text-white
          hover:bg-accent-hover transition-colors">
        上传简历
      </RouterLink>
    </EmptyState>

    <div v-else class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="r in items" :key="r.id"
        class="bg-panel border border-line rounded-lg p-5 flex flex-col hover:border-accent/50
          transition-colors group">
        <!-- 名称 + 分数 -->
        <div class="flex items-start gap-3 mb-3">
          <input type="checkbox" :checked="selected.has(r.id)"
            @change="toggleSelect(r.id)" title="选择"
            class="mt-1 w-4 h-4 accent-accent cursor-pointer shrink-0" />
          <div class="w-9 h-9 rounded-lg bg-inset border border-line flex items-center
            justify-center shrink-0">
            <span class="text-sm">📄</span>
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-1.5 min-w-0">
              <span class="text-sm font-medium text-ink truncate" :title="r.filename">
                {{ r.filename }}
              </span>
              <!-- 原文件类型徽标（PDF 可原版式预览） -->
              <span v-if="r.file_type" class="shrink-0 px-1.5 py-0.5 text-[10px] font-mono
                uppercase rounded border border-line text-ink-faint">{{ r.file_type }}</span>
            </div>
            <div class="text-xs text-ink-faint mt-0.5 font-mono">
              {{ fmtTime(r.created_at) }} · {{ r.text_length }} 字
            </div>
          </div>
          <div v-if="r.latest_diagnosis?.overall" class="text-right shrink-0">
            <div class="text-lg font-semibold font-mono"
              :class="scoreColor(r.latest_diagnosis.overall)">
              {{ r.latest_diagnosis.overall }}
            </div>
            <div class="text-[10px] text-ink-faint">最近诊断</div>
          </div>
        </div>

        <!-- 最近诊断信息 -->
        <div class="text-xs text-ink-faint mb-4 min-h-[16px]">
          <span v-if="r.latest_diagnosis">上次诊断于 {{ fmtTime(r.latest_diagnosis.created_at) }}</span>
          <span v-else>尚未诊断过</span>
        </div>

        <!-- 操作区 -->
        <div class="mt-auto flex items-center gap-2">
          <RouterLink :to="{ path: '/app/analyze', query: { resume_id: r.id, resume_name: r.filename } }"
            class="flex-1 px-3 py-2 text-center text-xs font-medium rounded-md bg-accent text-white
              hover:bg-accent-hover transition-colors">
            发起诊断
          </RouterLink>
          <button @click="preview(r)" title="预览"
            class="px-3 py-2 text-xs rounded-md border border-line text-ink-sub
              hover:border-accent hover:text-accent transition-colors">预览</button>
          <button @click="rename(r)" title="重命名"
            class="px-3 py-2 text-xs rounded-md border border-line text-ink-sub
              hover:border-accent hover:text-accent transition-colors">改名</button>
          <button @click="openVersions(r)" title="版本历史与对比"
            class="px-3 py-2 text-xs rounded-md border border-line text-ink-sub
              hover:border-accent hover:text-accent transition-colors">版本</button>
          <button @click="remove(r)" title="删除"
            class="px-3 py-2 text-xs rounded-md border border-line text-ink-sub
              hover:border-bad/60 hover:text-bad transition-colors">删除</button>
        </div>
      </div>
    </div>

    <!-- M44 版本历史与对比弹层 -->
    <ResumeVersionsModal v-model:visible="versionsVisible" :resume-id="versionTarget?.id"
      :resume-name="versionTarget?.filename" />

    <!-- 预览弹层：pdf 原版式直渲；docx 文本 + 原文件下载；纯文本简历文本预览 -->
    <div v-if="previewing" class="fixed inset-0 z-50 flex items-center justify-center
      bg-black/60 backdrop-blur-sm p-4 md:p-8" @click.self="previewing = null">
      <div class="bg-panel border border-line rounded-xl w-full max-w-5xl h-[90vh]
        flex flex-col shadow-2xl overflow-hidden">
        <div class="flex items-center justify-between px-5 py-3 border-b border-line shrink-0">
          <div class="flex items-center gap-2 min-w-0">
            <span class="shrink-0 w-6 h-6 rounded-md bg-inset border border-line
              flex items-center justify-center text-[10px] font-mono uppercase text-accent">
              {{ previewing.file_type || 'txt' }}
            </span>
            <span class="text-sm font-medium text-ink truncate">{{ previewing.filename }}</span>
          </div>
          <div class="flex items-center gap-3 shrink-0">
            <a v-if="previewing.file_type"
              :href="`/api/v1/resumes/${previewing.id}/file`" :download="previewing.filename"
              class="text-xs text-accent hover:underline">下载原文件</a>
            <button @click="previewing = null"
              class="w-7 h-7 rounded-md text-ink-faint hover:text-ink hover:bg-inset
                transition-colors flex items-center justify-center">✕</button>
          </div>
        </div>

        <!-- PDF：iframe 浏览器原生渲染（保真版式）
          #toolbar=0&navpanes=0 隐藏 viewer 自带工具栏/侧栏，观感更干净；@load 前显示加载态 -->
        <div v-if="previewing.file_type === 'pdf'" class="relative flex-1 bg-inset">
          <div v-if="pdfLoading" class="absolute inset-0 z-10 flex items-center justify-center
            text-xs text-ink-faint bg-inset">
            正在加载原文件…
          </div>
          <iframe :src="`/api/v1/resumes/${previewing.id}/file#toolbar=0&navpanes=0`"
            class="w-full h-full bg-white" :title="previewing.filename"
            @load="pdfLoading = false"></iframe>
        </div>

        <!-- 其他：提取文本预览 -->
        <div v-else class="flex-1 overflow-y-auto bg-inset">
          <pre class="max-w-2xl mx-auto px-6 py-5 text-xs text-ink-sub leading-relaxed
            whitespace-pre-wrap font-mono">{{ previewText }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import api from '../api'
import EmptyState from '../components/EmptyState.vue'
import LoadingBlock from '../components/LoadingBlock.vue'
import ResumeVersionsModal from '../components/ResumeVersionsModal.vue'

const items = ref([])
const loading = ref(true)
const previewing = ref(null)
// M44 版本历史弹层
const versionsVisible = ref(false)
const versionTarget = ref(null)

function openVersions(r) {
  versionTarget.value = r
  versionsVisible.value = true
}
const previewText = ref('')
const pdfLoading = ref(false)
const selected = ref(new Set())

function toggleSelect(id) {
  const s = selected.value
  s.has(id) ? s.delete(id) : s.add(id)
  selected.value = new Set(s) // 触发响应式更新
}

function removeBatch() {
  const ids = [...selected.value]
  if (!ids.length) return
  Modal.warning({
    title: `确认删除选中的 ${ids.length} 份简历？`,
    content: '所选简历将从简历库删除（历史诊断报告保留）。',
    okText: '删除',
    cancelText: '取消',
    onOk: async () => {
      try {
        await api.deleteResumesBatch(ids)
        Message.success(`已删除 ${ids.length} 份简历`)
        selected.value = new Set()
        load()
      } catch (e) {
        Message.error(e.response?.data?.detail || '批量删除失败')
      }
    },
  })
}

function fmtTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

function scoreColor(score) {
  if (score >= 80) return 'text-ok'
  if (score >= 60) return 'text-warn'
  return 'text-bad'
}

async function load() {
  loading.value = true
  try {
    const res = await api.listResumes()
    items.value = res.data.items || []
  } catch (e) {
    Message.error(e.response?.data?.detail || '加载简历库失败')
  } finally {
    loading.value = false
  }
}

async function preview(r) {
  // PDF 走 iframe 直渲原文件，无需取文本；@load 前显示加载态
  pdfLoading.value = true
  if (r.file_type === 'pdf') {
    previewText.value = ''
    previewing.value = r
    return
  }
  try {
    const res = await api.getResume(r.id)
    previewText.value = res.data.text || res.data.raw_text || '（无内容）'
    previewing.value = r
  } catch (e) {
    // ResumeOut 只有 text_length；预览需要原文——走完整内容接口
    Message.error(e.response?.data?.detail || '预览加载失败')
  }
}

function rename(r) {
  // 轻量重命名：原生 prompt（避免再引一层弹窗组件）
  const name = window.prompt('新的名称：', r.filename)
  if (!name || name.trim() === r.filename) return
  api.renameResume(r.id, name.trim()).then(() => {
    Message.success('已重命名')
    load()
  }).catch((e) => Message.error(e.response?.data?.detail || '重命名失败'))
}

function remove(r) {
  Modal.warning({
    title: '确认删除该简历？',
    content: `「${r.filename}」将从简历库删除（历史诊断报告保留）。`,
    okText: '删除',
    cancelText: '取消',
    hideCancel: false,
    onOk: async () => {
      try {
        await api.deleteResume(r.id)
        Message.success('已删除')
        load()
      } catch (e) {
        Message.error(e.response?.data?.detail || '删除失败')
      }
    },
  })
}

onMounted(load)
</script>
