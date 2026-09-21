import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 180000,
})

export default {
  // 健康
  health: () => api.get('/health'),
  // 运行形态（桌面版 / 网页版界面切换依据）
  getMeta: () => api.get('/meta'),

  // 简历
  uploadResume: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/resumes/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 实时分析
  startLiveAnalyze: (data) => api.post('/live/analyze', data),
  getTaskStatus: (taskId) => api.get(`/live/status/${taskId}`),
  // 动态追问（M11-B）：提交补充回答，恢复暂停的诊断
  submitClarify: (taskId, answers) => api.post(`/live/clarify/${taskId}`, { answers }),

  // 历史记录
  getHistory: (params) => api.get('/history', { params }),
  getHistoryDetail: (taskId) => api.get(`/history/${taskId}`),
  deleteHistory: (taskId) => api.delete(`/history/${taskId}`),

  // 一键优化（基于诊断结果生成优化简历，可携带追问回答）
  quickOptimize: (taskId, llmConfig, answers = {}) =>
    api.post(`/optimize/${taskId}`, { answers, llm_config: llmConfig || null }),

  // ★ 对答式优化
  startChat: (taskId, llmConfig) =>
    api.post(`/chat/start/${taskId}`, { llm_config: llmConfig || null }),
  replyChat: (taskId, questionId, answer) =>
    api.post(`/chat/reply/${taskId}`, { question_id: questionId, answer }),
  finishChat: (taskId, llmConfig) =>
    api.post(`/chat/finish/${taskId}`, { llm_config: llmConfig || null }),
  getChatHistory: (taskId) => api.get(`/chat/history/${taskId}`),

  // Word 导出（blob 下载，网页形态）
  exportDocx: (data) => api.post('/resumes/export-docx', data, {
    responseType: 'blob',
  }),
  // Word 导出（桌面形态：save_path 由原生另存为对话框选定，服务端直写）
  exportDocxToPath: (data) => api.post('/resumes/export-docx', data),

  // 导出历史（桌面态含保存路径，可打开所在位置）
  listExportHistory: () => api.get('/resumes/export-history'),
  deleteExportHistory: (id) => api.delete(`/resumes/export-history/${id}`),

  // 简历模板目录（导出 Word 用的多套版式）
  listTemplates: () => api.get('/resumes/templates'),

  // 证件照（嵌入导出的 Word）
  uploadPhoto: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/resumes/photo', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  deletePhoto: (photoId) => api.delete(`/resumes/photo/${photoId}`),

  // 测试 LLM
  testLLM: (config) => api.post('/settings/test-llm', config),
  // 服务端是否已预置 Key（零配置分发）
  llmDefault: () => api.get('/settings/llm-default'),
}