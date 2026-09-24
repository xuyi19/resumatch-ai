<template>
  <div class="min-h-screen">

    <!-- 屏幕界面 -->
    <div class="editor-screen">

      <!-- 顶部工具条 -->
      <div class="sticky top-0 z-40 bg-panel/95 backdrop-blur border-b border-line">
        <div class="max-w-[1400px] mx-auto px-6 py-3 flex items-center justify-between gap-4">
          <div class="flex items-center gap-4">
            <RouterLink v-if="taskId" :to="`/app/result/${taskId}`"
            class="text-sm text-ink-sub hover:text-accent transition-colors">
            ← 返回报告
          </RouterLink>
          <div v-if="taskId" class="w-px h-5 bg-line-strong/60"></div>
          <h1 class="text-base font-semibold text-ink">
            {{ taskId ? '简历编辑' : '创建简历' }}
          </h1>
          </div>

          <div class="flex items-center gap-3">
            <select v-model="currentTemplate"
              class="px-3 py-2 text-sm rounded-lg bg-inset border border-line text-ink
                focus:outline-none focus:border-accent transition-colors">
              <option v-for="t in templateList" :key="t.id" :value="t.id">
                {{ t.name }} · {{ t.desc }}
              </option>
            </select>

            <button @click="saveToLibrary" :disabled="savingToLibrary"
              class="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg
                bg-accent text-white hover:bg-accent-hover
                disabled:opacity-50 transition-colors">
              {{ savingToLibrary ? '保存中...' : '⭐ 保存到简历库' }}
            </button>

            <button @click="downloadWord" :disabled="downloading"
              class="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg
                bg-panel border border-line text-ink-sub
                hover:border-line-strong hover:text-ink
                disabled:opacity-50 transition-colors">
              📄 {{ downloading ? '生成中...' : '下载 Word' }}
            </button>

            <button @click="openHistory"
              class="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg
                bg-panel border border-line text-ink-sub
                hover:border-line-strong hover:text-ink
                transition-colors">
              🗂 导出历史
            </button>

            <button @click="downloadPdf"
              class="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg
                bg-accent text-white hover:bg-accent-hover
                transition-colors">
              🖨 下载 PDF
            </button>
          </div>
        </div>
      </div>

      <!-- 主体 -->
      <div class="max-w-[1400px] mx-auto px-6 py-6 grid grid-cols-[380px_1fr] gap-6">

        <!-- 左侧表单 -->
        <div class="space-y-4 editor-panel">

          <!-- F3 简历快速体检：纯规则实时检查 -->
          <div class="bg-panel border border-line rounded-lg p-5">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-2">
                <span class="text-base">🩺</span>
                <span class="text-sm font-semibold text-ink">快速体检</span>
              </div>
              <span class="text-xs font-mono"
                :class="healthBad ? 'text-bad' : 'text-ok'">
                {{ healthBad ? `${healthBad} 项硬伤` : '无硬伤' }}
              </span>
            </div>
            <ul v-if="healthIssues.length" class="space-y-1.5">
              <li v-for="(it, i) in healthIssues" :key="i" class="flex items-start gap-2 text-xs">
                <span :class="it.level === 'bad' ? 'text-bad' : 'text-warn'" class="shrink-0">
                  {{ it.level === 'bad' ? '✕' : '!' }}
                </span>
                <span class="text-ink-sub leading-relaxed">{{ it.msg }}</span>
              </li>
            </ul>
            <div v-else class="text-xs text-ok">各项检查通过，可放心导出</div>
          </div>

          <!-- 基本信息 -->
          <div class="bg-panel border border-line rounded-lg p-5">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <span class="text-base">👤</span>
                <span class="text-sm font-semibold text-ink">基本信息</span>
              </div>
              <!-- 证件照：上传后嵌入导出的 Word（右上角一寸照位） -->
              <div class="flex items-center gap-3">
                <div v-if="photoUrl"
                  class="relative w-[64px] h-[86px] rounded-lg overflow-hidden border border-line">
                  <img :src="photoUrl" class="w-full h-full object-cover" alt="证件照" />
                  <button @click="removePhoto"
                    class="absolute inset-x-0 bottom-0 bg-black/50 text-white text-[10px] py-0.5">
                    移除
                  </button>
                </div>
                <label v-else
                  class="w-[64px] h-[86px] rounded-lg border border-dashed border-line-strong
                    flex flex-col items-center justify-center cursor-pointer text-ink-faint
                    hover:text-accent hover:border-accent transition-colors">
                  <span class="text-lg leading-none">📷</span>
                  <span class="text-[10px] mt-1">证件照</span>
                  <input type="file" accept="image/jpeg,image/png" class="hidden"
                    @change="onPhotoChange" />
                </label>
                <div v-if="photoUploading" class="text-xs text-ink-faint">上传中…</div>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="text-xs text-ink-sub block mb-1">姓名</label>
                <input v-model="data.name" class="w-full px-3 py-2 text-sm rounded-lg bg-inset border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
              </div>
              <div>
                <label class="text-xs text-ink-sub block mb-1">求职意向</label>
                <input v-model="data.job_intention" class="w-full px-3 py-2 text-sm rounded-lg bg-inset border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
              </div>
              <div>
                <label class="text-xs text-ink-sub block mb-1">电话</label>
                <input v-model="data.phone" class="w-full px-3 py-2 text-sm rounded-lg bg-inset border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
              </div>
              <div>
                <label class="text-xs text-ink-sub block mb-1">邮箱</label>
                <input v-model="data.email" class="w-full px-3 py-2 text-sm rounded-lg bg-inset border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
              </div>
              <div>
                <label class="text-xs text-ink-sub block mb-1">微信</label>
                <input v-model="data.wechat" class="w-full px-3 py-2 text-sm rounded-lg bg-inset border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
              </div>
              <div>
                <label class="text-xs text-ink-sub block mb-1">现居地</label>
                <input v-model="data.location" class="w-full px-3 py-2 text-sm rounded-lg bg-inset border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
              </div>
            </div>
            <div class="mt-3">
              <label class="text-xs text-ink-sub block mb-1">个人简介</label>
              <textarea v-model="data.summary" rows="3" class="w-full px-3 py-2 text-sm rounded-lg bg-inset border border-line text-ink resize-none focus:outline-none focus:border-accent transition-colors"></textarea>
            </div>
          </div>

          <!-- 教育背景 -->
          <div class="bg-panel border border-line rounded-lg p-5">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <span class="text-base">🎓</span>
                <span class="text-sm font-semibold text-ink">教育背景</span>
              </div>
              <button @click="addEducation" class="w-7 h-7 rounded-lg bg-accent/10 text-accent text-sm font-bold hover:bg-accent/20 transition-colors">+</button>
            </div>
            <div v-for="(edu, i) in data.education" :key="i" class="p-3 rounded-lg bg-inset border border-line mb-3">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs text-ink-faint font-mono">#{{ i + 1 }}</span>
                <button @click="data.education.splice(i, 1)" class="text-xs text-ink-faint hover:text-bad transition-colors">删除</button>
              </div>
              <div class="grid grid-cols-2 gap-2">
                <input v-model="edu.school" placeholder="学校" class="px-2 py-1.5 text-xs rounded-md bg-panel border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
                <input v-model="edu.major" placeholder="专业" class="px-2 py-1.5 text-xs rounded-md bg-panel border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
                <input v-model="edu.degree" placeholder="学历" class="px-2 py-1.5 text-xs rounded-md bg-panel border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
                <input v-model="edu.time" placeholder="2017-2021" class="px-2 py-1.5 text-xs rounded-md bg-panel border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
              </div>
              <input v-model="edu.courses" placeholder="主修课程" class="w-full mt-2 px-2 py-1.5 text-xs rounded-md bg-panel border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
            </div>
            <div v-if="!data.education?.length" class="text-xs text-ink-faint text-center py-3">暂无，点 + 添加</div>
          </div>

          <!-- 工作经历 -->
          <div class="bg-panel border border-line rounded-lg p-5">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <span class="text-base">💼</span>
                <span class="text-sm font-semibold text-ink">工作经历</span>
              </div>
              <button @click="addExperience" class="w-7 h-7 rounded-lg bg-accent/10 text-accent text-sm font-bold hover:bg-accent/20 transition-colors">+</button>
            </div>
            <div v-for="(exp, i) in data.experience" :key="i" class="p-3 rounded-lg bg-inset border border-line mb-3">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs text-ink-faint font-mono">#{{ i + 1 }}</span>
                <button @click="data.experience.splice(i, 1)" class="text-xs text-ink-faint hover:text-bad transition-colors">删除</button>
              </div>
              <div class="grid grid-cols-2 gap-2">
                <input v-model="exp.company" placeholder="公司" class="px-2 py-1.5 text-xs rounded-md bg-panel border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
                <input v-model="exp.position" placeholder="职位" class="px-2 py-1.5 text-xs rounded-md bg-panel border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
                <input v-model="exp.time" placeholder="2021.07-2024.07" class="col-span-2 px-2 py-1.5 text-xs rounded-md bg-panel border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
              </div>
              <textarea v-model="exp.desc" rows="3" placeholder="工作描述（每行一条）" class="w-full mt-2 px-2 py-1.5 text-xs rounded-md bg-panel border border-line text-ink resize-none placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors"></textarea>
            </div>
            <div v-if="!data.experience?.length" class="text-xs text-ink-faint text-center py-3">暂无，点 + 添加</div>
          </div>

          <!-- 项目经历 -->
          <div class="bg-panel border border-line rounded-lg p-5">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <span class="text-base">📦</span>
                <span class="text-sm font-semibold text-ink">项目经历</span>
              </div>
              <button @click="addProject" class="w-7 h-7 rounded-lg bg-accent/10 text-accent text-sm font-bold hover:bg-accent/20 transition-colors">+</button>
            </div>
            <div v-for="(proj, i) in data.projects" :key="i" class="p-3 rounded-lg bg-inset border border-line mb-3">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs text-ink-faint font-mono">#{{ i + 1 }}</span>
                <button @click="data.projects.splice(i, 1)" class="text-xs text-ink-faint hover:text-bad transition-colors">删除</button>
              </div>
              <div class="grid grid-cols-2 gap-2">
                <input v-model="proj.name" placeholder="项目名" class="px-2 py-1.5 text-xs rounded-md bg-panel border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
                <input v-model="proj.role" placeholder="角色" class="px-2 py-1.5 text-xs rounded-md bg-panel border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
                <input v-model="proj.time" placeholder="时间" class="col-span-2 px-2 py-1.5 text-xs rounded-md bg-panel border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
              </div>
              <textarea v-model="proj.desc" rows="3" placeholder="项目描述（每行一条）" class="w-full mt-2 px-2 py-1.5 text-xs rounded-md bg-panel border border-line text-ink resize-none placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors"></textarea>
            </div>
            <div v-if="!data.projects?.length" class="text-xs text-ink-faint text-center py-3">暂无，点 + 添加</div>
          </div>

          <!-- 技能 -->
          <div class="bg-panel border border-line rounded-lg p-5">
            <div class="flex items-center gap-2 mb-4">
              <span class="text-base">⚡</span>
              <span class="text-sm font-semibold text-ink">专业技能</span>
            </div>
            <div class="flex flex-wrap gap-2 mb-3">
              <span v-for="(s, i) in data.skills" :key="i" class="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-xs bg-accent/10 text-accent">
                {{ s }}
                <button @click="data.skills.splice(i, 1)" class="text-accent/60 hover:text-bad ml-1 transition-colors">×</button>
              </span>
            </div>
            <div class="flex gap-2">
              <input v-model="newSkill" @keyup.enter="addSkill" placeholder="输入技能后回车" class="flex-1 px-3 py-2 text-sm rounded-lg bg-inset border border-line text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors" />
              <button @click="addSkill" class="px-3 py-2 text-sm rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors">+</button>
            </div>
          </div>

          <!-- 证书 -->
          <div class="bg-panel border border-line rounded-lg p-5">
            <div class="flex items-center gap-2 mb-4">
              <span class="text-base">🏆</span>
              <span class="text-sm font-semibold text-ink">证书荣誉</span>
            </div>
            <textarea v-model="certText" rows="4" placeholder="每行一条" class="w-full px-3 py-2 text-sm rounded-lg bg-inset border border-line text-ink resize-none placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors"></textarea>
          </div>

        </div>

        <!-- 右侧预览（真实渲染导出的 Word 文件，与下载版式完全一致） -->
        <div class="preview-area">
          <div class="sticky top-24">
            <div class="bg-inset border border-line rounded-lg p-6 overflow-auto max-h-[calc(100vh-120px)]">
              <div class="text-xs text-ink-sub mb-3 text-center">
                预览即导出效果 · 实时渲染 Word 文件
              </div>
              <div class="relative">
                <div ref="docxBox" v-show="!previewError" class="docx-preview-box shadow-2xl mx-auto w-fit"></div>
                <div v-if="previewLoading" class="absolute inset-0 flex items-center justify-center text-xs text-ink-sub pointer-events-none">
                  排版生成中…
                </div>
                <div v-else-if="previewError" class="text-center text-xs text-bad py-8">{{ previewError }}</div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>

  </div>

  <!-- 打印专用区域：优先直印 docx 预览 DOM（打印=预览=导出三者一致），失败回落 HTML 模板 -->
  <Teleport to="body">
    <div class="print-root">
      <div v-if="printHtml" v-html="printHtml"></div>
      <ResumePreview v-else :data="data" :template="currentTemplate" :photo-url="photoUrl" />
    </div>
  </Teleport>

  <!-- 导出历史弹层 -->
  <Teleport to="body">
    <div v-if="showHistory" class="fixed inset-0 z-[100] flex items-center justify-center bg-black/40"
      @click.self="showHistory = false">
      <div class="w-[560px] max-w-[92vw] max-h-[70vh] flex flex-col rounded-lg bg-panel border border-line shadow-xl">
        <div class="flex items-center justify-between px-5 py-4 border-b border-line">
          <h3 class="text-base font-semibold text-ink">导出历史</h3>
          <button @click="showHistory = false" class="text-ink-sub hover:text-ink text-lg leading-none transition-colors">✕</button>
        </div>
        <div class="flex-1 overflow-y-auto px-5 py-3">
          <LoadingBlock v-if="historyLoading" text="加载中..." />
          <EmptyState v-else-if="!historyItems.length"
            title="暂无导出记录"
            desc="点击「下载 Word」后会出现在这里" />
          <div v-for="h in historyItems" :key="h.id"
            class="flex items-center justify-between gap-3 py-3 border-b border-line last:border-0">
            <div class="min-w-0">
              <div class="text-sm font-medium text-ink truncate">{{ h.filename }}</div>
              <div class="text-xs text-ink-sub mt-0.5 truncate">
                <span class="font-mono">{{ formatTime(h.created_at) }}</span><template v-if="h.save_path"> · {{ h.save_path }}</template>
                <template v-else> · 浏览器下载</template>
              </div>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <button v-if="h.save_path && desktopReady" @click="revealHistoryFile(h.save_path)"
                class="px-3 py-1.5 text-xs rounded-lg text-accent
                  hover:bg-accent/10 transition-colors">
                打开位置
              </button>
              <button @click="removeHistory(h.id)"
                class="px-3 py-1.5 text-xs rounded-lg text-ink-faint
                  hover:text-bad hover:bg-bad/10 transition-colors">
                删除
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { renderAsync } from 'docx-preview'
import api from '../api'
import { checkResume } from '../utils/checker'
import ResumePreview from '../components/ResumePreview.vue'
import EmptyState from '../components/EmptyState.vue'
import LoadingBlock from '../components/LoadingBlock.vue'

