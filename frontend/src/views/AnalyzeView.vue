<template>
  <div class="max-w-3xl mx-auto px-6 md:px-8 py-12 md:py-20">

    <div class="mb-10 text-center">
      <h1 class="text-3xl md:text-4xl font-semibold text-gray-800 mb-2">新建诊断</h1>
      <p class="text-sm text-gray-600">上传简历，填写意向职位，实时获取诊断报告</p>
    </div>

    <div class="bg-[#e0e5ec] rounded-2xl p-8 md:p-12
      shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">

      <div class="space-y-8">

        <!-- 1. 上传 -->
        <div>
          <div class="flex items-center gap-3 mb-4">
            <span class="w-7 h-7 rounded-xl bg-[#6d5dfc] text-white text-xs font-semibold flex items-center justify-center
              shadow-[3px_3px_6px_#b8bcc2,-3px_-3px_6px_#ffffff]">1</span>
            <span class="text-sm font-semibold text-gray-800">上传简历</span>
            <span class="text-xs text-gray-500">PDF / Word</span>
          </div>
          <label class="block cursor-pointer group">
            <input type="file" accept=".pdf,.docx,.doc" class="hidden" @change="onFileChange"/>
            <div class="rounded-xl px-6 py-10 text-center
              bg-[#e0e5ec]
              shadow-[inset_6px_6px_12px_#b8bcc2,inset_-6px_-6px_12px_#ffffff]
              group-hover:shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
              transition-all duration-300 ease-in-out">
              <div class="text-3xl mb-3">📄</div>
              <div v-if="!file" class="text-sm text-gray-600">点击选择简历文件</div>
              <div v-else class="text-sm text-[#6d5dfc] font-medium">{{ file.name }}</div>
              <div class="text-xs text-gray-400 mt-2">支持 .pdf .docx .doc</div>
            </div>
          </label>
        </div>

        <!-- 2. 意向职位 -->
        <div>
          <div class="flex items-center gap-3 mb-4">
            <span class="w-7 h-7 rounded-xl bg-[#6d5dfc] text-white text-xs font-semibold flex items-center justify-center
              shadow-[3px_3px_6px_#b8bcc2,-3px_-3px_6px_#ffffff]">2</span>
            <span class="text-sm font-semibold text-gray-800">意向职位</span>
          </div>
          <input v-model="keyword" type="text" placeholder="如：Python 后端 / 数据分析 / 大模型"
                 class="w-full px-5 py-3.5 text-sm text-gray-800 placeholder-gray-400
              bg-[#e0e5ec] rounded-xl border-0
              shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
              focus:outline-none
              focus:shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]
              transition-shadow duration-300 ease-in-out"/>

          <div class="flex flex-wrap gap-2 mt-4">
            <button v-for="t in quickTags" :key="t" @click="keyword = t"
                    class="px-3 py-1.5 text-xs font-medium rounded-xl
                bg-[#e0e5ec] text-gray-600
                shadow-[3px_3px_6px_#b8bcc2,-3px_-3px_6px_#ffffff]
                hover:shadow-[1px_1px_2px_#b8bcc2,-1px_-1px_2px_#ffffff]
                active:shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]
                transition-all duration-300 ease-in-out">
              {{ t }}
            </button>
          </div>
        </div>

        <!-- 3. 城市 + 数量 -->
        <div>
          <div class="flex items-center gap-3 mb-4">
            <span class="w-7 h-7 rounded-xl bg-[#6d5dfc] text-white text-xs font-semibold flex items-center justify-center
              shadow-[3px_3px_6px_#b8bcc2,-3px_-3px_6px_#ffffff]">3</span>
            <span class="text-sm font-semibold text-gray-800">城市 / 推荐数量</span>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <select v-model="city"
                    class="w-full px-5 py-3.5 text-sm text-gray-800
                bg-[#e0e5ec] rounded-xl border-0
                shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
                focus:outline-none
                focus:shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]
                transition-shadow duration-300 ease-in-out">
              <option v-for="c in ['北京','上海','深圳','广州','杭州']" :key="c">{{ c }}</option>
            </select>

            <div class="flex items-center gap-4 px-5 py-3.5 rounded-xl
              bg-[#e0e5ec]
              shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]">
              <input v-model.number="topK" type="range" min="3" max="20" class="flex-1"/>
              <span class="text-gray-800 font-semibold text-sm w-6 text-right">{{ topK }}</span>
            </div>
          </div>
        </div>

        <!-- 按钮 -->
        <button @click="startAnalyze" :disabled="loading || !file || !keyword"
                class="w-full px-5 py-4 text-sm font-medium rounded-xl
            bg-[#6d5dfc] text-white
            shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]
            hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
            disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
            active:shadow-[inset_4px_4px_8px_rgba(0,0,0,0.2),inset_-4px_-4px_8px_rgba(255,255,255,0.1)]
            transition-all duration-300 ease-in-out">
          {{ loading ? '启动中...' : '🚀 开始实时分析' }}
        </button>

        <div class="text-center text-xs text-gray-500">
          首次分析约需 3-5 分钟
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import {ref} from 'vue'
import {useRouter} from 'vue-router'
import api from '../api'

const router = useRouter()
const file = ref(null)
const keyword = ref('Python 后端')
const city = ref('北京')
const topK = ref(10)
const loading = ref(false)

const quickTags = ['Python 后端', '数据分析', '大模型', '算法工程师', 'Java 开发', '前端开发']

function onFileChange(e) {
  file.value = e.target.files[0] || null
}

async function startAnalyze() {
  if (!file.value || !keyword.value) return
  loading.value = true
  try {
    const up = await api.uploadResume(file.value)
    const resumeId = up.data.id

    let llmConfig = null
    try {
      const cfg = JSON.parse(localStorage.getItem('llm_config') || '{}')
      if (cfg.api_key) llmConfig = cfg
    } catch (e) {
    }

    const res = await api.startLiveAnalyze({
      resume_id: resumeId,
      keyword: keyword.value,
      city: city.value,
      top_k: topK.value,
      llm_config: llmConfig,
      resume_name: file.value?.name || '',
    })
    router.push(`/result/${res.data.task_id}`)
  } catch (e) {
    console.error(e)
    alert('失败：' + (e.response?.data?.detail || e.message))
    loading.value = false
  }
}
</script>