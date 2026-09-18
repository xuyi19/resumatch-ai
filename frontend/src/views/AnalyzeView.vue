<template>
  <div class="bg-[#f5f5f7] py-20 px-6 min-h-[calc(100vh-12rem)]">
    <div class="max-w-2xl mx-auto">
      <div class="mb-12 text-center">
        <h1 class="text-4xl md:text-5xl font-semibold tracking-tight text-black mb-3">新建诊断</h1>
        <p class="text-base text-gray-500">上传简历 + 粘贴岗位 JD，AI 生成针对性诊断</p>
      </div>

      <div class="bg-white rounded-2xl p-8 md:p-12 shadow-[0_4px_12px_rgba(0,0,0,0.06)]">
        <div class="space-y-10">

          <!-- 1. 上传简历 -->
          <div>
            <div class="flex items-center gap-3 mb-4">
              <span class="w-7 h-7 rounded-full bg-[#0071e3] text-white text-sm font-semibold flex items-center justify-center">1</span>
              <span class="text-base font-semibold tracking-tight text-black">上传简历</span>
              <span class="text-xs text-gray-400">PDF / Word</span>
            </div>
            <label class="block cursor-pointer">
              <input type="file" accept=".pdf,.docx,.doc" class="hidden" @change="onFileChange" />
              <div class="border border-dashed border-gray-300 rounded-2xl px-6 py-10 text-center
                hover:border-[#0071e3] hover:bg-[#0071e3]/5
                active:scale-[0.99]
                transition-all duration-200 ease-[cubic-bezier(0.25,0.1,0.25,1)]">
                <div class="text-3xl mb-3">📄</div>
                <div v-if="!file" class="text-sm text-gray-500">点击选择简历文件</div>
                <div v-else class="text-sm text-[#0071e3] font-medium">{{ file.name }}</div>
                <div class="text-xs text-gray-400 mt-2">支持 .pdf .docx .doc</div>
              </div>
            </label>
          </div>

          <!-- 2. 岗位 JD -->
          <div>
            <div class="flex items-center gap-3 mb-4">
              <span class="w-7 h-7 rounded-full bg-[#0071e3] text-white text-sm font-semibold flex items-center justify-center">2</span>
              <span class="text-base font-semibold tracking-tight text-black">岗位 JD</span>
            </div>
            <textarea v-model="jdText" rows="8"
              placeholder="粘贴目标岗位的 JD 文本&#10;&#10;可以从 BOSS、智联、拉勾等平台复制岗位描述，直接粘贴到此处。"
              class="w-full px-4 py-3 text-sm text-black placeholder-gray-400
                bg-[#f5f5f7] rounded-xl border-0 resize-none
                focus:outline-none focus:ring-2 focus:ring-[#0071e3]
                transition-all duration-200" />
            <div class="text-xs text-gray-400 mt-2">
              已输入 {{ jdText.length }} 字（至少 20 字）
            </div>
          </div>

          <!-- 提交 -->
          <button @click="startAnalyze" :disabled="loading || !canSubmit"
            class="w-full py-4 rounded-full text-base font-medium
              bg-[#0071e3] text-white
              hover:bg-[#0077ed]
              disabled:opacity-40 disabled:cursor-not-allowed
              active:scale-[0.98]
              transition-all duration-200">
            {{ loading ? '启动中...' : '🚀 开始诊断' }}
          </button>

          <div class="text-center text-xs text-gray-400">
            诊断约需 60-90 秒
          </div>

        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import api from '../api'

const router = useRouter()

const file = ref(null)
const jdText = ref('')
const loading = ref(false)

const canSubmit = computed(() => {
  return !!file.value && jdText.value.trim().length >= 20
})

function onFileChange(e) {
  file.value = e.target.files[0] || null
}

async function startAnalyze() {
  if (!canSubmit.value) {
    Message.warning('请上传简历并粘贴至少 20 字的岗位 JD')
    return
  }

  loading.value = true
  try {
    // 1. 上传简历
    const up = await api.uploadResume(file.value)
    const resumeId = up.data.id

    // 2. 构建请求
    let cfg = {}
    try { cfg = JSON.parse(localStorage.getItem('llm_config') || '{}') } catch (e) {}

    const body = {
      resume_id: resumeId,
      jd_text: jdText.value.trim(),
      resume_name: file.value?.name || '',
    }
    if (cfg.api_key) body.llm_config = cfg

    // 3. 启动
    const res = await api.startLiveAnalyze(body)
    router.push(`/result/${res.data.task_id}`)
  } catch (e) {
    console.error(e)
    Message.error('失败：' + (e.response?.data?.detail || e.message))
    loading.value = false
  }
}
</script>
