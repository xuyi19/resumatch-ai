/**
 * M54 E2E 冒烟：vite dev 起前端（无后端），断言核心路由页壳渲染。
 *
 * 两个环境事实（勿删预置逻辑）：
 * 1. 无后端时 /meta 请求失败 → useAppMode 默认按桌面形态跑，App.vue 的
 *    「启动直进工作台」会在 boot 早期（懒加载路由 chunk 尚未 resolve、
 *    route.path 仍是 '/' 时）replace('/app/analyze')，抢断任何 hash 直达 ——
 *    这里拦截 /meta 返回 app_mode='web' 釜底抽薪（web 态永不直跳）；
 * 2. 未配 Key 时全局弹 Key 引导层、总览弹 onboarding —— 预置
 *    llm_config / onboarding_done 抹平弹层。
 */
import { test, expect } from '@playwright/test'

async function open(page, path) {
  await page.route('**/api/v1/meta', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ app_mode: 'web', version: '0.0.0-e2e' }),
    }),
  )
  await page.addInitScript((p) => {
    localStorage.setItem('llm_config', JSON.stringify({ api_key: 'sk-e2e-mock' }))
    try { localStorage.setItem('onboarding_done', '1') } catch (e) {}
    location.hash = p
  }, path)
  await page.goto('/')
}

test('诊断页壳渲染', async ({ page }) => {
  await open(page, '#/app/analyze')
  await expect(page.locator('h1')).toContainText('发起诊断')
})

test('更新日志页渲染', async ({ page }) => {
  await open(page, '#/changelog')
  await expect(page.locator('h1')).toContainText('更新日志')
})

test('使用说明页渲染', async ({ page }) => {
  await open(page, '#/guide')
  await expect(page.locator('h1')).toContainText('使用说明')
})

test('两次直达路由各自渲染（SPA 可达性）', async ({ page }) => {
  await open(page, '#/guide')
  await expect(page.locator('h1')).toContainText('使用说明')
  await open(page, '#/changelog')
  await expect(page.locator('h1')).toContainText('更新日志')
})
