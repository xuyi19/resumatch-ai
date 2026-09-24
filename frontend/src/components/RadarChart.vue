<template>
  <div ref="chartRef" style="width: 100%; height: 100%;"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

/**
 * 六维雷达图（M20 抽取复用：结果页单系列 / 历史对比双系列）
 * series: [{ name, values, color? }]  color 传 CSS 变量名（如 --c-accent）或 rgb 串
 */
const props = defineProps({
  series: { type: Array, required: true },
})

const DIMS = [
  '信息完整',
  '量化成果',
  'STAR 结构',
  '技能含金量',
  '业绩亮点',
  '可读性',
]

let chart = null
const chartRef = ref(null)

function colorOf(c, alpha = 1) {
  const css = getComputedStyle(document.documentElement)
  const raw = c && c.startsWith('--')
    ? css.getPropertyValue(c).trim()
    : (c || css.getPropertyValue('--c-accent').trim())
  return alpha >= 1 ? `rgb(${raw})` : `rgb(${raw} / ${alpha})`
}

function render() {
  if (!chartRef.value || !props.series.length) return
  chart = chart || echarts.init(chartRef.value)
  chart.setOption({
    radar: {
      indicator: DIMS.map(name => ({ name, max: 100 })),
      splitNumber: 5,
      axisName: { color: colorOf('--c-ink-sub'), fontSize: 12, fontWeight: 500 },
      splitLine: { lineStyle: { color: colorOf('--c-line') } },
      splitArea: { areaStyle: { color: ['transparent', colorOf('--c-line', 0.4)] } },
      axisLine: { lineStyle: { color: colorOf('--c-line') } },
    },
    legend: props.series.length > 1 ? {
      bottom: 0,
      textStyle: { color: colorOf('--c-ink-sub'), fontSize: 12 },
    } : undefined,
    series: [{
      type: 'radar',
      data: props.series.map((s, i) => ({
        name: s.name,
        value: s.values,
        areaStyle: { color: colorOf(s.color, i === 0 ? 0.2 : 0.12) },
        lineStyle: { color: colorOf(s.color), width: 2 },
        itemStyle: { color: colorOf(s.color) },
      })),
    }],
  }, { notMerge: true })
}

function onResize() {
  chart?.resize()
}

watch(() => props.series, render, { deep: true })

onMounted(() => {
  render()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>
