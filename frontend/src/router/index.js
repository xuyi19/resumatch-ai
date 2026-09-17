import { createRouter, createWebHashHistory } from 'vue-router'

export default createRouter({
  history: createWebHashHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    { path: '/', name: 'home', component: () => import('../views/HomeView.vue') },
    { path: '/analyze', name: 'analyze', component: () => import('../views/AnalyzeView.vue') },
    { path: '/result/:taskId', name: 'result', component: () => import('../views/ResultView.vue') },
    { path: '/chat/:taskId', name: 'chat', component: () => import('../views/ChatView.vue') },
    { path: '/editor/:taskId', name: 'editor', component: () => import('../views/EditorView.vue') },
    { path: '/history', name: 'history', component: () => import('../views/HistoryView.vue') },
    { path: '/changelog', name: 'changelog', component: () => import('../views/ChangelogView.vue') },
    { path: '/settings', name: 'settings', component: () => import('../views/SettingsView.vue') },
  ],
})