/**
 * M54 组件冒烟：HeatmapChart（M53 活跃热力图，纯 DOM 渲染）
 * 断言挂载不报错 + 格子数量/色阶/title 提示/空数据隐藏
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import HeatmapChart from '../../src/components/HeatmapChart.vue'

const days = [
  { date: '2026-10-06', count: 0 },   // 周二
  { date: '2026-10-07', count: 2 },
  { date: '2026-10-08', count: 5 },   // 今天·满档
]

describe('HeatmapChart', () => {
  it('渲染 90 天子图：lead 对齐 + 每日一格 + title 提示', () => {
    // 2026-10-06 是周二：lead = 1（周一空格）
    const wrap = mount(HeatmapChart, { props: { days } })
    const cells = wrap.findAll('span[title]')
    expect(cells).toHaveLength(3)
    expect(cells[2].attributes('title')).toBe('10 月 8 日：5 次活跃')
    // 第一格是 lead 空位（无 title）
    const allSpans = wrap.findAll('.grid span')
    expect(allSpans.length).toBe(4)
    // 图例 5 档
    expect(wrap.findAll('.mt-2 span').length).toBe(7) // 少 + 5 档 + 多
  })

  it('空数组时不渲染', () => {
    const wrap = mount(HeatmapChart, { props: { days: [] } })
    expect(wrap.find('.grid').exists()).toBe(false)
  })

  it('色阶分档：0/1/2/3-4/5+ 五档', () => {
    const wrap = mount(HeatmapChart, {
      props: { days: [
        { date: '2026-10-06', count: 0 },
        { date: '2026-10-07', count: 1 },
        { date: '2026-10-08', count: 3 },
      ] },
    })
    const cells = wrap.findAll('span[title]')
    expect(cells[0].classes()).toContain('bg-inset')
    expect(cells[1].classes()).toContain('bg-accent/30')
    expect(cells[2].classes()).toContain('bg-accent/80')
  })
})
