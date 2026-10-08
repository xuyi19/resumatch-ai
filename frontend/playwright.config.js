import { defineConfig } from '@playwright/test'

// M54 质量保障：E2E 冒烟（纯前端路由页，不依赖后端 API）。
// channel: 'msedge' 直接用 Windows 自带 Edge，免去 playwright install 下载浏览器。
// 项目为 hash 路由（createWebHashHistory），E2E URL 一律 /#/path。
// 独立端口 5199 + strictPort：与开发者手动跑的 5173 dev server 完全隔离
// （复用旧 server 会吃到过期代码，页面路由表现不可信）。
export default defineConfig({
  testDir: 'e2e',
  timeout: 30000,
  retries: 0,
  use: {
    baseURL: 'http://localhost:5199',
    channel: 'msedge',
    headless: true,
  },
  webServer: {
    command: 'npm run dev -- --port 5199 --strictPort',
    url: 'http://localhost:5199',
    reuseExistingServer: true,
    timeout: 60000,
  },
})
