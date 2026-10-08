/**
 * M54 组件冒烟：工具函数（job_links 深链生成的镜像逻辑不可测——后端纯函数已有 pytest；
 * 此处覆盖前端侧最核心的纯逻辑：投递状态机元数据 / 渠道标签映射）
 * 直接从 JobLibraryView 源码 import 不现实（依赖 api/router），改为对关键映射表
 * 做单一事实源校验：从源码文本断言映射存在，防止手滑删改（轻量护栏）。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const SRC = resolve(__dirname, '../../src/views/JobLibraryView.vue')
const src = readFileSync(SRC, 'utf-8')

describe('JobLibraryView 关键映射（源码护栏）', () => {
  it('PLATFORM_LABELS 覆盖四平台', () => {
    expect(src).toContain("boss: 'BOSS 直聘'")
    expect(src).toContain("zhilian: '智联招聘'")
    expect(src).toContain("liepin: '猎聘'")
    expect(src).toContain("nowcoder: '牛客'")
  })

  it('CHANNEL_OPTIONS 覆盖六渠道', () => {
    for (const ch of ['boss', 'zhilian', 'liepin', 'nowcoder', 'email', 'other']) {
      expect(src).toContain(`value: '${ch}'`)
    }
  })

  it('STATUS 五档齐全', () => {
    for (const st of ['wish', 'applied', 'interviewing', 'offer', 'closed']) {
      expect(src).toContain(st)
    }
  })
})
