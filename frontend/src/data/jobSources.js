/**
 * M19 招聘数据源预设（与 LLM 厂商预设同款模式）
 * provider id 需与后端 app/services/job_market.py 的 PROVIDER_IDS 一致
 */
export const JOB_SOURCES = [
  {
    id: 'ai',
    name: 'AI 生成（推荐）',
    keyLabel: '',
    keyPlaceholder: '',
    needId: false,
    keyUrl: '',
    keyUrlText: '',
    note: '用你已配置的模型生成目标岗位参考画像，国内岗位可用、无需额外 Key；非实时在招数据',
  },
  {
    id: 'mock',
    name: '示例数据',
    keyLabel: '',
    keyPlaceholder: '',
    needId: false,
    keyUrl: '',
    keyUrlText: '',
    note: '内置样例岗位，无需配置，演示/离线可用',
  },
]

const CONFIG_KEY = 'job_source_config'

export function loadJobSource() {
  try {
    const cfg = JSON.parse(localStorage.getItem(CONFIG_KEY) || '{}')
    // M30：已删除的数据源标识（jsearch/adzuna 等）迁移到 AI 生成
    if (cfg.provider && !JOB_SOURCES.some((s) => s.id === cfg.provider)) {
      return { ...cfg, provider: 'ai' }
    }
    return cfg
  } catch (e) {
    return {}
  }
}

export function saveJobSource(cfg) {
  try {
    localStorage.setItem(CONFIG_KEY, JSON.stringify(cfg))
  } catch (e) {}
}
