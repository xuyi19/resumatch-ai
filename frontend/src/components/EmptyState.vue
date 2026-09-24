<template>
  <div class="flex flex-col items-center justify-center text-center py-16 px-6">
    <div class="w-12 h-12 rounded-lg bg-inset text-ink-faint flex items-center justify-center mb-4">
      <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" v-html="icon" />
    </div>
    <div class="text-sm font-medium text-ink mb-1.5">{{ title }}</div>
    <div v-if="desc" class="text-xs text-ink-faint leading-relaxed max-w-xs mb-5">{{ desc }}</div>
    <div v-else class="mb-5" />
    <slot />
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, default: '暂无数据' },
  desc: { type: String, default: '' },
  type: { type: String, default: 'empty' }, // empty | error | search
})

const ICONS = {
  empty:
    '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2"/><path d="M3 12h18"/>',
  error:
    '<circle cx="12" cy="12" r="9"/><path d="M12 8v4.5"/><path d="M12 16h.01"/>',
  search:
    '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
}

const icon = computed(() => ICONS[props.type] || ICONS.empty)
</script>
