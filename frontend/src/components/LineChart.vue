<template>
  <div ref="chartRef" style="width: 100%; height: 100%;"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

/**
 * 折线趋势图（M38 工作台，复用 RadarChart 的主题取色方式）
 * points: [{ x: '09-24', y: 74 }]（时间正序）；max: y 轴量程上限
 */
const props = defineProps({
  points: { type: Array, required: true },
  max: { type: Number, default: 100 },
})

let chart = null
const chartRef = ref(null)

function colorOf(c) {
  return getComputedStyle(document.documentElement).getPropertyValue(c).trim()
}

function render() {
  if (!chartRef.value) return
  chart = chart || echarts.init(chartRef.value)
  if (!props.points.length) {
    chart.clear()
    chart.setOption({
      title: {
        text: '暂无数据', left: 'center', top: 'middle',
        textStyle: { color: colorOf('--c-ink-faint'), fontSize: 12, fontWeight: 400 },
      },
    })
    return
  }
  chart.setOption({
    grid: { left: 34, right: 12, top: 14, bottom: 24 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: colorOf('--c-panel'),
      borderColor: colorOf('--c-line-strong'),
      textStyle: { color: colorOf('--c-ink'), fontSize: 12 },
      // 单点时 ECharts 默认会把白底 tooltip 顶到图表中间，限制样式避免突兀
      valueFormatter: v => `${v} 分`,
    },
    xAxis: {
      type: 'category', data: props.points.map(p => p.x),
      axisLine: { lineStyle: { color: colorOf('--c-line') } },
      axisTick: { show: false },
      axisLabel: { color: colorOf('--c-ink-faint'), fontSize: 11 },
    },
    yAxis: {
      type: 'value', min: 0, max: props.max,
      splitLine: { lineStyle: { color: colorOf('--c-line') } },
      axisLabel: { color: colorOf('--c-ink-faint'), fontSize: 11 },
    },
    series: [{
      type: 'line', data: props.points.map(p => p.y),
      smooth: true, symbol: 'circle', symbolSize: 6,
      lineStyle: { color: colorOf('--c-accent'), width: 2 },
      itemStyle: { color: colorOf('--c-accent') },
      areaStyle: { color: colorOf('--c-accent'), opacity: 0.08 },
    }],
  }, { notMerge: true })
}

function onResize() {
  chart?.resize()
}

watch(() => props.points, render, { deep: true })

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
