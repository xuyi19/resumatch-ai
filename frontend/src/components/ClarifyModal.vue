<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[100] flex items-center justify-center p-4"
      style="background: rgba(224, 229, 236, 0.85)"
      @click.self="$emit('close')">
      <div class="max-w-2xl w-full bg-[#e0e5ec] rounded-2xl
        shadow-[12px_12px_24px_#b8bcc2,-12px_-12px_24px_#ffffff]
        flex flex-col max-h-[85vh]">

        <!-- 头部 -->
        <div class="flex items-start justify-between p-6 border-b border-[#b8bcc2]/20">
          <div>
            <h3 class="text-xl font-semibold text-gray-800">生成专业简历</h3>
            <p class="text-xs text-gray-500 mt-1">
              请补充以下关键信息，以便为您量身定制简历
            </p>
          </div>
          <button @click="$emit('close')"
            class="w-9 h-9 rounded-xl bg-[#e0e5ec]
              shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
              hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
              flex items-center justify-center text-gray-500">✕</button>
        </div>

        <!-- 内容区（滚动）-->
        <div class="flex-1 overflow-y-auto p-6 space-y-6">
          <div v-for="(q, i) in questions" :key="q.id" class="space-y-3">
            <div class="flex items-start gap-3">
              <span class="w-6 h-6 rounded-lg bg-[#6d5dfc]/10 text-[#6d5dfc] text-xs font-semibold flex items-center justify-center shrink-0 mt-0.5">
                {{ i + 1 }}
              </span>
              <div class="flex-1">
                <div class="text-sm text-gray-800 leading-relaxed">
                  {{ q.question }}
                  <span v-if="!q.required" class="text-xs text-gray-400 ml-1">（选填）</span>
                </div>
                <div v-if="q.hint" class="text-xs text-gray-500 mt-1 italic">
                  如：{{ q.hint }}
                </div>
              </div>
            </div>

            <textarea v-model="answers[q.id]" :placeholder="q.placeholder || '请输入具体内容'"
              rows="3"
              class="w-full px-4 py-3 text-sm text-gray-800 placeholder-gray-400
                bg-[#e0e5ec] rounded-xl border-0 resize-none
                shadow-[inset_4px_4px_8px_#b8bcc2,inset_-4px_-4px_8px_#ffffff]
                focus:outline-none
                focus:shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]
                transition-shadow duration-300" />
          </div>
        </div>

        <!-- 底部 -->
        <div class="p-6 border-t border-[#b8bcc2]/20">
          <div class="flex items-center justify-between mb-3">
            <span class="text-xs text-gray-500">
              已填 <span class="text-[#6d5dfc] font-semibold">{{ filledCount }}</span> / {{ requiredCount }}
            </span>
            <button @click="skipAndGenerate"
              class="text-xs text-gray-400 hover:text-gray-600">
              跳过追问，直接生成
            </button>
          </div>
          <button @click="submit" :disabled="!canSubmit || generating"
            class="w-full py-3.5 text-sm font-medium rounded-xl
              bg-[#6d5dfc] text-white
              shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]
              hover:shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-all duration-300">
            {{ generating ? '生成中...' : '开始生成' }}
          </button>
        </div>

      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  questions: { type: Array, default: () => [] },
  generating: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'submit'])

const answers = ref({})

const requiredCount = computed(() =>
  props.questions.filter(q => q.required).length
)

const filledCount = computed(() =>
  props.questions.filter(q => q.required && (answers.value[q.id] || '').trim()).length
)

const canSubmit = computed(() => filledCount.value >= requiredCount.value)

function submit() {
  if (!canSubmit.value) return
  emit('submit', { ...answers.value })
}

function skipAndGenerate() {
  emit('submit', { ...answers.value })
}
</script>