const route = useRoute()
// 支持两种模式：/editor/:taskId（诊断/对话优化后进入，读取任务数据）
// 与 /editor（独立创建简历：空白起步，编辑内容自动存 localStorage）
const taskId = route.params.taskId || ''

const STORAGE_KEY = `resume_edit_${taskId || 'blank'}`
const SESSION_KEY = `resume_optimized_${taskId || 'blank'}`

const currentTemplate = ref('classic')
const downloading = ref(false)

// ---- F1：保存到简历库（结构化编辑数据 → 纯文本入库，可从简历库直接发起诊断） ----
const savingToLibrary = ref(false)

// F3 快速体检：随编辑实时刷新
const healthIssues = computed(() => checkResume(data.value))
const healthBad = computed(() => healthIssues.value.filter((i) => i.level === 'bad').length)

function buildPlainText() {
  const d = data.value
  const lines = []
  if (d.name) lines.push(d.name)
  if (d.job_intention) lines.push(`求职意向：${d.job_intention}`)
  const contacts = [
    d.phone && `电话：${d.phone}`,
    d.email && `邮箱：${d.email}`,
    d.wechat && `微信：${d.wechat}`,
    d.location && `现居：${d.location}`,
  ].filter(Boolean)
  if (contacts.length) lines.push(contacts.join(' | '))
  if (d.summary) lines.push(`\n个人总结\n${d.summary}`)
  if (d.education?.length) {
    lines.push('\n教育背景')
    d.education.forEach((e) => {
      lines.push([e.time, e.school, e.major, e.degree].filter(Boolean).join(' | '))
    })
  }
  if (d.experience?.length) {
    lines.push('\n工作经历')
    d.experience.forEach((e) => {
      lines.push([e.time, e.company, e.position].filter(Boolean).join(' | '))
      if (e.desc) lines.push(e.desc)
    })
  }
  if (d.projects?.length) {
    lines.push('\n项目经历')
    d.projects.forEach((p) => {
      lines.push([p.time, p.name, p.role].filter(Boolean).join(' | '))
      if (p.desc) lines.push(p.desc)
    })
  }
  if (d.skills?.length) lines.push(`\n技能\n${d.skills.join('、')}`)
  if (d.certificates?.length) lines.push(`\n证书\n${d.certificates.join('、')}`)
  return lines.join('\n')
}

