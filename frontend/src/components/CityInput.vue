<template>
  <div class="relative">
    <input v-bind="$attrs" :value="modelValue" autocomplete="off"
      @input="onInput" @focus="open = true" @blur="open = false" @keydown.esc="open = false"
      class="w-full px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
        focus:border-accent placeholder:text-ink-faint transition-colors" />
    <!-- 自绘候选项：原生 datalist 在 WebView2 桌面端渲染成深色系统弹层（截断+压住下方内容），不可控 -->
    <ul v-if="open && suggestions.length"
      class="absolute left-0 top-full z-20 mt-1 max-h-44 overflow-y-auto w-full min-w-[110px]
        bg-panel border border-line rounded-lg shadow-lg py-1">
      <li v-for="c in suggestions" :key="c" @mousedown.prevent="pick(c)"
        class="px-3 py-1.5 text-xs cursor-pointer hover:bg-accent/10 transition-colors">
        {{ c }}
      </li>
    </ul>
  </div>
</template>

<script setup>
/**
 * 城市输入：常用城市自动补全 + 自由输入（不受限于候选项）。
 * attrs（placeholder/maxlength/class 等）透传到 input；下拉为组件自绘、随主题。
 */
import { ref, computed } from 'vue'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  modelValue: { type: String, default: '' },
  options: {
    type: Array,
    default: () => [
      '北京', '上海', '广州', '深圳', '天津', '重庆',
      '杭州', '成都', '武汉', '西安', '南京', '苏州', '长沙', '郑州', '合肥',
      '福州', '厦门', '济南', '青岛', '沈阳', '大连', '哈尔滨', '长春',
      '石家庄', '太原', '南昌', '南宁', '海口', '贵阳', '昆明', '兰州',
      '宁波', '无锡', '佛山', '东莞', '珠海', '烟台', '潍坊', '呼和浩特',
      '乌鲁木齐', '西宁', '银川', '拉萨', '唐山', '保定', '洛阳', '中山', '惠州',
    ],
  },
})
const emit = defineEmits(['update:modelValue'])

const open = ref(false)

const suggestions = computed(() => {
  const q = (props.modelValue || '').trim()
  const pool = q ? props.options.filter((c) => c.includes(q) && c !== q) : props.options
  return pool.slice(0, 8)
})

function onInput(e) {
  emit('update:modelValue', e.target.value)
  open.value = true
}

function pick(c) {
  emit('update:modelValue', c)
  open.value = false
}
</script>
