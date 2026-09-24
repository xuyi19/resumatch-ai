/**
 * M40 岗位收藏夹：localStorage 持久化（key: resumatch_job_favorites）
 * 收藏对象保留开面试/诊断所需的完整字段（jd_text 等），上限 50 条防膨胀。
 */
const KEY = 'resumatch_job_favorites'
const MAX = 50

export function loadFavorites() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]')
  } catch {
    return []
  }
}

export function isFavorite(jobId, list = loadFavorites()) {
  return list.some(j => j.id === jobId)
}

/** 切换收藏；返回 true 表示本次为收藏、false 为取消 */
export function toggleFavorite(job) {
  const list = loadFavorites()
  const idx = list.findIndex(j => j.id === job.id)
  if (idx >= 0) {
    list.splice(idx, 1)
  } else {
    list.unshift({
      id: job.id, title: job.title, company: job.company, city: job.city,
      salary: job.salary, jd_text: job.jd_text, url: job.url, source: job.source,
      saved_at: Date.now(),
    })
    if (list.length > MAX) list.length = MAX
  }
  localStorage.setItem(KEY, JSON.stringify(list))
  return idx < 0
}
