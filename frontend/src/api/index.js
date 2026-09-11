import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 180000,
})

export default {
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

  // 优化
  getClarifyQuestions: (taskId, llmConfig) =>
    api.post(`/optimize/${taskId}/questions`, llmConfig || {}),
  generateOptimizedResume: (taskId, answers, llmConfig) =>
    api.post(`/optimize/${taskId}/generate`, {
      answers,
      llm_config: llmConfig || null,
    }),
  quickOptimize: (taskId, llmConfig) =>
    api.post(`/optimize/${taskId}`, llmConfig || {}),

  // Word 导出
  exportDocx: (data) => api.post('/resumes/export-docx', data, {
    responseType: 'blob',
  }),

  // 测试 LLM
  testLLM: (config) => api.post('/settings/test-llm', config),
}