async function saveToLibrary() {
  const text = buildPlainText().trim()
  if (text.length < 50) {
    Message.warning('简历内容太少（至少 50 字），请先填写完整再保存')
    return
  }
  savingToLibrary.value = true
  const name = `${data.value.name || '未命名'}的简历.txt`
  try {
    // M44 版本链：同名简历已存在则追加版本（不重复堆简历），否则新建
    const listRes = await api.listResumes()
    const same = (listRes.data || []).find((r) => r.filename === name)
    if (same) {
      const res = await api.saveResumeVersion(same.id, text)
      Message.success(
        res.data.updated
          ? `已更新「${name}」（v${res.data.version_count}），可在简历库查看版本对比`
          : `内容与「${name}」当前版本相同，无需保存`,
      )
    } else {
      const res = await api.uploadResumeText({ filename: name, text })
      Message.success(`已保存到简历库（#${res.data.id}），可在简历库一键发起诊断`)
    }
  } catch (e) {
    Message.error(e.response?.data?.detail || '保存失败')
  } finally {
    savingToLibrary.value = false
  }
}
const newSkill = ref('')
const certText = ref('')

// ---- docx 实时预览 ----
const docxBox = ref(null)
const previewLoading = ref(false)
const previewError = ref('')
let previewSeq = 0
let previewTimer = null

