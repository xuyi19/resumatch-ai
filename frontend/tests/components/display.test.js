/**
 * M54 组件冒烟：EmptyState / LoadingBlock（纯展示组件，挂载 + 关键文案断言）
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EmptyState from '../../src/components/EmptyState.vue'
import LoadingBlock from '../../src/components/LoadingBlock.vue'

describe('EmptyState', () => {
  it('默认标题 + 无 desc 渲染占位', () => {
    const wrap = mount(EmptyState)
    expect(wrap.text()).toContain('暂无数据')
  })

  it('自定义标题/描述/插槽内容', () => {
    const wrap = mount(EmptyState, {
      props: { title: '还没有岗位', desc: '先入库一个岗位试试' },
      slots: { default: '<button>＋ 入库</button>' },
    })
    expect(wrap.text()).toContain('还没有岗位')
    expect(wrap.text()).toContain('先入库一个岗位试试')
    expect(wrap.find('button').text()).toBe('＋ 入库')
  })

  it('type=search 切换图标路径', () => {
    const wrap = mount(EmptyState, { props: { type: 'search' } })
    expect(wrap.html()).toContain('M21 21l-4.3-4.3')
  })
})

describe('LoadingBlock', () => {
  it('默认文案渲染', () => {
    const wrap = mount(LoadingBlock)
    expect(wrap.text()).toContain('加载中…')
  })

  it('自定义文案 + hint', () => {
    const wrap = mount(LoadingBlock, { props: { text: 'AI 思考中', hint: '约 10s' } })
    expect(wrap.text()).toContain('AI 思考中')
    expect(wrap.text()).toContain('约 10s')
  })
})
