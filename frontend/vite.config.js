import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  // 桌面版与后端同域挂载，用相对 base + hash 路由，无需 SPA 回退
  base: './',
  server: {
    host: '0.0.0.0',
    port: 5173,
    // ★ 允许所有 Host 访问（开发环境穿透需要）
    allowedHosts: true,
    // ★ 关闭 HMR 的 host 校验（避免控制台报错）
    hmr: {
      clientPort: 443,
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/frontend': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})