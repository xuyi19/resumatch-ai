<template>
  <div class="min-h-screen bg-[#e0e5ec] py-10">
    <div class="max-w-3xl mx-auto px-6">

      <!-- 头部 -->
      <div class="mb-8 flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-semibold text-gray-800">对答式优化</h1>
          <p class="text-sm text-gray-500 mt-1">
            AI 追问关键信息，你补充后生成更真实的简历
          </p>
        </div>
        <RouterLink :to="`/result/${taskId}`"
                    class="text-sm text-gray-500 hover:text-gray-800">← 返回报告
        </RouterLink>
      </div>

      <!-- 进度条 -->
      <div v-if="total > 0 && !finished" class="mb-6 bg-[#e0e5ec] rounded-2xl p-4
        shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-gray-500">进度</span>
          <span class="text-sm font-semibold text-[#6d5dfc]">
            {{ currentIndex }} / {{ total }}
          </span>
        </div>
        <div class="h-2 rounded-full bg-[#e0e5ec]
          shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff] overflow-hidden">
          <div class="h-full bg-[#6d5dfc] rounded-full transition-all duration-500"
               :style="{ width: (total ? (currentIndex / total * 100) : 0) + '%' }"/>
        </div>
      </div>

      <!-- 对话区 -->
      <div class="bg-[#e0e5ec] rounded-2xl p-6
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">

        <!-- 加载中 -->
        <div v-if="loading" class="py-12 text-center">
          <div
              class="inline-block w-12 h-12 rounded-xl border-4 border-transparent border-t-[#6d5dfc] animate-spin"></div>
          <div class="text-sm text-gray-500 mt-4">{{ loadingMsg }}</div>
        </div>

        <!-- 问答列表 -->
        <div v-else class="space-y-6">

          <div v-for="(item, i) in history" :key="i" class="space-y-3">
            <div class="flex gap-3">
              <div
                  class="w-9 h-9 rounded-xl bg-[#6d5dfc] text-white flex items-center justify-center text-sm shrink-0 font-bold">
                AI
              </div>
              <div class="flex-1">
                <div class="text-xs text-gray-400 mb-1">{{ item.dimension }}</div>
                <div class="text-sm text-gray-800 leading-relaxed">{{ item.question }}</div>
                <div v-if="item.hint" class="text-xs text-gray-400 mt-1 italic">如：{{ item.hint }}</div>
              </div>
            </div>

            <div class="flex gap-3 justify-end">
              <div class="flex-1 max-w-[80%] text-right">
                <div class="inline-block px-4 py-2.5 rounded-2xl bg-[#6d5dfc] text-white text-sm text-left">
                  {{ item.answer }}
                </div>
              </div>
              <div
                  class="w-9 h-9 rounded-xl bg-gray-300 text-white flex items-center justify-center text-sm shrink-0 font-bold">
                我
              </div>
            </div>
          </div>

          <!-- 当前问题 -->
          <div v-if="currentQuestion" class="pt-4 border-t border-[#b8bcc2]/30">
            <div class="flex gap-3 mb-3">
              <div
                  class="w-9 h-9 rounded-xl bg-[#6d5dfc] text-white flex items-center justify-center text-sm shrink-0 font-bold">
                AI
              </div>
              <div class="flex-1">
                <div class="text-xs text-gray-400 mb-1">{{ currentQuestion.dimension }}</div>
                <div class="text-sm text-gray-800 leading-relaxed">{{ currentQuestion.question }}</div>
                <div v-if="currentQuestion.hint" class="text-xs text-gray-400 mt-1 italic">如：{{
                    currentQuestion.hint
                  }}
                </div>
              </div>
            </div>
            <textarea v-model="currentAnswer" rows="3"
                      placeholder="输入你的回答...（可留空跳过）"
                      class="w-full px-4 py-3 text-sm rounded-xl bg-[#e0e5ec] border-0 resize-none
                shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]
                focus:outline-none"/>
            <div class="flex gap-3 mt-3 justify-end">
              <button @click="skipQuestion" :disabled="submitting"
                      class="px-5 py-2 text-sm rounded-xl bg-[#e0e5ec] text-gray-500
                  shadow-[3px_3px_6px_#b8bcc2,-3px_-3px_6px_#ffffff]">
                跳过
              </button>
              <button @click="submitAnswer" :disabled="submitting"
                      class="px-6 py-2 text-sm font-medium rounded-xl
                  bg-[#6d5dfc] text-white
                  shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
                  disabled:opacity-50">
                {{ submitting ? '提交中...' : '提交' }}
              </button>
            </div>
          </div>

          <!-- 完成 -->
          <div v-else-if="finished && !diff" class="pt-6 text-center">
            <div class="text-lg font-semibold text-gray-800 mb-2">✓ 所有问题已答完</div>
            <div class="text-sm text-gray-500 mb-6">点击下方按钮生成优化简历</div>
            <button @click="generateResume" :disabled="generating"
                    class="px-8 py-3 text-sm font-medium rounded-xl
                bg-[#6d5dfc] text-white
                shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]
                disabled:opacity-50">
              {{ generating ? '生成中...（约 30 秒）' : '✨ 生成优化简历' }}
            </button>
          </div>

        </div>

      </div>

      <!-- diff 对比 -->
      <div v-if="diff" class="mt-8 space-y-4">
        <div class="text-lg font-semibold text-gray-800 mb-4">优化对比</div>
        <div v-for="(field, key) in diff" :key="key"
             class="bg-[#e0e5ec] rounded-2xl p-5
            shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]">
          <div class="text-sm font-semibold text-gray-700 mb-3">{{ fieldLabel(key) }}</div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <div class="text-xs text-gray-400 mb-2">原文</div>
              <div class="text-xs text-gray-500 bg-red-50 p-3 rounded-lg leading-relaxed whitespace-pre-wrap">
                {{ field.original || '（空）' }}
              </div>
            </div>
            <div>
              <div class="text-xs text-gray-400 mb-2">优化后</div>
              <div class="text-xs text-gray-800 bg-green-50 p-3 rounded-lg leading-relaxed whitespace-pre-wrap">
                {{ field.optimized || '（空）' }}
              </div>
            </div>
          </div>
        </div>

        <div class="text-center pt-4 flex gap-3 justify-center">
          <RouterLink :to="`/result/${taskId}`"
                      class="inline-block px-6 py-3 text-sm font-medium rounded-xl
              bg-[#e0e5ec] text-gray-700
              shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]">
            返回报告
          </RouterLink>
          <button @click="goToEditor"
                  class="inline-block px-6 py-3 text-sm font-medium rounded-xl
    bg-[#6d5dfc] text-white
    shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]">
            编辑并导出
          </button>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import {ref, onMounted} from 'vue'
import {useRoute, RouterLink} from 'vue-router'
import {Message} from '@arco-design/web-vue'
import api from '../api'

const route = useRoute()
const taskId = route.params.taskId

const loading = ref(true)
const loadingMsg = ref('正在准备...')
const submitting = ref(false)
const generating = ref(false)
const finished = ref(false)

const history = ref([])
const currentQuestion = ref(null)
const currentAnswer = ref('')
const currentIndex = ref(0)
const total = ref(0)
const diff = ref(null)

function fieldLabel(key) {
  return {
    summary: '个人简介',
    experience: '工作经历',
    projects: '项目经历',
    skills: '技能',
  }[key] || key
}

async function start() {
  loading.value = true
  loadingMsg.value = 'AI 正在分析简历，生成追问...'
  try {
    let cfg = {}
    try {
      cfg = JSON.parse(localStorage.getItem('llm_config') || '{}')
    } catch (e) {
    }

    const res = await api.startChat(taskId, cfg.api_key ? cfg : null)
    const data = res.data

    if (data.status === 'finished') {
      finished.value = true
      return
    }

    total.value = data.total
    currentIndex.value = data.current_index
    currentQuestion.value = data.question
  } catch (e) {
    Message.error('启动失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

async function submitAnswer() {
  if (!currentQuestion.value) return
  submitting.value = true
  const q = currentQuestion.value
  const answer = currentAnswer.value.trim()

  try {
    const res = await api.replyChat(taskId, q.id, answer || '（跳过）')
    const data = res.data

    history.value.push({
      dimension: q.dimension,
      question: q.question,
      hint: q.hint,
      answer: answer || '（跳过）',
    })
    currentAnswer.value = ''
    currentIndex.value = data.current_index

    if (data.status === 'finished') {
      currentQuestion.value = null
      finished.value = true
    } else {
      currentQuestion.value = data.question
    }
  } catch (e) {
    Message.error('提交失败：' + (e.response?.data?.detail || e.message))
  } finally {
    submitting.value = false
  }
}

function skipQuestion() {
  currentAnswer.value = ''
  submitAnswer()
}

async function generateResume() {
  generating.value = true
  try {
    let cfg = {}
    try {
      cfg = JSON.parse(localStorage.getItem('llm_config') || '{}')
    } catch (e) {
    }

    const res = await api.finishChat(taskId, cfg.api_key ? cfg : null)
    diff.value = res.data.diff

    // ★ 把优化简历缓存到 sessionStorage，供 EditorView 读取
    try {
      sessionStorage.setItem(
          `resume_optimized_${taskId}`,
          JSON.stringify(res.data.optimized_resume)
      )
    } catch (e) {
    }

    Message.success('优化简历已生成')
  } catch (e) {
    Message.error('生成失败：' + (e.response?.data?.detail || e.message))
  } finally {
    generating.value = false
  }
}

import {useRouter} from 'vue-router'

const router = useRouter()

function goToEditor() {
  // 确保 optimized_resume 已缓存
  if (!sessionStorage.getItem(`resume_optimized_${taskId}`) && diff.value) {
    // 如果没有缓存（比如页面刷新过），不影响，EditorView 会从后端读
  }
  router.push(`/editor/${taskId}`)
}

onMounted(start)
</script>