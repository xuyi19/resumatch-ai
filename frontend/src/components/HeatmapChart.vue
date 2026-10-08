<script setup>
/**
 * M53 活跃热力图：GitHub 风格贡献子图（近 90 天每日活跃）。
 * props: days — [{date:'2026-07-11', count:n}]，时间正序。
 * 行 = 周一~周日，列 = 周；首列按首个日期的星期补空对齐。
 * grid-template-rows 用 inline style（tailwind 默认无 grid-rows-7）。
 * 回炉：① 满档色 bg-accent 纯克莱因蓝在亮色板显黑 → 阶梯封顶 accent/80；
 *      ② 13 列小格子撑不满整卡 → 格子放大 + 右侧活跃统计块填补空白。
 */
import { computed } from 'vue'

const props = defineProps({
  days: { type: Array, default: () => [] },
})

function heatLevel(n) {
  if (!n) return 0
  if (n === 1) return 1
  if (n === 2) return 2
  if (n <= 4) return 3
  return 4
}

const cells = computed(() => {
  if (!props.days.length) return []
  const lead = (new Date(props.days[0].date + 'T00:00:00').getDay() + 6) % 7
  return [
    ...Array.from({ length: lead }, () => null),
    ...props.days.map((d) => ({ ...d, level: heatLevel(d.count) })),
  ]
})

// 顶档 80% 透明度：克莱因蓝在奶油底上保持「蓝」而不是发黑
const LEVEL_BG = ['bg-inset', 'bg-accent/25', 'bg-accent/45', 'bg-accent/65', 'bg-accent/80']

const stats = computed(() => {
  const list = props.days
  const total = list.reduce((s, d) => s + d.count, 0)
  const activeDays = list.filter((d) => d.count > 0).length
  let streak = 0
  for (let i = list.length - 1; i >= 0; i--) {
    if (list[i].count > 0) streak++
    else break
  }
  return { total, activeDays, streak }
})

function label(c) {
  return `${Number(c.date.slice(5, 7))} 月 ${Number(c.date.slice(8, 10))} 日：${c.count} 次活跃`
}
</script>

<template>
  <div v-if="days.length" class="flex flex-col lg:flex-row lg:items-center gap-5">
    <!-- 热力格子：14px 大格，触控也更好点按 -->
    <div class="overflow-x-auto shrink-0">
      <div
        class="grid grid-flow-col gap-[4px] w-max"
        style="grid-template-rows: repeat(7, 14px)"
      >
        <template v-for="(c, i) in cells" :key="i">
          <span v-if="!c" class="w-3.5 h-3.5 rounded-[4px] bg-transparent" />
          <span v-else :title="label(c)"
            class="w-3.5 h-3.5 rounded-[4px] transition-colors hover:ring-1 hover:ring-accent/60"
            :class="LEVEL_BG[c.level]" />
        </template>
      </div>
      <div class="flex items-center justify-end gap-1 mt-2 text-[10px] text-ink-faint">
        <span>少</span>
        <span v-for="(bg, i) in LEVEL_BG" :key="i" class="w-2.5 h-2.5 rounded-[3px]" :class="bg" />
        <span>多</span>
      </div>
    </div>

    <!-- 活跃统计：填补宽屏下的右侧空白 -->
    <div class="flex-1 min-w-0 grid grid-cols-3 gap-3 lg:border-l lg:border-line/60 lg:pl-6">
      <div>
        <div class="text-2xl font-semibold bg-gradient-to-r from-ink to-accent bg-clip-text text-transparent">
          {{ stats.total }}
        </div>
        <div class="text-[11px] text-ink-faint mt-0.5">近 90 天活跃次数</div>
      </div>
      <div>
        <div class="text-2xl font-semibold bg-gradient-to-r from-ink to-accent bg-clip-text text-transparent">
          {{ stats.activeDays }}
        </div>
        <div class="text-[11px] text-ink-faint mt-0.5">有记录的天数</div>
      </div>
      <div>
        <div class="text-2xl font-semibold bg-gradient-to-r from-ink to-accent bg-clip-text text-transparent">
          {{ stats.streak }}
          <span class="text-xs font-normal text-ink-faint">天</span>
        </div>
        <div class="text-[11px] text-ink-faint mt-0.5">连续活跃（截至今天）</div>
      </div>
    </div>
  </div>
</template>
