<template>
  <div class="min-h-screen py-12">
    <div class="max-w-5xl mx-auto px-6">

      <!-- 标题 -->
      <div class="mb-8">
        <h1 class="text-3xl font-semibold text-gray-800 mb-2">历史记录</h1>
        <p class="text-sm text-gray-600">查看过往的诊断任务，点击查看可恢复完整结果</p>
      </div>

      <!-- 卡片 -->
      <div class="bg-[#e0e5ec] rounded-2xl p-6
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">

        <!-- 加载中 -->
        <div v-if="loading" class="py-20 text-center">
          <div class="inline-block w-10 h-10 rounded-xl border-4 border-transparent border-t-[#6d5dfc] animate-spin"></div>
          <div class="text-sm text-gray-500 mt-4">加载中...</div>
        </div>

        <!-- 空状态 -->
        <div v-else-if="!records.length" class="py-20 text-center">
          <div class="inline-flex items-center justify-center w-20 h-20 rounded-3xl mb-6
            bg-[#e0e5ec]
            shadow-[inset_6px_6px_12px_#b8bcc2,inset_-6px_-6px_12px_#ffffff]">
            <span class="text-4xl">📭</span>
          </div>
          <div class="text-gray-700 font-medium mb-1">还没有诊断记录</div>
          <div class="text-xs text-gray-500 mb-8">上传简历，开始你的第一次诊断</div>
          <RouterLink to="/analyze"
            class="inline-block px-7 py-3 text-sm font-medium rounded-xl
              bg-[#6d5dfc] text-white
              shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]
              hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
              active:shadow-[inset_4px_4px_8px_rgba(0,0,0,0.2),inset_-4px_-4px_8px_rgba(255,255,255,0.1)]
              transition-all duration-300">
            新建诊断
          </RouterLink>
        </div>

        <!-- 列表 -->
        <div v-else class="space-y-3">
          <div v-for="r in records" :key="r.task_id"
            class="flex items-center gap-4 p-4 rounded-xl
              bg-[#e0e5ec]
              shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
              hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
              transition-all duration-300">

            <!-- 状态点 -->
            <div :class="statusDot(r.status)" class="w-3 h-3 rounded-full shrink-0"></div>

            <!-- 信息 -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-3 mb-1">
                <span class="font-semibold text-gray-800">{{ r.keyword }}</span>
                <span class="text-xs text-gray-400">{{ r.city }}</span>
              </div>
              <div class="text-xs text-gray-500 truncate">
                {{ r.resume_name || '未命名简历' }} · {{ formatTime(r.created_at) }}
              </div>
            </div>

            <!-- 状态标签 -->
            <span :class="statusClass(r.status)"
              class="px-2.5 py-1 rounded-lg text-xs font-medium shrink-0">
              {{ statusText(r.status) }}
            </span>

            <!-- 操作 -->
            <div class="flex items-center gap-2 shrink-0">
              <button @click="viewDetail(r.task_id)"
                class="px-3 py-1.5 text-xs font-medium rounded-lg
                  bg-[#e0e5ec] text-[#6d5dfc]
                  shadow-[3px_3px_6px_#b8bcc2,-3px_-3px_6px_#ffffff]
                  hover:shadow-[1px_1px_2px_#b8bcc2,-1px_-1px_2px_#ffffff]
                  transition-all duration-300">
                查看
              </button>
              <button @click="confirmDelete(r.task_id)"
                class="px-3 py-1.5 text-xs font-medium rounded-lg
                  bg-[#e0e5ec] text-gray-500
                  shadow-[3px_3px_6px_#b8bcc2,-3px_-3px_6px_#ffffff]
                  hover:shadow-[1px_1px_2px_#b8bcc2,-1px_-1px_2px_#ffffff]
                  hover:text-red-500
                  transition-all duration-300">
                删除
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import api from '../api'

const router = useRouter()
const records = ref([])
const loading = ref(false)

async function loadHistory() {
  loading.value = true
  try {
    const res = await api.getHistory({ limit: 50 })
    records.value = res.data.items || []
  } catch (e) {
    Message.error('加载失败：' + e.message)
  } finally {
    loading.value = false
  }
}

function viewDetail(taskId) {
  router.push(`/result/${taskId}`)
}

function confirmDelete(taskId) {
  Modal.warning({
    title: '确认删除',
    content: '删除后不可恢复，确定继续？',
    hideCancel: false,
    okText: '删除',
    cancelText: '取消',
    onOk: async () => {
      try {
        await api.deleteHistory(taskId)
        Message.success('已删除')
        loadHistory()
      } catch (e) {
        Message.error('删除失败：' + e.message)
      }
    },
  })
}

function statusDot(status) {
  return {
    success: 'bg-green-500',
    failed: 'bg-red-500',
    running: 'bg-blue-500',
    pending: 'bg-gray-400',
  }[status] || 'bg-gray-400'
}

function statusClass(status) {
  return {
    success: 'bg-green-50 text-green-700',
    failed: 'bg-red-50 text-red-700',
    running: 'bg-blue-50 text-blue-700',
    pending: 'bg-gray-100 text-gray-600',
  }[status] || 'bg-gray-100 text-gray-600'
}

function statusText(status) {
  return {
    success: '成功',
    failed: '失败',
    running: '进行中',
    pending: '排队',
  }[status] || status
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

onMounted(loadHistory)
</script>