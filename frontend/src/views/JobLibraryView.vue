<template>
  <div class="max-w-6xl mx-auto px-6 md:px-10 py-8 md:py-10">

    <!-- 页头（全站统一规范：渐变标题 + 短横线） -->
    <div class="flex items-end justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold tracking-tight">
          <span class="bg-gradient-to-r from-ink to-accent bg-clip-text text-transparent">岗位库</span>
        </h1>
        <div class="h-0.5 w-14 rounded-full bg-gradient-to-r from-accent to-accent-hover/0 mt-1.5"></div>
        <p class="text-xs text-ink-faint mt-1.5">
          统一管理心仪岗位 · 粘贴 JD 建档 · 一键与简历批量匹配
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button @click="importFromClipboard()"
          class="px-4 py-2 text-xs font-medium rounded-lg border border-accent/50 text-accent
            hover:bg-accent/10 active:scale-[0.98] transition-all">
          📋 剪贴板导入
        </button>
        <button @click="openImport()"
          class="px-4 py-2 text-xs font-medium rounded-lg border border-accent/50 text-accent
            hover:bg-accent/10 active:scale-[0.98] transition-all">
          ⇪ 批量导入
        </button>
        <button @click="toggleForm()"
          class="px-4 py-2 text-xs font-medium rounded-lg bg-accent text-white
            hover:bg-accent-hover active:scale-[0.98] transition-all">
          {{ formOpen ? '收起' : '＋ 添加岗位' }}
        </button>
      </div>
    </div>

    <!-- 批量导入弹窗（回炉：原页顶大块与编辑表单同病，改居中 Modal） -->
    <Teleport to="body">
      <div v-if="importOpen" @click.self="closeImport"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/40">
        <div class="bg-panel border-2 border-ink/80 shadow-[3px_3px_0_0] shadow-ink/20 rounded-2xl w-full max-w-2xl max-h-[88vh]
          overflow-y-auto p-5 md:p-6">
          <div class="flex items-center justify-between gap-3 mb-3">
            <div class="text-sm font-semibold">⇪ 批量导入岗位</div>
            <button @click="closeImport"
              class="text-lg leading-none text-ink-sub hover:text-ink shrink-0">×</button>
          </div>
          <p class="text-xs text-ink-faint mb-3">
            粘贴一个或多个岗位的混排文本（招聘网站复制的 JD、岗位列表等），AI 自动提取岗位信息，确认后入库。
            不同岗位之间建议用空行分隔，解析更准。
          </p>
          <!-- M70-A 剪贴板自动读取失败时的手动粘贴引导 -->
          <div v-if="clipboardHint" class="mb-3 px-4 py-3 rounded-xl text-xs bg-warn/10 border border-warn/40 text-warn">
            无法自动读取剪贴板，请 Ctrl+V 粘贴到下方输入框
          </div>
          <textarea v-model="rawImportText" rows="8" maxlength="60000"
            placeholder="例如从 BOSS 直聘批量复制的多个岗位描述，或各处收集的 JD 文本……"
            class="w-full px-3.5 py-3 text-sm bg-inset rounded-lg border border-line resize-y
              focus:outline-none focus:border-accent placeholder:text-ink-faint transition-colors"></textarea>
          <div class="flex items-center gap-3 mt-3">
            <button @click="parseBatch" :disabled="parsing || rawImportText.trim().length < 30"
              class="px-5 py-2 text-xs font-medium rounded-lg bg-accent text-white
                hover:bg-accent-hover active:scale-[0.98] transition-all disabled:opacity-40">
              {{ parsing ? 'AI 解析中…' : parsed.length ? '重新解析' : 'AI 解析预览' }}
            </button>
            <button @click="closeImport"
              class="px-4 py-2 text-xs text-ink-sub hover:text-ink transition-colors">关闭</button>
          </div>

          <div v-if="parseDegraded" class="mt-3 px-4 py-3 rounded-xl text-xs bg-warn/10 border border-warn/40 text-warn">
            {{ parseDegradedReason }}
          </div>

          <!-- 解析预览（勾选） -->
          <div v-if="parsed.length" class="mt-4">
            <div class="flex items-center justify-between mb-2">
              <span class="text-xs text-ink-sub">解析出 {{ parsed.length }} 个岗位 · 已全选，可取消勾选</span>
              <button @click="toggleSelectAll"
                class="text-xs text-accent hover:underline">{{ allSelected ? '全不选' : '全选' }}</button>
            </div>
            <div class="space-y-2 max-h-80 overflow-y-auto pr-1">
              <label v-for="(j, i) in parsed" :key="i"
                class="flex items-start gap-2.5 px-3 py-2.5 rounded-lg bg-inset cursor-pointer
                  hover:bg-accent/5 transition-colors"
                :class="!j._sel && 'opacity-50'">
                <input type="checkbox" v-model="j._sel" class="mt-0.5 w-4 h-4 accent-accent shrink-0" />
                <div class="min-w-0">
                  <div class="text-xs font-medium truncate">
                    {{ j.title || '（无岗位名）' }}
                    <span v-if="j.company" class="font-normal text-ink-faint ml-1.5">{{ j.company }}</span>
                    <span v-if="j.city || j.salary" class="font-normal text-ink-faint ml-1.5">{{ [j.city, j.salary].filter(Boolean).join(' · ') }}</span>
                    <a v-if="j.url" :href="j.url" target="_blank" rel="noopener"
                      class="font-normal text-accent ml-1.5 hover:underline" @click.stop>🔗 原链</a>
                  </div>
                  <div class="text-[11px] text-ink-faint mt-0.5 line-clamp-2 whitespace-pre-line">{{ j.jd || '（无 JD）' }}</div>
                </div>
              </label>
            </div>
            <div class="flex items-center gap-3 mt-4">
              <button @click="importSelected" :disabled="importing || !selectedCount"
                class="px-5 py-2 text-xs font-medium rounded-lg bg-accent text-white
                  hover:bg-accent-hover active:scale-[0.98] transition-all disabled:opacity-40">
                {{ importing ? '导入中…' : `导入选中（${selectedCount}）· 自动跳过重复` }}
              </button>
            </div>
          </div>

          <!-- M70-B 采集书签（bookmarklet）：拖到书签栏，岗位页一键复制文本 -->
          <details class="mt-4 border-t border-line/60 pt-3">
            <summary class="text-xs text-ink-faint cursor-pointer hover:text-ink-sub select-none">
              🚀 安装采集书签（进阶）
            </summary>
            <div class="mt-2.5 text-xs text-ink-faint leading-relaxed">
              <p>
                从浏览器书签栏一键采集当前岗位页文本：在招聘网站的岗位详情页点击该书签，页面文本会自动复制，
                回知岗点「📋 剪贴板导入」即可完成建档。
              </p>
              <!-- javascript: 书签链接：拖拽到书签栏安装；click.prevent 防止误点执行 -->
              <a :href="bookmarkletHref" @click.prevent draggable="true"
                class="inline-block mt-2 px-3.5 py-1.5 text-xs font-medium rounded-lg border border-accent/50
                  text-accent hover:bg-accent/10 transition-colors cursor-grab active:cursor-grabbing select-none">
                ⇪ 拖我到浏览器书签栏
              </a>
            </div>
          </details>
        </div>
      </div>
    </Teleport>

    <!-- 添加 / 编辑弹窗（M56 后回炉：原表单块撑满页顶难看难用，改居中 Modal） -->
    <Teleport to="body">
      <div v-if="formOpen" @click.self="closeForm"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/40">
        <div class="bg-panel border-2 border-ink/80 shadow-[3px_3px_0_0] shadow-ink/20 rounded-2xl w-full max-w-2xl max-h-[88vh]
          overflow-y-auto p-5 md:p-6">
          <div class="flex items-center justify-between gap-3 mb-4">
            <div class="text-sm font-semibold">
              {{ editingId != null ? '✏️ 编辑岗位' : '＋ 添加岗位' }}
              <span class="ml-2 text-xs font-normal text-ink-faint">带 * 必填，其余可留空</span>
            </div>
            <button @click="closeForm"
              class="text-lg leading-none text-ink-sub hover:text-ink shrink-0">×</button>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
            <input v-model="form.title" maxlength="80" placeholder="岗位名 *"
              class="px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
                focus:border-accent transition-colors" />
            <input v-model="form.company" maxlength="60" placeholder="公司（可留空）"
              class="px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
                focus:border-accent transition-colors" />
            <CityInput v-model="form.city" maxlength="20" placeholder="城市" />
            <input v-model="form.salary" maxlength="40" placeholder="薪资（如 25-40K）"
              class="px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
                focus:border-accent transition-colors" />
          </div>
          <textarea v-model="form.jd" rows="12" maxlength="20000"
            placeholder="粘贴岗位 JD 全文（可从 BOSS / 智联 / 拉勾等平台复制岗位描述）&#10;支持多行输入，换行会原样保留并在岗位卡上显示&#10;JD 越完整，匹配推荐与面试出题越准"
            class="w-full px-3.5 py-3 text-sm bg-inset rounded-lg border border-line resize-y leading-relaxed
              focus:outline-none focus:border-accent placeholder:text-ink-faint transition-colors"></textarea>
          <!-- M69 岗位链接快存 -->
          <div class="flex items-center gap-2 mt-2">
            <span class="text-xs text-ink-faint shrink-0">岗位链接</span>
            <input v-model="form.url" maxlength="300" placeholder="岗位原链接（BOSS/智联/猎聘/牛客等，可留空）"
              class="flex-1 min-w-0 px-3 py-2 text-xs bg-inset rounded-lg border border-line
                focus:outline-none focus:border-accent placeholder:text-ink-faint transition-colors" />
          </div>
          <!-- M60 面试日程（写入工作台「求职跟进」提醒） -->
          <div class="flex items-center gap-2 mt-2">
            <span class="text-xs text-ink-faint shrink-0">面试日程</span>
            <input v-model="form.next_interview_at" type="datetime-local"
              class="flex-1 min-w-0 px-3 py-2 text-xs bg-inset rounded-lg border border-line
                focus:outline-none focus:border-accent transition-colors" />
            <button v-if="form.next_interview_at" @click="form.next_interview_at = ''"
              class="text-xs text-ink-faint hover:text-bad shrink-0 transition-colors">清除</button>
          </div>
          <div class="flex items-center gap-3 mt-3">
            <button @click="saveForm" :disabled="formSaving"
              class="px-5 py-2 text-xs font-medium rounded-lg bg-accent text-white
                hover:bg-accent-hover active:scale-[0.98] transition-all disabled:opacity-50">
              {{ formSaving ? '保存中…' : editingId != null ? '保存修改' : '保存（可连续录入）' }}
            </button>
            <button @click="closeForm"
              class="px-4 py-2 text-xs text-ink-sub hover:text-ink transition-colors">取消</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 匹配操作条 -->
    <div v-if="jobs.length" class="bg-panel rounded-2xl px-5 py-4 mb-5
      flex flex-wrap items-center gap-3">
      <span class="text-xs text-ink-sub shrink-0">与简历匹配：</span>
      <select v-model="selectedResumeId"
        class="px-3 py-2 text-sm bg-inset rounded-lg border border-line focus:outline-none
          focus:border-accent transition-colors min-w-0 max-w-[280px]">
        <option value="">选择简历…</option>
        <option v-for="r in resumes" :key="r.id" :value="r.id">
          {{ r.filename }}
        </option>
      </select>
      <button @click="runMatch" :disabled="matching || !selectedResumeId"
        class="px-4 py-2 text-xs font-medium rounded-lg border border-accent text-accent
          hover:bg-accent/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
        {{ matching ? 'AI 匹配中…' : matchDone ? '重新匹配' : '开始匹配' }}
      </button>
      <button @click="clearMatch"
        class="px-3 py-2 text-xs text-ink-faint hover:text-ink transition-colors">清除结果</button>
      <span class="w-px h-4 bg-line shrink-0 mx-1" />
      <CityInput v-model="generateCity" maxlength="20" placeholder="期望城市（可选）"
        class="w-40 shrink-0" />
      <button @click="runGenerate" :disabled="generating || !selectedResumeId"
        :title="selectedResumeId ? 'AI 根据选中简历生成适合的岗位并入库（不编造公司，投递时再补充）' : '先选择一份简历'"
        class="px-4 py-2 text-xs font-medium rounded-lg border border-accent/50 text-accent
          hover:bg-accent/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
        {{ generating ? 'AI 生成中…' : '✨ AI 生成岗位入库' }}
      </button>
      <span v-if="!matchDone && !matching" class="text-[11px] text-ink-faint ml-auto hidden md:block">
        {{ hasFilters
          ? `对筛选出的 ${filteredJobs.length}/${jobs.length} 个岗位打匹配分（0-100）`
          : `对全部 ${jobs.length} 个岗位打匹配分（0-100）并给推荐理由` }}
      </span>
    </div>

    <!-- 搜索与筛选栏 -->
    <div v-if="jobs.length" class="bg-panel rounded-2xl px-5 py-3 mb-5 flex flex-wrap items-center gap-2.5">
      <div class="relative flex-1 min-w-[190px]">
        <svg class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
        </svg>
        <input v-model="keyword" type="text" placeholder="搜索岗位名 / 公司 / 城市…"
          class="w-full pl-9 pr-3 py-2 text-sm bg-inset rounded-lg border border-line
            focus:outline-none focus:border-accent placeholder:text-ink-faint transition-colors" />
      </div>
      <select v-model="sourceFilter"
        class="px-3 py-2 text-xs bg-inset rounded-lg border border-line text-ink-sub
          focus:outline-none focus:border-accent transition-colors">
        <option value="">全部来源</option>
        <option value="manual">手动添加</option>
        <option value="ai_gen">AI 生成</option>
        <option value="ai">面板入库</option>
        <option value="favorite">收藏迁移</option>
        <option value="sample">示例岗位</option>
      </select>
      <select v-if="cityOptions.length" v-model="cityFilter"
        class="px-3 py-2 text-xs bg-inset rounded-lg border border-line text-ink-sub
          focus:outline-none focus:border-accent transition-colors max-w-[140px]">
        <option value="">全部城市</option>
        <option v-for="c in cityOptions" :key="c" :value="c">{{ c }}</option>
      </select>
      <select v-model="statusFilter"
        class="px-3 py-2 text-xs bg-inset rounded-lg border border-line text-ink-sub
          focus:outline-none focus:border-accent transition-colors">
        <option value="">全部状态</option>
        <option v-for="(s, key) in STATUS" :key="key" :value="key">{{ s.label }}</option>
      </select>
      <button v-if="hasFilters" @click="clearFilters"
        class="px-3 py-2 text-xs text-ink-faint hover:text-ink transition-colors">清除筛选</button>
      <span class="text-[11px] font-mono text-ink-faint ml-auto shrink-0">
        {{ filteredJobs.length }}/{{ jobs.length }}
      </span>
      <span class="w-px h-4 bg-line shrink-0" />
      <button @click="toggleSelMode" :title="selMode ? '退出管理模式' : '进入管理模式，勾选岗位批量删除'"
        class="px-3 py-2 text-xs font-medium rounded-lg border transition-colors shrink-0"
        :class="selMode ? 'bg-accent text-white border-accent' : 'border-line text-ink-sub hover:border-accent/60 hover:text-accent'">
        {{ selMode ? '✓ 完成' : '☐ 批量管理' }}
      </button>
      <button v-if="selMode" @click="toggleSelectAllCards"
        class="px-3 py-2 text-xs text-ink-sub hover:text-ink transition-colors">
        {{ allCardsSelected ? '全不选' : '全选' }}
      </button>
    </div>

    <!-- 管理模式浮动操作条 -->
    <Teleport to="body">
      <Transition enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 translate-y-4" leave-active-class="transition duration-150 ease-in"
        leave-to-class="opacity-0 translate-y-4">
        <div v-if="selMode && selCount"
          class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-4
            bg-float rounded-xl px-5 py-3 border border-line-strong shadow-lg">
          <span class="text-sm text-ink-sub">已选 <b class="text-ink">{{ selCount }}</b> 个岗位</span>
          <span class="w-px h-5 bg-line" />
          <!-- M49 批量设置投递状态 -->
          <select @change="batchSetStatus($event.target.value); $event.target.value = ''"
            class="px-3 py-2 text-xs bg-inset rounded-lg border border-line text-ink-sub
              focus:outline-none focus:border-accent transition-colors cursor-pointer">
            <option value="" disabled selected>设为状态…</option>
            <option v-for="(s, key) in STATUS" :key="key" :value="key">{{ s.label }}</option>
          </select>
          <span class="w-px h-5 bg-line" />
          <button @click="batchRemove" :disabled="batchRemoving"
            class="px-4 py-2 text-xs font-medium rounded-lg bg-bad text-white
              hover:opacity-90 active:scale-[0.98] transition-all disabled:opacity-40">
            {{ batchRemoving ? '删除中…' : '🗑 批量删除' }}
          </button>
          <button @click="toggleSelMode"
            class="px-3 py-2 text-xs text-ink-sub hover:text-ink transition-colors">取消</button>
        </div>
      </Transition>
    </Teleport>

    <!-- M56 投递弹层：平台深链 + AI 材料包 + 标记已投递 -->
    <Teleport to="body">
      <div v-if="applyJob" @click.self="closeApply"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/40">
        <div class="bg-panel border-2 border-ink/80 shadow-[3px_3px_0_0] shadow-ink/20 rounded-2xl w-full max-w-xl max-h-[88vh] overflow-y-auto
          p-5 md:p-6">
          <div class="flex items-start justify-between gap-3 mb-4">
            <div class="min-w-0">
              <div class="text-sm font-semibold truncate">🚀 投递「{{ applyJob.title }}」</div>
              <div class="text-xs text-ink-faint mt-0.5 truncate">
                {{ applyJob.company || '公司待定' }}<span v-if="applyJob.city"> · {{ applyJob.city }}</span>
              </div>
            </div>
            <button @click="closeApply" class="text-lg leading-none text-ink-sub hover:text-ink shrink-0">×</button>
          </div>

          <!-- 平台深链 -->
          <div class="text-xs font-semibold mb-2">直达平台搜索页</div>
          <div v-if="linksLoading" class="text-xs text-ink-faint mb-4">生成深链中…</div>
          <template v-else>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-1.5">
              <a v-for="(url, key) in applyLinks" :key="key" :href="url" target="_blank" rel="noopener"
                class="px-3 py-2 text-xs font-medium rounded-lg border border-line text-center text-ink-sub
                  hover:border-accent hover:text-accent transition-colors">
                {{ PLATFORM_LABELS[key] || key }}
              </a>
            </div>
            <p class="text-[11px] text-ink-faint mb-4">
              新窗口打开对应平台的搜索结果，找到岗位后由你手动提交——知岗不代你操作、不接触平台账号。
            </p>
          </template>

          <!-- AI 投递材料包 -->
          <div class="border-t border-line pt-4">
            <div class="flex items-center gap-2 flex-wrap mb-2.5">
              <span class="text-xs font-semibold shrink-0">AI 材料包</span>
              <select v-model="applyResumeId"
                class="px-2.5 py-1.5 text-xs bg-inset rounded-lg border border-line
                  focus:outline-none focus:border-accent transition-colors min-w-0 max-w-[200px]">
                <option value="">选择简历…</option>
                <option v-for="r in resumes" :key="r.id" :value="r.id">{{ r.filename }}</option>
              </select>
              <button @click="genKit" :disabled="kitLoading || !applyResumeId"
                class="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-accent text-white
                  hover:bg-accent-hover active:scale-[0.98] transition-all disabled:opacity-40">
                {{ kitLoading ? 'AI 生成中…' : (kit.greeting || kit.cover_letter ? '重新生成' : '生成材料包') }}
              </button>
            </div>

            <!-- M65 引用素材卡（可选）：求职信生成时引用素材卡真实内容，AI 只引用不编造 -->
            <details class="mb-3">
              <summary class="text-[11px] text-ink-faint cursor-pointer hover:text-ink-sub select-none">
                引用素材卡（可选）<span v-if="applyStarIds.length" class="text-accent">：已选 {{ applyStarIds.length }}/5</span>
              </summary>
              <div v-if="starLoading" class="mt-1.5 text-[11px] text-ink-faint">素材加载中…</div>
              <template v-else-if="starCards.length">
                <div class="mt-1.5 max-h-40 overflow-y-auto space-y-1">
                  <label v-for="c in starCards" :key="c.id"
                    class="flex items-center gap-2 px-2.5 py-1.5 text-xs bg-inset rounded-lg border border-line
                      cursor-pointer hover:border-accent/50 transition-colors">
                    <input type="checkbox" :value="c.id" v-model="applyStarIds"
                      :disabled="applyStarIds.length >= 5 && !applyStarIds.includes(c.id)"
                      class="w-4 h-4 accent-accent shrink-0" />
                    <span class="truncate min-w-0 flex-1" :title="c.title">{{ c.title }}</span>
                    <span v-if="c.tags" class="text-[10px] text-ink-faint truncate max-w-[120px]">{{ c.tags }}</span>
                  </label>
                </div>
                <p class="text-[11px] text-ink-faint mt-1">求职信将引用所选素材卡的真实内容，AI 只引用不编造。</p>
              </template>
              <p v-else-if="starFailed" class="mt-1.5 text-[11px] text-warn">素材卡加载失败，可关闭弹层后重试。</p>
              <p v-else class="mt-1.5 text-[11px] text-ink-faint">还没有素材卡，去「素材库」建立你的 STAR 档案。</p>
            </details>

            <details class="mb-3">
              <summary class="text-[11px] text-ink-faint cursor-pointer hover:text-ink-sub select-none">
                投递档案（可选）：期望薪资 / 到岗时间等，AI 只引用不编造
              </summary>
              <textarea v-model="applyProfile" rows="2" maxlength="1000"
                placeholder="例如：期望 25-35K，可 2 周内到岗，接受必要出差……"
                class="w-full mt-1.5 px-3 py-2 text-xs bg-inset rounded-lg border border-line resize-y
                  focus:outline-none focus:border-accent placeholder:text-ink-faint transition-colors"></textarea>
            </details>

            <div v-if="kitLoading" class="text-xs text-ink-faint">
              正在按简历与 JD 生成招呼语 / 自我介绍要点 / 求职信…
            </div>
            <template v-else-if="kit.greeting || kit.cover_letter || kit.intro_points.length">
              <div class="mb-3">
                <div class="flex items-center justify-between mb-1">
                  <span class="text-xs font-medium text-ink-sub">招呼语（BOSS 风格）</span>
                  <button @click="copyText(kit.greeting, '招呼语已复制')"
                    class="text-xs text-accent hover:underline shrink-0">📋 复制</button>
                </div>
                <p class="text-xs text-ink-sub bg-inset rounded-lg px-3 py-2.5 leading-relaxed whitespace-pre-wrap">
                  {{ kit.greeting }}</p>
              </div>
              <div v-if="kit.intro_points.length" class="mb-3">
                <div class="flex items-center justify-between mb-1">
                  <span class="text-xs font-medium text-ink-sub">自我介绍要点</span>
                  <button @click="copyText(kit.intro_points.join('\n'), '要点已复制')"
                    class="text-xs text-accent hover:underline shrink-0">📋 复制</button>
                </div>
                <ul class="text-xs text-ink-sub bg-inset rounded-lg px-3 py-2.5 leading-relaxed list-disc pl-6">
                  <li v-for="(p, i) in kit.intro_points" :key="i">{{ p }}</li>
                </ul>
              </div>
              <div>
                <div class="flex items-center justify-between mb-1">
                  <span class="text-xs font-medium text-ink-sub">求职信</span>
                  <button @click="copyText(kit.cover_letter, '求职信已复制')"
                    class="text-xs text-accent hover:underline shrink-0">📋 复制</button>
                </div>
                <p class="text-xs text-ink-sub bg-inset rounded-lg px-3 py-2.5 leading-relaxed whitespace-pre-wrap">
                  {{ kit.cover_letter }}</p>
              </div>

              <!-- M56.3 邮件投递 + 材料包导出 -->
              <div v-if="kit.cover_letter" class="flex items-center gap-2.5 mt-3 pt-3 border-t border-line/60 flex-wrap">
                <a :href="mailtoUrl"
                  class="px-3.5 py-1.5 text-xs font-medium rounded-lg border border-accent/50 text-accent
                    hover:bg-accent/10 transition-colors">📧 邮件投递</a>
                <button @click="exportKit" :disabled="exporting"
                  class="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-accent text-white
                    hover:bg-accent-hover active:scale-[0.98] transition-all disabled:opacity-40">
                  {{ exporting ? '导出中…' : '📄 导出材料包 Word' }}
                </button>
              </div>
              <p v-if="kit.cover_letter" class="text-[11px] text-ink-faint mt-1.5">
                邮件投递会打开本机邮件客户端并预填主题与正文（收件人请自行填写）；
                导出的 Word 含求职信与要点{{ applyResumeId ? '，并附所选简历内容' : '（选简历后可附简历内容）' }}。
              </p>
            </template>
            <p v-else class="text-[11px] text-ink-faint">
              选一份简历后点「生成材料包」，AI 按简历与 JD 生成招呼语、自我介绍要点和求职信，逐段一键复制。
            </p>
          </div>

          <!-- M61 投递前体检：JD 关键词覆盖（纯本地词库比对，复用上方所选简历） -->
          <div class="border-t border-line pt-4 mt-4">
            <details>
              <summary class="text-xs font-semibold cursor-pointer select-none">
                🔍 投递前体检 · 关键词覆盖
              </summary>

              <div class="flex items-center gap-2 flex-wrap mt-2.5">
                <span class="text-[11px] shrink-0"
                  :class="applyResumeId ? 'text-ink-faint' : 'text-warn'">
                  {{ applyResumeId ? `使用简历：${kcResumeName}` : '⚠️ 未选择简历（在上方材料包处选择）' }}
                </span>
                <button @click="runKeywordCheck"
                  :disabled="kcLoading || !applyResumeId || !kcJdReady"
                  class="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-accent text-white
                    hover:bg-accent-hover active:scale-[0.98] transition-all disabled:opacity-40">
                  {{ kcLoading ? '体检中…' : (kcResult ? '重新体检' : '开始体检') }}
                </button>
              </div>
              <p v-if="!kcJdReady" class="text-[11px] text-ink-faint mt-1.5">
                该岗位暂无有效 JD 描述，先编辑补充 JD 才能体检。
              </p>

              <div v-if="kcLoading" class="text-xs text-ink-faint mt-3">
                正在本地提取 JD 高频技能词并与简历比对…
              </div>
              <template v-else-if="kcResult">
                <div class="flex items-center gap-3 mt-3">
                  <div class="text-2xl font-semibold font-mono shrink-0"
                    :class="kcResult.coverage >= 70 ? 'text-ok'
                      : kcResult.coverage >= 40 ? 'text-warn' : 'text-bad'">
                    {{ kcResult.coverage }}%
                  </div>
                  <div class="flex-1 h-3 rounded-full border-2 border-ink/70 bg-inset overflow-hidden">
                    <div class="h-full bg-accent transition-all duration-500"
                      :style="{ width: kcResult.coverage + '%' }"></div>
                  </div>
                </div>
                <div class="text-[11px] text-ink-faint mt-1">
                  命中 {{ kcResult.hits.length }} / {{ kcResult.total }} 个关键词
                </div>

                <div v-if="kcResult.hits.length" class="mt-2.5">
                  <div class="text-[11px] font-medium text-ok mb-1">✓ 已命中 {{ kcResult.hits.length }}</div>
                  <div class="flex flex-wrap gap-1.5">
                    <span v-for="w in kcResult.hits" :key="'kc-h-' + w"
                      class="px-1.5 py-0.5 rounded text-[11px] text-ok bg-ok/10 border border-ok/30">{{ w }}</span>
                  </div>
                </div>
                <div v-if="kcResult.missing.length" class="mt-2.5">
                  <div class="text-[11px] font-medium text-warn mb-1">✗ 缺失 {{ kcResult.missing.length }}</div>
                  <div class="flex flex-wrap gap-1.5">
                    <span v-for="w in kcResult.missing" :key="'kc-m-' + w"
                      class="px-1.5 py-0.5 rounded text-[11px] text-warn bg-warn/10 border border-warn/30">{{ w }}</span>
                  </div>
                </div>
                <p class="text-[11px] text-ink-faint mt-2.5">
                  缺失词可考虑补充到简历或面试前突击——纯本地词库比对，不上传任何内容。
                </p>
              </template>
              <p v-else-if="kcError" class="text-xs text-warn mt-3">{{ kcError }}</p>
              <p v-else class="text-[11px] text-ink-faint mt-3">
                点击「开始体检」，本地词库提取 JD 高频技能词并比对简历命中情况，秒级完成、零 AI 调用。
              </p>
            </details>
          </div>

          <!-- 底部操作 -->
          <div class="flex items-center justify-between gap-3 mt-5 pt-4 border-t border-line">
            <button @click="closeApply" class="px-4 py-2 text-xs text-ink-sub hover:text-ink transition-colors">关闭</button>
            <div v-if="(applyJob.status || 'wish') !== 'applied'" class="flex items-center gap-2">
              <select v-model="applyChannel"
                class="px-2.5 py-2 text-xs bg-inset rounded-lg border border-line
                  focus:outline-none focus:border-accent transition-colors">
                <option value="">投递渠道（可选）</option>
                <option v-for="c in CHANNEL_OPTIONS" :key="c.value" :value="c.value">{{ c.label }}</option>
              </select>
              <button @click="markApplied"
                class="px-4 py-2 text-xs font-medium rounded-lg border border-accent/50 text-accent
                  hover:bg-accent/10 transition-colors">📨 投出了，标记「已投递」</button>
            </div>
            <span v-else class="text-xs text-ok">
              ✓ 已投递{{ applyJob.apply_at ? `（${applyJob.apply_at.slice(5, 10).replace('-', '/')}）` : '' }}{{ applyJob.apply_channel ? ` · ${CHANNEL_LABELS[applyJob.apply_channel] || applyJob.apply_channel}` : '' }}
            </span>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 降级提示 -->
    <div v-if="matchDegraded" class="mb-5 px-4 py-3 rounded-xl text-xs
      bg-warn/10 border border-warn/40 text-warn">
      AI 精排不可用，已按关键词重合度排序——可在设置页配置 API Key 后重新匹配获得更准的排序。
    </div>

    <!-- 岗位列表 -->
    <!-- M51 旧版收藏迁移引导：localStorage 收藏一次性并入岗位库 -->
    <div v-if="legacyFavs.length" class="bg-accent/10 border border-accent/40 rounded-2xl px-5 py-4
      flex flex-wrap items-center justify-between gap-3 mb-5">
      <div class="text-sm text-ink-sub">
        <span class="font-medium text-ink">检测到 {{ legacyFavs.length }} 条旧版收藏岗位</span>
        · 收藏已升级并入岗位库，支持投递状态追踪与批量匹配
      </div>
      <button @click="migrateLegacyFavorites" :disabled="migrating"
        class="px-4 py-2 text-xs font-medium rounded-lg bg-accent text-white
          hover:bg-accent-hover transition-colors disabled:opacity-50 shrink-0">
        {{ migrating ? '迁移中…' : '一键迁移到岗位库' }}
      </button>
    </div>

    <LoadingBlock v-if="loading" text="岗位库加载中…" />
    <div v-else-if="loadError" class="bg-warn/10 border border-warn/40 rounded-2xl px-5 py-4
      flex items-center justify-between">
      <span class="text-sm text-warn">岗位库加载失败</span>
      <button @click="loadAll" class="text-sm font-medium text-warn hover:text-ink transition-colors">重试</button>
    </div>

    <template v-else>
      <div v-if="!jobs.length" class="bg-panel rounded-2xl p-12 text-center">
        <div class="text-4xl mb-4">💼</div>
        <div class="text-lg font-semibold mb-2">从一份 JD 开始建库</div>
        <p class="text-sm text-ink-sub max-w-md mx-auto">
          把心仪岗位的 JD 粘贴进来统一管理；之后选一份简历即可批量匹配出分，
          也可以直接「用此岗位诊断 / 面试」。
        </p>
        <div class="flex items-center justify-center gap-3 mt-5">
          <button @click="openForm()"
            class="px-5 py-2 text-xs font-medium rounded-lg bg-accent text-white
              hover:bg-accent-hover transition-colors">＋ 添加第一个岗位</button>
          <button @click="fillSamples" :disabled="fillingSamples"
            class="px-5 py-2 text-xs font-medium rounded-lg border border-accent/50 text-accent
              hover:bg-accent/10 transition-colors disabled:opacity-40">
            {{ fillingSamples ? '填充中…' : '🧪 填充 6 个示例岗位' }}
          </button>
        </div>
      </div>

      <!-- 筛选无结果（库非空但过滤后为空） -->
      <div v-else-if="hasFilters && !filteredJobs.length"
        class="bg-panel rounded-2xl p-10 text-center">
        <div class="text-3xl mb-3">🔍</div>
        <div class="text-sm text-ink-sub mb-1">没有符合筛选条件的岗位</div>
        <p class="text-xs text-ink-faint mb-4">换个关键词，或清除筛选查看全部 {{ jobs.length }} 个岗位</p>
        <button @click="clearFilters"
          class="px-4 py-2 text-xs font-medium rounded-lg border border-accent/50 text-accent
            hover:bg-accent/10 transition-colors">清除筛选</button>
      </div>

      <!-- M51+ 网格卡片布局（对齐简历库）：同屏容量与信息可读性平衡 -->
      <div v-else class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="j in displayJobs" :key="j.id" :id="`job-card-${j.id}`"
          class="bg-panel border-2 border-ink/80 shadow-[3px_3px_0_0] shadow-ink/15 rounded-lg p-5 flex flex-col
            hover:-translate-y-0.5 hover:shadow-[4px_4px_0_0] hover:shadow-ink/25 transition-all"
          :class="[
            selMode && selIds.has(j.id) && 'ring-2 ring-accent/50 border-accent/40',
            focusJobId === j.id && 'ring-2 ring-accent border-accent/60',
          ]">
          <!-- 头部：复选 + 岗位名/公司 + 匹配分 -->
          <div class="flex items-start gap-2.5 mb-2">
            <input v-if="selMode" type="checkbox" :checked="selIds.has(j.id)"
              @change="toggleCardSel(j.id)"
              class="mt-1 w-4 h-4 accent-accent shrink-0 cursor-pointer" />
            <div class="min-w-0 flex-1">
              <div class="text-sm font-semibold text-ink truncate" :title="j.title">{{ j.title }}</div>
              <div class="text-xs text-ink-faint mt-0.5 font-mono truncate"
                :title="j.company ? '' : '公司待定 · 点卡片右下 ✏️ 编辑补填真实公司'">
                {{ j.company || '公司待定' }}<span v-if="j.city"> · {{ j.city }}</span><span
                  v-if="!matchMap[j.id]"> · {{ fmtTime(j.created_at) }}</span>
              </div>
            </div>
            <div v-if="matchMap[j.id]" class="text-right shrink-0">
              <div class="text-lg font-semibold font-mono"
                :class="matchMap[j.id].score >= 70 ? 'text-ok'
                  : matchMap[j.id].score >= 40 ? 'text-warn' : 'text-ink-faint'">
                {{ matchMap[j.id].score }}
              </div>
              <div class="text-[10px] text-ink-faint">匹配分</div>
            </div>
          </div>

          <!-- 徽标行：薪资 / 来源 / 匹配理由 / 投递状态（直改） -->
          <div class="flex items-center gap-1.5 flex-wrap mb-2.5 min-h-[22px]">
            <span v-if="j.salary" class="px-1.5 py-0.5 rounded text-[11px] bg-ok/10 text-ok font-mono shrink-0">{{ j.salary }}</span>
            <!-- M69 岗位链接命中招聘平台域名时显示来源徽标 -->
            <span v-if="urlPlatform(j.url)" class="px-1.5 py-0.5 rounded text-[10px] border border-line text-ink-faint shrink-0">{{ urlPlatform(j.url) }}</span>
            <span class="px-1.5 py-0.5 rounded text-[11px] bg-inset text-ink-faint shrink-0">{{ sourceLabel(j.source) }}</span>
            <!-- M60 面试日程徽标：今天/明天临近 accent 强调 -->
            <span v-if="j.next_interview_at" class="px-1.5 py-0.5 rounded text-[11px] shrink-0"
              :class="interviewSoon(j.next_interview_at) ? 'bg-accent/10 text-accent' : 'bg-inset text-ink-faint'">
              📅 {{ fmtBadgeDate(j.next_interview_at) }} 面试
            </span>
            <span v-if="matchMap[j.id]?.reason" :title="matchMap[j.id].reason"
              class="text-[10px] text-ink-faint truncate max-w-[100px]">{{ matchMap[j.id].reason }}</span>
            <select :value="j.status || 'wish'" @change="setStatus(j, $event.target.value)" @click.stop
              :title="'投递状态：' + (STATUS[j.status || 'wish']?.label || '') + '，点击切换'"
              class="ml-auto px-1.5 py-0.5 rounded text-[11px] font-medium shrink-0 border-0 cursor-pointer
                appearance-none focus:outline-none focus:ring-1 focus:ring-accent -mr-1"
              :class="STATUS[j.status || 'wish']?.cls">
              <option v-for="(s, key) in STATUS" :key="key" :value="key">{{ s.label }}</option>
            </select>
          </div>

          <!-- JD 摘要（默认两行截断，点击展开；无 JD 显示占位） -->
          <p v-if="j.jd" class="text-xs text-ink-faint mb-4 leading-relaxed cursor-pointer flex-1"
            :class="expandedId === j.id ? 'whitespace-pre-wrap text-ink-sub' : 'line-clamp-2 whitespace-pre-line'"
            :title="expandedId === j.id ? '点击收起' : '点击展开'"
            @click="expandedId = expandedId === j.id ? null : j.id">{{ j.jd }}</p>
          <p v-else class="text-xs text-ink-faint/60 italic mb-4 flex-1">暂无 JD 描述 · 编辑补充后可用于诊断/面试</p>

          <!-- 操作区 -->
          <div class="mt-auto flex items-center gap-2.5 pt-3 border-t border-line/60">
            <button @click="diagnoseWith(j)" class="text-xs text-accent hover:underline shrink-0">🩺 诊断</button>
            <button @click="interviewWith(j)" class="text-xs text-accent hover:underline shrink-0">🎤 面试</button>
            <button @click="openApply(j)" title="平台深链直达 + AI 投递材料包"
              class="text-xs text-accent hover:underline shrink-0">🚀 投递</button>
            <!-- M69 原链直达（有链接才显示） -->
            <a v-if="j.url" :href="j.url" target="_blank" rel="noopener" title="打开岗位原链接"
              class="text-xs text-accent hover:underline shrink-0">🔗 原链</a>
            <span class="flex-1" />
            <button v-if="!selMode" @click="openEdit(j)" title="编辑岗位"
              class="text-xs text-ink-sub hover:text-accent transition-colors shrink-0">✏️</button>
            <button v-if="!selMode" @click="remove(j)" title="删除岗位"
              class="text-xs text-ink-sub hover:text-bad transition-colors shrink-0">🗑</button>
          </div>
        </div>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import api from '../api'