// ---- 导出（双形态）+ 导出历史 ----
// 桌面形态：原生「另存为」选路径 → 服务端直写（保存位置明确）
// 网页形态：浏览器 blob 下载（下载目录由浏览器管理）
const printHtml = ref('')          // PDF 打印内容：docx 预览 DOM 快照
const showHistory = ref(false)
const historyItems = ref([])
const historyLoading = ref(false)
const desktopReady = !!window.pywebview?.api?.pick_save_path

// ---- 模板目录（后端下发，失败时用内置兜底） ----
const templateList = ref([
  { id: 'classic', name: '经典居中', desc: '稳重通用' },
  { id: 'sidebar', name: '侧栏双栏', desc: '推荐配照片' },
  { id: 'business', name: '商务蓝', desc: '国企外企风' },
  { id: 'elegant', name: '典雅衬线', desc: '庄重雅致' },
  { id: 'modern', name: '现代竖标', desc: '简洁活力' },
  { id: 'minimal', name: '极简黑白', desc: '技术设计岗' },
  { id: 'academic', name: '学术衬线', desc: '高校科研' },
  { id: 'creative', name: '活力橙', desc: '运营市场' },
  { id: 'twocol', name: '单行页眉', desc: '节省空间' },
  { id: 'compact', name: '紧凑单页', desc: '内容多' },
])

