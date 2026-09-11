<template>
  <div class="max-w-6xl mx-auto px-6 md:px-8 py-12 md:py-20">

    <!-- 进度 -->
    <div v-if="status === 'running' || status === 'pending'"
      class="max-w-2xl mx-auto text-center py-20">
      <div class="inline-block relative mb-8">
        <div class="w-20 h-20 rounded-2xl bg-[#e0e5ec]
          shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]"></div>
        <div class="absolute inset-0 w-20 h-20 rounded-2xl border-4 border-transparent border-t-[#6d5dfc] animate-spin"></div>
      </div>
      <div class="text-xl font-semibold text-gray-800 mb-2">{{ message || '正在初始化...' }}</div>
      <div class="text-sm text-gray-600 mb-8">实时爬取 + 多智能体诊断约需 3-5 分钟</div>

      <div class="max-w-md mx-auto h-3 rounded-full bg-[#e0e5ec]
        shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] overflow-hidden">
        <div class="h-full bg-[#6d5dfc] rounded-full transition-all duration-300"
          :style="{ width: progress + '%' }" />
      </div>
      <div class="text-sm text-gray-600 mt-4 font-medium">{{ progress }}%</div>
    </div>

    <!-- 结果 -->
    <div v-else-if="status === 'success'" class="space-y-6">

      <!-- 标题 -->
      <div class="text-center mb-8">
        <h1 class="text-3xl md:text-4xl font-semibold text-gray-800 mb-2">诊断报告</h1>
        <p v-if="result.diagnosis_target" class="text-sm text-gray-600">
          {{ result.diagnosis_target.title }} · {{ result.diagnosis_target.company }}
        </p>
      </div>

      <!-- 综合评分 -->
      <div class="bg-[#e0e5ec] rounded-2xl p-8
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6 items-center">
          <div class="text-center md:text-left">
            <div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">综合评分</div>
            <div class="text-6xl font-semibold text-[#6d5dfc]">{{ result.diagnosis?.scores?.overall || '--' }}</div>
            <div class="text-xs text-gray-500 mt-1">/ 100</div>
          </div>
          <div class="md:col-span-3">
            <div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">技能标签</div>
            <div class="flex flex-wrap gap-2">
              <span v-for="s in result.diagnosis?.parsed?.skills || []" :key="s"
                class="px-3 py-1.5 rounded-xl text-xs font-medium
                  bg-[#e0e5ec] text-[#6d5dfc]
                  shadow-[3px_3px_6px_#b8bcc2,-3px_-3px_6px_#ffffff]">
                {{ s }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 雷达图 + 综合评价 -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="lg:col-span-2 bg-[#e0e5ec] rounded-2xl p-6
          shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
          <h2 class="text-base font-semibold text-gray-800 mb-4">六维评分</h2>
          <div ref="chartRef" style="width:100%; height:360px" />
        </div>

        <div class="bg-[#e0e5ec] rounded-2xl p-6
          shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
          <h2 class="text-base font-semibold text-gray-800 mb-4">综合评价</h2>
          <p class="text-sm text-gray-600 leading-relaxed">{{ overallComment }}</p>
        </div>
      </div>

      <!-- Top 岗位 -->
      <div class="bg-[#e0e5ec] rounded-2xl p-6
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-base font-semibold text-gray-800">推荐岗位</h2>
          <span class="text-xs text-gray-500">Top {{ (result.top_jobs || []).length }}</span>
        </div>
        <div class="space-y-2">
          <div v-for="(job, i) in result.top_jobs" :key="i"
            class="flex items-center gap-4 py-3 px-4 rounded-xl
              transition-all duration-300 ease-in-out
              hover:shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]">
            <div class="w-9 h-9 rounded-xl bg-[#e0e5ec] text-gray-600 text-xs font-semibold flex items-center justify-center shrink-0
              shadow-[3px_3px_6px_#b8bcc2,-3px_-3px_6px_#ffffff]">
              {{ i + 1 }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium text-gray-800 truncate">{{ job.title }}</div>
              <div class="text-xs text-gray-500 truncate mt-0.5">{{ job.company }} · {{ job.city }}</div>
            </div>
            <div class="text-base font-semibold text-[#6d5dfc] shrink-0">{{ job.score }}</div>
          </div>
        </div>
      </div>

      <!-- 优势 + 差距 -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div class="bg-[#e0e5ec] rounded-2xl p-6
          shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-8 h-8 rounded-xl bg-[#e0e5ec] flex items-center justify-center text-green-600
              shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]">✓</div>
            <h2 class="text-base font-semibold text-gray-800">主要优势</h2>
          </div>
          <ul class="space-y-3 text-sm text-gray-700">
            <li v-for="(item, i) in strengths" :key="i" class="flex gap-3 items-start">
              <span class="text-green-600 shrink-0 mt-0.5">✓</span>
              <span>{{ item }}</span>
            </li>
            <li v-if="!strengths.length" class="text-gray-400 text-sm">暂无高亮优势维度</li>
          </ul>
        </div>

        <div class="bg-[#e0e5ec] rounded-2xl p-6
          shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-8 h-8 rounded-xl bg-[#e0e5ec] flex items-center justify-center text-amber-600
              shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]">△</div>
            <h2 class="text-base font-semibold text-gray-800">待提升项</h2>
          </div>
          <ul class="space-y-3 text-sm text-gray-700">
            <li v-for="(g, i) in gaps" :key="i" class="flex gap-3 items-start">
              <span :class="severityColor(g.severity)" class="shrink-0 mt-0.5">△</span>
              <span>
                <span :class="severityColor(g.severity)" class="text-xs font-semibold">[{{ g.severity || '-' }}]</span>
                {{ g.description }}
              </span>
            </li>
            <li v-if="!gaps.length" class="text-gray-400 text-sm">暂无差距分析</li>
          </ul>
        </div>
      </div>

      <!-- 改写建议 -->
      <div class="bg-[#e0e5ec] rounded-2xl p-6
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <h2 class="text-base font-semibold text-gray-800 mb-4">改写建议</h2>
        <div class="space-y-4">
          <div v-for="(s, i) in suggestions" :key="i"
            class="p-5 rounded-xl bg-[#e0e5ec]
              shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]">
            <div class="text-xs text-gray-500 mb-2">{{ s.target }}</div>
            <div class="text-sm text-gray-400 line-through mb-2">{{ s.original || '（新增内容）' }}</div>
            <div class="text-sm text-gray-800 px-3 py-2 rounded-lg bg-[#6d5dfc]/10 border-l-2 border-[#6d5dfc]">
              {{ s.rewritten }}
            </div>
            <div class="text-xs text-gray-500 mt-3">💡 {{ s.reason }}</div>
          </div>

          <div v-if="overallAdvice"
            class="p-5 rounded-xl bg-[#6d5dfc]/10 text-sm text-gray-800">
            <span class="font-semibold text-[#6d5dfc]">整体建议：</span>{{ overallAdvice }}
          </div>
        </div>
      </div>

    </div>

    <!-- 失败 -->
    <div v-else-if="status === 'failed'"
      class="max-w-2xl mx-auto bg-[#e0e5ec] rounded-2xl p-12 text-center mt-12
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
      <div class="text-5xl mb-4">⚠️</div>
      <div class="text-base text-gray-700 mb-6">{{ errorMsg }}</div>
      <RouterLink to="/analyze"
        class="inline-block px-6 py-3 text-sm font-medium rounded-xl
          bg-[#6d5dfc] text-white
          shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]
          hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
          active:shadow-[inset_4px_4px_8px_rgba(0,0,0,0.2),inset_-4px_-4px_8px_rgba(255,255,255,0.1)]
          transition-all duration-300 ease-in-out">
        返回重试
      </RouterLink>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import * as echarts from 'echarts'
import api from '../api'

const route = useRoute()
const taskId = route.params.taskId

const status = ref('running')
const message = ref('')
const progress = ref(0)
const result = ref({})
const errorMsg = ref('')
const chartRef = ref(null)

let pollTimer = null
let chart = null

const scores = computed(() => result.value.diagnosis?.scores || {})

const overallComment = computed(() => {
  const s = scores.value
  const keys = ['completeness', 'skill_match', 'quantification', 'star_structure']
  return keys.map(k => s[k]?.comment).filter(Boolean).join(' ') || '（暂无评语）'
})

const strengths = computed(() => {
  const s = scores.value
  const labels = {
    completeness: '信息完整', quantification: '量化清晰', star_structure: 'STAR 结构',
    skill_match: '技能含金量', achievement: '业绩亮点', readability: '可读性',
  }
  const list = []
  Object.entries(s).forEach(([k, v]) => {
    if (typeof v === 'object' && v.score >= 80 && labels[k]) {
      list.push(`${labels[k]}（${v.score} 分）`)
    }
  })
  return list
})

const gaps = computed(() => (result.value.diagnosis?.gaps || []).filter(g => !g.summary))
const suggestions = computed(() => (result.value.diagnosis?.suggestions || []).filter(s => !s.overall_advice))
const overallAdvice = computed(() => {
  const arr = result.value.diagnosis?.suggestions || []
  return arr.find(s => s.overall_advice)?.overall_advice || ''
})

function severityColor(sev) {
  if (sev === 'high') return 'text-red-500'
  if (sev === 'medium') return 'text-amber-600'
  return 'text-gray-500'
}

async function poll() {
  try {
    const res = await api.getTaskStatus(taskId)
    const t = res.data
    status.value = t.status
    message.value = t.message
    progress.value = t.progress

    if (t.status === 'success') {
      result.value = t.result
      clearInterval(pollTimer)
      await nextTick()
      renderChart()
    } else if (t.status === 'failed') {
      errorMsg.value = t.error || '任务失败'
      clearInterval(pollTimer)
    }
  } catch (e) {
    // 内存里没有（服务重启过）→ 从数据库恢复
    if (e.response?.status === 404) {
      clearInterval(pollTimer)
      try {
        const hres = await api.getHistoryDetail(taskId)
        const record = hres.data
        if (record.status === 'success' && record.result) {
          status.value = 'success'
          result.value = record.result
          await nextTick()
          renderChart()
        } else {
          status.value = 'failed'
          errorMsg.value = record.error || '任务已过期'
        }
      } catch (err) {
        status.value = 'failed'
        errorMsg.value = '任务不存在'
      }
    }
  }
}

function renderChart() {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  const s = scores.value
  const dims = [
    { key: 'completeness', name: '信息完整' },
    { key: 'quantification', name: '量化成果' },
    { key: 'star_structure', name: 'STAR 结构' },
    { key: 'skill_match', name: '技能含金量' },
    { key: 'achievement', name: '业绩亮点' },
    { key: 'readability', name: '可读性' },
  ]
  const values = dims.map(d => s[d.key]?.score || 0)

  chart.setOption({
    radar: {
      indicator: dims.map(d => ({ name: d.name, max: 100 })),
      splitNumber: 5,
      axisName: { color: '#6b7280', fontSize: 12, fontWeight: 500 },
      splitLine: { lineStyle: { color: '#b8bcc2' } },
      splitArea: { areaStyle: { color: ['#e0e5ec', '#e8ecf2'] } },
      axisLine: { lineStyle: { color: '#b8bcc2' } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: values,
        areaStyle: { color: 'rgba(109, 93, 252, 0.2)' },
        lineStyle: { color: '#6d5dfc', width: 2 },
        itemStyle: { color: '#6d5dfc' },
      }],
    }],
  })
}

onMounted(() => {
  poll()
  pollTimer = setInterval(poll, 2000)
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  clearInterval(pollTimer)
  chart?.dispose()
})
</script>