import { useAppMode } from '../composables/useAppMode'
import LoadingBlock from '../components/LoadingBlock.vue'
import CityInput from '../components/CityInput.vue'
import { loadFavorites, clearFavorites } from '../utils/favorites'

const { isDesktop } = useAppMode()

const router = useRouter()
const route = useRoute()

const loading = ref(true)
const loadError = ref(false)
const jobs = ref([])
const resumes = ref([])
const selectedResumeId = ref('')

const formOpen = ref(false)
const editingId = ref(null)
const formSaving = ref(false)
const form = reactive({ title: '', company: '', city: '', salary: '', jd: '', url: '', next_interview_at: '' })

const matching = ref(false)
const matchDone = ref(false)
const matchDegraded = ref(false)
const matchMap = reactive({})   // id -> {score, reason}
const expandedId = ref(null)

/* ---- M49 投递状态 ---- */
const STATUS = {
  wish: { label: '💧 想投', cls: 'bg-inset text-ink-sub' },
  applied: { label: '📨 已投递', cls: 'bg-accent/10 text-accent' },
  interviewing: { label: '🎯 面试中', cls: 'bg-warn/10 text-warn' },
  offer: { label: '🎉 Offer', cls: 'bg-ok/10 text-ok' },
  closed: { label: '🏁 已结束', cls: 'bg-bad/10 text-bad' },
}
const statusFilter = ref('')