// ---- 证件照 ----
const photoUrl = ref('')       // 本地预览
const photoId = ref('')        // 上传成功后的服务端 ID
const photoUploading = ref(false)

async function onPhotoChange(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  if (!['image/jpeg', 'image/png'].includes(file.type)) {
    Message.error('仅支持 JPG / PNG 格式照片')
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    Message.error('照片不能超过 5MB')
    return
  }
  photoUploading.value = true
  try {
    // 先本地预览，再上传拿 photo_id（导出时随请求带上）
    if (photoUrl.value) URL.revokeObjectURL(photoUrl.value)
    photoUrl.value = URL.createObjectURL(file)
    const res = await api.uploadPhoto(file)
    photoId.value = res.data.photo_id
    Message.success('照片已就绪，导出 Word 时自动嵌入')
  } catch (err) {
    photoUrl.value = ''
    photoId.value = ''
    Message.error('照片上传失败：' + (err.response?.data?.detail || err.message))
  } finally {
    photoUploading.value = false
  }
}

async function removePhoto() {
  if (photoUrl.value) URL.revokeObjectURL(photoUrl.value)
  const oldId = photoId.value
  photoUrl.value = ''
  photoId.value = ''
  if (oldId) {
    try { await api.deletePhoto(oldId) } catch (e) { /* 静默清理 */ }
  }
}

const data = ref({
  name: '',
  job_intention: '',
  phone: '',
  email: '',
  wechat: '',
  location: '',
  summary: '',
  education: [],
  experience: [],
  projects: [],
  skills: [],
  certificates: [],
})

watch(certText, (v) => {
  data.value.certificates = v.split('\n').map(s => s.trim()).filter(Boolean)
})

watch(() => data.value.certificates, (v) => {
  const joined = (v || []).join('\n')
  if (joined !== certText.value) certText.value = joined
})

/**
 * ★ 智能解析教育/工作/项目字符串行
 * 输入示例：
 *   "2017.09-2021.06 河海大学 新闻传播学 硕士"
 *   "2021.07 - 2024.07 某互联网公司 后端开发工程师"
 * 输出：结构化的对象
 */
function parseLine(line, type) {
  if (!line) return null
  // 匹配时间格式
  const timePatterns = [
    /(\d{4}[.\-/]\d{1,2}\s*[-—~]\s*\d{4}[.\-/]\d{1,2})/,
    /(\d{4}\s*[-—~]\s*\d{4})/,
    /(\d{4}[.\-/]\d{1,2}\s*[-—~]\s*(?:至今|现在|今))/,
  ]
  let time = ''
  for (const p of timePatterns) {
    const m = line.match(p)
    if (m) { time = m[0].trim(); break }
  }

  let rest = time ? line.replace(time, '').trim() : line
  rest = rest.replace(/^[\s,，、\-—~]+/, '').trim()

  const parts = rest.split(/\s+/).filter(Boolean)

  if (type === 'education') {
    return {
      school: parts[0] || '',
      major: parts[1] || '',
      degree: parts[2] || '',
      time,
      courses: '',
    }
  }
  if (type === 'experience') {
    return {
      company: parts[0] || '',
      position: parts.slice(1).join(' ') || '',
      time,
      desc: '',
    }
  }
  if (type === 'projects') {
    return {
      name: parts[0] || '',
      role: parts.slice(1).join(' ') || '',
      time,
      desc: '',
    }
  }
  return null
}

