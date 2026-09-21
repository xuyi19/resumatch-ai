<template>
  <div class="min-h-screen bg-[#e0e5ec] text-gray-800">

    <header class="fixed top-0 left-0 right-0 z-50 bg-[#e0e5ec]">
      <div class="relative max-w-7xl mx-auto px-4 md:px-8 h-16 grid grid-cols-[auto_1fr_auto] items-center gap-3">

        <!-- 左：Logo + 形态标识 -->
        <div class="flex items-center justify-start gap-2 min-w-0">
          <RouterLink to="/" class="flex items-center gap-3 shrink-0">
            <div class="w-9 h-9 md:w-10 md:h-10 rounded-xl bg-[#e0e5ec]
              shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
              flex items-center justify-center text-[#6d5dfc] font-bold shrink-0">
              R
            </div>
            <span class="font-semibold text-sm md:text-base text-gray-800 truncate">ResuMatch</span>
          </RouterLink>
          <!-- 形态徽标：桌面版 / 网页版 -->
          <span v-if="meta.app_mode"
            class="hidden sm:inline-block px-2 py-0.5 rounded-md text-[10px] font-medium tracking-wide
              bg-[#e0e5ec] shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]
              text-gray-500">
            {{ isWeb ? '网页版' : '桌面版' }}
          </span>
        </div>

        <!-- 中：主导航（md+ 视口绝对居中；小屏保持弹性列） -->
        <nav class="flex items-center justify-center gap-0.5 md:gap-2 overflow-x-auto
          md:absolute md:left-1/2 md:top-1/2 md:-translate-x-1/2 md:-translate-y-1/2">
          <RouterLink to="/" class="nav-item" :class="navActive('/')">
            首页
          </RouterLink>
          <RouterLink to="/analyze" class="nav-item" :class="navActive('/analyze') || navActive('/result')">
            诊断
          </RouterLink>
          <RouterLink to="/history" class="nav-item" :class="navActive('/history')">
            历史
          </RouterLink>
        </nav>

        <!-- 右：仓库 + 更新日志 + 设置 -->
        <div class="flex items-center justify-end gap-1 shrink-0">

          <!-- 开源仓库入口（GitHub / Gitee） -->
          <a :href="REPO.github" target="_blank" rel="noopener" title="GitHub 仓库"
              class="w-9 h-9 rounded-lg flex items-center justify-center text-gray-500
                hover:text-gray-900 hover:bg-white/40 transition-colors duration-200">
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 .3a12 12 0 00-3.8 23.4c.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.4-1.8-1.4-1.8-1-.7.1-.7.1-.7 1.2 0 1.9 1.2 1.9 1.2 1 1.8 2.8 1.3 3.5 1 0-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-6 0-1.2.5-2.3 1.2-3.1-.1-.4-.5-1.7.1-3.5 0 0 1-.3 3.3 1.2a11.5 11.5 0 016 0c2.3-1.5 3.3-1.2 3.3-1.2.7 1.8.3 3.1.1 3.5.8.8 1.2 1.9 1.2 3.1 0 4.7-2.8 5.7-5.5 6 .4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0012 .3"/>
              </svg>
            </a>
            <a :href="REPO.gitee" target="_blank" rel="noopener" title="Gitee 仓库"
              class="w-9 h-9 rounded-lg flex items-center justify-center
                hover:bg-white/40 transition-colors duration-200 group">
              <img src="https://gitee.com/favicon.ico" alt="Gitee"
                class="w-5 h-5 opacity-50 grayscale group-hover:opacity-100 group-hover:grayscale-0 transition-all duration-200" />
          </a>

          <!-- 网页版 + 服务端预置 Key时：显示每日配额 -->
          <span v-if="quotaEnabled" :title="`每日免费诊断 ${meta.daily_limit} 次`"
            class="hidden lg:inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs text-gray-500
              bg-[#e0e5ec] shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]">
            ⚡ 每日免费 {{ meta.daily_limit }} 次
          </span>

          <RouterLink to="/changelog" title="更新日志"
            class="px-3 py-2 rounded-lg text-xs font-medium transition-all duration-300 ease-in-out"
            :class="route.path === '/changelog'
              ? 'bg-[#e0e5ec] shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] text-[#6d5dfc]'
              : 'text-gray-500 hover:text-gray-900 hover:bg-white/40'">
            📋
          </RouterLink>

          <RouterLink to="/settings" title="设置"
            class="relative w-9 h-9 rounded-lg flex items-center justify-center text-gray-600 text-base transition-colors duration-200"
            :class="route.path === '/settings' ? 'text-[#6d5dfc]' : 'hover:bg-white/40'">
            ⚙️
            <span v-if="hasApiKey" class="absolute top-1 right-1 w-2 h-2 rounded-full bg-[#6d5dfc]" />
          </RouterLink>
        </div>
      </div>
    </header>

    <main class="pt-16 min-h-screen">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { useAppMode } from './composables/useAppMode'

const REPO = {
  github: 'https://github.com/xuyi19/resumatch-ai',
  gitee: 'https://gitee.com/xuyi_19/resumatch-ai',
}

const route = useRoute()
const hasApiKey = ref(false)

const { meta, isWeb, quotaEnabled } = useAppMode()

function navActive(prefix) {
  return route.path === prefix || route.path.startsWith(prefix + '/')
    ? 'bg-[#e0e5ec] shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] text-[#6d5dfc]'
    : 'text-gray-600 hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]'
}

function checkApiKey() {
  try {
    const cfg = JSON.parse(localStorage.getItem('llm_config') || '{}')
    hasApiKey.value = !!cfg.api_key
  } catch (e) {}
}

onMounted(checkApiKey)
watch(() => route.path, checkApiKey)
</script>

<style scoped>
.nav-item {
  padding: 0.4rem 0.7rem;
  border-radius: 0.75rem;
  font-size: 0.8rem;
  font-weight: 500;
  white-space: nowrap;
  transition: all 0.3s ease-in-out;
}
@media (min-width: 768px) {
  .nav-item { padding: 0.5rem 1rem; font-size: 0.875rem; }
}
</style>