async function setStatus(j, status, channel = null) {
  const prev = j.status || 'wish'
  if (status === prev && !channel) return
  try {
    const res = await api.updateJobStatus(j.id, status, channel)
    j.status = res.data.status
    j.apply_channel = res.data.apply_channel
    j.apply_at = res.data.apply_at
  } catch (e) {
    Message.error(e.response?.data?.detail || '状态更新失败')
    j.status = prev
  }
}

async function batchSetStatus(status) {
  if (!status || !selIds.value.size) return
  try {
    await api.batchUpdateJobStatus([...selIds.value], status)
    jobs.value.forEach((j) => {
      if (selIds.value.has(j.id)) j.status = status
    })
    Message.success(`已将 ${selIds.value.size} 个岗位设为「${STATUS[status].label}」`)
  } catch (e) {
    Message.error(e.response?.data?.detail || '批量更新失败')
  }
}

/* ---- M56 投递直达：平台深链 + AI 材料包 ---- */
const PLATFORM_LABELS = { boss: 'BOSS 直聘', zhilian: '智联招聘', liepin: '猎聘', nowcoder: '牛客' }
const APPLY_PROFILE_KEY = 'apply_profile'
// M56.4 投递台账渠道
const CHANNEL_OPTIONS = [
  { value: 'boss', label: 'BOSS 直聘' },
  { value: 'zhilian', label: '智联招聘' },
  { value: 'liepin', label: '猎聘' },
  { value: 'nowcoder', label: '牛客' },
  { value: 'email', label: '邮件' },
  { value: 'other', label: '其他' },
]
const CHANNEL_LABELS = Object.fromEntries(CHANNEL_OPTIONS.map((c) => [c.value, c.label]))

