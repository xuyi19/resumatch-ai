<template>
  <div class="min-h-screen bg-page text-ink">

    <!-- ============ 侧边栏（D0 统一应用壳：介绍页与工作台共用） ============ -->
    <aside class="hidden md:flex fixed inset-y-0 left-0 z-40 w-56 flex-col
      bg-panel border-r border-line">

      <!-- Logo + 形态标识 -->
      <div class="h-16 px-5 flex items-center gap-2.5 shrink-0">
        <div class="w-8 h-8 rounded-lg bg-accent text-white font-bold
          flex items-center justify-center text-sm shrink-0">R</div>
        <span class="font-semibold text-sm">ResuMatch</span>
        <span v-if="meta.app_mode"
          class="ml-auto px-1.5 py-0.5 rounded text-[10px] font-medium
            bg-inset text-ink-faint border border-line">
          {{ isWeb ? 'Web' : '桌面' }}
        </span>
      </div>

      <!-- 主导航 -->
      <nav class="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        <template v-for="item in navItems" :key="item.label">
          <span v-if="item.disabled" class="side-item disabled" :title="'即将上线'">
            <svg class="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="1.8" stroke-linecap="round"
              stroke-linejoin="round" v-html="item.icon" />
            <span class="truncate">{{ item.label }}</span>
            <span class="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-inset text-ink-faint">
              即将上线
            </span>
          </span>
          <RouterLink v-else :to="item.to" class="side-item" :class="sideItemCls(item)">
            <svg class="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="1.8" stroke-linecap="round"
              stroke-linejoin="round" v-html="item.icon" />
            <span class="truncate">{{ item.label }}</span>
          </RouterLink>
        </template>

        <div class="my-3 border-t border-line" />

        <!-- 设置（未配 Key 常驻小红点） -->
        <RouterLink to="/settings" :class="sideItemCls(settingsItem)" class="side-item">
          <svg class="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="1.8" stroke-linecap="round"
            stroke-linejoin="round" v-html="settingsItem.icon" />
          <span class="truncate">设置</span>
          <span v-if="guide.state.needGuide"
            class="ml-auto w-2 h-2 rounded-full bg-bad animate-pulse"
            title="尚未配置 API Key" />
        </RouterLink>

        <RouterLink to="/changelog" :class="sideItemCls(changelogItem)" class="side-item">
          <svg class="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="1.8" stroke-linecap="round"
            stroke-linejoin="round" v-html="changelogItem.icon" />
          <span class="truncate">更新日志</span>
        </RouterLink>
      </nav>

      <!-- 底部：仓库 / 主题切换 / 版本 / 配额 -->
      <div class="shrink-0 border-t border-line px-3 py-3 space-y-2">
        <div class="flex items-center gap-1">
          <a :href="REPO.github" target="_blank" rel="noopener" title="GitHub 仓库"
            class="icon-btn">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 .3a12 12 0 00-3.8 23.4c.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.4-1.8-1.4-1.8-1-.7.1-.7.1-.7 1.2 0 1.9 1.2 1.9 1.2 1 1.8 2.8 1.3 3.5 1 0-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-6 0-1.2.5-2.3 1.2-3.1-.1-.4-.5-1.7.1-3.5 0 0 1-.3 3.3 1.2a11.5 11.5 0 016 0c2.3-1.5 3.3-1.2 3.3-1.2.7 1.8.3 3.1.1 3.5.8.8 1.2 1.9 1.2 3.1 0 4.7-2.8 5.7-5.5 6 .4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0012 .3"/>
            </svg>
          </a>
          <a :href="REPO.gitee" target="_blank" rel="noopener" title="Gitee 仓库" class="icon-btn">
            <img src="https://gitee.com/favicon.ico" alt="Gitee" class="w-4 h-4 opacity-60" />
          </a>

          <span class="flex-1" />

          <span v-if="quotaEnabled"
            :title="`每日免费诊断 ${meta.daily_limit} 次`"
            class="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent font-mono">
            免费 {{ meta.daily_limit }}/日
          </span>

          <button @click="toggle" :title="themeTitle" class="icon-btn">
            <!-- 太阳（当前亮色，点击切暗） -->
            <svg v-if="resolved === 'light'" class="w-4 h-4" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4l1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>
            </svg>
            <!-- 月亮（当前暗色，点击切亮） -->
            <svg v-else class="w-4 h-4" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="1.8" stroke-linecap="round"
              stroke-linejoin="round">
              <path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z" />
            </svg>
          </button>
        </div>
        <div class="px-1 text-[10px] font-mono text-ink-faint">
          {{ meta.version || 'v?' }}
        </div>
      </div>
    </aside>

    <!-- ============ 窄屏顶栏（简单可达即可，深度适配见后续里程碑） ============ -->
    <header class="md:hidden fixed top-0 inset-x-0 z-40 h-14 flex items-center gap-1 px-3
      bg-panel border-b border-line">
      <RouterLink to="/" class="flex items-center gap-2 mr-2">
        <div class="w-7 h-7 rounded-md bg-accent text-white font-bold
          flex items-center justify-center text-xs">R</div>
        <span class="font-semibold text-sm">ResuMatch</span>
      </RouterLink>
      <span class="flex-1" />
      <RouterLink v-for="m in mobileNav" :key="m.label" :to="m.to" class="icon-btn"
        :class="m.active() ? 'text-accent bg-accent/10' : 'text-ink-sub'">
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" v-html="m.icon" />
      </RouterLink>
      <button @click="toggle" class="icon-btn text-ink-sub">
        <svg v-if="resolved === 'light'" class="w-5 h-5" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4l1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>
        </svg>
        <svg v-else class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z" />
        </svg>
      </button>
    </header>

    <!-- ============ 主工作区 ============ -->
    <main class="md:pl-56 pt-14 md:pt-0 min-h-screen">
      <RouterView />
    </main>

    <!-- ============ A5 新用户 Key 引导层 ============ -->
    <Teleport to="body">
      <div v-if="guide.state.needGuide"
        class="fixed inset-0 z-[100] bg-black/50 flex items-center justify-center p-4">
        <div class="w-full max-w-md bg-float border border-line rounded-xl p-7 shadow-xl">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-lg bg-accent/10 text-accent
              flex items-center justify-center">
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M15 7a2 2 0 012 2m3-2a5 5 0 01-7.5 4.3L7 16.7V19H4v-3l7.7-7.7A5 5 0 0115 7z" />
              </svg>
            </div>
            <div>
              <h2 class="text-base font-semibold">配置 AI 服务，开始诊断</h2>
              <p class="text-xs text-ink-sub mt-0.5">首次使用需要一个大模型 API Key</p>
            </div>
          </div>

          <p class="text-sm text-ink-sub leading-relaxed mb-4">
            诊断、改写建议等 AI 能力由大模型驱动。Key 只保存在本机不上传，
            支持智谱 / DeepSeek / 通义千问 / Kimi / 豆包 / OpenAI 等主流厂商，
            也支持 Ollama 本地模型（免费）。
          </p>

          <ol class="space-y-2 text-sm text-ink-sub mb-6">
            <li class="flex gap-2.5">
              <span class="w-5 h-5 rounded bg-inset text-accent text-xs font-mono
                flex items-center justify-center shrink-0">1</span>
              <span>在设置页选择厂商（自动填入接口地址）</span>
            </li>
            <li class="flex gap-2.5">
              <span class="w-5 h-5 rounded bg-inset text-accent text-xs font-mono
                flex items-center justify-center shrink-0">2</span>
              <span>粘贴在厂商控制台创建的 API Key</span>
            </li>
            <li class="flex gap-2.5">
              <span class="w-5 h-5 rounded bg-inset text-accent text-xs font-mono
                flex items-center justify-center shrink-0">3</span>
              <span>点「测试连接」验证，保存后即可使用</span>
            </li>
          </ol>

          <div class="flex gap-3">
            <button @click="dismissGuide"
              class="px-4 py-2.5 rounded-lg text-sm text-ink-sub border border-line
                hover:bg-inset transition-colors">
              稍后再说
            </button>
            <button @click="goSettings"
              class="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium
                bg-accent text-white hover:bg-accent-hover transition-colors">
              去配置 API Key
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watchEffect } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useAppMode } from './composables/useAppMode'
import { useTheme } from './composables/useTheme'
import { useKeyGuide } from './composables/useKeyGuide'
import api from './api'

