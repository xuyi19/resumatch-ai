<template>
  <div class="min-h-screen py-12">
    <div class="max-w-3xl mx-auto px-6">

      <div class="mb-12">
        <h1 class="text-3xl font-semibold text-gray-800 mb-2">更新日志</h1>
        <p class="text-sm text-gray-600">ResuMatch AI 的版本历史与发布说明</p>
      </div>

      <div class="relative pl-8">
        <div class="absolute left-[5px] top-2 bottom-2 w-px bg-[#b8bcc2]/60"></div>

        <div v-for="log in logs" :key="log.version"
          class="relative mb-12 last:mb-0">

          <div class="absolute -left-8 top-1.5 w-3 h-3 rounded-full bg-[#6d5dfc]
            shadow-[0_0_0_4px_rgba(109,93,252,0.15)]"></div>

          <div class="flex items-baseline gap-4 mb-4 flex-wrap">
            <div class="text-xl font-semibold text-gray-800">{{ log.version }}</div>
            <div class="text-sm text-gray-500 font-mono">{{ log.date }}</div>
          </div>

          <div v-if="log.title" class="text-base font-medium text-gray-700 mb-4">
            {{ log.title }}
          </div>

          <div class="space-y-3">
            <div v-for="(item, j) in log.items" :key="j"
              class="flex gap-3 items-start">
              <span :class="tagClass(item.type)"
                class="shrink-0 mt-0.5 px-2.5 py-1 rounded-lg text-xs font-medium
                  shadow-[inset_2px_2px_4px_rgba(184,188,194,0.3),inset_-2px_-2px_4px_rgba(255,255,255,0.5)]">
                {{ item.type }}
              </span>
              <span class="text-sm text-gray-700 leading-relaxed">{{ item.text }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="mt-16 text-center">
        <RouterLink to="/"
          class="inline-block px-6 py-3 text-sm font-medium rounded-xl
            bg-[#e0e5ec] text-gray-700
            shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
            hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
            active:shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]
            transition-all duration-300 ease-in-out">
          返回首页
        </RouterLink>
      </div>

    </div>
  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router'

const logs = [
  {
    version: 'v0.5.0',
    date: '2026-09-11',
    title: '简历编辑器 + PDF 导出 + 实时日志',
    items: [
      { type: '新增', text: '简历在线编辑器（左侧表单 + 右侧实时预览）' },
      { type: '新增', text: '浏览器打印导出 PDF，所见即所得，无第三方依赖' },
      { type: '新增', text: 'Word 导出保留，与 PDF 双通道下载' },
      { type: '新增', text: 'Word 模板扩充至 8 套（经典/现代/简约/商务/学术/创意/两栏/紧凑）' },
      { type: '新增', text: '诊断进度页新增实时日志面板与阶段追踪' },
      { type: '新增', text: '独立 API 配置页（/settings），支持连接测试' },
      { type: '新增', text: '顶部导航新增 GitHub / Gitee 仓库入口' },
      { type: '优化', text: '编辑数据自动保存到 localStorage，刷新不丢失' },
      { type: '优化', text: '打印区域与编辑区域彻底分离，避免打印污染' },
      { type: '修复', text: '修复诊断进度页长时间空白无反馈的问题' },
    ],
  },
  {
    version: 'v0.4.0',
    date: '2026-09-10',
    title: '对答式优化 + 多模板 Word',
    items: [
      { type: '新增', text: '对答式优化：AI 追问 3-5 个关键信息，用户补充后精准生成' },
      { type: '新增', text: 'ClarifyModal 弹窗组件，支持必答/选答区分' },
      { type: '新增', text: '优化简历从主流程剥离为独立接口（/optimize/{task_id}）' },
      { type: '新增', text: 'Word 模板扩充至 3 套（经典/现代/简约）' },
      { type: '优化', text: '诊断流程从 5 Agent 优化到 4 Agent，缩短响应时间' },
      { type: '优化', text: '结果页改为 Tab 结构（诊断/优化/面试/模拟面试）' },
    ],
  },
  {
    version: 'v0.3.0',
    date: '2026-09-08',
    title: '历史记录 + 代码清理',
    items: [
      { type: '新增', text: '诊断历史记录持久化，服务重启后仍可查看' },
      { type: '新增', text: '全局错误处理 + 日志落盘（按天切分，错误单独存档）' },
      { type: '新增', text: 'CORS + 安全响应头（X-Frame-Options 等）' },
      { type: '新增', text: '一键启动脚本 start.bat' },
      { type: '变更', text: '数据库索引优化（jobs 表加 city+created / source+created 联合索引）' },
      { type: '优化', text: '删除异步版爬虫、旧 HTML 前端等冗余文件' },
    ],
  },
  {
    version: 'v0.2.0',
    date: '2026-09-05',
    title: '前端重构 + 视觉升级',
    items: [
      { type: '新增', text: 'Vue3 + Vite 前端重构（替代旧 HTML）' },
      { type: '新增', text: '新拟物派设计语言，统一视觉风格' },
      { type: '新增', text: 'ECharts 六维雷达图，可视化简历评分' },
      { type: '变更', text: '首页 / 控制台 / 结果页 / 历史记录 四页面结构' },
      { type: '修复', text: '修复 Vue 路由切换时的白屏问题' },
    ],
  },
  {
    version: 'v0.1.0',
    date: '2026-09-01',
    title: '项目初始化',
    items: [
      { type: '新增', text: '智联招聘实时爬虫（Playwright + 同步模式）' },
      { type: '新增', text: '混合匹配算法（关键词 + 语义向量 + 加权排序）' },
      { type: '新增', text: '4 Agent 诊断流程（解析/评分/差距/改写）' },
      { type: '新增', text: '用户自定义 LLM API（DeepSeek / 智谱 / OpenAI）' },
      { type: '新增', text: '简历上传（PDF/DOCX）+ Word 导出（3 模板）' },
    ],
  },
]

function tagClass(type) {
  const map = {
    '新增': 'bg-green-50 text-green-700',
    '变更': 'bg-blue-50 text-blue-700',
    '修复': 'bg-amber-50 text-amber-700',
    '删除': 'bg-red-50 text-red-700',
    '优化': 'bg-purple-50 text-purple-700',
  }
  return map[type] || 'bg-gray-100 text-gray-700'
}
</script>