/**
 * 兼容后端返回的多种格式：
 * A. ["2017.09-2021.06 XX大学 计算机 本科"]
 * B. [{school: "...", major: "..."}]
 * C. ["2017.09-2021.06 XX大学 计算机 本科\n- 主修课程：xxx"]
 */
function normalizeArray(arr, type) {
  if (!Array.isArray(arr)) return []
  const result = []
  for (const item of arr) {
    if (typeof item === 'object' && item !== null) {
      // 已经是对象
      result.push({
        school: item.school || '',
        company: item.company || '',
        name: item.name || '',
        major: item.major || '',
        position: item.position || '',
        role: item.role || '',
        degree: item.degree || '',
        time: item.time || '',
        courses: item.courses || '',
        desc: item.desc || '',
      })
    } else if (typeof item === 'string') {
      // 字符串 → 解析
      const lines = item.split('\n').filter(l => l.trim())
      const firstLine = lines[0] || ''
      const descLines = lines.slice(1).map(l => l.replace(/^[-•·]\s*/, '').trim())
      const parsed = parseLine(firstLine, type)
      if (parsed) {
        parsed.desc = descLines.join('\n') || parsed.desc || ''
        parsed.courses = parsed.courses || ''
        result.push(parsed)
      }
    }
  }
  return result
}

async function loadData() {
  console.log('[Editor] 开始加载数据, taskId =', taskId)

  // ========== 第 1 层：localStorage（用户编辑过的）==========
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      const hasData = parsed.name || parsed.phone || parsed.summary ||
                      parsed.education?.length || parsed.experience?.length ||
                      parsed.projects?.length || parsed.skills?.length
      if (hasData) {
        Object.assign(data.value, parsed)
        certText.value = (data.value.certificates || []).join('\n')
        console.log('[Editor] 从 localStorage 恢复', data.value)
        return
      }
    }
  } catch (e) {
    console.warn('[Editor] localStorage 加载失败', e)
  }

  // 独立创建模式（/editor）：空白起步即可编辑，不拉取任何任务数据
  if (!taskId) return

  // ========== 第 2 层：sessionStorage（刚从 ChatView 生成过来）==========
  let opt = null
  try {
    const cached = sessionStorage.getItem(SESSION_KEY)
    if (cached) {
      opt = JSON.parse(cached)
      console.log('[Editor] 从 sessionStorage 拿到数据', opt)
    }
  } catch (e) {
    console.warn('[Editor] sessionStorage 加载失败', e)
  }

  // ========== 第 3 层：后端 /chat/history（对话生成的结果）==========
  if (!opt) {
    try {
      const res = await api.getChatHistory(taskId)
      console.log('[Editor] /chat/history 返回', res.data)
      if (res.data?.exists && res.data.optimized_resume) {
        opt = res.data.optimized_resume
        console.log('[Editor] 从 /chat/history 拿到数据')
      }
    } catch (e) {
      console.warn('[Editor] /chat/history 加载失败', e)
    }
  }

  // ========== 第 4 层：后端 /history（一键优化的兜底）==========
  if (!opt) {
    try {
      const res = await api.getHistoryDetail(taskId)
      const fallback = res.data?.result?.diagnosis?.optimized_resume
      if (fallback) {
        opt = fallback
        console.log('[Editor] 从 /history 拿到数据')
      }
    } catch (e) {
      console.warn('[Editor] /history 加载失败', e)
    }
  }

  // ========== 数据都拿不到 ==========
  if (!opt) {
    console.warn('[Editor] 所有数据源都没有 optimized_resume')
    Message.warning('尚未生成优化简历，请先返回报告页生成')
    return
  }

  // ========== 应用到 data ==========
  data.value.name = opt.name || ''
  data.value.job_intention = opt.job_intention || ''
  data.value.phone = opt.contact || opt.phone || ''
  data.value.email = opt.email || ''
  data.value.wechat = opt.wechat || ''
  data.value.location = opt.location || ''
  data.value.summary = opt.summary || ''

  // 智能映射：兼容字符串数组和对象数组
  data.value.education = normalizeArray(opt.education, 'education')
  data.value.experience = normalizeArray(opt.experience, 'experience')
  data.value.projects = normalizeArray(opt.projects, 'projects')
  data.value.skills = Array.isArray(opt.skills) ? [...opt.skills] : []
  data.value.certificates = Array.isArray(opt.certificates) ? [...opt.certificates] : []

  certText.value = data.value.certificates.join('\n')

  console.log('[Editor] 数据映射完成', data.value)
}

// 防抖自动保存
let saveTimer = null
watch(data, () => {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data.value)) } catch (e) {}
  }, 500)
}, { deep: true })

