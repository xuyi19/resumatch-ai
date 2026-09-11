<template>
  <div class="min-h-screen bg-[#e0e5ec] text-gray-800">

    <!-- 顶部导航 -->
    <header class="fixed top-0 left-0 right-0 z-50 bg-[#e0e5ec]">
      <div class="max-w-6xl mx-auto px-6 md:px-8 h-16 flex items-center justify-between">

        <RouterLink to="/" class="flex items-center gap-3 group">
          <div class="w-10 h-10 rounded-xl bg-[#e0e5ec]
            shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
            flex items-center justify-center text-[#6d5dfc] font-bold">
            R
          </div>
          <span class="font-semibold text-base text-gray-800">ResuMatch</span>
        </RouterLink>

        <nav class="hidden md:flex items-center gap-2">
          <RouterLink to="/"
            class="px-4 py-2 rounded-xl text-sm font-medium
              transition-all duration-300 ease-in-out"
            :class="route.path === '/'
              ? 'bg-[#e0e5ec] shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] text-[#6d5dfc]'
              : 'text-gray-600 hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]'">
            首页
          </RouterLink>
          <RouterLink to="/analyze"
            class="px-4 py-2 rounded-xl text-sm font-medium
              transition-all duration-300 ease-in-out"
            :class="route.path.startsWith('/analyze') || route.path.startsWith('/result')
              ? 'bg-[#e0e5ec] shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] text-[#6d5dfc]'
              : 'text-gray-600 hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]'">
            控制台
          </RouterLink>
          <RouterLink to="/history"
            class="px-4 py-2 rounded-xl text-sm font-medium
              transition-all duration-300 ease-in-out"
            :class="route.path === '/history'
              ? 'bg-[#e0e5ec] shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] text-[#6d5dfc]'
              : 'text-gray-600 hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]'">
            历史记录
          </RouterLink>
          <RouterLink to="/changelog"
            class="px-4 py-2 rounded-xl text-sm font-medium
              transition-all duration-300 ease-in-out"
            :class="route.path === '/changelog'
              ? 'bg-[#e0e5ec] shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] text-[#6d5dfc]'
              : 'text-gray-600 hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]'">
            更新日志
          </RouterLink>
        </nav>

        <button @click="openSettings"
          class="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-gray-600
            shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
            hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
            active:shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]
            transition-all duration-300 ease-in-out">
          <span>⚙️</span>
          <span class="hidden md:inline">设置</span>
          <span v-if="hasApiKey" class="w-2 h-2 rounded-full bg-[#6d5dfc]" />
        </button>
      </div>
    </header>

    <!-- 主内容 -->
    <main class="pt-16 min-h-screen">
      <RouterView />
    </main>

    <!-- 设置弹窗 -->
    <Teleport to="body">
      <div v-if="settingsOpen"
        class="fixed inset-0 z-[100] flex items-center justify-center p-4"
        style="background: rgba(224, 229, 236, 0.85)"
        @click.self="closeSettings">
        <div class="max-w-md w-full bg-[#e0e5ec] rounded-2xl
          shadow-[12px_12px_24px_#b8bcc2,-12px_-12px_24px_#ffffff]
          p-8">

          <div class="flex items-start justify-between mb-8">
            <div>
              <h3 class="text-xl font-semibold text-gray-800">API 配置</h3>
              <p class="text-xs text-gray-500 mt-1">Key 仅保存在浏览器本地</p>
            </div>
            <button @click="closeSettings"
              class="w-9 h-9 rounded-xl bg-[#e0e5ec]
                shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
                hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
                active:shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]
                flex items-center justify-center text-gray-500
                transition-all duration-300">
              ✕
            </button>
          </div>

          <div class="space-y-6">
            <div>
              <label class="text-xs font-medium text-gray-600 block mb-3">服务商预设</label>
              <div class="flex gap-2">
                <button v-for="p in presets" :key="p.name"
                  @click="applyPreset(p)"
                  class="flex-1 px-3 py-2.5 text-xs font-medium rounded-xl
                    bg-[#e0e5ec] text-gray-700
                    shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
                    hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
                    active:shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]
                    transition-all duration-300 ease-in-out">
                  {{ p.name }}
                </button>
              </div>
            </div>

            <div>
              <label class="text-xs font-medium text-gray-600 block mb-3">API Key</label>
              <input v-model="form.api_key" type="password" placeholder="sk-..."
                class="w-full px-4 py-3 text-sm text-gray-800 placeholder-gray-400
                  bg-[#e0e5ec] rounded-xl border-0
                  shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
                  focus:outline-none
                  focus:shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]
                  transition-shadow duration-300 ease-in-out" />
            </div>

            <div>
              <label class="text-xs font-medium text-gray-600 block mb-3">Base URL</label>
              <input v-model="form.base_url" type="text" placeholder="https://api.deepseek.com/v1"
                class="w-full px-4 py-3 text-sm text-gray-800 placeholder-gray-400
                  bg-[#e0e5ec] rounded-xl border-0
                  shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
                  focus:outline-none
                  focus:shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]
                  transition-shadow duration-300 ease-in-out" />
            </div>

            <div>
              <label class="text-xs font-medium text-gray-600 block mb-3">模型名称</label>
              <input v-model="form.model" type="text" placeholder="deepseek-chat"
                class="w-full px-4 py-3 text-sm text-gray-800 placeholder-gray-400
                  bg-[#e0e5ec] rounded-xl border-0
                  shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
                  focus:outline-none
                  focus:shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]
                  transition-shadow duration-300 ease-in-out" />
            </div>
          </div>

          <div class="flex gap-3 mt-8">
            <button @click="clearSettings"
              class="px-5 py-2.5 text-sm font-medium rounded-xl
                bg-[#e0e5ec] text-gray-500
                shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
                hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
                hover:text-red-500
                active:shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]
                transition-all duration-300 ease-in-out">
              清空
            </button>
            <button @click="saveSettings"
              class="flex-1 px-5 py-2.5 text-sm font-medium rounded-xl
                bg-[#6d5dfc] text-white
                shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
                hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
                active:shadow-[inset_3px_3px_6px_rgba(0,0,0,0.2),inset_-3px_-3px_6px_rgba(255,255,255,0.1)]
                transition-all duration-300 ease-in-out">
              保存配置
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

const route = useRoute()
const settingsOpen = ref(false)
const hasApiKey = ref(false)
const form = reactive({ api_key: '', base_url: '', model: '' })

const presets = [
  { name: 'DeepSeek', base_url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  { name: '智谱 GLM', base_url: 'https://open.bigmodel.cn/api/paas/v4/', model: 'glm-4-flash' },
  { name: 'OpenAI', base_url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
]

function loadConfig() {
  try {
    const cfg = JSON.parse(localStorage.getItem('llm_config') || '{}')
    Object.assign(form, {
      api_key: cfg.api_key || '',
      base_url: cfg.base_url || '',
      model: cfg.model || '',
    })
    hasApiKey.value = !!cfg.api_key
  } catch (e) {}
}

function openSettings() { loadConfig(); settingsOpen.value = true }
function closeSettings() { settingsOpen.value = false }
function applyPreset(p) { form.base_url = p.base_url; form.model = p.model }

function saveSettings() {
  localStorage.setItem('llm_config', JSON.stringify({ ...form }))
  hasApiKey.value = !!form.api_key
  closeSettings()
}

function clearSettings() {
  localStorage.removeItem('llm_config')
  form.api_key = ''; form.base_url = ''; form.model = ''
  hasApiKey.value = false
}

onMounted(loadConfig)
</script>