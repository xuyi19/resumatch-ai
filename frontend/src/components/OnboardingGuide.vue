<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/45 backdrop-blur-sm"
    @click.self="finish(false)">
    <div class="w-full max-w-lg bg-panel border-2 border-ink rounded-2xl
      shadow-[6px_6px_0_0] shadow-ink/20 overflow-hidden">

      <!-- 头部：品牌 + 跳过 -->
      <div class="px-6 pt-5 pb-4 flex items-center justify-between border-b border-line">
        <div class="flex items-center gap-2.5">
          <span class="w-9 h-9 rounded-lg bg-gradient-to-br from-accent to-accent-hover text-white
            flex items-center justify-center text-base border-2 border-ink/80
            shadow-[2px_2px_0_0] shadow-ink/50">🎯</span>
          <div>
            <div class="text-sm font-semibold text-ink">欢迎使用知岗</div>
            <div class="text-[11px] text-ink-faint">三步开始你的求职加速</div>
          </div>
        </div>
        <button @click="finish(false)"
          class="text-xs text-ink-faint hover:text-ink px-2.5 py-1.5 rounded-lg
            border border-line hover:border-line-strong transition-colors">
          跳过
        </button>
      </div>

      <!-- 步骤进度条 -->
      <div class="px-6 pt-4 flex gap-2">
        <div v-for="(s, i) in steps" :key="i"
          class="h-1.5 flex-1 rounded-full transition-colors duration-300"
          :class="i <= step ? 'bg-accent' : 'bg-inset border border-line'"></div>
      </div>

      <!-- 步骤内容 -->
      <div class="px-8 py-7 min-h-[248px] flex flex-col items-center justify-center text-center">
        <div class="text-5xl mb-4">{{ steps[step].icon }}</div>
        <div class="text-[11px] font-medium text-accent tracking-widest mb-1.5">
          第 {{ step + 1 }} 步 · 共 {{ steps.length }} 步
        </div>
        <div class="text-lg font-semibold text-ink mb-2">{{ steps[step].title }}</div>
        <p class="text-sm text-ink-sub leading-relaxed max-w-sm mb-5">{{ steps[step].desc }}</p>
        <div class="flex flex-wrap justify-center gap-2">
          <span v-for="p in steps[step].points" :key="p"
            class="px-3 py-1.5 text-xs rounded-full bg-inset border border-line text-ink-sub">
            {{ p }}
          </span>
        </div>
      </div>

      <!-- 底部导航 -->
      <div class="px-6 py-4 border-t border-line flex items-center justify-between">
        <button v-if="step > 0" @click="step--"
          class="px-4 py-2 text-xs font-medium rounded-lg border border-line text-ink-sub
            hover:border-line-strong hover:text-ink transition-colors">
          ← 上一步
        </button>
        <span v-else class="text-[11px] text-ink-faint">首次使用会引导你配置 AI 模型</span>

        <button v-if="step < steps.length - 1" @click="step++"
          class="bg-accent text-white px-5 py-2 text-xs font-medium rounded-lg transition-all">
          下一步 →
        </button>
        <button v-else @click="finish(true)"
          class="bg-accent text-white px-5 py-2 text-xs font-medium rounded-lg transition-all">
          开始第一次诊断 →
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
// M55 首次启动引导：三步弹层（传简历 → 贴 JD → 看报告）
// 触发与标记策略：父组件按 localStorage / ?onboarding=1 控制显隐；
// 本组件负责在关闭时落标记（try/catch 兜底，损坏不白屏）。
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const emit = defineEmits(['done'])
const router = useRouter()

const steps = [
  {
    icon: '📄',
    title: '上传简历',
    desc: '上传 PDF / DOCX 原件或直接粘贴文本，也可以在编辑器从零创建。简历入库存档，随时复用与版本对比。',
    points: ['支持 PDF / DOCX / 纯文本', '重复上传自动拦截', '每次保存自动记录版本'],
  },
  {
    icon: '🎯',
    title: '粘贴岗位 JD',
    desc: '把目标岗位的招聘要求原文贴进来，AI 按六维评分逐条对照——你和岗位之间差在哪，一目了然。',
    points: ['JD 越完整，分析越准', '可从岗位市场 / 岗位库一键带入', '心仪岗位可收藏统一管理'],
  },
  {
    icon: '📊',
    title: '获取诊断报告',
    desc: '生成六维评分、差距分析与改写建议，支持导出 Word 存档；改完再诊，两次成绩自动对比。',
    points: ['建议可一键应用到编辑器', '报告导出 / 历史对比', 'AI 面试官随时实战演练'],
  },
]

const step = ref(0)

function finish(navigate) {
  try {
    localStorage.setItem('onboarding_done', '1')
  } catch (e) { /* 隐私模式 / 存储损坏时静默，下次仍会弹出 */ }
  emit('done')
  if (navigate) router.push('/app/analyze')
}
</script>
