<template>
  <div class="flex flex-col items-center justify-center text-center py-16 px-6">
    <div class="w-8 h-8 mb-4 relative">
      <div class="absolute inset-0 rounded-full border-2 border-line" />
      <div class="absolute inset-0 rounded-full border-2 border-transparent
        border-t-accent animate-spin" />
    </div>
    <div class="text-sm text-ink-sub">{{ text }}</div>
    <div v-if="hint" class="text-xs text-ink-faint mt-1.5 font-mono">{{ hint }}</div>
  </div>
</template>

<script setup>
defineProps({
  text: { type: String, default: '加载中…' },
  hint: { type: String, default: '' },
})
</script>
