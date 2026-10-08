<script setup>
/**
 * M53 活跃热力图：GitHub 风格贡献子图（近 90 天每日活跃）。
 * props: days — [{date:'2026-07-11', count:n}]，时间正序。
 * 行 = 周一~周日，列 = 周；首列按首个日期的星期补空对齐。
 * grid-template-rows 用 inline style（tailwind 默认无 grid-rows-7）。
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

const LEVEL_BG = ['bg-inset', 'bg-accent/30', 'bg-accent/55', 'bg-accent/80', 'bg-accent']

function label(c) {
  return `${Number(c.date.slice(5, 7))} 月 ${Number(c.date.slice(8, 10))} 日：${c.count} 次活跃`
}
</script>

<template>
  <div v-if="days.length" class="overflow-x-auto">
    <div
      class="grid grid-flow-col gap-[3px] w-max"
      style="grid-template-rows: repeat(7, minmax(0, 1fr))"
    >
      <template v-for="(c, i) in cells" :key="i">
        <span v-if="!c" class="w-2.5 h-2.5 rounded-[3px] bg-transparent" />
        <span v-else :title="label(c)"
          class="w-2.5 h-2.5 rounded-[3px] transition-colors hover:ring-1 hover:ring-accent/60"
          :class="LEVEL_BG[c.level]" />
      </template>
    </div>
    <div class="flex items-center justify-end gap-1 mt-2 text-[10px] text-ink-faint">
      <span>少</span>
      <span v-for="(bg, i) in LEVEL_BG" :key="i" class="w-2.5 h-2.5 rounded-[3px]" :class="bg" />
      <span>多</span>
    </div>
  </div>
</template>