const REPO = {
  github: 'https://github.com/xuyi19/resumatch-ai',
  gitee: 'https://gitee.com/xuyi_19/resumatch-ai',
}

const route = useRoute()
const router = useRouter()
const { meta, isWeb, quotaEnabled } = useAppMode()
const { resolved, toggle } = useTheme()
const guide = useKeyGuide()

/* ---- 图标（inline path，v-html 注入） ---- */
const ICONS = {
  home: '<path d="M3 10.5L12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
  target:
    '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2"/>',
  edit: '<path d="M4 20h16"/><path d="M6 16l10.5-10.5a2.12 2.12 0 013 3L9 19l-4 1 1-4z"/>',
  folder:
    '<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
  sliders:
    '<path d="M4 7h7"/><circle cx="14" cy="7" r="2.5"/><path d="M19.5 7H20"/><path d="M4 17h4.5"/><circle cx="11" cy="17" r="2.5"/><path d="M16.5 17H20"/>',
  doc: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/><path d="M10 13h6M10 17h4"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0"/><path d="M12 18v3"/>',
}

/* ---- 侧边栏导航 ---- */
const navItems = computed(() => [
  { label: '介绍', to: '/', icon: ICONS.home, active: route.path === '/' },
  {
    label: '发起诊断',
    to: '/app/analyze',
    icon: ICONS.target,
    active: route.path.startsWith('/app/analyze') ||
      route.path.startsWith('/app/result') ||
      route.path.startsWith('/app/chat'),
  },
  {
    label: '创建简历',
    to: '/app/editor',
    icon: ICONS.edit,
    active: route.path.startsWith('/app/editor'),
  },
  {
    label: '简历库',
    to: '/app/resumes',
    icon: ICONS.folder,
    active: route.path.startsWith('/app/resumes'),
  },
  {
    label: '模拟面试',
    to: '/app/interview',
    icon: ICONS.mic,
    active: route.path.startsWith('/app/interview'),
  },
  {
    label: '诊断历史',
    to: '/app/history',
    icon: ICONS.clock,
    active: route.path.startsWith('/app/history'),
  },
])
const settingsItem = { label: '设置', icon: ICONS.sliders, active: route.path === '/settings' }
const changelogItem = { label: '更新日志', icon: ICONS.doc, active: route.path === '/changelog' }

