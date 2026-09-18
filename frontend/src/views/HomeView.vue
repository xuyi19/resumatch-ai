<template>
  <div class="max-w-6xl mx-auto px-6 md:px-8 pb-24">

    <!-- ★ 快入口：随滚动固定在顶栏下方，随时一键直达诊断 -->
    <div class="sticky top-16 z-40 -mx-6 md:-mx-8 px-6 md:px-8 py-3 bg-[#e0e5ec]/95 backdrop-blur-sm">
      <div class="flex items-center justify-between gap-4 rounded-2xl px-5 py-3
        bg-[#e0e5ec] shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]">
        <p class="text-xs md:text-sm text-gray-600 truncate">
          <span class="font-medium text-gray-800">上传简历 + 粘贴 JD</span>
          <span class="hidden sm:inline">，约 3 分钟拿到六维评分与改写建议</span>
        </p>
        <RouterLink to="/analyze"
          class="shrink-0 px-5 py-2 text-xs md:text-sm font-medium rounded-xl
            bg-[#6d5dfc] text-white
            shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
            hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
            active:shadow-[inset_3px_3px_6px_rgba(0,0,0,0.2),inset_-3px_-3px_6px_rgba(255,255,255,0.1)]
            transition-all duration-300 ease-in-out">
          立即诊断
        </RouterLink>
      </div>
    </div>

    <!-- Hero -->
    <section class="text-center pt-10 md:pt-16 pb-8 md:pb-12">
      <div class="inline-flex items-center gap-2 px-4 py-2 rounded-2xl mb-8
        bg-[#e0e5ec] shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]">
        <span class="w-2 h-2 rounded-full bg-[#6d5dfc] animate-pulse" />
        <span class="text-xs font-medium text-gray-600">{{ badgeText }}</span>
      </div>

      <h1 class="text-4xl md:text-6xl font-semibold text-gray-800 leading-tight mb-6">
        简历诊断，<br />
        <span class="text-[#6d5dfc]">对着岗位改</span>
      </h1>
      <p class="text-base text-gray-600 max-w-2xl mx-auto leading-relaxed mb-10">
        多智能体流水线：并行解析简历与岗位 JD，给出六维评分、差距分析与 STAR 改写建议，
        再经一轮自省精修——最后用 10 套模板导出 Word。
      </p>

      <div class="flex gap-4 justify-center flex-wrap">
        <RouterLink to="/analyze"
          class="px-8 py-3.5 text-sm font-medium rounded-xl
            bg-[#6d5dfc] text-white
            shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]
            hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
            active:shadow-[inset_4px_4px_8px_rgba(0,0,0,0.2),inset_-4px_-4px_8px_rgba(255,255,255,0.1)]
            transition-all duration-300 ease-in-out">
          开始诊断
        </RouterLink>
        <RouterLink to="/history"
          class="px-8 py-3.5 text-sm font-medium rounded-xl
            bg-[#e0e5ec] text-gray-700
            shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]
            hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
            active:shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
            transition-all duration-300 ease-in-out">
          查看历史记录
        </RouterLink>
      </div>
    </section>

    <!-- 功能亮点 -->
    <section class="py-8 md:py-12">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div v-for="f in features" :key="f.title"
          class="bg-[#e0e5ec] rounded-2xl p-8
            shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]
            hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
            transition-all duration-300 ease-in-out">
          <div class="w-14 h-14 rounded-2xl bg-[#e0e5ec]
            shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
            flex items-center justify-center text-2xl mb-5">
            {{ f.icon }}
          </div>
          <h3 class="text-lg font-semibold text-gray-800 mb-2">{{ f.title }}</h3>
          <p class="text-sm text-gray-600 leading-relaxed">{{ f.desc }}</p>
        </div>
      </div>
    </section>

    <!-- 工作流程 -->
    <section class="py-8 md:py-12">
      <div class="bg-[#e0e5ec] rounded-2xl p-8 md:p-12
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <h2 class="text-xl md:text-2xl font-semibold text-gray-800 mb-2 text-center">
          诊断流水线
        </h2>
        <p class="text-xs md:text-sm text-gray-600 text-center mb-10">
          解析简历与解析岗位并行执行，省去一次串行等待
        </p>

        <ol class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <li v-for="(s, i) in steps" :key="s.title"
            class="flex gap-4 items-start rounded-xl p-4 bg-[#e0e5ec]
              shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]">
            <span class="w-8 h-8 shrink-0 rounded-lg flex items-center justify-center text-xs font-semibold
              bg-[#e0e5ec] text-[#6d5dfc]
              shadow-[3px_3px_6px_#b8bcc2,-3px_-3px_6px_#ffffff]">
              {{ i + 1 }}
            </span>
            <div class="min-w-0">
              <div class="text-sm font-medium text-gray-800 mb-1">
                {{ s.title }}
                <span v-if="s.parallel"
                  class="ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-normal text-[#6d5dfc] bg-white/50">
                  并行
                </span>
              </div>
              <p class="text-xs text-gray-600 leading-relaxed">{{ s.desc }}</p>
            </div>
          </li>
        </ol>
      </div>
    </section>

    <!-- 数据 -->
    <section class="py-8 md:py-12">
      <div class="bg-[#e0e5ec] rounded-2xl p-10
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          <div v-for="s in stats" :key="s.label">
            <div class="text-4xl md:text-5xl font-semibold text-gray-800 mb-2">{{ s.num }}</div>
            <div class="text-xs md:text-sm text-gray-600">{{ s.label }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- 形态说明：桌面版 / 网页版差异化 -->
    <section class="py-8 md:py-12">
      <div class="bg-[#e0e5ec] rounded-2xl p-8 md:p-10
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <h2 class="text-lg md:text-xl font-semibold text-gray-800 mb-6 text-center">
          {{ isWeb ? '关于在线使用' : '关于本机使用' }}
        </h2>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-6 text-center">
          <div v-for="n in notes" :key="n.title">
            <div class="text-xl mb-2">{{ n.icon }}</div>
            <div class="text-sm font-medium text-gray-800 mb-1">{{ n.title }}</div>
            <p class="text-xs text-gray-600 leading-relaxed">{{ n.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="py-8 md:py-12">
      <div class="bg-[#e0e5ec] rounded-2xl p-12 md:p-16 text-center
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <h2 class="text-2xl md:text-4xl font-semibold text-gray-800 mb-4">
          准备好优化你的简历了吗？
        </h2>
        <p class="text-sm text-gray-600 mb-8">
          {{ isWeb ? '无需注册，粘贴 JD 即可开始' : '数据只存在本机，随时可查历史记录' }}
        </p>
        <div class="flex gap-4 justify-center flex-wrap">
          <RouterLink to="/analyze"
            class="inline-block px-8 py-3.5 text-sm font-medium rounded-xl
              bg-[#6d5dfc] text-white
              shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]
              hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
              active:shadow-[inset_4px_4px_8px_rgba(0,0,0,0.2),inset_-4px_-4px_8px_rgba(255,255,255,0.1)]
              transition-all duration-300 ease-in-out">
            立即开始
          </RouterLink>
          <RouterLink to="/changelog"
            class="inline-block px-8 py-3.5 text-sm font-medium rounded-xl
              bg-[#e0e5ec] text-gray-700
              shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]
              hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
              active:shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
              transition-all duration-300 ease-in-out">
            📋 查看更新日志
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
  isWeb ? '多智能体引擎已就绪 · 无需注册' : '多智能体引擎已就绪 · 本机运行',
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