/* ---- M69 岗位链接：域名 → 平台徽标 / 投递渠道推断 ---- */
const URL_PLATFORM_MAP = [
  ['zhipin.com', 'BOSS', 'boss'],
  ['zhaopin.com', '智联', 'zhilian'],
  ['liepin.com', '猎聘', 'liepin'],
  ['nowcoder.com', '牛客', 'nowcoder'],
]

function matchUrlPlatform(url) {
  const u = (url || '').toLowerCase()
  return URL_PLATFORM_MAP.find(([domain]) => u.includes(domain)) || null
}
const urlPlatform = (url) => matchUrlPlatform(url)?.[1] || ''   // 卡片徽标用
const urlChannel = (url) => matchUrlPlatform(url)?.[2] || ''    // 投递渠道推断用

const applyJob = ref(null)
const applyLinks = ref({})
const linksLoading = ref(false)
const applyResumeId = ref('')
const applyProfile = ref('')
const applyChannel = ref('')
const kitLoading = ref(false)
const kit = reactive({ greeting: '', cover_letter: '', intro_points: [] })

/* ---- M65 引用素材卡：求职信生成时作为事实依据（后端按 owner 过滤注入 prompt） ---- */
const starCards = ref([])
const starLoading = ref(false)
const starFailed = ref(false)
const applyStarIds = ref([])

