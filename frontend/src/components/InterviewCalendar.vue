<template>
  <div>
    <!-- 月份导航：‹ 往前（更早）/ › 往后，对齐周报卡的「‹ 上周 / › 」方向惯例 -->
    <div class="flex items-center justify-between mb-3">
      <div class="text-sm font-semibold text-ink font-mono">{{ viewYear }} 年 {{ viewMonth }} 月</div>
      <div class="flex items-center gap-1.5">
        <button v-if="!isCurrentMonth" @click="goToday"
          class="text-xs px-2 py-1 rounded-lg border border-line text-ink-sub
            hover:border-accent/60 transition-colors">回到今天</button>
        <button @click="shiftMonth(-1)" :disabled="!canGoPrev" :title="canGoPrev ? '上一月' : '已到最早可查看月份'"
          class="w-7 h-7 rounded-lg border border-line text-ink-sub text-sm leading-none
            hover:border-accent/60 transition-colors
            disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:border-line">‹</button>
        <button @click="shiftMonth(1)" :disabled="!canGoNext" :title="canGoNext ? '下一月' : '已到最晚可查看月份'"
          class="w-7 h-7 rounded-lg border border-line text-ink-sub text-sm leading-none
            hover:border-accent/60 transition-colors
            disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:border-line">›</button>
      </div>
    </div>

    <!-- 星期表头：周一起始 -->
    <div class="grid grid-cols-7 gap-1 mb-1">
      <div v-for="w in weekdays" :key="w" class="text-center text-[11px] text-ink-faint py-0.5">{{ w }}</div>
    </div>

    <!-- 日期网格 -->
    <div class="grid grid-cols-7 gap-1">
      <div v-for="(cell, i) in cells" :key="i"
        class="cal-cell min-h-[64px] rounded-lg border p-1 transition-colors"
        :class="[
          cell.isToday ? 'cal-today border-2 border-ink/80 bg-accent/5' : 'border-line',
          cell.inMonth ? '' : 'opacity-40',
          cell.events.length ? 'bg-inset/50' : '',
        ]">
        <div class="text-xs font-mono mb-0.5 px-0.5"
          :class="cell.isToday ? 'text-accent font-semibold' : cell.inMonth ? 'text-ink-sub' : 'text-ink-faint'">
          {{ cell.day }}
        </div>
        <!-- 日程条：最多露 2 条，多的折叠 +N；点击跳岗位库调整 -->
        <button v-for="ev in cell.events.slice(0, 2)" :key="ev.id"
          class="cal-chip block w-full text-left px-1 py-0.5 rounded text-[10px] leading-tight
            truncate transition-colors"
          :class="evMeta(ev).past ? 'bg-warn/10 text-warn hover:bg-warn/20' : 'bg-accent/10 text-accent hover:bg-accent/20'"
          :title="evMeta(ev).full"
          @click="$emit('open', ev.id)">
          {{ evMeta(ev).hm }} {{ evMeta(ev).label }}
        </button>
        <span v-if="cell.events.length > 2" class="block px-1 text-[10px] text-ink-faint"
          :title="cell.events.slice(2).map((e) => evMeta(e).full).join('\n')">
          +{{ cell.events.length - 2 }}
        </span>
      </div>
    </div>

    <!-- 图例 -->
    <div class="flex items-center gap-4 mt-3">
      <span class="flex items-center gap-1.5 text-[11px] text-ink-faint">
        <span class="w-2.5 h-2.5 rounded border-2 border-ink/80 bg-accent/5 inline-block"></span>今天
      </span>
      <span class="flex items-center gap-1.5 text-[11px] text-ink-faint">
        <span class="w-2.5 h-2.5 rounded bg-accent/10 inline-block"></span>待面试
      </span>
      <span class="flex items-center gap-1.5 text-[11px] text-ink-faint">
        <span class="w-2.5 h-2.5 rounded bg-warn/10 inline-block"></span>已过期（记得跟进结果）
      </span>
    </div>
  </div>
</template>

<script setup>
/**
 * 优化⑪ 面试日程月历：SavedJob.next_interview_at 全量日程按月集中展示。
 * 纯前端组件零请求——数据来自 /jobs/followups 的 upcoming_interviews_all
 * （后端已滤掉 offer/closed 终态），点击日程条 emit open(id) 由父级跳岗位库。
 * 跨月导航限 ±12 个月：日程是近期事务，放开通行无意义还容易迷路。
 */
import { computed, ref } from 'vue'

const props = defineProps({
  // followups.upcoming_interviews_all：{id,title,company,next_interview_at,status,days_left}
  interviews: { type: Array, default: () => [] },
})
defineEmits(['open'])

const weekdays = ['一', '二', '三', '四', '五', '六', '日']

const now = new Date()
const viewYear = ref(now.getFullYear())
const viewMonth = ref(now.getMonth() + 1) // 1-12

const monthKey = computed(() => viewYear.value * 12 + (viewMonth.value - 1))
const currentKey = now.getFullYear() * 12 + now.getMonth()
const isCurrentMonth = computed(() => monthKey.value === currentKey)
const canGoPrev = computed(() => monthKey.value > currentKey - 12)
const canGoNext = computed(() => monthKey.value < currentKey + 12)

function shiftMonth(delta) {
  const key = monthKey.value + delta
  viewYear.value = Math.floor(key / 12)
  viewMonth.value = (key % 12) + 1
}
function goToday() {
  viewYear.value = now.getFullYear()
  viewMonth.value = now.getMonth() + 1
}

const cells = computed(() => {
  const first = new Date(viewYear.value, viewMonth.value - 1, 1)
  const lead = (first.getDay() + 6) % 7 // 周一=0 … 周日=6
  const daysInMonth = new Date(viewYear.value, viewMonth.value, 0).getDate()
  const total = Math.ceil((lead + daysInMonth) / 7) * 7
  const start = new Date(viewYear.value, viewMonth.value - 1, 1 - lead)

  // 日程按「本地年-月-日」分桶（naive ISO 经 new Date 按本地时区解析，与列表卡口径一致）
  const byDay = new Map()
  for (const ev of props.interviews) {
    const d = new Date(ev.next_interview_at)
    if (Number.isNaN(d.getTime())) continue
    const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
    if (!byDay.has(key)) byDay.set(key, [])
    byDay.get(key).push(ev)
  }

  const out = []
  for (let i = 0; i < total; i++) {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)
    out.push({
      day: d.getDate(),
      inMonth: d.getMonth() === viewMonth.value - 1,
      isToday: d.getFullYear() === now.getFullYear()
        && d.getMonth() === now.getMonth() && d.getDate() === now.getDate(),
      events: byDay.get(`${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`) || [],
    })
  }
  return out
})

function evMeta(ev) {
  const d = new Date(ev.next_interview_at)
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  return {
    hm,
    label: ev.company || ev.title,
    past: ev.days_left < 0,
    full: `${d.getMonth() + 1}月${d.getDate()}日 ${hm} · ${ev.title}${ev.company ? ' · ' + ev.company : ''}`,
  }
}
</script>