/* ---- 窄屏顶栏（诊断/创建/历史/设置） ---- */
const mobileNav = computed(() => [
  { label: '诊断', to: '/app/analyze', icon: ICONS.target, active: () => route.path.startsWith('/app/analyze') || route.path.startsWith('/app/result') },
  { label: '创建', to: '/app/editor', icon: ICONS.edit, active: () => route.path.startsWith('/app/editor') },
  { label: '历史', to: '/app/history', icon: ICONS.clock, active: () => route.path.startsWith('/app/history') },
  { label: '设置', to: '/settings', icon: ICONS.sliders, active: () => route.path === '/settings' },
])

function sideItemCls(item) {
  return item.active
    ? 'bg-accent/10 text-accent'
    : 'text-ink-sub hover:bg-inset hover:text-ink'
}

const themeTitle = computed(() =>
  resolved.value === 'dark' ? '切换到亮色模式' : '切换到暗色模式',
)

/* ---- 桌面端启动直进工作台（仅启动时一次，不劫持用户回介绍页） ---- */
const redirected = ref(false)
watchEffect(() => {
  if (meta.value.app_mode && redirected.value === false) {
    redirected.value = true
    if (meta.value.app_mode !== 'web' && route.path === '/') {
      router.replace('/app/analyze')
    }
  }
})

onMounted(() => {
  guide.bootCheck()
  // 页面心跳：run.py 看门狗据此判断「是否还有页面在使用」。
  // 关闭专属浏览器窗口但仍在其他浏览器使用时，服务不会被误杀；
  // 后台标签页定时器最坏节流到 1 次/分钟，看门狗阈值 90s 覆盖该情况。
  api.heartbeat().catch(() => {})
  setInterval(() => api.heartbeat().catch(() => {}), 20000)
})

function goSettings() {
  guide.dismissGuide()
  router.push('/settings')
}
</script>

<style scoped>
.side-item {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.55rem 0.7rem;
  border-radius: 0.5rem;
  font-size: 0.85rem;
  font-weight: 500;
  transition: background-color 0.15s ease, color 0.15s ease;
  cursor: pointer;
}
.side-item.disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 0.5rem;
  color: rgb(var(--c-ink-sub));
  transition: background-color 0.15s ease, color 0.15s ease;
}
.icon-btn:hover {
  background: rgb(var(--c-inset));
  color: rgb(var(--c-ink));
}
</style>