async function loadStarCards() {
  if (starLoading.value) return
  starLoading.value = true
  starFailed.value = false
  try {
    const res = await api.listStarCards()
    starCards.value = res.data.items || []
  } catch {
    starFailed.value = true
  } finally {
    starLoading.value = false
  }
}

async function openApply(j) {
  applyJob.value = j
  applyLinks.value = {}
  kit.greeting = ''
  kit.cover_letter = ''
  kit.intro_points = []
  kcResult.value = null
  kcError.value = ''
  applyResumeId.value = selectedResumeId.value || ''
  applyStarIds.value = []
  loadStarCards()  // 每次打开刷新素材卡列表（静默失败，弹层内给提示）
  // M69 岗位链接能推断渠道时自动预选（每次打开均为新会话，用户尚未手动选择，可改选）
  applyChannel.value = urlChannel(j.url)
  try { applyProfile.value = localStorage.getItem(APPLY_PROFILE_KEY) || '' } catch { /* 损坏值兜底 */ }
  linksLoading.value = true
  try {
    const res = await api.getApplyLinks(j.id)
    applyLinks.value = res.data.links || {}
  } catch (e) {
    Message.error(e.response?.data?.detail || '深链生成失败')
  } finally {
    linksLoading.value = false
  }
}

function closeApply() {
  applyJob.value = null
}

