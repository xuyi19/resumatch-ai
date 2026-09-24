<template>
  <div class="max-w-6xl mx-auto px-6 md:px-10 py-10 md:py-14 pb-24">

    <!-- Hero -->
    <section class="pb-10 md:pb-14">
      <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-md mb-7
        bg-panel border border-line">
        <span class="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
        <span class="text-xs font-medium text-ink-sub font-mono">{{ badgeText }}</span>
      </div>

      <p class="text-sm text-ink-faint font-mono mb-3 tracking-wide">知岗 ResuMatch-AI</p>
      <h1 class="text-4xl md:text-6xl font-semibold leading-tight mb-6 tracking-tight">
        <span class="bg-gradient-to-br from-ink via-ink to-accent bg-clip-text text-transparent">
        简历诊断，<br />
        <span class="text-accent">对着岗位改</span>
        </span>
      </h1>
      <p class="text-base text-ink-sub max-w-2xl leading-relaxed mb-9">
        知岗，意在<strong class="text-ink font-semibold">读懂岗位所求，认清自身所长</strong>。
        它是求职者的岗位需求分析师——以岗位 JD 为标尺，多智能体并行解析简历与岗位，
        量化六维适配度、定位能力短板、挖掘被忽略的亮点，让简历不再是经历的堆砌，
        而是对岗位需求的有效回应。
      </p>

      <div class="flex gap-3 flex-wrap">
        <RouterLink to="/app/analyze"
          class="px-6 py-3 text-sm font-medium rounded-lg bg-accent text-white
            hover:bg-accent-hover active:scale-[0.98] transition-all duration-150">
          开始诊断
        </RouterLink>
        <RouterLink to="/guide"
          class="px-6 py-3 text-sm font-medium rounded-lg bg-panel border border-line
            text-ink hover:border-accent hover:text-accent transition-colors duration-150">
          📖 使用说明
        </RouterLink>
        <RouterLink to="/app/editor"
          class="px-6 py-3 text-sm font-medium rounded-lg bg-panel border border-line
            text-ink hover:border-accent hover:text-accent transition-colors duration-150">
          免费创建简历
        </RouterLink>
      </div>
    </section>

    <!-- 功能亮点 -->
    <section class="py-8 md:py-10 border-t border-line">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8">
        <div v-for="f in features" :key="f.title"
          class="bg-panel border border-line rounded-lg p-6
            hover:border-accent/50 transition-colors duration-150">
          <div class="w-9 h-9 rounded-md bg-accent/10 text-accent
            flex items-center justify-center text-lg mb-4">{{ f.icon }}</div>
          <h3 class="text-base font-semibold mb-2">{{ f.title }}</h3>
          <p class="text-sm text-ink-sub leading-relaxed">{{ f.desc }}</p>
        </div>
      </div>
    </section>

    <!-- 诊断流水线 -->
    <section class="py-8 md:py-10 border-t border-line">
      <h2 class="text-xl md:text-2xl font-semibold mt-8 mb-1">诊断流水线</h2>
      <p class="text-xs md:text-sm text-ink-faint mb-8 font-mono">
        // 解析简历与解析岗位并行执行，省去一次串行等待
      </p>

      <ol class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <li v-for="(s, i) in steps" :key="s.title"
          class="flex gap-3.5 items-start rounded-lg p-4 bg-panel border border-line">
          <span class="w-7 h-7 shrink-0 rounded-md flex items-center justify-center
            text-xs font-semibold font-mono bg-accent/10 text-accent">
            {{ String(i + 1).padStart(2, '0') }}
          </span>
          <div class="min-w-0">
            <div class="text-sm font-medium mb-1">
              {{ s.title }}
              <span v-if="s.parallel"
                class="ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-normal
                  text-accent bg-accent/10 font-mono">并行</span>
            </div>
            <p class="text-xs text-ink-sub leading-relaxed">{{ s.desc }}</p>
          </div>
        </li>
      </ol>
    </section>

    <!-- 数据 -->
    <section class="py-8 md:py-10 border-t border-line">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-6 mt-8">
        <div v-for="s in stats" :key="s.label" class="text-center py-6 rounded-lg
          bg-panel border border-line">
          <div class="text-4xl md:text-5xl font-semibold font-mono text-accent mb-2">
            {{ s.num }}
          </div>
          <div class="text-xs md:text-sm text-ink-sub">{{ s.label }}</div>
        </div>
      </div>
    </section>

    <!-- 形态说明 -->
    <section class="py-8 md:py-10 border-t border-line">
      <h2 class="text-lg md:text-xl font-semibold mt-8 mb-6">
        {{ isWeb ? '关于在线使用' : '关于本机使用' }}
      </h2>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div v-for="n in notes" :key="n.title" class="p-5 rounded-lg bg-panel border border-line">
          <div class="text-lg mb-2">{{ n.icon }}</div>
          <div class="text-sm font-medium mb-1">{{ n.title }}</div>
          <p class="text-xs text-ink-sub leading-relaxed">{{ n.desc }}</p>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="py-8 md:py-10 border-t border-line">
      <div class="mt-8 p-10 md:p-14 rounded-lg bg-panel border border-line text-center">
        <h2 class="text-2xl md:text-4xl font-semibold mb-4">准备好优化你的简历了吗？</h2>
        <p class="text-sm text-ink-sub mb-8">
          {{ isWeb ? '无需注册，粘贴 JD 即可开始' : '数据只存在本机，随时可查历史记录' }}
        </p>
        <div class="flex gap-3 justify-center flex-wrap">
          <RouterLink to="/app/analyze"
            class="inline-block px-8 py-3 text-sm font-medium rounded-lg bg-accent text-white
              hover:bg-accent-hover active:scale-[0.98] transition-all duration-150">
            立即开始
          </RouterLink>
          <RouterLink to="/changelog"
            class="inline-block px-8 py-3 text-sm font-medium rounded-lg
              bg-panel border border-line text-ink hover:border-accent hover:text-accent
              transition-colors duration-150">
            查看更新日志
          </RouterLink>
        </div>
      </div>
    </section>

  </div>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useAppMode } from '../composables/useAppMode'

