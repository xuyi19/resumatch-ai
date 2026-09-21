<template>
  <div class="max-w-6xl mx-auto px-6 md:px-8 py-12 md:py-16">

    <!-- 进度页（带实时日志） -->
    <div v-if="status === 'running' || status === 'pending'"
         class="max-w-3xl mx-auto py-12">

      <div class="text-center mb-10">
        <div class="inline-block relative mb-6">
          <div class="w-16 h-16 rounded-2xl bg-[#e0e5ec]
            shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]"></div>
          <div
              class="absolute inset-0 w-16 h-16 rounded-2xl border-4 border-transparent border-t-[#6d5dfc] animate-spin"></div>
        </div>
        <div class="text-xl font-semibold text-gray-800 mb-1">
          {{ message || '正在初始化...' }}
        </div>
        <div class="text-xs text-gray-500 mt-2">
          多智能体诊断约需 60 秒
        </div>
        <div v-if="elapsedText" class="text-xs text-[#6d5dfc] mt-1 font-mono">
          ⏱ 已运行 {{ elapsedText }}
        </div>
      </div>

      <div class="bg-[#e0e5ec] rounded-2xl p-6 mb-6
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <div class="flex items-center justify-between mb-3">
          <span class="text-xs font-medium text-gray-500">整体进度</span>
          <span class="text-sm font-semibold text-[#6d5dfc]">{{ progress }}%</span>
        </div>
        <div class="h-3 rounded-full bg-[#e0e5ec]
          shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] overflow-hidden">
          <div class="h-full bg-[#6d5dfc] rounded-full transition-all duration-300"
               :style="{ width: progress + '%' }"/>
        </div>
      </div>

      <div class="bg-[#e0e5ec] rounded-2xl p-6 mb-6
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <div class="space-y-3">
          <div v-for="(s, i) in stages" :key="i"
               class="flex items-center gap-3 transition-all duration-300">
            <div class="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-xs font-semibold"
                 :class="stageStatusClass(s.key)">
              <span v-if="isStageDone(s.key)">✓</span>
              <span v-else-if="isStageActive(s.key)"
                    class="inline-block w-3 h-3 rounded-full border-2 border-transparent border-t-current animate-spin"></span>
              <span v-else>{{ i + 1 }}</span>
            </div>
            <span class="text-sm font-medium transition-colors duration-300"
                  :class="isStageDone(s.key) ? 'text-gray-400 line-through' :
                      isStageActive(s.key) ? 'text-[#6d5dfc]' :
                      'text-gray-500'">
              {{ s.label }}
            </span>
            <span v-if="isStageDone(s.key)" class="ml-auto text-xs text-green-500">完成</span>
          </div>
        </div>
      </div>

      <div class="bg-[#e0e5ec] rounded-2xl p-6
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <div class="flex items-center justify-between mb-4">
          <span class="text-xs font-medium text-gray-500">实时日志</span>
          <span class="w-2 h-2 rounded-full bg-[#6d5dfc] animate-pulse"></span>
        </div>
        <div ref="logRef" class="space-y-2 max-h-64 overflow-y-auto pr-2">
          <div v-for="(log, i) in logs" :key="i"
               class="flex items-start gap-3 text-xs animate-fade-in">
            <span class="text-gray-400 font-mono shrink-0">{{ log.time }}</span>
            <span class="text-gray-700 flex-1 leading-relaxed">{{ log.message }}</span>
          </div>
          <div v-if="!logs.length" class="text-xs text-gray-400 text-center py-4">
            等待后端返回日志...
          </div>
        </div>
      </div>

    </div>

    <!-- 动态追问（M11-B）：AI 判定信息不足，interrupt 等待补充 -->
    <div v-else-if="status === 'waiting_clarify'" class="max-w-2xl mx-auto py-12">

      <div class="text-center mb-8">
        <div class="text-4xl mb-4">🤔</div>
        <h1 class="text-xl font-semibold text-gray-800">需要补充几条信息</h1>
        <p class="text-sm text-gray-500 mt-2">
          AI 判断回答以下问题能让差距结论与改写建议更可靠，一两句话回答即可
        </p>
      </div>

      <div class="space-y-4">
        <div v-for="(q, i) in clarifyQuestions" :key="q.id || i"
             class="bg-[#e0e5ec] rounded-2xl p-6
            shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
          <div class="text-xs font-semibold text-[#6d5dfc] mb-2">
            追问 {{ i + 1 }}<span v-if="q.gap"> · 针对：{{ q.gap }}</span>
          </div>
          <div class="text-sm text-gray-800 mb-3 leading-relaxed">{{ q.question }}</div>
          <div v-if="q.hint" class="text-xs text-gray-400 mb-2">💡 {{ q.hint }}</div>
          <textarea v-model="clarifyAnswers[q.id || `q${i + 1}`]" rows="2"
                    placeholder="一句话回答即可，例：该项目峰值 QPS 约 3000，日活 5 万"
                    class="w-full px-4 py-3 rounded-xl bg-[#e0e5ec] text-sm text-gray-800
                placeholder-gray-400 outline-none resize-none
                shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]
                focus:ring-2 focus:ring-[#6d5dfc]/30"></textarea>
        </div>
      </div>

      <div class="text-center mt-8">
        <button @click="submitClarify" :disabled="clarifySubmitting"
                class="px-8 py-3 text-sm font-medium rounded-xl bg-[#6d5dfc] text-white
            shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]
            hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
            transition-all duration-300 disabled:opacity-50">
          {{ clarifySubmitting ? '提交中...' : '提交并继续诊断' }}
        </button>
        <div class="text-xs text-gray-400 mt-3">至少回答一个问题；提交后诊断将在改写建议处继续</div>
      </div>
    </div>

    <!-- 结果 -->
    <div v-else-if="status === 'success'">

      <div class="text-center mb-8">
        <h1 class="text-3xl md:text-4xl font-semibold text-gray-800 mb-2">诊断报告</h1>
        <p v-if="result.diagnosis_target" class="text-sm text-gray-600">
          {{ result.diagnosis_target.title }} · {{ result.diagnosis_target.company }}
        </p>
      </div>

      <!-- Tab 导航 -->
      <div class="flex justify-center mb-8">
        <div class="inline-flex gap-2 p-1.5 rounded-2xl bg-[#e0e5ec]
          shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]">
          <button v-for="tab in tabs" :key="tab.key"
                  @click="activeTab = tab.key"
                  class="px-5 py-2.5 text-sm font-medium rounded-xl
              transition-all duration-300 ease-in-out"
                  :class="activeTab === tab.key
              ? 'bg-[#e0e5ec] text-[#6d5dfc] shadow-[3px_3px_6px_#b8bcc2,-3px_-3px_6px_#ffffff]'
              : 'text-gray-600 hover:text-gray-800'">
            {{ tab.icon }} {{ tab.label }}
          </button>
        </div>
      </div>

      <!-- ============ Tab 1: 诊断报告 ============ -->
      <div v-show="activeTab === 'diagnosis'" class="space-y-6">

        <div class="bg-[#e0e5ec] rounded-2xl p-8
          shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
          <div class="grid grid-cols-1 md:grid-cols-4 gap-6 items-center">
            <div class="text-center md:text-left">
              <div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">综合评分</div>
              <div class="text-6xl font-semibold text-[#6d5dfc]">{{ result.diagnosis?.scores?.overall || '--' }}</div>
              <div class="text-xs text-gray-500 mt-1">/ 100</div>
            </div>
            <div class="md:col-span-3">
              <div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">技能标签</div>
              <div class="flex flex-wrap gap-2">
                <span v-for="s in result.diagnosis?.parsed?.skills || []" :key="s"
                      class="px-3 py-1.5 rounded-xl text-xs font-medium
                    bg-[#e0e5ec] text-[#6d5dfc]
                    shadow-[3px_3px_6px_#b8bcc2,-3px_-3px_6px_#ffffff]">
                  {{ s }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div class="lg:col-span-2 bg-[#e0e5ec] rounded-2xl p-6
            shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
            <h2 class="text-base font-semibold text-gray-800 mb-4">六维评分</h2>
            <div ref="chartRef" style="width:100%; height:360px"/>
          </div>

          <div class="bg-[#e0e5ec] rounded-2xl p-6
            shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
            <h2 class="text-base font-semibold text-gray-800 mb-4">综合评价</h2>
            <p class="text-sm text-gray-600 leading-relaxed">{{ overallComment }}</p>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="bg-[#e0e5ec] rounded-2xl p-6
            shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-8 h-8 rounded-xl bg-[#e0e5ec] flex items-center justify-center text-green-600
                shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]">✓
              </div>
              <h2 class="text-base font-semibold text-gray-800">主要优势</h2>
            </div>
            <ul class="space-y-3 text-sm text-gray-700">
              <li v-for="(item, i) in strengths" :key="i" class="flex gap-3 items-start">
                <span class="text-green-600 shrink-0 mt-0.5">✓</span>
                <span>{{ item }}</span>
              </li>
              <li v-if="!strengths.length" class="text-gray-400 text-sm">暂无高亮优势维度</li>
            </ul>
          </div>

          <div class="bg-[#e0e5ec] rounded-2xl p-6
            shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-8 h-8 rounded-xl bg-[#e0e5ec] flex items-center justify-center text-amber-600
                shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]">△
              </div>
              <h2 class="text-base font-semibold text-gray-800">待提升项</h2>
            </div>
            <ul class="space-y-3 text-sm text-gray-700">
              <li v-for="(g, i) in gaps" :key="i" class="flex gap-3 items-start">
                <span :class="severityColor(g.severity)" class="shrink-0 mt-0.5">△</span>
                <span class="flex-1">
                  <span :class="severityColor(g.severity)" class="text-xs font-semibold">[{{
                      g.severity || '-'
                    }}]</span>
                  {{ g.description }}
                  <span v-if="g.is_inferred"
                        class="ml-1 text-[10px] px-1.5 py-0.5 rounded bg-gray-200 text-gray-500 align-middle">推断</span>
                  <!-- RAG 证据引用（M11-A）：展示支撑该差距的简历原文 -->
                  <span v-if="g.evidence && g.evidence.length" class="block mt-2 space-y-1.5">
                    <span v-for="ev in g.evidence" :key="ev.id"
                          class="block text-xs text-gray-500 rounded-lg px-3 py-2 border-l-2 border-[#6d5dfc]/40 bg-white/40">
                      <span class="font-mono text-[#6d5dfc] mr-1">[{{ ev.id }}]</span>{{ ev.text }}
                    </span>
                  </span>
                </span>
              </li>
              <li v-if="!gaps.length" class="text-gray-400 text-sm">暂无差距分析</li>
            </ul>
            <p v-if="gapSummary" class="mt-3 text-sm text-amber-700 leading-relaxed">{{ gapSummary }}</p>
          </div>
        </div>

        <div class="bg-[#e0e5ec] rounded-2xl p-6
          shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
          <h2 class="text-base font-semibold text-gray-800 mb-4">改写建议</h2>
          <div class="space-y-4">
            <div v-for="(s, i) in suggestions" :key="i"
                 class="p-5 rounded-xl bg-[#e0e5ec]
                shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]">
              <div class="text-xs text-gray-500 mb-2">{{ s.target }}</div>
              <div class="text-sm text-gray-400 line-through mb-2">{{ s.original || '（新增内容）' }}</div>
              <div class="text-sm text-gray-800 px-3 py-2 rounded-lg bg-[#6d5dfc]/10 border-l-2 border-[#6d5dfc]">
                {{ s.rewritten }}
              </div>
              <div class="text-xs text-gray-500 mt-3">💡 {{ s.reason }}</div>
              <div v-if="s.evidence_ids && s.evidence_ids.length" class="text-xs text-gray-400 mt-1">
                📎 依据证据：{{ s.evidence_ids.join(' / ') }}
              </div>
            </div>
            <div v-if="overallAdvice" class="p-5 rounded-xl bg-[#6d5dfc]/10 text-sm text-gray-800">
              <span class="font-semibold text-[#6d5dfc]">整体建议：</span>{{ overallAdvice }}
            </div>
          </div>
        </div>
      </div>

      <!-- ============ Tab 2: 优化简历 ============ -->
      <div v-show="activeTab === 'optimize'">

        <div v-if="!optimizedResume && !optimizing"
             class="bg-[#e0e5ec] rounded-2xl p-12
            shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
          <div class="text-center mb-10">
            <div class="inline-flex items-center justify-center w-20 h-20 rounded-3xl mb-6
              bg-[#e0e5ec]
              shadow-[inset_6px_6px_12px_#b8bcc2,inset_-6px_-6px_12px_#ffffff]">
              <span class="text-4xl">📝</span>
            </div>
            <div class="text-lg font-semibold text-gray-800 mb-2">优化你的简历</div>
            <p class="text-sm text-gray-600">选择优化模式</p>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-2xl mx-auto">
            <button @click="$router.push(`/chat/${taskId}`)"
                    class="p-6 rounded-2xl text-left
    bg-[#e0e5ec]
    shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]
    hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
    active:shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
    transition-all duration-300">
              <div class="text-2xl mb-3">💬</div>
              <div class="font-semibold text-[#6d5dfc] mb-2">对答式优化</div>
              <div class="text-xs text-gray-600 leading-relaxed">
                AI 追问 3-5 个关键信息，你补充后生成更精准的简历
              </div>
              <div class="text-xs text-gray-400 mt-3">约 2 分钟，推荐</div>
            </button>

            <button @click="quickGenerate" :disabled="optimizing"
                    class="p-6 rounded-2xl text-left
                bg-[#e0e5ec]
                shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]
                hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
                active:shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
                transition-all duration-300">
              <div class="text-2xl mb-3">⚡</div>
              <div class="font-semibold text-gray-700 mb-2">快速生成</div>
              <div class="text-xs text-gray-600 leading-relaxed">
                直接基于诊断结果生成优化简历
              </div>
              <div class="text-xs text-gray-400 mt-3">约 30 秒</div>
            </button>
          </div>
        </div>

        <div v-else-if="optimizing"
             class="bg-[#e0e5ec] rounded-2xl p-16 text-center
            shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
          <div class="inline-block relative mb-8">
            <div class="w-16 h-16 rounded-2xl bg-[#e0e5ec]
              shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]"></div>
            <div
                class="absolute inset-0 w-16 h-16 rounded-2xl border-4 border-transparent border-t-[#6d5dfc] animate-spin"></div>
          </div>
          <div class="text-base font-semibold text-gray-800 mb-2">
            {{ 'AI 正在重写简历...' }}
          </div>
          <div class="text-sm text-gray-500">{{ '约 30 秒，请稍候' }}</div>
        </div>

        <div v-else-if="optimizedResume" class="space-y-6">
          <div class="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h2 class="text-lg font-semibold text-gray-800">优化后的简历</h2>
              <p class="text-xs text-gray-500 mt-1">点击编辑可自定义内容，再导出</p>
            </div>
            <div class="flex gap-2">
              <RouterLink :to="`/chat/${taskId}`"
                          class="flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-xl
    bg-[#6d5dfc] text-white
    shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
    hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
    transition-all duration-300">
                💬 对答式优化
              </RouterLink>
              <RouterLink :to="`/editor/${taskId}`"
                          class="flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-xl
    bg-[#e0e5ec] text-gray-700
    shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
    hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
    transition-all duration-300">
                ✏️ 编辑
              </RouterLink>
              <button @click="downloadDocx" :disabled="downloading"
                      class="flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-xl
                  bg-[#6d5dfc] text-white
                  shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
                  hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
                  disabled:opacity-50">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                </svg>
                <span>{{ downloading ? '生成中...' : '下载 Word' }}</span>
              </button>
            </div>
          </div>

          <div class="bg-[#e0e5ec] rounded-2xl p-6
            shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
            <div class="text-xs font-medium text-gray-500 mb-3">选择模板</div>
            <div class="flex gap-2 flex-wrap">
              <button v-for="t in templates" :key="t.key"
                      @click="currentTemplate = t.key"
                      class="px-5 py-2.5 text-sm font-medium rounded-xl transition-all duration-300"
                      :class="currentTemplate === t.key
                  ? 'bg-[#e0e5ec] text-[#6d5dfc] shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]'
                  : 'bg-[#e0e5ec] text-gray-600 shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]'">
                {{ t.label }}
              </button>
            </div>
          </div>

          <div class="rounded-xl bg-[#d1d5db] p-4 md:p-6 overflow-auto">
            <div class="mx-auto bg-white shadow-lg"
                 style="max-width: 720px; min-height: 500px; padding: 40px 44px;">
              <div :class="`resume-paper ${currentTemplate}`">
                <div class="r-name">{{ optimizedResume.name || '个人简历' }}</div>
                <div v-if="optimizedResume.contact" class="r-contact">{{ optimizedResume.contact }}</div>
                <div v-if="optimizedResume.summary" class="r-section">
                  <div class="r-section-title">个人简介</div>
                  <div class="r-line">{{ optimizedResume.summary }}</div>
                </div>
                <div v-if="optimizedResume.education?.length" class="r-section">
                  <div class="r-section-title">教育经历</div>
                  <div v-for="(l, i) in optimizedResume.education" :key="i" class="r-line">{{ l }}</div>
                </div>
                <div v-if="optimizedResume.experience?.length" class="r-section">
                  <div class="r-section-title">工作经历</div>
                  <div v-for="(l, i) in optimizedResume.experience" :key="i" class="r-line">{{ l }}</div>
                </div>
                <div v-if="optimizedResume.projects?.length" class="r-section">
                  <div class="r-section-title">项目经历</div>
                  <div v-for="(l, i) in optimizedResume.projects" :key="i" class="r-line">{{ l }}</div>
                </div>
                <div v-if="optimizedResume.skills?.length" class="r-section">
                  <div class="r-section-title">技能</div>
                  <div class="r-line">{{ optimizedResume.skills.join(' · ') }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ============ Tab 3: 面试准备 ============ -->
      <div v-show="activeTab === 'interview'"
           class="bg-[#e0e5ec] rounded-2xl p-16 text-center
          shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <div class="inline-flex items-center justify-center w-24 h-24 rounded-3xl mb-6
          bg-[#e0e5ec]
          shadow-[inset_6px_6px_12px_#b8bcc2,inset_-6px_-6px_12px_#ffffff]">
          <span class="text-4xl">🎤</span>
        </div>
        <div class="text-lg font-semibold text-gray-800 mb-2">面试准备</div>
        <p class="text-sm text-gray-600 max-w-md mx-auto">
          基于简历与目标岗位，AI 生成面试官可能的问题、考察点与回答提示。
          <br/>
          <span class="text-xs text-[#6d5dfc]">即将上线</span>
        </p>
      </div>

      <!-- ============ Tab 4: 模拟面试 ============ -->
      <div v-show="activeTab === 'mock'"
           class="bg-[#e0e5ec] rounded-2xl p-16 text-center
          shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
        <div class="inline-flex items-center justify-center w-24 h-24 rounded-3xl mb-6
          bg-[#e0e5ec]
          shadow-[inset_6px_6px_12px_#b8bcc2,inset_-6px_-6px_12px_#ffffff]">
          <span class="text-4xl">🎬</span>
        </div>
        <div class="text-lg font-semibold text-gray-800 mb-2">模拟面试</div>
        <p class="text-sm text-gray-600 max-w-md mx-auto">
          与 AI 面试官实时对话，模拟真实面试场景。
          <br/>
          <span class="text-xs text-[#6d5dfc]">即将上线</span>
        </p>
      </div>

    </div>

    <!-- 失败 -->
    <div v-else-if="status === 'failed'"
         class="max-w-2xl mx-auto bg-[#e0e5ec] rounded-2xl p-12 text-center mt-12
        shadow-[8px_8px_16px_#b8bcc2,-8px_-8px_16px_#ffffff]">
      <div class="text-5xl mb-4">⚠️</div>
      <div class="text-base text-gray-700 mb-6">{{ errorMsg }}</div>
      <RouterLink to="/analyze"
                  class="inline-block px-6 py-3 text-sm font-medium rounded-xl
          bg-[#6d5dfc] text-white
          shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]
          hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
          transition-all duration-300">
        返回重试
      </RouterLink>
    </div>

  </div>
</template>

<script setup>
import {ref, reactive, computed, onMounted, onUnmounted, nextTick, watch} from 'vue'
import {useRoute, RouterLink} from 'vue-router'
import {Message} from '@arco-design/web-vue'
import * as echarts from 'echarts'
import api from '../api'

const route = useRoute()
const taskId = route.params.taskId

const status = ref('running')
const message = ref('')
const progress = ref(0)
const result = ref({})
const errorMsg = ref('')
const chartRef = ref(null)

const activeTab = ref('diagnosis')
const currentTemplate = ref('classic')
const downloading = ref(false)
const optimizing = ref(false)
const optimizedResumeLocal = ref(null)

const logs = ref([])
const logRef = ref(null)
const runningStage = ref('准备中')
const refineEnabled = ref(true)  // self-refine 开关由后端首帧下发

// ---- 运行计时（长 LLM 调用期间给用户「还在跑」的反馈） ----
const elapsedSec = ref(0)
let elapsedTimer = null
const elapsedText = computed(() => {
  const m = Math.floor(elapsedSec.value / 60)
  const s = elapsedSec.value % 60
  return m > 0 ? `${m} 分 ${String(s).padStart(2, '0')} 秒` : `${s} 秒`
})

function startElapsed() {
  if (elapsedTimer) return
  elapsedTimer = setInterval(() => { elapsedSec.value += 1 }, 1000)
}

function stopElapsed() {
  if (elapsedTimer) {
    clearInterval(elapsedTimer)
    elapsedTimer = null
  }
}

// ---- 动态追问（M11-B）：AI 判定信息不足时暂停，收集回答后恢复 ----
const clarifyQuestions = ref([])
const clarifyAnswers = reactive({})
const clarifySubmitting = ref(false)

async function submitClarify() {
  const answers = {}
  Object.entries(clarifyAnswers).forEach(([k, v]) => {
    if (v && String(v).trim()) answers[k] = String(v).trim()
  })
  if (!Object.keys(answers).length) {
    Message.warning('请至少回答一个问题')
    return
  }
  clarifySubmitting.value = true
  try {
    await api.submitClarify(taskId, answers)
    status.value = 'running'
    message.value = '已收到补充信息，继续诊断...'
    Message.success('已提交，继续诊断')
  } catch (e) {
    Message.error(e.response?.data?.detail || '提交失败，请重试')
  } finally {
    clarifySubmitting.value = false
  }
}

const allStages = [
  {key: '解析简历', label: '解析简历'},
  {key: '解析岗位', label: '解析岗位'},
  {key: '六维评分', label: '六维评分'},
  {key: '差距分析', label: '差距分析'},
  {key: '改写建议', label: '改写建议'},
  {key: '精修优化', label: '精修优化'},
  {key: '生成报告', label: '生成报告'},
]

const stages = computed(() =>
  refineEnabled.value ? allStages : allStages.filter(s => s.key !== '精修优化')
)

const stageOrder = ['准备中', '解析简历', '解析岗位', '六维评分', '差距分析', '改写建议', '精修优化', '生成报告', '完成']

const currentStage = computed(() => runningStage.value || '准备中')

function isStageDone(stageKey) {
  const currentIdx = stageOrder.indexOf(currentStage.value)
  const targetIdx = stageOrder.indexOf(stageKey)
  return targetIdx >= 0 && currentIdx > targetIdx
}

function isStageActive(stageKey) {
  return currentStage.value === stageKey
}

function stageStatusClass(stageKey) {
  if (isStageDone(stageKey)) {
    return 'bg-green-50 text-green-600 shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]'
  }
  if (isStageActive(stageKey)) {
    return 'bg-[#6d5dfc]/10 text-[#6d5dfc] shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]'
  }
  return 'bg-[#e0e5ec] text-gray-400 shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]'
}

watch(logs, () => {
  nextTick(() => {
    if (logRef.value) {
      logRef.value.scrollTop = logRef.value.scrollHeight
    }
  })
}, {deep: true})

const tabs = [
  {key: 'diagnosis', label: '诊断报告', icon: '📊'},
  {key: 'optimize', label: '优化简历', icon: '📝'},
  {key: 'interview', label: '面试准备', icon: '🎤'},
  {key: 'mock', label: '模拟面试', icon: '🎬'},
]

const templates = [
  {key: 'classic', label: '经典'},
  {key: 'modern', label: '现代'},
  {key: 'minimal', label: '简约'},
  {key: 'business', label: '商务'},
  {key: 'academic', label: '学术'},
  {key: 'creative', label: '创意'},
  {key: 'twocol', label: '两栏'},
  {key: 'compact', label: '紧凑'},
]

let pollTimer = null
let es = null
let chart = null

const scores = computed(() => result.value.diagnosis?.scores || {})

const optimizedResume = computed(() =>
    optimizedResumeLocal.value || result.value.diagnosis?.optimized_resume || null
)

const overallComment = computed(() => {
  const s = scores.value
  const keys = ['completeness', 'skill_match', 'quantification', 'star_structure']
  return keys.map(k => s[k]?.comment).filter(Boolean).join(' ') || '（暂无评语）'
})

const strengths = computed(() => {
  const s = scores.value
  const labels = {
    completeness: '信息完整', quantification: '量化清晰', star_structure: 'STAR 结构',
    skill_match: '技能含金量', achievement: '业绩亮点', readability: '可读性',
  }
  const list = []
  Object.entries(s).forEach(([k, v]) => {
    if (typeof v === 'object' && v.score >= 80 && labels[k]) {
      list.push(`${labels[k]}（${v.score} 分）`)
    }
  })
  return list
})

const gaps = computed(() => result.value.diagnosis?.gaps || [])
const gapSummary = computed(() => result.value.diagnosis?.gap_summary || '')
const suggestions = computed(() => result.value.diagnosis?.suggestions || [])
const overallAdvice = computed(() => result.value.diagnosis?.overall_advice || '')

function severityColor(sev) {
  if (sev === 'high') return 'text-red-500'
  if (sev === 'medium') return 'text-amber-600'
  return 'text-gray-500'
}

function handleTaskData(t) {
  status.value = t.status
  message.value = t.message
  progress.value = t.progress
  runningStage.value = t.stage || '准备中'
  if (typeof t.refine === 'boolean') refineEnabled.value = t.refine
  if (t.status === 'running' || t.status === 'pending') startElapsed()
  if (Array.isArray(t.questions) && t.questions.length) {
    clarifyQuestions.value = t.questions
  }

  if (t.logs && Array.isArray(t.logs)) {
    logs.value = t.logs
  }

  if (t.status === 'success') {
    result.value = t.result
    stopTracking()
    nextTick(() => renderChart())
  } else if (t.status === 'failed') {
    errorMsg.value = t.error || '任务失败'
    stopTracking()
  }
}

function stopTracking() {
  stopElapsed()
  if (es) {
    try { es.close() } catch (e) {}
    es = null
  }
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function fallbackToHistory() {
  try {
    const hres = await api.getHistoryDetail(taskId)
    const record = hres.data
    if (record.status === 'success' && record.result) {
      status.value = 'success'
      result.value = record.result
      await nextTick()
      renderChart()
    } else {
      status.value = 'failed'
      errorMsg.value = record.error || '任务已过期'
    }
  } catch (err) {
    status.value = 'failed'
    errorMsg.value = '任务不存在'
  }
}

async function poll() {
  try {
    const res = await api.getTaskStatus(taskId)
    handleTaskData(res.data)
  } catch (e) {
    if (e.response?.status === 404) {
      stopTracking()
      await fallbackToHistory()
    }
  }
}

function startPolling() {
  if (pollTimer) return
  poll()
  pollTimer = setInterval(poll, 2000)
}

function startTracking() {
  // SSE 优先（1s 推送，替代轮询）；连接失败/中断自动回退轮询
  try {
    es = new EventSource(`/api/v1/live/stream/${taskId}`)
  } catch (e) {
    startPolling()
    return
  }
  es.onmessage = (ev) => {
    try {
      handleTaskData(JSON.parse(ev.data))
    } catch (e) {
      console.error(e)
    }
  }
  es.addEventListener('fatal', (ev) => {
    stopTracking()
    let detail = ''
    try { detail = JSON.parse(ev.data).detail } catch (e) {}
    if (detail === '任务不存在') {
      fallbackToHistory()
    } else {
      status.value = 'failed'
      errorMsg.value = detail || '任务已断开'
    }
  })
  es.onerror = () => {
    // 正常完成后已 stopTracking，此处只会是连接中断
    stopTracking()
    startPolling()
  }
}

async function quickGenerate() {
  optimizing.value = true
  try {
    let cfg = {}
    try {
      cfg = JSON.parse(localStorage.getItem('llm_config') || '{}')
    } catch (e) {
    }
    const res = await api.quickOptimize(taskId, cfg.api_key ? cfg : null)
    optimizedResumeLocal.value = res.data.optimized_resume
    Message.success('优化完成')
  } catch (e) {
    console.error(e)
    Message.error('失败：' + (e.response?.data?.detail || e.message))
  } finally {
    optimizing.value = false
  }
}

async function downloadDocx() {
  if (!optimizedResume.value) return
  downloading.value = true
  try {
    const res = await api.exportDocx({
      optimized_resume: optimizedResume.value,
      template: currentTemplate.value,
    })
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `优化后的简历_${currentTemplate.value}.docx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    Message.success('下载成功')
  } catch (e) {
    Message.error('下载失败：' + e.message)
  } finally {
    downloading.value = false
  }
}

function renderChart() {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  const s = scores.value
  const dims = [
    {key: 'completeness', name: '信息完整'},
    {key: 'quantification', name: '量化成果'},
    {key: 'star_structure', name: 'STAR 结构'},
    {key: 'skill_match', name: '技能含金量'},
    {key: 'achievement', name: '业绩亮点'},
    {key: 'readability', name: '可读性'},
  ]
  const values = dims.map(d => s[d.key]?.score || 0)

  chart.setOption({
    radar: {
      indicator: dims.map(d => ({name: d.name, max: 100})),
      splitNumber: 5,
      axisName: {color: '#6b7280', fontSize: 12, fontWeight: 500},
      splitLine: {lineStyle: {color: '#b8bcc2'}},
      splitArea: {areaStyle: {color: ['#e0e5ec', '#e8ecf2']}},
      axisLine: {lineStyle: {color: '#b8bcc2'}},
    },
    series: [{
      type: 'radar',
      data: [{
        value: values,
        areaStyle: {color: 'rgba(109, 93, 252, 0.2)'},
        lineStyle: {color: '#6d5dfc', width: 2},
        itemStyle: {color: '#6d5dfc'},
      }],
    }],
  })
}

onMounted(() => {
  startTracking()
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  stopTracking()
  chart?.dispose()
})
</script>

<style scoped>
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in {
  animation: fadeInUp 0.3s ease-out;
}

.resume-paper {
  font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: #374151;
  line-height: 1.7;
  font-size: 13px;
}

.resume-paper .r-section {
  margin-top: 18px;
}

.resume-paper .r-line {
  margin: 3px 0;
}

.resume-paper.classic .r-name {
  text-align: center;
  font-size: 26px;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 6px;
}

.resume-paper.classic .r-contact {
  text-align: center;
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 24px;
}

.resume-paper.classic .r-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #0d9488;
  padding-bottom: 4px;
  border-bottom: 1px solid #e5e7eb;
  margin-bottom: 8px;
}

.resume-paper.modern .r-name {
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
  padding-bottom: 8px;
  border-bottom: 3px solid #14b8a6;
  margin-bottom: 6px;
}

.resume-paper.modern .r-contact {
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 24px;
}

.resume-paper.modern .r-section-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.resume-paper.modern .r-section-title::before {
  content: '';
  width: 4px;
  height: 15px;
  background: #14b8a6;
  border-radius: 2px;
}

.resume-paper.modern .r-section .r-line {
  padding-left: 12px;
}

.resume-paper.minimal .r-name {
  text-align: center;
  font-size: 24px;
  font-weight: 700;
  color: #000;
  letter-spacing: 6px;
  margin-bottom: 6px;
}

.resume-paper.minimal .r-contact {
  text-align: center;
  font-size: 11px;
  color: #999;
  margin-bottom: 28px;
}

.resume-paper.minimal .r-section-title {
  font-size: 11px;
  font-weight: 600;
  color: #666;
  letter-spacing: 3px;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.resume-paper.business .r-name {
  font-size: 26px;
  font-weight: 700;
  color: #0C294E;
  padding-bottom: 8px;
  border-bottom: 2px solid #1E40AF;
  margin-bottom: 6px;
}

.resume-paper.business .r-contact {
  font-size: 12px;
  color: #666;
  margin-bottom: 24px;
}

.resume-paper.business .r-section-title {
  font-size: 12px;
  font-weight: 700;
  color: #1E40AF;
  letter-spacing: 2px;
  text-transform: uppercase;
  padding-bottom: 4px;
  border-bottom: 1px solid #1E40AF;
  margin-bottom: 8px;
}

.resume-paper.academic {
  font-family: Georgia, 'Times New Roman', 'Songti SC', serif;
}

.resume-paper.academic .r-name {
  text-align: center;
  font-size: 22px;
  font-weight: 700;
  color: #000;
  margin-bottom: 6px;
  font-family: Georgia, 'Times New Roman', serif;
}

.resume-paper.academic .r-contact {
  text-align: center;
  font-size: 12px;
  color: #666;
  margin-bottom: 24px;
}

.resume-paper.academic .r-section-title {
  font-size: 14px;
  font-weight: 700;
  color: #444;
  margin-bottom: 8px;
  font-family: Georgia, 'Times New Roman', serif;
  border-bottom: 1px solid #999;
  padding-bottom: 3px;
}

.resume-paper.creative .r-name {
  font-size: 30px;
  font-weight: 700;
  color: #7C2D12;
  margin-bottom: 6px;
}

.resume-paper.creative .r-contact {
  font-size: 12px;
  color: #888;
  margin-bottom: 24px;
}

.resume-paper.creative .r-section-title {
  font-size: 15px;
  font-weight: 700;
  color: #C2410C;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.resume-paper.creative .r-section-title::before {
  content: '●';
  color: #C2410C;
  font-size: 10px;
}

.resume-paper.creative .r-section .r-line {
  padding-left: 16px;
}

.resume-paper.twocol .r-name {
  font-size: 24px;
  font-weight: 700;
  color: #1F2937;
  padding-bottom: 4px;
  border-bottom: 1px solid #E5E7EB;
  margin-bottom: 6px;
}

.resume-paper.twocol .r-contact {
  font-size: 12px;
  color: #888;
  margin-bottom: 20px;
}

.resume-paper.twocol .r-section-title {
  font-size: 14px;
  font-weight: 700;
  color: #0D9488;
  margin-bottom: 6px;
}

.resume-paper.compact {
  font-size: 12px;
}

.resume-paper.compact .r-name {
  text-align: center;
  font-size: 20px;
  font-weight: 700;
  color: #000;
  margin-bottom: 4px;
}

.resume-paper.compact .r-contact {
  text-align: center;
  font-size: 11px;
  color: #888;
  margin-bottom: 18px;
}

.resume-paper.compact .r-section {
  margin-top: 12px;
}

.resume-paper.compact .r-section-title {
  font-size: 12px;
  font-weight: 700;
  color: #000;
  margin-bottom: 6px;
}

.resume-paper.compact .r-line {
  margin: 2px 0;
}
</style>