async function genKit() {
  if (!applyResumeId.value) {
    Message.warning('先选择一份简历')
    return
  }
  kitLoading.value = true
  try {
    try { localStorage.setItem(APPLY_PROFILE_KEY, applyProfile.value.trim()) } catch { /* 忽略 */ }
    const res = await api.jobApplyKit(applyJob.value.id, {
      resume_id: Number(applyResumeId.value),
      profile: applyProfile.value.trim() || null,
      star_ids: applyStarIds.value,  // M65 引用素材卡：求职信事实依据
      llm_config: null,
    })
    kit.greeting = res.data.greeting || ''
    kit.cover_letter = res.data.cover_letter || ''
    kit.intro_points = res.data.intro_points || []
  } catch (e) {
    Message.error(e.response?.data?.detail || 'AI 生成失败')
  } finally {
    kitLoading.value = false
  }
}

async function copyText(text, tip) {
  try {
    await navigator.clipboard.writeText(text)
    Message.success(tip || '已复制到剪贴板')
  } catch {
    Message.error('复制失败，请手动选择文本复制')
  }
}

async function markApplied() {
  await setStatus(applyJob.value, 'applied', applyChannel.value || null)
  closeApply()
}

/* ---- M56.3 邮件投递（mailto: 预填） + 材料包导出 Word ---- */
const exporting = ref(false)

const mailtoUrl = computed(() => {
  if (!kit.cover_letter || !applyJob.value) return ''
  const subject = `应聘${applyJob.value.company || ''}「${applyJob.value.title}」岗位`
  const parts = []
  if (kit.greeting) parts.push(kit.greeting)
  parts.push(kit.cover_letter)
  if (kit.intro_points.length) {
    parts.push('自我介绍要点：\n' + kit.intro_points.map((p) => '· ' + p).join('\n'))
  }
  return `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(parts.join('\n\n'))}`
})

async function exportKit() {
  if (!kit.cover_letter?.trim()) {
    Message.warning('先生成材料包')
    return
  }
  exporting.value = true
  const payload = {
    greeting: kit.greeting || null,
    cover_letter: kit.cover_letter,
    intro_points: kit.intro_points.length ? kit.intro_points : null,
    resume_id: applyResumeId.value ? Number(applyResumeId.value) : null,
  }
  try {
    // 桌面形态（M71）：统一保存到「导出位置」设置的目录「投递材料包」子目录
    if (isDesktop.value) {
      const res = await api.exportApplyKitToPath(applyJob.value.id,
        { ...payload, save_path: 'auto' })
      Message.success(`材料包已保存到：${res.data?.saved_to || res.data?.save_path || ''}`)
      return
    }
    const res = await api.exportApplyKit(applyJob.value.id, payload)
    const url = URL.createObjectURL(new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }))
    const a = document.createElement('a')
    a.href = url
    a.download = `投递材料包_${applyJob.value.title || Date.now()}.docx`
    a.click()
    URL.revokeObjectURL(url)
    Message.success('材料包已导出（见浏览器下载目录）')
  } catch (e) {
    Message.error(e.response?.data?.detail || '导出失败')
  } finally {
    exporting.value = false
  }
}

/* ---- M61 投递前体检：JD 关键词覆盖（纯本地词库比对，复用材料包的简历选择） ---- */
const kcLoading = ref(false)
const kcResult = ref(null)
const kcError = ref('')

// JD 有效即可体检（与后端 min_length=30 同口径）；空 JD/占位 JD 禁用
const kcJdReady = computed(() => ((applyJob.value?.jd || '').trim().length) >= 30)

const kcResumeName = computed(() => {
  const r = resumes.value.find((x) => String(x.id) === String(applyResumeId.value))
  return r?.filename || ''
})

// 换简历后旧结果失效，清掉避免误读
watch(applyResumeId, () => {
  kcResult.value = null
  kcError.value = ''
})

async function runKeywordCheck() {
  const jd = (applyJob.value?.jd || '').trim()
  if (!applyResumeId.value) {
    Message.warning('先在上方选择一份简历')
    return
  }
  if (jd.length < 30) {
    Message.warning('该岗位暂无有效 JD，无法体检')
    return
  }
  kcLoading.value = true
  kcError.value = ''
  try {
    const res = await api.checkKeywordCoverage({
      jd,
      resume_id: Number(applyResumeId.value),
    })
    kcResult.value = res.data
  } catch (e) {
    kcError.value = e.response?.data?.detail || '体检失败，请重试'
  } finally {
    kcLoading.value = false
  }
}

/* ---- 搜索与筛选（本地过滤，匹配分排序作用于筛选后的子集） ---- */
const keyword = ref('')
const sourceFilter = ref('')
const cityFilter = ref('')

const filteredJobs = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return jobs.value.filter((j) => {
    if (kw && ![j.title, j.company, j.city].some((v) => (v || '').toLowerCase().includes(kw)))
      return false
    if (sourceFilter.value && (j.source || 'manual') !== sourceFilter.value) return false
    if (cityFilter.value && (j.city || '') !== cityFilter.value) return false
    if (statusFilter.value && (j.status || 'wish') !== statusFilter.value) return false
    return true
  })
})

const cityOptions = computed(() =>
  [...new Set(jobs.value.map((j) => (j.city || '').trim()).filter(Boolean))].sort(),
)

const hasFilters = computed(() => !!(keyword.value.trim() || sourceFilter.value || cityFilter.value || statusFilter.value))

function clearFilters() {
  keyword.value = ''
  sourceFilter.value = ''
  cityFilter.value = ''
  statusFilter.value = ''
}

const displayJobs = computed(() => {
  const base = filteredJobs.value
  if (!matchDone.value) return base
  return [...base].sort(
    (a, b) => (matchMap[b.id]?.score ?? -1) - (matchMap[a.id]?.score ?? -1),
  )
})

