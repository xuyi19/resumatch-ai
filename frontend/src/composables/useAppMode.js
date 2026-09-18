import { computed, ref } from 'vue'
import api from '../api'

/**
 * 运行形态：桌面/本机版（local）与线上网站版（web）共用一套代码，
 * 由后端 /meta 下发形态，界面按形态做差异化（不维护两套 UI）。
 *
 * 单例：只在首次调用时请求一次，之后复用同一份状态。
 */
const meta = ref({
  app_mode: 'local',
  app_name: 'ResuMatch AI',
  version: '',
  build_tag: '',
  daily_limit: 10,
  has_server_key: false,
})
const loaded = ref(false)
let pending = null

async function loadMeta() {
  if (loaded.value) return meta.value
  if (!pending) {
    pending = api.getMeta()
      .then((res) => {
        meta.value = { ...meta.value, ...res.data }
        loaded.value = true
        return meta.value
      })
      .catch(() => meta.value)  // 拿不到就按桌面版渲染，不影响使用
      .finally(() => { pending = null })
  }
  return pending
}

export function useAppMode() {
  loadMeta()
  return {
    meta,
    loaded,
    /** 桌面 / 本机形态 */
    isDesktop: computed(() => meta.value.app_mode !== 'web'),
    /** 线上网站形态 */
    isWeb: computed(() => meta.value.app_mode === 'web'),
    /** 服务端预置了 Key 才存在每日配额概念 */
    quotaEnabled: computed(
      () => meta.value.app_mode === 'web' && meta.value.has_server_key,
    ),
    reload: loadMeta,
  }
}