function addEducation() {
  data.value.education.push({ school: '', major: '', degree: '', time: '', courses: '' })
}
function addExperience() {
  data.value.experience.push({ company: '', position: '', time: '', desc: '' })
}
function addProject() {
  data.value.projects.push({ name: '', role: '', time: '', desc: '' })
}
function addSkill() {
  const v = newSkill.value.trim()
  if (!v) return
  if (!data.value.skills.includes(v)) data.value.skills.push(v)
  newSkill.value = ''
}

function downloadPdf() {
  // 直印 docx 预览 DOM：打印输出与预览/导出的 Word 版式完全一致（含照片、分页）。
  // 预览尚未就绪时回落 ResumePreview HTML 模板。
  printHtml.value = docxBox.value?.innerHTML || ''
  setTimeout(async () => {
    window.print()
    await nextTick()
    setTimeout(() => { printHtml.value = '' }, 300)
  }, 150)
}

// 编辑器数据 → Word 生成器入参（预览与导出共用同一份转换，保证版式一致）
function buildWordData() {
  const contacts = [
    data.value.phone && `电话：${data.value.phone}`,
    data.value.email && `邮箱：${data.value.email}`,
    data.value.wechat && `微信：${data.value.wechat}`,
    data.value.location && `现居：${data.value.location}`,
  ].filter(Boolean)

  return {
    name: data.value.name,
    job_intention: data.value.job_intention,
    contacts,
    contact: contacts.join(' | '),
    summary: data.value.summary,
    education: data.value.education.map(e =>
      [e.time, e.school, e.major, e.degree].filter(Boolean).join(' ')
    ),
    experience: data.value.experience.flatMap(e => [
      [e.time, e.company, e.position].filter(Boolean).join(' '),
      ...(e.desc || '').split('\n').map(l => l.trim()).filter(Boolean),
    ]),
    projects: data.value.projects.flatMap(p => [
      [p.time, p.name, p.role].filter(Boolean).join(' '),
      ...(p.desc || '').split('\n').map(l => l.trim()).filter(Boolean),
    ]),
    skills: data.value.skills,
    certificates: data.value.certificates,
  }
}

async function renderDocxPreview() {
  if (!docxBox.value) return
  const seq = ++previewSeq
  previewLoading.value = true
  try {
    const res = await api.exportDocx({
      optimized_resume: buildWordData(),
      template: currentTemplate.value,
      photo_id: photoId.value || undefined,
    })
    if (seq !== previewSeq) return // 已有更新请求，丢弃过期结果
    const container = docxBox.value
    container.innerHTML = ''
    await renderAsync(res.data, container, undefined, {
      inWrapper: true,
      useBase64URL: true,
    })
    if (seq !== previewSeq) return
    previewError.value = ''
  } catch (e) {
    if (seq === previewSeq) previewError.value = '预览生成失败：' + (e?.message || e)
  } finally {
    if (seq === previewSeq) previewLoading.value = false
  }
}

// 编辑内容 / 模板 / 照片变化 → 防抖重新生成预览
watch([data, currentTemplate, photoId], () => {
  clearTimeout(previewTimer)
  previewTimer = setTimeout(renderDocxPreview, 600)
}, { deep: true })

async function downloadWord() {
  downloading.value = true
  const payload = {
    optimized_resume: buildWordData(),
    template: currentTemplate.value,
    photo_id: photoId.value || undefined,
  }
  try {
    // 桌面形态：原生「另存为」选路径 → 服务端直写，保存位置明确可见
    const bridge = window.pywebview?.api
    if (bridge?.pick_save_path) {
      const savePath = await bridge.pick_save_path(`${data.value.name || '简历'}.docx`)
      if (!savePath) return // 用户取消
      const res = await api.exportDocxToPath({ ...payload, save_path: savePath })
      Message.success(`已保存到：${res.data?.saved_to || savePath}`)
      return
    }
    // 网页形态：浏览器 blob 下载
    const res = await api.exportDocx(payload)
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${data.value.name || '简历'}.docx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    Message.success('Word 已下载（见浏览器下载目录）')
  } catch (e) {
    const detail = e?.response?.data?.detail || e.message
    console.error(e)
    Message.error('导出失败：' + detail)
  } finally {
    downloading.value = false
  }
}

// ---- 导出历史 ----
async function openHistory() {
  showHistory.value = true
  historyLoading.value = true
  try {
    const res = await api.listExportHistory()
    historyItems.value = res.data?.items || []
  } catch (e) {
    Message.error('获取导出历史失败')
  } finally {
    historyLoading.value = false
  }
}

async function revealHistoryFile(path) {
  const ok = await window.pywebview?.api?.reveal_file(path)
  if (!ok) Message.error('文件不存在或已被移动')
}

