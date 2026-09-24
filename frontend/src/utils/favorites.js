/**
 * M40 岗位收藏夹（localStorage，key: resumatch_job_favorites）
 * M51 起收藏并入岗位库 DB：本文件仅保留迁移所需的读取与清理。
 */
const KEY = 'resumatch_job_favorites'

export function loadFavorites() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]')
  } catch {
    return []
  }
}

export function clearFavorites() {
  try {
    localStorage.removeItem(KEY)
  } catch {}
}
