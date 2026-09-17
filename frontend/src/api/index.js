import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 180000,
})

export default {
  // 健康
  health: () => api.get('/health'),

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

  // Word 导出
  exportDocx: (data) => api.post('/resumes/export-docx', data, {
    responseType: 'blob',
  }),

  // 测试 LLM
  testLLM: (config) => api.post('/settings/test-llm', config),
  // 服务端是否已预置 Key（零配置分发）
  llmDefault: () => api.get('/settings/llm-default'),
}