const { meta, isWeb, quotaEnabled } = useAppMode()

const features = [
  {
    icon: '🤖',
    title: '多智能体诊断',
    desc: '6 个节点协同：并行解析简历与岗位、六维评分、差距分析、STAR 改写，最后自省精修一轮。',
  },
  {
    icon: '📝',
    title: '10 套模板导出 Word',
    desc: '经典、商务、侧栏、学术等 10 套版式，可嵌入证件照，改完一键导出可投递的 Word。',
  },
  {
    icon: '⚡',
    title: '实时流式进度',
    desc: '诊断过程逐节点实时推送，评分与建议边算边看，无需反复刷新等待。',
  },
]

const steps = [
  { title: '解析简历', desc: '抽取教育、经历、技能等结构化字段', parallel: true },
  { title: '解析岗位 JD', desc: '识别岗位要求与关键能力项', parallel: true },
  { title: '六维评分', desc: '匹配度、量化、结构、关键词等六维打分' },
  { title: '差距分析', desc: '逐条指出与岗位要求的差距' },
  { title: 'STAR 改写', desc: '把平淡描述改写成有结果、有量化的表达' },
  { title: '自省精修', desc: '自我批判一轮，剔除编造与重复的建议' },
]

const stats = [
  { num: '6', label: '智能体节点' },
  { num: '6', label: '评分维度' },
  { num: '10', label: '导出模板' },
  { num: '3', label: '分钟出报告' },
]

const badgeText = computed(() =>
  isWeb ? '知岗 ResuMatch-AI · 引擎就绪 · 无需注册' : '知岗 ResuMatch-AI · 引擎就绪 · 本机运行',
)

const notes = computed(() => isWeb
  ? [
      {
        icon: '🔒',
        title: '匿名会话隔离',
        desc: '首次访问自动分配会话，简历与诊断记录仅本会话可见，互不干扰。',
      },
      {
        icon: '⚡',
        title: quotaEnabled.value ? `每日免费 ${meta.value.daily_limit} 次` : '免费使用',
        desc: quotaEnabled.value
          ? '使用站点预置 Key 每日可免费诊断，在设置页填自己的 Key 则不限次数。'
          : '在设置页填入自己的 API Key 即可开始诊断。',
      },
      {
        icon: '🧭',
        title: '换设备需重新诊断',
        desc: '会话基于浏览器 Cookie，清除 Cookie 或更换设备后将看不到此前的记录。',
      },
    ]
  : [
      {
        icon: '💾',
        title: '数据只在本机',
        desc: '简历、诊断记录、导出文件全部存放在本机 data 目录，不经过第三方服务器。',
      },
      {
        icon: '🔑',
        title: '自带 Key 或预置 Key',
        desc: '可在设置页填写自己的大模型 API Key；分发版也可预置 config.json 免填写。',
      },
      {
        icon: '📴',
        title: '免安装、离线可用界面',
        desc: '双击即可运行，无需安装 Python / Node；仅诊断调用大模型时需要联网。',
      },
    ])
</script>
