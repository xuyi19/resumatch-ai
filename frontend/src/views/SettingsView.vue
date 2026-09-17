<template>
  <div class="max-w-4xl mx-auto px-6 md:px-8 py-12">

    <div class="mb-10">
      <h1 class="text-3xl font-semibold text-gray-800 mb-2">设置</h1>
      <p class="text-sm text-gray-600">配置大模型 API，Key 仅保存在浏览器本地</p>
    </div>

    <div class="space-y-6">

      <!-- 服务端预置提示（零配置分发） -->
    <div v-if="serverManaged"
      class="p-4 rounded-2xl text-sm bg-green-50 border border-green-200 text-green-700 leading-relaxed">
      ✅ 本程序已由分发者预置 API Key，<strong>无需填写即可直接使用</strong>。
      如需更换为自有 Key，可在下方填写并保存。
    </div>

    <!-- 状态卡片 -->
      <div class="bg-[#e0e5ec] rounded-2xl p-6
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 rounded-xl flex items-center justify-center text-2xl
              bg-[#e0e5ec]
              shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]">
              {{ hasConfig ? '✅' : '⚠️' }}
            </div>
            <div>
              <div class="font-semibold text-gray-800 mb-1">
                {{ hasConfig ? 'API 已配置' : '尚未配置 API' }}
              </div>
              <div class="text-xs text-gray-500">
                {{ hasConfig ? `当前模型：${form.model || '未设置'}` : '请填写下方配置以启用 AI 功能' }}
              </div>
            </div>
          </div>
          <div v-if="hasConfig" class="w-3 h-3 rounded-full bg-green-500 shadow-[0_0_0_4px_rgba(34,197,94,0.15)]"></div>
        </div>
      </div>

      <!-- 配置表单 -->
      <div class="bg-[#e0e5ec] rounded-2xl p-8
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">

        <h2 class="text-lg font-semibold text-gray-800 mb-6">API 配置</h2>

        <div class="space-y-6">

          <div>
            <label class="text-xs font-medium text-gray-600 block mb-3">服务商预设</label>
            <div class="grid grid-cols-3 gap-3">
              <button v-for="p in presets" :key="p.name"
                @click="applyPreset(p)"
                class="px-4 py-3 text-sm font-medium rounded-xl
                  transition-all duration-300 ease-in-out"
                :class="form.base_url === p.base_url
                  ? 'bg-[#e0e5ec] text-[#6d5dfc] shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]'
                  : 'bg-[#e0e5ec] text-gray-700 shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff] hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]'">
                {{ p.name }}
              </button>
            </div>
            <div class="text-xs text-gray-400 mt-2">
              <a href="https://platform.deepseek.com" target="_blank" class="hover:text-[#6d5dfc]">DeepSeek 注册</a>
              ·
              <a href="https://open.bigmodel.cn" target="_blank" class="hover:text-[#6d5dfc]">智谱 GLM 注册</a>
            </div>
          </div>

          <div>
            <label class="text-xs font-medium text-gray-600 block mb-3">
              API Key <span class="text-red-500">*</span>
            </label>
            <div class="relative">
              <input v-model="form.api_key" :type="showKey ? 'text' : 'password'"
                placeholder="sk-..."
                class="w-full px-4 py-3 pr-12 text-sm text-gray-800 placeholder-gray-400
                  bg-[#e0e5ec] rounded-xl border-0 font-mono
                  shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
                  focus:outline-none
                  focus:shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]
                  transition-shadow duration-300" />
              <button @click="showKey = !showKey"
                class="absolute right-3 top-1/2 -translate-y-1/2 w-8 h-8 rounded-lg
                  flex items-center justify-center text-gray-400 hover:text-gray-600">
                {{ showKey ? '🙈' : '👁' }}
              </button>
            </div>
            <div class="text-xs text-gray-400 mt-2">
              你的 Key 只保存在浏览器 localStorage，不会上传服务器
            </div>
          </div>

          <div>
            <label class="text-xs font-medium text-gray-600 block mb-3">Base URL</label>
            <input v-model="form.base_url" type="text"
              placeholder="https://api.deepseek.com/v1"
              class="w-full px-4 py-3 text-sm text-gray-800 placeholder-gray-400 font-mono
                bg-[#e0e5ec] rounded-xl border-0
                shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
                focus:outline-none
                focus:shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]
                transition-shadow duration-300" />
          </div>

          <div>
            <label class="text-xs font-medium text-gray-600 block mb-3">模型名称</label>
            <input v-model="form.model" type="text"
              placeholder="deepseek-chat"
              class="w-full px-4 py-3 text-sm text-gray-800 placeholder-gray-400 font-mono
                bg-[#e0e5ec] rounded-xl border-0
                shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
                focus:outline-none
                focus:shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]
                transition-shadow duration-300" />
          </div>
        </div>

        <div v-if="testResult" class="mt-6 p-4 rounded-xl text-sm"
          :class="testResult.success
            ? 'bg-green-50 text-green-700 border border-green-200'
            : 'bg-red-50 text-red-700 border border-red-200'">
          {{ testResult.message }}
        </div>

        <div class="flex gap-3 mt-8">
          <button @click="clearSettings"
            class="px-5 py-3 text-sm font-medium rounded-xl
              bg-[#e0e5ec] text-gray-500
              shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
              hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
              hover:text-red-500
              active:shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]
              transition-all duration-300">
            清空
          </button>
          <button @click="testConnection" :disabled="testing || !form.api_key"
            class="px-5 py-3 text-sm font-medium rounded-xl
              bg-[#e0e5ec] text-gray-700
              shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
              hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-all duration-300">
            {{ testing ? '测试中...' : '测试连接' }}
          </button>
          <button @click="saveSettings" :disabled="!form.api_key"
            class="flex-1 px-5 py-3 text-sm font-medium rounded-xl
              bg-[#6d5dfc] text-white
              shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]
              hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-all duration-300">
            保存配置
          </button>
        </div>
      </div>

      <!-- 使用说明 -->
      <div class="bg-[#e0e5ec] rounded-2xl p-8
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <h2 class="text-lg font-semibold text-gray-800 mb-6">使用说明</h2>
        <div class="space-y-4 text-sm text-gray-600 leading-relaxed">
          <div class="flex gap-3">
            <span class="text-[#6d5dfc] font-semibold shrink-0">①</span>
            <span>注册 DeepSeek 或智谱账号，在控制台创建 API Key</span>
          </div>
          <div class="flex gap-3">
            <span class="text-[#6d5dfc] font-semibold shrink-0">②</span>
            <span>点击上方"DeepSeek"或"智谱 GLM"按钮，自动填充 Base URL 和模型名</span>
          </div>
          <div class="flex gap-3">
            <span class="text-[#6d5dfc] font-semibold shrink-0">③</span>
            <span>粘贴你的 API Key，点"测试连接"验证</span>
          </div>
          <div class="flex gap-3">
            <span class="text-[#6d5dfc] font-semibold shrink-0">④</span>
            <span>点"保存配置"，即可开始使用</span>
          </div>
        </div>

        <div class="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-700 leading-relaxed">
          <strong>💡 说明：</strong> 你的 API Key 只保存在浏览器本地，不上传服务器。更换设备需要重新配置。
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import api from '../api'

const form = reactive({ api_key: '', base_url: '', model: '' })
const showKey = ref(false)
const testing = ref(false)
const testResult = ref(null)
const serverManaged = ref(false)

async function checkServerDefault() {
  try {
    const res = await api.llmDefault()
    serverManaged.value = !!res.data?.server_key_configured
  } catch (e) {
    serverManaged.value = false
  }
}

const presets = [
  { name: 'DeepSeek', base_url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  { name: '智谱 GLM', base_url: 'https://open.bigmodel.cn/api/paas/v4/', model: 'glm-4-flash' },
  { name: 'OpenAI', base_url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
]

const hasConfig = computed(() => !!form.api_key)

function loadConfig() {
  try {
    const cfg = JSON.parse(localStorage.getItem('llm_config') || '{}')
    Object.assign(form, {
      api_key: cfg.api_key || '',
      base_url: cfg.base_url || '',
      model: cfg.model || '',
    })
  } catch (e) {}
}

function applyPreset(p) {
  form.base_url = p.base_url
  form.model = p.model
  testResult.value = null
}

function saveSettings() {
  if (!form.api_key.trim()) {
    Message.warning('请填写 API Key')
    return
  }
  localStorage.setItem('llm_config', JSON.stringify({ ...form }))
  Message.success('配置已保存')
  testResult.value = { success: true, message: '✓ 配置已保存到本地' }
}

function clearSettings() {
  localStorage.removeItem('llm_config')
  form.api_key = ''
  form.base_url = ''
  form.model = ''
  testResult.value = null
  Message.success('已清空配置')
}

async function testConnection() {
  if (!form.api_key) return
  testing.value = true
  testResult.value = null

  try {
    const res = await api.testLLM({
      api_key: form.api_key,
      base_url: form.base_url,
      model: form.model,
    })
    if (res.data.success) {
      testResult.value = { success: true, message: `✓ 连接成功！模型：${res.data.model}，响应：${res.data.response || 'OK'}` }
    } else {
      testResult.value = { success: false, message: `✗ ${res.data.error}` }
    }
  } catch (e) {
    testResult.value = {
      success: false,
      message: '✗ 测试失败：' + (e.response?.data?.detail || e.message),
    }
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  loadConfig()
  checkServerDefault()
})
</script>