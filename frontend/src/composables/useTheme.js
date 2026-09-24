import { ref, computed, watchEffect } from 'vue'

/**
 * 亮/暗双主题（D1）：
 * - choice：'light' | 'dark' | 'auto'（默认跟随系统），手动选择持久化
 * - resolved：实际生效主题，写入 <html data-theme>（index.html 已提前写，
 *   这里负责运行时切换与系统偏好联动）
 */
const KEY = 'resumatch_theme'
const choice = ref(readStored())
const systemDark = ref(
  window.matchMedia('(prefers-color-scheme: dark)').matches,
)

function readStored() {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : 'auto'
  } catch (e) {
    return 'auto'
  }
}

const resolved = computed(() =>
  choice.value === 'auto' ? (systemDark.value ? 'dark' : 'light') : choice.value,
)

watchEffect(() => {
  document.documentElement.dataset.theme = resolved.value
  // Arco 组件库暗色适配
  document.body.setAttribute(
    'arco-theme',
    resolved.value === 'dark' ? 'dark' : 'light',
  )
})

// 系统偏好变化时联动（auto 模式下实时生效）
window
  .matchMedia('(prefers-color-scheme: dark)')
  .addEventListener('change', (e) => {
    systemDark.value = e.matches
  })

export function useTheme() {
  function setTheme(v) {
    choice.value = v
    try {
      localStorage.setItem(KEY, v)
    } catch (e) {}
  }
  /** 一键切换亮/暗（当前实际主题取反） */
  function toggle() {
    setTheme(resolved.value === 'dark' ? 'light' : 'dark')
  }
  return { choice, resolved, setTheme, toggle }
}
