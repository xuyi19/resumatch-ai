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
  // M71 统一导出目录：读取 / 保存（空串=恢复默认）/ 资源管理器打开（仅桌面版）
  getExportRoot: () => api.get('/settings/export-root'),
  setExportRoot: (path) => api.put('/settings/export-root', { path }),
  openExportDir: (subdir = '') => api.post('/settings/open-dir', { subdir }),
  // M60 跟进提醒阈值：applied 超 N 天未流转即提醒（1~30，默认 7）
  getFollowupDays: () => api.get('/settings/followup-days'),
  setFollowupDays: (days) => api.put('/settings/followup-days', { days }),

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
  // M49 投递状态
  updateJobStatus: (id, status, apply_channel = null) =>
    api.put(`/jobs/library/${id}/status`, { status, apply_channel }),  // M56.4 支持附投递渠道
  batchUpdateJobStatus: (ids, status) => api.put('/jobs/library/status-batch', { ids, status }),
  deleteLibraryJob: (id) => api.delete(`/jobs/library/${id}`),
  batchDeleteLibraryJobs: (ids) => api.post('/jobs/library/batch-delete', { ids }),
  matchLibraryJobs: (data) => api.post('/jobs/library-match', data),
  generateLibraryJobs: (data) => api.post('/jobs/library-generate', data),
  // M56 投递直达：平台搜索深链 + AI 投递材料包
  getApplyLinks: (id) => api.get(`/jobs/library/${id}/apply-links`),
  jobApplyKit: (id, data) => api.post(`/jobs/library/${id}/apply-kit`, data),
  // M56.3 材料包导出 Word（blob 下载；桌面态用 exportApplyKitToPath 服务端分类落盘）
  exportApplyKit: (id, data) => api.post(`/jobs/library/${id}/export-kit`, data, {
    responseType: 'blob',
  }),
  exportApplyKitToPath: (id, data) => api.post(`/jobs/library/${id}/export-kit`, data),
  // M60 求职跟进：工作台提醒聚合（逾期 applied + 面试日程）
  getFollowups: () => api.get('/jobs/followups'),
  // M61 投递前体检：JD 关键词覆盖检查（纯本地词库比对，零 AI 调用）
  checkKeywordCoverage: (data) => api.post('/jobs/keyword-check', data),

  // M22 数据与隐私：一键清空本用户全部数据
  clearAllData: () => api.delete('/data'),

  // M59 数据备份与恢复：条数统计 / 导出 JSON 快照（blob 下载）/ 合并式导入
  backupStats: () => api.get('/backup/stats'),
  exportBackup: () => api.get('/backup/export', { responseType: 'blob' }),
  // M71 桌面态备份导出：?save=1 服务端直写「数据备份」子目录，返回 save_path
  exportBackupToPath: () => api.get('/backup/export', { params: { save: 1 } }),
  importBackup: (payload) => api.post('/backup/import', payload),

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

  // M64 刷题工坊：AI 出题 / 交卷 / 会话管理 / 错题本
  quizGenerate: (data) => api.post('/quiz/generate', data),
  quizSubmit: (taskId, data) => api.post(`/quiz/${taskId}/submit`, data),
  quizSessions: () => api.get('/quiz/sessions'),
  quizGet: (taskId) => api.get(`/quiz/${taskId}`),
  quizDeleteSession: (taskId) => api.delete(`/quiz/sessions/${taskId}`),
  quizWrongbook: () => api.get('/quiz/wrongbook'),

  // M65 项目素材库：STAR 卡片 CRUD + AI 生成草稿
  listStarCards: () => api.get('/star/cards'),
  createStarCard: (data) => api.post('/star/cards', data),
  updateStarCard: (id, data) => api.put(`/star/cards/${id}`, data),
  deleteStarCard: (id) => api.delete(`/star/cards/${id}`),
  generateStarDraft: (data) => api.post('/star/generate', data),

  // F1 简历库：列表（含最近诊断分）/ 详情（预览原文）/ 重命名 / 删除
  listResumes: () => api.get('/resumes/list'),
  getResume: (id) => api.get(`/resumes/${id}`),
  renameResume: (id, filename) => api.post(`/resumes/rename/${id}`, { filename }),
  deleteResume: (id) => api.delete(`/resumes/${id}`),
  deleteResumesBatch: (ids) => api.post('/resumes/delete-batch', { ids }),
}