async function removeHistory(id) {
  try {
    await api.deleteExportHistory(id)
    historyItems.value = historyItems.value.filter(h => h.id !== id)
  } catch (e) {
    Message.error('删除失败')
  }
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

onMounted(() => {
  loadData()
  // 模板目录以后端为准（与 Word 导出实现保持同步）
  api.listTemplates().then(res => {
    if (res.data?.items?.length) templateList.value = res.data.items
  }).catch(() => { /* 用内置兜底列表 */ })
  // 首次预览渲染（数据加载后 watch 会再触发刷新）
  renderDocxPreview()
  // M50：诊断报告「应用」来的改写建议待应用清单
  checkApplyQueue()
})

/* ---- M50 改写建议一键采纳：从诊断报告跳转过来时应用待应用清单 ---- */
const APPLY_QUEUE_KEY = 'editor_apply_queue'

function readApplyQueue() {
  try { return JSON.parse(localStorage.getItem(APPLY_QUEUE_KEY) || '[]') } catch (e) { return [] }
}

function checkApplyQueue() {
  const queue = readApplyQueue()
  if (!queue.length) return
  Modal.confirm({
    title: '应用诊断改写建议？',
    content: `有 ${queue.length} 条来自诊断报告的改写建议待应用。将按内容类型追加到对应分区（工作/项目/技能/简介），追加后请人工核对位置并补全时间、主体等信息。`,
    okText: `应用 ${queue.length} 条`,
    cancelText: '暂不应用',
    onOk: () => applyQueue(queue),
  })
}

function applyQueue(queue) {
  let nExp = 0; let nPrj = 0; let nSkill = 0; let nCert = 0; let nSum = 0
  for (const q of queue) {
    const t = (q.target || '')
    const text = (q.rewritten || '').trim()
    if (!text) continue
    if (t.includes('技能')) {
      // 改写后的技能串按常见分隔符拆词追加，去重
      const words = text.split(/[、,，;；·|\s/]+/).map((w) => w.trim()).filter(Boolean)
      for (const w of words) {
        if (!data.value.skills.includes(w)) data.value.skills.push(w)
      }
      nSkill++
    } else if (t.includes('证书')) {
      for (const line of text.split(/[;；\n]+/).map((s) => s.trim()).filter(Boolean)) {
        if (!data.value.certificates.includes(line)) data.value.certificates.push(line)
      }
      nCert++
    } else if (t.includes('项目')) {
      data.value.projects.push({ time: '', name: '', role: '', desc: text })
      nPrj++
    } else if (t.includes('工作') || (t.includes('经历') && !t.includes('教育'))) {
      data.value.experience.push({ time: '', company: '', position: '', desc: text })
      nExp++
    } else {
      // 简介 / 教育 / 其他自由文本 → 追加到个人简介（教育为结构化字段，改写句不适合直接塞）
      data.value.summary = data.value.summary
        ? `${data.value.summary}\n${text}`
        : text
      nSum++
    }
  }
  try { localStorage.removeItem(APPLY_QUEUE_KEY) } catch (e) { /* 忽略 */ }
  const parts = []
  if (nExp) parts.push(`工作经历 ${nExp} 条`)
  if (nPrj) parts.push(`项目经历 ${nPrj} 条`)
  if (nSkill) parts.push(`技能 ${nSkill} 条`)
  if (nCert) parts.push(`证书 ${nCert} 条`)
  if (nSum) parts.push(`个人简介 ${nSum} 条`)
  Message.success(`已应用：${parts.join('、')}——请核对内容并补全时间、主体信息`)
}
</script>

<!-- 打印样式（全局） -->
<style>
/* docx 真实渲染预览 */
.docx-preview-box:empty {
  width: 210mm;
  min-height: 297mm;
}
.docx-preview-box .docx-wrapper {
  background: transparent;
  padding: 0;
}
.docx-preview-box .docx-wrapper > section.docx {
  margin-bottom: 16px;
}

.print-root {
  display: none;
}

@media print {
  @page { size: A4; margin: 0; }

  body > * { display: none !important; }
  body > .print-root { display: block !important; position: static !important; width: 100% !important; }

  html, body {
    background: #ffffff !important;
    margin: 0 !important;
    padding: 0 !important;
  }

  .print-root,
  .print-root * {
    box-shadow: none !important;
    border-radius: 0 !important;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }

  .print-root .page {
    width: 210mm !important;
    min-height: 297mm !important;
    margin: 0 auto !important;
    padding: 15mm 15mm !important;
  }

  .print-root .page.is-sidebar {
    padding: 0 !important;
  }

  .print-root .r-section,
  .print-root .r-item {
    page-break-inside: avoid;
  }

  /* docx 预览 DOM 直印适配：去灰底/阴影，按 Word 分页原样输出 */
  .print-root .docx-wrapper {
    background: #ffffff !important;
    padding: 0 !important;
  }
  .print-root .docx-wrapper > section.docx {
    margin: 0 auto !important;
  }
}
</style>
