/**
 * F3 简历快速体检：纯前端规则检查（不消耗 LLM），编辑器实时反馈。
 * 返回 [{level: 'bad'|'warn', msg}]，bad=硬伤（缺失关键项），warn=建议优化。
 */
export function checkResume(d = {}) {
  const issues = []

  // --- 硬伤（bad）---
  if (!d.name || !d.name.trim()) issues.push({ level: 'bad', msg: '缺少姓名' })
  if (!d.phone && !d.email) issues.push({ level: 'bad', msg: '缺少联系方式（电话/邮箱至少一项）' })
  if (!d.education || !d.education.length) issues.push({ level: 'bad', msg: '缺少教育背景' })
  if (!d.experience?.length && !d.projects?.length) {
    issues.push({ level: 'bad', msg: '缺少工作经历与项目经历（至少一项）' })
  }
  if (!d.skills || d.skills.length < 3) {
    issues.push({ level: 'warn', msg: '技能少于 3 项，建议补全技能清单' })
  }

  // --- 弱化表达（warn）---
  const WEAK_VERBS = /^(负责|参与|协助|帮助|了解|熟悉一下)/
  const descSources = [
    ...(d.experience || []).map((e) => e.desc || ''),
    ...(d.projects || []).map((p) => p.desc || ''),
  ].filter(Boolean)
  const weakCount = descSources.filter((t) => WEAK_VERBS.test(t.trim())).length
  if (weakCount > 0) {
    issues.push({
      level: 'warn',
      msg: `${weakCount} 段描述以「负责/参与」等弱动词开头，建议改为「主导/设计/实现」+ 成果`,
    })
  }

  // --- 缺量化数字（warn）---
  const hasNumber = (t) => /\d/.test(t)
  const noQuant = descSources.filter((t) => !hasNumber(t)).length
  if (descSources.length && noQuant === descSources.length) {
    issues.push({
      level: 'warn',
      msg: '所有经历/项目描述都没有量化数字，建议补充规模、百分比或性能数据',
    })
  }

  // --- 描述过短（warn）---
  const shortDesc = descSources.filter((t) => t.trim().length < 40).length
  if (shortDesc > 0) {
    issues.push({ level: 'warn', msg: `${shortDesc} 段描述过短（少于 40 字），建议展开 STAR 结构` })
  }

  if (!d.summary || d.summary.trim().length < 30) {
    issues.push({ level: 'warn', msg: '个人总结缺失或过短，建议 2-3 句概括核心竞争力' })
  }

  return issues
}
