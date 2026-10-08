import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// M54 质量保障：组件冒烟测试（happy-dom 环境，纯 DOM 组件优先；
// echarts 系图表（LineChart/RadarChart）依赖 canvas，jsdom 下不可靠，不纳入冒烟）
export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'happy-dom',
    include: ['tests/**/*.test.js'],
  },
})
