<template>
  <a-modal :visible="visible" @cancel="$emit('update:visible', false)" :footer="false"
    :width="920" unmount-on-close title="版本历史与对比">
    <div class="flex gap-4 min-h-[420px]">
      <!-- 左：版本列表 -->
      <div class="w-56 shrink-0 flex flex-col border-r border-line pr-4">
        <div class="text-xs text-ink-faint mb-2">勾选两版进行对比（先旧后新）</div>
        <div class="flex-1 overflow-y-auto space-y-1.5 max-h-[400px]">
          <button v-for="v in versions" :key="v.id" @click="pick(v)"
            class="w-full text-left px-3 py-2 rounded-lg border transition-colors"
            :class="rowCls(v)">
            <div class="flex items-center gap-1.5">
              <span class="text-xs font-mono font-semibold">#{{ v.seq }}</span>
              <span class="text-[10px] px-1 py-0.5 rounded" :class="sourceCls(v.source)">
                {{ sourceLabel(v.source) }}
              </span>
              <span v-if="selA?.id === v.id" class="ml-auto text-[10px] text-ink-sub">旧版</span>
              <span v-else-if="selB?.id === v.id" class="ml-auto text-[10px] text-accent">新版</span>
            </div>
            <div class="text-[10px] text-ink-faint mt-0.5 font-mono">
              {{ fmtTime(v.created_at) }} · {{ v.chars }} 字
            </div>
          </button>
        </div>
      </div>

      <!-- 右：对比视图 -->
      <div class="flex-1 min-w-0 flex flex-col">
        <template v-if="rows">
          <div class="flex items-center gap-3 mb-2 text-xs">
            <span class="font-medium text-ink">{{ selA ? `#${selA.seq}` : '—' }} → {{ selB ? `#${selB.seq}` : '—' }}</span>
            <span class="text-ok">+{{ stats.added }} 行</span>
            <span class="text-bad">-{{ stats.removed }} 行</span>
          </div>
          <div class="flex-1 overflow-auto rounded-xl border border-line bg-panel max-h-[430px] font-mono text-xs leading-5">
            <div class="grid grid-cols-2">
              <div class="px-2 py-1 border-b border-line text-center text-[10px] text-ink-faint bg-inset">旧版</div>
              <div class="px-2 py-1 border-b border-l border-line text-center text-[10px] text-ink-faint bg-inset">新版</div>
            </div>
            <div v-for="(row, idx) in rows" :key="idx" class="grid grid-cols-2">
              <div class="px-2 whitespace-pre-wrap break-words border-b border-line/40"
                :class="cellCls(row.left)">{{ row.left?.text || ' ' }}</div>
              <div class="px-2 whitespace-pre-wrap break-words border-b border-l border-line/40"
                :class="cellCls(row.right)">{{ row.right?.text || ' ' }}</div>
            </div>
          </div>
        </template>
        <div v-else class="flex-1 flex flex-col items-center justify-center text-center px-8">
          <template v-if="versions.length >= 2">
            <div class="text-3xl mb-3">🔀</div>
            <div class="text-sm text-ink-sub">从左侧选两个版本开始对比</div>
          </template>
          <template v-else-if="versions.length === 1">
            <div class="text-3xl mb-3">🗂</div>
            <div class="text-sm text-ink-sub">当前只有 1 个版本；在编辑器中修改并保存后将形成版本链</div>
          </template>
          <template v-else>
            <div class="text-3xl mb-3">🗂</div>
            <div class="text-sm text-ink-sub">暂无版本快照</div>
            <div class="text-xs text-ink-faint mt-1">该简历创建于版本功能上线前；在编辑器中修改并保存后将自动形成版本链</div>
          </template>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import api from '../api'
import { diffLines, toPairedRows, diffStats } from '../utils/diff'

const props = defineProps({
  visible: { type: Boolean, default: false },
  resumeId: { type: Number, default: null },
  resumeName: { type: String, default: '' },
})
defineEmits(['update:visible'])

const versions = ref([]) // [{id, source, chars, created_at, seq}]
const selA = ref(null) // 旧版（先点）
const selB = ref(null) // 新版（后点）
const rows = ref(null)
const stats = ref({ added: 0, removed: 0 })

const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '')

const sourceLabel = (s) => ({ initial: '初始', editor: '编辑器', manual: '更新' }[s] || s)
const sourceCls = (s) => ({
  initial: 'bg-inset text-ink-sub',
  editor: 'bg-accent/10 text-accent',
  manual: 'bg-warn/10 text-warn',
}[s] || 'bg-inset text-ink-sub')

function rowCls(v) {
  if (selA.value?.id === v.id) return 'border-line-strong bg-inset'
  if (selB.value?.id === v.id) return 'border-accent/60 bg-accent/5'
  return 'border-line hover:border-line-strong'
}

function cellCls(cell) {
  if (!cell) return ''
  return {
    same: 'text-ink',
    del: 'bg-bad/10 text-ink',
    add: 'bg-ok/10 text-ink',
    empty: 'bg-inset/40',
  }[cell.type] || ''
}

function pick(v) {
  // 重复点已选中的取消；否则按 A→B 顺序填充
  if (selA.value?.id === v.id) {
    selA.value = null
  } else if (selB.value?.id === v.id) {
    selB.value = null
  } else if (!selA.value) {
    selA.value = v
  } else if (!selB.value) {
    selB.value = v
  } else {
    // 都已选则重新开始：新点击作为旧版，原新版清空
    selA.value = v
    selB.value = null
  }
  renderDiff()
}

async function renderDiff() {
  if (!selA.value || !selB.value) {
    rows.value = null
    return
  }
  try {
    const [ra, rb] = await Promise.all([
      api.getResumeVersion(props.resumeId, selA.value.id),
      api.getResumeVersion(props.resumeId, selB.value.id),
    ])
    const blocks = diffLines(ra.data.content, rb.data.content)
    rows.value = toPairedRows(blocks)
    stats.value = diffStats(blocks)
  } catch (e) {
    Message.error(e.response?.data?.detail || '版本内容加载失败')
    rows.value = null
  }
}

watch(
  () => props.visible,
  async (open) => {
    if (!open || !props.resumeId) return
    versions.value = []
    selA.value = null
    selB.value = null
    rows.value = null
    try {
      const res = await api.listResumeVersions(props.resumeId)
      // 时间正序编号为 v1..vN（展示倒序）
      const asc = [...res.data].reverse()
      versions.value = res.data.map((v) => ({ ...v, seq: asc.findIndex((x) => x.id === v.id) + 1 }))
    } catch (e) {
      Message.error(e.response?.data?.detail || '版本列表加载失败')
    }
  },
)
</script>
