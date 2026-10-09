/**
 * 优化⑪ 组件冒烟：InterviewCalendar（面试日程月历，纯 DOM 渲染）
 * 断言网格渲染 / 今天高亮 / 日程条分桶与 +N 折叠 / 跨月导航 / 点击 emit open
 * 日期全部相对「真实今天」构造，测试不随日期漂移。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import InterviewCalendar from '../../src/components/InterviewCalendar.vue'

const now = new Date()
const pad = (n) => String(n).padStart(2, '0')
// 本地 naive ISO（同后端 isoformat 口径），分钟精度
const isoOf = (d, hm = '14:30') =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${hm}`
const dayShift = (n) => new Date(now.getFullYear(), now.getMonth(), now.getDate() + n)

// 今日 / 明天 / 昨天 / 32 天后（必落在别的月份）
const evToday = { id: 1, title: '前端岗', company: '字节', next_interview_at: isoOf(dayShift(0)), days_left: 0, status: 'interviewing' }
const evTomorrow = { id: 2, title: '后端岗', company: '', next_interview_at: isoOf(dayShift(1), '10:00'), days_left: 1, status: 'applied' }
const evPast = { id: 3, title: '测试岗', company: '腾讯', next_interview_at: isoOf(dayShift(-2)), days_left: -2, status: 'interviewing' }
const evNext = { id: 4, title: '算法岗', company: '阿里', next_interview_at: isoOf(dayShift(32)), days_left: 32, status: 'applied' }

/** 点 ›/‹ 直到视图月份与目标一致（组件限 ±12 月，2 步内必达） */
async function goto(wrap, target) {
  const want = target.getFullYear() * 12 + target.getMonth()
  for (let i = 0; i < 3; i++) {
    const have = viewYear(wrap) * 12 + (viewMonth(wrap) - 1)
    if (have === want) return
    await wrap.find(want > have ? 'button[title="下一月"]' : 'button[title="上一月"]').trigger('click')
  }
}
const viewYear = (wrap) => Number(wrap.text().match(/(\d+) 年/)[1])
const viewMonth = (wrap) => Number(wrap.text().match(/年 (\d+) 月/)[1])

describe('InterviewCalendar', () => {
  it('当月视图：今天高亮 + 日程条按天分桶 + 点击 emit open', async () => {
    const wrap = mount(InterviewCalendar, { props: { interviews: [evToday, evTomorrow] } })
    // 月份导航按今天初始化
    expect(wrap.text()).toContain(`${now.getFullYear()} 年 ${now.getMonth() + 1} 月`)
    // 星期表头 7 格 + 当月日格 ≥ 28
    expect(wrap.text()).toContain('一二三四五六日')
    expect(wrap.findAll('.cal-cell').length).toBeGreaterThanOrEqual(28)
    // 今天格有 cal-today；日程条落在对应日
    expect(wrap.find('.cal-today').exists()).toBe(true)
    const chips = wrap.findAll('.cal-chip')
    expect(chips.some((c) => c.text().includes('14:30 字节'))).toBe(true)
    // 当月视图不显示「回到今天」
    expect(wrap.text()).not.toContain('回到今天')
    // 点击日程条 emit open(岗位 id)
    chips[0].trigger('click')
    expect(wrap.emitted('open')).toBeTruthy()
    expect(wrap.emitted('open')[0]).toEqual([evToday.id])
    // 明天的日程：月末场景会落到下月，翻到目标月断言（无公司回落标题展示）
    await goto(wrap, dayShift(1))
    expect(wrap.findAll('.cal-chip').some((c) => c.text().includes('10:00 后端岗'))).toBe(true)
  })

  it('跨月导航：32 天后的日程要翻月才可见；已过期日程条 warn 配色', async () => {
    const wrap = mount(InterviewCalendar, { props: { interviews: [evPast, evNext] } })
    // 当月看不到 32 天后的日程
    expect(wrap.findAll('.cal-chip').some((c) => c.text().includes('阿里'))).toBe(false)
    // 翻到目标月出现
    await goto(wrap, dayShift(32))
    const chip = wrap.findAll('.cal-chip').find((c) => c.text().includes('阿里'))
    expect(chip).toBeTruthy()
    // 回到今天按钮出现且有效
    await wrap.find('button:not([title])').trigger('click') // 「回到今天」是无 title 的唯一按钮
    expect(wrap.text()).toContain(`${now.getFullYear()} 年 ${now.getMonth() + 1} 月`)
    // 翻到昨天所在月：过期日程 warn 配色
    await goto(wrap, dayShift(-2))
    const past = wrap.findAll('.cal-chip').find((c) => c.text().includes('腾讯'))
    expect(past.classes()).toContain('bg-warn/10')
  })

  it('同日 3 场折叠：露 2 条 + 「+1」', () => {
    const three = [
      evToday,
      { ...evTomorrow, id: 11, title: '岗A', next_interview_at: isoOf(dayShift(0), '09:00') },
      { ...evTomorrow, id: 12, title: '岗B', next_interview_at: isoOf(dayShift(0), '16:00') },
    ]
    const wrap = mount(InterviewCalendar, { props: { interviews: three } })
    expect(wrap.findAll('.cal-chip')).toHaveLength(2)
    expect(wrap.text()).toContain('+1')
  })

  it('空数组：网格照常渲染但无日程条', () => {
    const wrap = mount(InterviewCalendar, { props: { interviews: [] } })
    expect(wrap.findAll('.cal-cell').length).toBeGreaterThanOrEqual(28)
    expect(wrap.findAll('.cal-chip')).toHaveLength(0)
  })
})