const SOURCE_LABELS = { manual: '手动添加', ai: '面板入库', ai_gen: 'AI 生成', sample: '示例岗位', favorite: '收藏迁移' }
const sourceLabel = (s) => SOURCE_LABELS[s] || s

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}-${String(d.getDate()).padStart(2, '0')}`
}

/* ---- 管理模式（批量选择删除） ---- */
const selMode = ref(false)
const selIds = ref(new Set())
const batchRemoving = ref(false)

const selCount = computed(() => selIds.value.size)
const allCardsSelected = computed(
  () => filteredJobs.value.length > 0 && filteredJobs.value.every((j) => selIds.value.has(j.id)),
)

function toggleSelMode() {
  selMode.value = !selMode.value
  if (!selMode.value) selIds.value = new Set()
}

function toggleCardSel(id) {
  const next = new Set(selIds.value)
  next.has(id) ? next.delete(id) : next.add(id)
  selIds.value = next
}

function toggleSelectAllCards() {
  selIds.value = allCardsSelected.value
    ? new Set()
    : new Set(filteredJobs.value.map((j) => j.id))
}

async function batchRemove() {
  const n = selIds.value.size
  Modal.warning({
    title: `确认删除选中的 ${n} 个岗位？`,
    content: '删除后不可恢复（正在进行的诊断/面试不受影响）。',
    okText: '删除',
    okButtonProps: { status: 'danger' },
    cancelText: '取消',
    hideCancel: false,
    onOk: async () => {
      batchRemoving.value = true
      try {
        await api.batchDeleteLibraryJobs([...selIds.value])
        const gone = new Set(selIds.value)
        jobs.value = jobs.value.filter((j) => !gone.has(j.id))
        selIds.value = new Set()
        selMode.value = false
        Message.success(`已删除 ${n} 个岗位`)
      } catch (e) {
        Message.error(e.response?.data?.detail || '批量删除失败')
      } finally {
        batchRemoving.value = false
      }
    },
  })
}

/* ---- 数据加载 ---- */
async function loadAll() {
  loading.value = true
  loadError.value = false
  try {
    const [jobRes, resumeRes] = await Promise.all([api.listLibraryJobs(), api.listResumes()])
    jobs.value = jobRes.data.items || []
    resumes.value = resumeRes.data.items || []
  } catch (e) {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

/* ---- M51 旧版收藏迁移（localStorage → 岗位库 DB，company+title 去重） ---- */
const legacyFavs = ref([])
const migrating = ref(false)

async function migrateLegacyFavorites() {
  if (!legacyFavs.value.length) return
  migrating.value = true
  try {
    const items = legacyFavs.value.map(j => ({
      title: j.title || '未命名岗位',
      company: j.company || '',
      city: j.city || '',
      salary: j.salary || '',
      jd: j.jd_text || '',
      url: j.url || '',
    }))
    const res = await api.addLibraryJobs(items, 'favorite', true)
    const imported = (res.data.items || []).length
    const skipped = res.data.skipped || 0
    clearFavorites()
    legacyFavs.value = []
    await loadAll()
    Message.success(`迁移完成：入库 ${imported} 条${skipped ? `，跳过重复 ${skipped} 条` : ''}`)
  } catch (e) {
    Message.error(e.response?.data?.detail || '迁移失败，请重试')
  } finally {
    migrating.value = false
  }
}

/* ---- 添加 / 编辑 ---- */
function toggleForm() {
  formOpen.value ? closeForm() : openForm()
}

function openForm() {
  resetForm()
  editingId.value = null
  formOpen.value = true
}

function openEdit(j) {
  editingId.value = j.id
  Object.assign(form, {
    title: j.title || '',
    company: j.company || '',
    city: j.city || '',
    salary: j.salary || '',
    jd: j.jd || '',
    url: j.url || '',  // M69 老数据可能无 url，容错空值
    // M60 ISO 截断到分钟供 datetime-local 回显（"2026-10-15T14:30:00" → "2026-10-15T14:30"）
    next_interview_at: (j.next_interview_at || '').slice(0, 16),
  })
  formOpen.value = true
}

function closeForm() {
  formOpen.value = false
  resetForm()
  editingId.value = null
}

function resetForm() {
  Object.assign(form, { title: '', company: '', city: '', salary: '', jd: '', url: '', next_interview_at: '' })
}

async function saveForm() {
  const title = form.title.trim()
  if (!title) {
    Message.warning('岗位名必填')
    return
  }
  formSaving.value = true
  try {
    const payload = {
      title,
      company: form.company.trim(),
      city: form.city.trim(),
      salary: form.salary.trim(),
      jd: form.jd.trim(),
      url: form.url.trim(),  // M69 岗位链接快存
      // M60 面试日程：空值提交 null = 清除，有值提交 ISO（分钟精度）
      next_interview_at: form.next_interview_at || null,
    }
    if (editingId.value != null) {
      const res = await api.updateLibraryJob(editingId.value, payload)
      const idx = jobs.value.findIndex((j) => j.id === editingId.value)
      if (idx >= 0) jobs.value.splice(idx, 1, res.data)
      Message.success('已保存修改')
      closeForm()
    } else {
      const res = await api.addLibraryJobs([payload], 'manual')
      jobs.value.unshift(...(res.data.items || []))
      Message.success('已加入岗位库，可继续录入')
      resetForm()  // 连续录入：清空不收起
    }
  } catch (e) {
    Message.error(e.response?.data?.detail || '保存失败')
  } finally {
    formSaving.value = false
  }
}

/* ---- 删除 ---- */
function remove(j) {
  Modal.warning({
    title: '确认删除该岗位？',
    content: `「${j.company || ''} ${j.title}」将从岗位库删除。`,
    okText: '删除',
    cancelText: '取消',
    hideCancel: false,
    onOk: async () => {
      try {
        await api.deleteLibraryJob(j.id)
        jobs.value = jobs.value.filter((x) => x.id !== j.id)
        delete matchMap[j.id]
        Message.success('已删除')
      } catch (e) {
        Message.error(e.response?.data?.detail || '删除失败')
      }
    },
  })
}

/* ---- 匹配推荐 ---- */
async function runMatch() {
  if (!selectedResumeId.value) {
    Message.warning('先选择一份简历')
    return
  }
  matching.value = true
  try {
    // 筛选出子集时只匹配子集（后端按 job_ids 过滤候选池）
    const subset = filteredJobs.value.length < jobs.value.length
    const res = await api.matchLibraryJobs({
      resume_id: Number(selectedResumeId.value),
      job_ids: subset ? filteredJobs.value.map((j) => j.id) : undefined,
      llm_config: null,
    })
    Object.keys(matchMap).forEach((k) => delete matchMap[k])
    for (const it of res.data.items || []) {
      matchMap[it.id] = { score: it.score, reason: it.reason }
    }
    matchDegraded.value = !!res.data.degraded
    matchDone.value = true
    if (res.data.message) Message.info(res.data.message)
    else Message.success(`已为 ${res.data.items?.length ?? 0} 个岗位打分`)
  } catch (e) {
    Message.error(e.response?.data?.detail || '匹配失败')
  } finally {
    matching.value = false
  }
}

function clearMatch() {
  matchDone.value = false
  matchDegraded.value = false
  Object.keys(matchMap).forEach((k) => delete matchMap[k])
}

/* ---- 批量导入：粘贴混排文本 → AI 解析 → 勾选入库 ---- */
const importOpen = ref(false)
const rawImportText = ref('')
const parsing = ref(false)
const parsed = ref([])   // [{title, company, city, salary, jd, _sel}]
const parseDegraded = ref(false)
const parseDegradedReason = ref('')
const importing = ref(false)

const selectedCount = computed(() => parsed.value.filter((j) => j._sel).length)
const allSelected = computed(() => parsed.value.length > 0 && selectedCount.value === parsed.value.length)

function openImport() {
  importOpen.value = true
}

function closeImport() {
  importOpen.value = false
  rawImportText.value = ''
  parsed.value = []
  parseDegraded.value = false
  clipboardHint.value = false
}

function toggleSelectAll() {
  const target = !allSelected.value
  parsed.value.forEach((j) => (j._sel = target))
}

async function parseBatch() {
  if (rawImportText.value.trim().length < 30) {
    Message.warning('文本太短（至少 30 字）')
    return
  }
  parsing.value = true
  try {
    const res = await api.parseBatchImport({ raw_text: rawImportText.value, llm_config: null })
    // url 防御性截断：Boss 等平台链接带 securityId 等参数动辄超长，超 300 字符不再入库
    parsed.value = (res.data.items || []).map((j) => ({ ...j, url: (j.url || '').slice(0, 300), _sel: true }))
    parseDegraded.value = !!res.data.degraded
    parseDegradedReason.value = res.data.degraded_reason || ''
    if (!parsed.value.length) {
      Message.info(res.data.message || '没有解析出岗位')
    } else {
      Message.success(`解析出 ${parsed.value.length} 个岗位，请确认后导入`)
    }
  } catch (e) {
    Message.error(e.response?.data?.detail || '解析失败')
  } finally {
    parsing.value = false
  }
}

async function importSelected() {
  const items = parsed.value
    .filter((j) => j._sel)
    .map(({ _sel, ...j }) => j)
  if (!items.length) return
  importing.value = true
  try {
    const res = await api.addLibraryJobs(items, 'manual', true)  // 后端自动跳过与库内重复
    const added = res.data.items || []
    jobs.value.unshift(...added)
    const skipped = res.data.skipped || 0
    if (added.length) {
      Message.success(`已导入 ${added.length} 个岗位${skipped ? `，跳过重复 ${skipped} 个` : ''}`)
    } else {
      Message.info(res.data.message || '没有新岗位入库')
    }
    closeImport()
  } catch (e) {
    Message.error(e.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

/* ---- M70-A 剪贴板导入：读剪贴板 → 填入面板 → 自动解析 ---- */
const clipboardHint = ref(false)  // 无法自动读取剪贴板时的手动粘贴提示

async function importFromClipboard() {
  clipboardHint.value = false
  importOpen.value = true
  try {
    const text = await navigator.clipboard.readText()
    if (text && text.trim()) {
      rawImportText.value = text
      parseBatch()  // 读取成功直接解析（内部有 30 字下限校验，太短会提示）
    } else {
      clipboardHint.value = true  // 剪贴板为空，引导手动粘贴
    }
  } catch {
    // 权限拒绝 / 非安全上下文等：退回手动粘贴流程
    clipboardHint.value = true
  }
}

/* ---- M70-B 采集书签（bookmarklet）：岗位页文本一键复制，回站「剪贴板导入」入库 ---- */
// 单行压缩代码；\n 为书签源码中的字面转义（双引号字符串里写 \\n 保留原样），中文原样保留
const BOOKMARKLET_CODE = "(function(){var t=document.title||'';var u=location.href;var el=document.querySelector('.job-detail,.job-sec-text,.jd,.description,[class*=job-detail],[class*=job-desc],[class*=description]');var txt=el?el.innerText:document.body.innerText;txt=(txt||'').trim().slice(0,8000);var out='岗位：'+t+'\\n链接：'+u+'\\n\\n'+txt;(navigator.clipboard&&navigator.clipboard.writeText?navigator.clipboard.writeText(out):Promise.reject()).then(function(){alert('已复制岗位信息，请回到知岗点「剪贴板导入」')},function(){var ta=document.createElement('textarea');ta.value=out;document.body.appendChild(ta);ta.select();try{document.execCommand('copy')?alert('已复制岗位信息，请回到知岗点「剪贴板导入」'):window.prompt('复制以下岗位信息',out)}catch(e){window.prompt('复制以下岗位信息',out)}document.body.removeChild(ta)})})();"
const bookmarkletHref = 'javascript:' + encodeURIComponent(BOOKMARKLET_CODE)

/* ---- 示例岗位：一键填充体验完整流程（可删除） ---- */
const SAMPLE_JOBS = [
  { title: 'Python 后端开发工程师', company: '', city: '北京', salary: '30-50K·16薪',
    jd: '岗位职责：1. 负责内容分发与创作平台后端服务的架构设计与研发；2. 参与高并发、高可用分布式系统建设，保障核心链路稳定性；3. 与算法、前端团队协作完成业务迭代。任职要求：1. 本科及以上学历，3 年以上 Python 开发经验；2. 精通 FastAPI/Flask 至少一种框架，熟悉 MySQL、Redis、Kafka；3. 有大规模分布式系统或高并发订单/内容系统经验者优先。' },
  { title: '前端开发工程师（React 方向）', company: '', city: '深圳', salary: '25-45K·16薪',
    jd: '岗位职责：1. 负责公司核心 SaaS 产品的前端架构与研发；2. 建设前端工程化体系，优化构建与首屏性能；3. 设计通用组件库，提升团队研发效率。任职要求：1. 熟练掌握 React/TypeScript，理解 Hooks 原理；2. 熟悉 Vite/Webpack 构建链路，有性能调优实战经验；3. 对可视化（ECharts/D3）有经验者优先。' },
  { title: '算法工程师（推荐方向）', company: '', city: '北京', salary: '35-60K·15.5薪',
    jd: '岗位职责：1. 负责到店推荐算法的建模与迭代，提升转化与留存；2. 建设 User/Item 表征、排序与重排策略；3. 跟进业界前沿论文并落地。任职要求：1. 硕士及以上学历，计算机/数学相关专业；2. 扎实的机器学习基础，熟悉 PyTorch，有召回/排序实战经验；3. 有 KDD/SIGIR 等论文发表者优先。' },
  { title: '数据分析师（商业化方向）', company: '', city: '上海', salary: '20-35K·14薪',
    jd: '岗位职责：1. 负责商业化广告业务的数据分析，输出增长洞察；2. 搭建指标体系与看板，监控核心漏斗；3. 支持 A/B 实验设计与效果归因。任职要求：1. 本科及以上学历，统计学/计算机相关专业；2. 精通 SQL 与 Python 数据分析，熟悉 Hive/Spark；3. 有互联网广告或增长分析经验者优先。' },
  { title: '测试开发工程师', company: '', city: '杭州', salary: '22-38K·14薪',
    jd: '岗位职责：1. 负责云计算产品测试平台与自动化框架建设；2. 设计接口/性能/稳定性测试方案并落地；3. 推动 CI/CD 流水线质量卡点。任职要求：1. 本科及以上学历，2 年以上测试开发经验；2. 精通 Python，熟悉 pytest/locust，了解 Docker 与 K8s；3. 有大型分布式系统测试经验者优先。' },
  { title: '产品经理（AI 应用方向）', company: '', city: '杭州', salary: '28-50K·16薪',
    jd: '岗位职责：1. 负责 AI 助手类产品从 0 到 1 的规划与落地；2. 深挖用户场景，设计 Prompt 与 Agent 工作流的产品化方案；3. 协同算法、研发推进迭代并复盘数据。任职要求：1. 本科及以上学历，3 年以上产品经验；2. 对 LLM/Agent 生态有深入理解，用过主流大模型 API；3. 有 AI 产品或工具类产品上线经验者优先。' },
]

const fillingSamples = ref(false)

async function fillSamples() {
  fillingSamples.value = true
  try {
    const res = await api.addLibraryJobs(SAMPLE_JOBS, 'sample')
    jobs.value.unshift(...(res.data.items || []))
    Message.success('已填充 6 个示例岗位，可删除或直接体验匹配/诊断/面试')
  } catch (e) {
    Message.error(e.response?.data?.detail || '填充失败')
  } finally {
    fillingSamples.value = false
  }
}

/* ---- AI 自动入库：按选中简历生成岗位（不编造公司，城市可指定） ---- */
const generating = ref(false)
const generateCity = ref('')

async function runGenerate() {
  if (!selectedResumeId.value) {
    Message.warning('先选择一份简历')
    return
  }
  generating.value = true
  try {
    const res = await api.generateLibraryJobs({
      resume_id: Number(selectedResumeId.value),
      city: generateCity.value.trim() || null,
      llm_config: null,
    })
    const added = res.data.items || []
    if (added.length) {
      jobs.value.unshift(...added)
      Message.success(`已生成 ${added.length} 个岗位并入库（公司留空，投递前请在卡片上 ✏️ 补填真实公司）`)
    } else {
      Message.info(res.data.message || '没有新岗位入库')
    }
  } catch (e) {
    Message.error(e.response?.data?.detail || 'AI 生成失败')
  } finally {
    generating.value = false
  }
}

/* ---- 跳转：诊断 / 面试（带 JD） ---- */
function diagnoseWith(j) {
  if (!j.jd || j.jd.trim().length < 20) {
    Message.warning('该岗位缺少完整 JD，请先编辑补全')
    return
  }
  router.push({ path: '/app/analyze', query: { jd: j.jd } })
}

function interviewWith(j) {
  if (!j.jd || j.jd.trim().length < 20) {
    Message.warning('该岗位缺少完整 JD，请先编辑补全')
    return
  }
  router.push(`/app/interview?jd=${encodeURIComponent(j.jd)}`)
}

/* ---- M60 面试日程徽标 + ?focus 深链定位（工作台「去跟进」跳转） ---- */
// 徽标日期 M/D
function fmtBadgeDate(iso) {
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()}`
}
// 今天/明天临近 → accent 强调
function interviewSoon(iso) {
  const d = new Date(iso); d.setHours(0, 0, 0, 0)
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const diff = Math.round((d - today) / 86400000)
  return diff >= 0 && diff <= 1
}

const focusJobId = ref(null)

async function applyFocus() {
  const fid = Number(route.query.focus)
  if (!fid) return
  // 用后即清（对齐 onboarding 清 query 惯例，防刷新重触发）
  router.replace({ query: { ...route.query, focus: undefined } })
  await nextTick()
  const el = document.getElementById(`job-card-${fid}`)
  if (!el) return  // 岗位不存在/被筛选隐藏：静默跳过
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  focusJobId.value = fid
  setTimeout(() => { if (focusJobId.value === fid) focusJobId.value = null }, 2000)
}

function onEscKey(e) {
  if (e.key !== 'Escape') return
  if (applyJob.value) closeApply()
  else if (formOpen.value) closeForm()
  else if (importOpen.value) closeImport()
}

onMounted(async () => {
  await loadAll()
  applyFocus()
  // M51 旧版收藏检测（有则显示迁移横幅）
  legacyFavs.value = loadFavorites()
  window.addEventListener('keydown', onEscKey)
})

onUnmounted(() => window.removeEventListener('keydown', onEscKey))
</script>
