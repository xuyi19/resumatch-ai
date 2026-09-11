<template>
  <div class="min-h-screen py-12">
    <div class="max-w-5xl mx-auto px-6">

      <!-- 标题 -->
      <div class="mb-8">
        <h1 class="text-3xl font-semibold text-gray-800 mb-2">历史记录</h1>
        <p class="text-sm text-gray-600">查看过往的诊断任务，点击查看可恢复完整结果</p>
      </div>

      <!-- 表格卡片（新拟物风） -->
      <div class="bg-[#e0e5ec] rounded-2xl p-6
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">

        <a-table
          v-if="records.length"
          :data="records"
          :loading="loading"
          :pagination="records.length > 10 ? { pageSize: 10, showTotal: true } : false"
          row-key="task_id"
          :bordered="{ wrapper: false, cell: false }"
        >
          <template #columns>
            <a-table-column title="关键词" data-index="keyword" :width="160">
              <template #cell="{ record }">
                <span class="font-medium text-[#6d5dfc]">{{ record.keyword }}</span>
              </template>
            </a-table-column>

            <a-table-column title="简历" data-index="resume_name">
              <template #cell="{ record }">
                <span class="text-gray-700 text-sm">{{ record.resume_name || '—' }}</span>
              </template>
            </a-table-column>

            <a-table-column title="城市" data-index="city" :width="90">
              <template #cell="{ record }">
                <span class="text-gray-600 text-sm">{{ record.city || '—' }}</span>
              </template>
            </a-table-column>

            <a-table-column title="状态" data-index="status" :width="100">
              <template #cell="{ record }">
                <a-tag :color="statusColor(record.status)" size="small">
                  {{ statusText(record.status) }}
                </a-tag>
              </template>
            </a-table-column>

            <a-table-column title="时间" data-index="created_at" :width="160">
              <template #cell="{ record }">
                <span class="text-gray-500 text-xs">{{ formatTime(record.created_at) }}</span>
              </template>
            </a-table-column>

            <a-table-column title="操作" :width="130" align="center">
              <template #cell="{ record }">
                <a-space>
                  <a-link @click="viewDetail(record.task_id)">查看</a-link>
                  <a-link status="danger" @click="confirmDelete(record.task_id)">删除</a-link>
                </a-space>
              </template>
            </a-table-column>
          </template>
        </a-table>

        <!-- 空状态（新拟物风） -->
        <div v-if="!loading && !records.length" class="py-20 text-center">
          <div class="inline-flex items-center justify-center w-24 h-24 rounded-3xl mb-6
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
              transition-all duration-300 ease-in-out">
            新建诊断
          </RouterLink>
        </div>

        <!-- Loading 骨架 -->
        <div v-if="loading && !records.length" class="py-20 text-center">
          <a-spin :size="32" />
          <div class="text-xs text-gray-500 mt-4">加载中...</div>
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

function statusColor(status) {
  return { success: 'green', failed: 'red', running: 'blue', pending: 'gray' }[status] || 'gray'
}

function statusText(status) {
  return { success: '成功', failed: '失败', running: '进行中', pending: '排队' }[status] || status
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

onMounted(loadHistory)
</script>