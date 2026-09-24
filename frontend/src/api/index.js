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
  // 页面心跳（run.py 看门狗：浏览器窗口关闭后仍有人使用则不关停服务）
  heartbeat: () => api.post('/meta/heartbeat'),

  // 简历
  uploadResume: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/resumes/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  // A1 粘贴文本简历直存（跳过文件解析）
  uploadResumeText: (data) => api.post('/resumes/upload-text', data),
  // M44 简历版本链
  saveResumeVersion: (id, text) => api.post(`/resumes/${id}/save-version`, { text }),
  listResumeVersions: (id) => api.get(`/resumes/${id}/versions`),
  getResumeVersion: (id, vid) => api.get(`/resumes/${id}/versions/${vid}`),

  // 实时分析
  startLiveAnalyze: (data) => api.post('/live/analyze', data),
  getTaskStatus: (taskId) => api.get(`/live/status/${taskId}`),
  // 动态追问（M11-B）：提交补充回答，恢复暂停的诊断
  submitClarify: (taskId, answers) => api.post(`/live/clarify/${taskId}`, { answers }),
  // B1 失败任务重试（断点续跑，已完成节点不重跑）
  retryLive: (taskId) => api.post(`/live/retry/${taskId}`),
  // 放弃未完成任务（pending/running/waiting_clarify），释放「进行中」名额
  abandonTask: (taskId) => api.post(`/live/abandon/${taskId}`),

  // 历史记录
  getHistory: (params) => api.get('/history', { params }),
  // M36 工作台仪表盘：简历/诊断/面试统计聚合
  getStats: () => api.get('/history/stats'),
  getHistoryDetail: (taskId) => api.get(`/history/${taskId}`),
  deleteHistory: (taskId) => api.delete(`/history/${taskId}`),
  // M20 诊断报告导出 Word（blob 下载；桌面态用 exportReportToPath）
  exportReport: (taskId) => api.post(`/history/${taskId}/export-report`, {}, {
    responseType: 'blob',
  }),
  exportReportToPath: (taskId, savePath) =>
    api.post(`/history/${taskId}/export-report`, { save_path: savePath }),

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

  // M19 岗位市场：一键获取岗位 + 按简历推荐 + 数据源测试
  searchJobs: (data) => api.post('/jobs/search', data),
  recommendJobs: (data) => api.post('/jobs/recommend', data),
  // M30 手动导入公司比对推荐（用户录入目标公司，与简历匹配排序）
  importMatchJobs: (data) => api.post('/jobs/import-match', data),
  testJobProvider: (config) => api.post('/settings/test-job', config),
  // M45 岗位库：自管理岗位 CRUD + 库×简历批量匹配推荐
  listLibraryJobs: () => api.get('/jobs/library'),
  addLibraryJobs: (items, source = 'manual', skipDuplicates = false) =>
    api.post('/jobs/library', { items, source, skip_duplicates: skipDuplicates }),
  parseBatchImport: (data) => api.post('/jobs/library/parse-batch', data),
  updateLibraryJob: (id, data) => api.put(`/jobs/library/${id}`, data),
  deleteLibraryJob: (id) => api.delete(`/jobs/library/${id}`),
  batchDeleteLibraryJobs: (ids) => api.post('/jobs/library/batch-delete', { ids }),
  matchLibraryJobs: (data) => api.post('/jobs/library-match', data),
  generateLibraryJobs: (data) => api.post('/jobs/library-generate', data),

  // M22 数据与隐私：一键清空本用户全部数据
  clearAllData: () => api.delete('/data'),

  // M23 面试：题单生成 / 恢复会话；M32 多轮自由对话（聊天式模拟面试）
  interviewStart: (taskId, llmConfig, regenerate = false) =>
    api.post(`/interview/start/${taskId}`, { llm_config: llmConfig || null, regenerate }),
  interviewGet: (taskId) => api.get(`/interview/${taskId}`),
  interviewChat: (taskId, content, forceAdvance = false, llmConfig = null) =>
    api.post(`/interview/chat/${taskId}`,
      { content, force_advance: forceAdvance, llm_config: llmConfig }),
  // M31 独立面试：按简历 + 意向岗位直接开一场面试（无需先诊断）/ 会话列表
  interviewStartFree: (data) => api.post('/interview/start-free', data),
  interviewSessions: () => api.get('/interview/sessions'),
  // M37 删除面试会话（清理废弃会话）
  interviewDeleteSession: (taskId) => api.delete(`/interview/sessions/${taskId}`),
  // M33 面试报告导出 Word（blob 下载；桌面态可传 save_path 服务端直写）
  interviewExport: (taskId) =>
    api.post(`/interview/export/${taskId}`, {}, { responseType: 'blob' }),
  interviewExportToPath: (taskId, savePath) =>
    api.post(`/interview/export/${taskId}`, { save_path: savePath }),

  // F1 简历库：列表（含最近诊断分）/ 详情（预览原文）/ 重命名 / 删除
  listResumes: () => api.get('/resumes/list'),
  getResume: (id) => api.get(`/resumes/${id}`),
  renameResume: (id, filename) => api.post(`/resumes/rename/${id}`, { filename }),
  deleteResume: (id) => api.delete(`/resumes/${id}`),
  deleteResumesBatch: (ids) => api.post('/resumes/delete-batch', { ids }),
}