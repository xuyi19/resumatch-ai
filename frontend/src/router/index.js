import { createRouter, createWebHashHistory } from 'vue-router'

/**
 * D0 路由重组：/ = 纯介绍页；/app/* = 工作台功能页（共用同一应用壳）。
 * 桌面端启动由 App.vue 判定 app_mode 后直进 /app；旧路径做重定向兼容。
 */
export default createRouter({
  history: createWebHashHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    { path: '/', name: 'home', component: () => import('../views/HomeView.vue') },

    {
      path: '/app',
      children: [
        { path: '', redirect: { name: 'app-dashboard' } },
        { path: 'dashboard', name: 'app-dashboard', component: () => import('../views/DashboardView.vue') },
        { path: 'analyze', name: 'app-analyze', component: () => import('../views/AnalyzeView.vue') },
        { path: 'editor', name: 'app-editor-new', component: () => import('../views/EditorView.vue') },
        { path: 'editor/:taskId', name: 'app-editor', component: () => import('../views/EditorView.vue') },
        { path: 'resumes', name: 'app-resumes', component: () => import('../views/ResumeListView.vue') },
        { path: 'jobs', name: 'app-jobs', component: () => import('../views/JobLibraryView.vue') },
        { path: 'interview', name: 'app-interview', component: () => import('../views/InterviewView.vue') },
        { path: 'result/:taskId', name: 'app-result', component: () => import('../views/ResultView.vue') },
        { path: 'chat/:taskId', name: 'app-chat', component: () => import('../views/ChatView.vue') },
        { path: 'history', name: 'app-history', component: () => import('../views/HistoryView.vue') },
      ],
    },

    { path: '/settings', name: 'settings', component: () => import('../views/SettingsView.vue') },
    { path: '/guide', name: 'guide', component: () => import('../views/GuideView.vue') },
    { path: '/changelog', name: 'changelog', component: () => import('../views/ChangelogView.vue') },

    // ---- 旧路径重定向（兼容历史书签 / 旧版本 exe） ----
    { path: '/analyze', redirect: { name: 'app-analyze' } },
    { path: '/editor', redirect: { name: 'app-editor-new' } },
    {
      path: '/editor/:taskId',
      redirect: (to) => ({ name: 'app-editor', params: to.params }),
    },
    {
      path: '/result/:taskId',
      redirect: (to) => ({ name: 'app-result', params: to.params }),
    },
    {
      path: '/chat/:taskId',
      redirect: (to) => ({ name: 'app-chat', params: to.params }),
    },
    { path: '/history', redirect: { name: 'app-history' } },

    // ---- 404 兜底：乱路径一律回工作台，避免主区空白 ----
    { path: '/:pathMatch(.*)*', redirect: { name: 'app-dashboard' } },
  ],
})
