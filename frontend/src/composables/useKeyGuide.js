import { reactive } from 'vue'
import api from '../api'

/**
 * A5 新用户 Key 引导（全局单例状态）：
 * - needGuide：本地未存 Key 且服务端未预置 Key 时为 true
 * - 壳层据 needGuide 渲染引导层；分析页发诊断前调用 ensureChecked 拦截
 */
const state = reactive({ checked: false, needGuide: false })
let checking = null

const DISMISS_KEY = 'key_guide_dismissed'

async function checkKey() {
  if (checking) return checking
  checking = (async () => {
    let hasKey = false
    try {
      hasKey = !!JSON.parse(localStorage.getItem('llm_config') || '{}').api_key
    } catch (e) {}
    let serverKey = false
    try {
      serverKey = !!(await api.llmDefault()).data?.server_key_configured
    } catch (e) {}
    state.checked = true
    state.needGuide = !hasKey && !serverKey
  })()
  return checking
}

/** 首启检测：未配置且本次会话未「稍后再说」过 → 弹引导层 */
async function bootCheck() {
  await checkKey()
  if (state.needGuide) {
    try {
      if (sessionStorage.getItem(DISMISS_KEY) === '1') state.needGuide = false
    } catch (e) {}
  }
}

function showGuide() {
  state.checked = true
  state.needGuide = true
}

function dismissGuide() {
  state.needGuide = false
  try {
    sessionStorage.setItem(DISMISS_KEY, '1')
  } catch (e) {}
}

export function useKeyGuide() {
  return { state, bootCheck, showGuide, dismissGuide, refresh: checkKey }
}
