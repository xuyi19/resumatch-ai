<template>
  <div class="max-w-6xl mx-auto px-6 md:px-8 py-12 md:py-20">

    <!-- Hero -->
    <section class="text-center py-8 md:py-16">
      <div class="inline-flex items-center gap-2 px-4 py-2 rounded-2xl mb-8
        bg-[#e0e5ec] shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]">
        <span class="w-2 h-2 rounded-full bg-[#6d5dfc] animate-pulse" />
        <span class="text-xs font-medium text-gray-600">多智能体引擎已就绪</span>
      </div>

      <h1 class="text-4xl md:text-6xl font-semibold text-gray-800 leading-tight mb-6">
        求职准备的<br />
        <span class="text-[#6d5dfc]">数字核心引擎</span>
      </h1>
      <p class="text-base text-gray-600 max-w-xl mx-auto leading-relaxed mb-10">
        基于大模型多智能体，为你提供简历诊断、岗位匹配、
        STAR 改写建议与简历自动优化的一站式服务。
      </p>

      <div class="flex gap-4 justify-center">
        <RouterLink to="/analyze"
          class="px-8 py-3.5 text-sm font-medium rounded-xl
            bg-[#6d5dfc] text-white
            shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]
            hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
            active:shadow-[inset_4px_4px_8px_rgba(0,0,0,0.2),inset_-4px_-4px_8px_rgba(255,255,255,0.1)]
            transition-all duration-300 ease-in-out">
          开始分析
        </RouterLink>
        <RouterLink to="/analyze"
          class="px-8 py-3.5 text-sm font-medium rounded-xl
            bg-[#e0e5ec] text-gray-700
            shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]
            hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
            active:shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
            transition-all duration-300 ease-in-out">
          了解更多
        </RouterLink>
      </div>
    </section>

    <!-- 功能卡片 -->
    <section class="py-8 md:py-16">
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

    <!-- 数据 -->
    <section class="py-8 md:py-16">
      <div class="bg-[#e0e5ec] rounded-2xl p-10
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <div class="grid grid-cols-3 gap-8 text-center">
          <div v-for="s in stats" :key="s.label">
            <div class="text-4xl md:text-5xl font-semibold text-gray-800 mb-2">{{ s.num }}</div>
            <div class="text-xs md:text-sm text-gray-600">{{ s.label }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="py-8 md:py-16">
      <div class="bg-[#e0e5ec] rounded-2xl p-12 md:p-16 text-center
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <h2 class="text-2xl md:text-4xl font-semibold text-gray-800 mb-4">
          准备好优化你的简历了吗？
        </h2>
        <p class="text-sm text-gray-600 mb-8">
          上传简历，3 分钟获得完整诊断报告
        </p>
        <RouterLink to="/analyze"
          class="inline-block px-8 py-3.5 text-sm font-medium rounded-xl
            bg-[#6d5dfc] text-white
            shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]
            hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
            active:shadow-[inset_4px_4px_8px_rgba(0,0,0,0.2),inset_-4px_-4px_8px_rgba(255,255,255,0.1)]
            transition-all duration-300 ease-in-out">
          立即开始
        </RouterLink>
      </div>
    </section>

    <!-- ★ 仓库 + 更新日志 -->
    <section class="py-8 md:py-16">
      <div class="bg-[#e0e5ec] rounded-2xl p-8 md:p-10
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <div class="flex flex-wrap items-center justify-center gap-4">

          <!-- GitHub -->
          <a :href="REPO.github" target="_blank" rel="noopener"
            class="flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-medium
              bg-[#e0e5ec] text-gray-700
              shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
              hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
              active:shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]
              transition-all duration-300 ease-in-out">
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 .3a12 12 0 00-3.8 23.4c.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.4-1.8-1.4-1.8-1-.7.1-.7.1-.7 1.2 0 1.9 1.2 1.9 1.2 1 1.8 2.8 1.3 3.5 1 0-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-6 0-1.2.5-2.3 1.2-3.1-.1-.4-.5-1.7.1-3.5 0 0 1-.3 3.3 1.2a11.5 11.5 0 016 0c2.3-1.5 3.3-1.2 3.3-1.2.7 1.8.3 3.1.1 3.5.8.8 1.2 1.9 1.2 3.1 0 4.7-2.8 5.7-5.5 6 .4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0012 .3"/>
            </svg>
            <span>GitHub</span>
          </a>

          <!-- Gitee -->
          <a :href="REPO.gitee" target="_blank" rel="noopener"
            class="flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-medium
              bg-[#e0e5ec] text-gray-700
              shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
              hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
              active:shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]
              transition-all duration-300 ease-in-out">
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 1.5C6.2 1.5 1.5 6.2 1.5 12c0 4.6 3 8.5 7.2 9.8.5.1.7-.2.7-.5v-1.7c-2.9.6-3.5-1.4-3.5-1.4-.5-1.2-1.2-1.5-1.2-1.5-1-.7.1-.6.1-.6 1.1.1 1.7 1.1 1.7 1.1 1 1.7 2.5 1.2 3.1.9.1-.7.4-1.2.7-1.5-2.4-.3-4.9-1.2-4.9-5.3 0-1.2.4-2.1 1.1-2.9-.1-.3-.5-1.4.1-2.9 0 0 .9-.3 3 1.1a10.2 10.2 0 015.4 0c2.1-1.4 3-1.1 3-1.1.6 1.5.2 2.6.1 2.9.7.8 1.1 1.7 1.1 2.9 0 4.1-2.5 5-4.9 5.3.4.3.7 1 .7 2v3c0 .3.2.6.7.5A10.5 10.5 0 0022.5 12c0-5.8-4.7-10.5-10.5-10.5z"/>
            </svg>
            <span>Gitee</span>
          </a>

          <!-- 更新日志 -->
          <RouterLink to="/changelog"
            class="flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-medium
              bg-[#e0e5ec] text-[#6d5dfc]
              shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
              hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
              active:shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]
              transition-all duration-300 ease-in-out">
            <span>📋</span>
            <span>更新日志</span>
          </RouterLink>

        </div>
      </div>
    </section>

  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router'

// ★ 换成你自己的仓库地址
const REPO = {
  github: 'https://github.com/your-username/resumatch-ai',
  gitee: 'https://gitee.com/your-username/resumatch-ai',
}

const features = [
  { icon: '🕷️', title: '实时岗位爬取', desc: '根据意向职位，实时抓取智联招聘最新岗位数据' },
  { icon: '🎯', title: '混合匹配算法', desc: '关键词硬匹配 + 语义向量相似度 + 加权综合排序' },
  { icon: '🤖', title: '多智能体诊断', desc: '5 个 Agent 协同：解析·评分·差距·改写·优化' },
]

const stats = [
  { num: '5', label: '智能体协同分析' },
  { num: '6', label: '简历评分维度' },
  { num: '3', label: '简历导出模板' },
]
</script>