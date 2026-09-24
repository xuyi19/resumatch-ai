/**
 * M44 行级文本 diff（LCS 最长公共子序列）。
 *
 * diffLines(oldText, newText) 返回块序列：
 *   { type: 'same', lines: [...] }          两版共有
 *   { type: 'del',  lines: [...] }          仅旧版有（被删除）
 *   { type: 'add',  lines: [...] }          仅新版有（新增）
 *
 * 简历文本行数在几百级，O(n·m) DP 完全够用；纯函数无依赖。
 */
export function diffLines(oldText, newText) {
  const a = String(oldText ?? '').split('\n')
  const b = String(newText ?? '').split('\n')
  const n = a.length
  const m = b.length

  // dp[i][j] = a[i:] 与 b[j:] 的 LCS 长度（滚动行省内存）
  const dp = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1))
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }

  // 回溯产出操作序列，再把连续同类型合并为块
  const blocks = []
  const push = (type, line) => {
    const last = blocks[blocks.length - 1]
    if (last && last.type === type) last.lines.push(line)
    else blocks.push({ type, lines: [line] })
  }
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      push('same', a[i])
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      push('del', a[i])
      i++
    } else {
      push('add', b[j])
      j++
    }
  }
  while (i < n) push('del', a[i++])
  while (j < m) push('add', b[j++])
  return blocks
}

/**
 * 把块序列展开为双栏对齐行（配对 del/add，多出的一侧补空行）。
 * 返回 [{ left: {type, text} | null, right: {type, text} | null }]
 * type: same | del | add | empty
 */
export function toPairedRows(blocks) {
  const rows = []
  let k = 0
  while (k < blocks.length) {
    const cur = blocks[k]
    if (cur.type === 'same') {
      cur.lines.forEach((t) => rows.push({ left: { type: 'same', text: t }, right: { type: 'same', text: t } }))
      k++
      continue
    }
    // del 块与紧随的 add 块配对
    const del = cur.type === 'del' ? cur : null
    const add = del ? blocks[k + 1]?.type === 'add' ? blocks[k + 1] : null : cur.type === 'add' ? cur : null
    if (del && add) {
      const len = Math.max(del.lines.length, add.lines.length)
      for (let x = 0; x < len; x++) {
        rows.push({
          left: x < del.lines.length ? { type: 'del', text: del.lines[x] } : { type: 'empty', text: '' },
          right: x < add.lines.length ? { type: 'add', text: add.lines[x] } : { type: 'empty', text: '' },
        })
      }
      k += 2
    } else if (del || add) {
      const blk = del || add
      const type = del ? 'del' : 'add'
      blk.lines.forEach((t) =>
        rows.push(
          del
            ? { left: { type, text: t }, right: { type: 'empty', text: '' } }
            : { left: { type: 'empty', text: '' }, right: { type, text: t } },
        ),
      )
      k++
    } else {
      k++
    }
  }
  return rows
}

/** diff 统计：新增/删除行数 */
export function diffStats(blocks) {
  let added = 0
  let removed = 0
  for (const b of blocks) {
    if (b.type === 'add') added += b.lines.length
    if (b.type === 'del') removed += b.lines.length
  }
  return { added, removed }
}
