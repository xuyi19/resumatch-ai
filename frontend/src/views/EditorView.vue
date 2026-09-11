<template>
  <div class="min-h-screen bg-[#e0e5ec]">

    <!-- 屏幕上显示的界面 -->
    <div class="editor-screen">

      <!-- 顶部工具条 -->
      <div class="sticky top-0 z-40 bg-[#e0e5ec] border-b border-[#b8bcc2]/30">
        <div class="max-w-[1400px] mx-auto px-6 py-3 flex items-center justify-between gap-4">
          <div class="flex items-center gap-4">
            <RouterLink :to="`/result/${taskId}`"
              class="text-sm text-gray-600 hover:text-[#6d5dfc] transition-colors">
              ← 返回报告
            </RouterLink>
            <div class="w-px h-5 bg-[#b8bcc2]/40"></div>
            <h1 class="text-base font-semibold text-gray-800">简历编辑</h1>
          </div>

          <div class="flex items-center gap-3">
            <select v-model="currentTemplate"
              class="px-3 py-2 text-sm rounded-xl bg-[#e0e5ec] border-0
                shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff]
                focus:outline-none">
              <option value="blue">蓝色专业</option>
            </select>

            <button @click="downloadWord" :disabled="downloading"
              class="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-xl
                bg-[#e0e5ec] text-gray-700
                shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
                hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
                disabled:opacity-50 transition-all duration-300">
              📄 {{ downloading ? '生成中...' : '下载 Word' }}
            </button>

            <button @click="downloadPdf"
              class="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-xl
                bg-[#6d5dfc] text-white
                shadow-[4px_4px_8px_#b8bcc2,-4px_-4px_8px_#ffffff]
                hover:shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]
                transition-all duration-300">
              🖨 下载 PDF
            </button>
          </div>
        </div>
      </div>

      <!-- 主体 -->
      <div class="max-w-[1400px] mx-auto px-6 py-6 grid grid-cols-[380px_1fr] gap-6">

        <!-- 左侧表单 -->
        <div class="space-y-4 editor-panel">

          <!-- 基本信息 -->
          <div class="bg-[#e0e5ec] rounded-2xl p-5 shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]">
            <div class="flex items-center gap-2 mb-4">
              <span class="text-base">👤</span>
              <span class="text-sm font-semibold text-gray-800">基本信息</span>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="text-xs text-gray-500 block mb-1">姓名</label>
                <input v-model="data.name" class="w-full px-3 py-2 text-sm rounded-xl bg-[#e0e5ec] border-0 shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] focus:outline-none" />
              </div>
              <div>
                <label class="text-xs text-gray-500 block mb-1">求职意向</label>
                <input v-model="data.job_intention" class="w-full px-3 py-2 text-sm rounded-xl bg-[#e0e5ec] border-0 shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] focus:outline-none" />
              </div>
              <div>
                <label class="text-xs text-gray-500 block mb-1">电话</label>
                <input v-model="data.phone" class="w-full px-3 py-2 text-sm rounded-xl bg-[#e0e5ec] border-0 shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] focus:outline-none" />
              </div>
              <div>
                <label class="text-xs text-gray-500 block mb-1">邮箱</label>
                <input v-model="data.email" class="w-full px-3 py-2 text-sm rounded-xl bg-[#e0e5ec] border-0 shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] focus:outline-none" />
              </div>
              <div>
                <label class="text-xs text-gray-500 block mb-1">微信</label>
                <input v-model="data.wechat" class="w-full px-3 py-2 text-sm rounded-xl bg-[#e0e5ec] border-0 shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] focus:outline-none" />
              </div>
              <div>
                <label class="text-xs text-gray-500 block mb-1">现居地</label>
                <input v-model="data.location" class="w-full px-3 py-2 text-sm rounded-xl bg-[#e0e5ec] border-0 shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] focus:outline-none" />
              </div>
            </div>
            <div class="mt-3">
              <label class="text-xs text-gray-500 block mb-1">个人简介</label>
              <textarea v-model="data.summary" rows="3" class="w-full px-3 py-2 text-sm rounded-xl bg-[#e0e5ec] border-0 resize-none shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] focus:outline-none"></textarea>
            </div>
          </div>

          <!-- 教育背景 -->
          <div class="bg-[#e0e5ec] rounded-2xl p-5 shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <span class="text-base">🎓</span>
                <span class="text-sm font-semibold text-gray-800">教育背景</span>
              </div>
              <button @click="addEducation" class="w-7 h-7 rounded-lg bg-[#e0e5ec] text-[#6d5dfc] text-sm font-bold shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]">+</button>
            </div>
            <div v-for="(edu, i) in data.education" :key="i" class="p-3 rounded-xl bg-[#e0e5ec] mb-3 shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs text-gray-400">#{{ i + 1 }}</span>
                <button @click="data.education.splice(i, 1)" class="text-xs text-gray-400 hover:text-red-500">删除</button>
              </div>
              <div class="grid grid-cols-2 gap-2">
                <input v-model="edu.school" placeholder="学校" class="px-2 py-1.5 text-xs rounded-lg bg-[#e0e5ec] border-0 shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff] focus:outline-none" />
                <input v-model="edu.major" placeholder="专业" class="px-2 py-1.5 text-xs rounded-lg bg-[#e0e5ec] border-0 shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff] focus:outline-none" />
                <input v-model="edu.degree" placeholder="学历" class="px-2 py-1.5 text-xs rounded-lg bg-[#e0e5ec] border-0 shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff] focus:outline-none" />
                <input v-model="edu.time" placeholder="2017-2021" class="px-2 py-1.5 text-xs rounded-lg bg-[#e0e5ec] border-0 shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff] focus:outline-none" />
              </div>
              <input v-model="edu.courses" placeholder="主修课程" class="w-full mt-2 px-2 py-1.5 text-xs rounded-lg bg-[#e0e5ec] border-0 shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff] focus:outline-none" />
            </div>
            <div v-if="!data.education?.length" class="text-xs text-gray-400 text-center py-3">暂无，点 + 添加</div>
          </div>

          <!-- 工作经历 -->
          <div class="bg-[#e0e5ec] rounded-2xl p-5 shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <span class="text-base">💼</span>
                <span class="text-sm font-semibold text-gray-800">工作经历</span>
              </div>
              <button @click="addExperience" class="w-7 h-7 rounded-lg bg-[#e0e5ec] text-[#6d5dfc] text-sm font-bold shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]">+</button>
            </div>
            <div v-for="(exp, i) in data.experience" :key="i" class="p-3 rounded-xl bg-[#e0e5ec] mb-3 shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs text-gray-400">#{{ i + 1 }}</span>
                <button @click="data.experience.splice(i, 1)" class="text-xs text-gray-400 hover:text-red-500">删除</button>
              </div>
              <div class="grid grid-cols-2 gap-2">
                <input v-model="exp.company" placeholder="公司" class="px-2 py-1.5 text-xs rounded-lg bg-[#e0e5ec] border-0 shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff] focus:outline-none" />
                <input v-model="exp.position" placeholder="职位" class="px-2 py-1.5 text-xs rounded-lg bg-[#e0e5ec] border-0 shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff] focus:outline-none" />
                <input v-model="exp.time" placeholder="2021.07-2024.07" class="col-span-2 px-2 py-1.5 text-xs rounded-lg bg-[#e0e5ec] border-0 shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff] focus:outline-none" />
              </div>
              <textarea v-model="exp.desc" rows="3" placeholder="工作描述（每行一条）" class="w-full mt-2 px-2 py-1.5 text-xs rounded-lg bg-[#e0e5ec] border-0 resize-none shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff] focus:outline-none"></textarea>
            </div>
            <div v-if="!data.experience?.length" class="text-xs text-gray-400 text-center py-3">暂无，点 + 添加</div>
          </div>

          <!-- 项目经历 -->
          <div class="bg-[#e0e5ec] rounded-2xl p-5 shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <span class="text-base">📦</span>
                <span class="text-sm font-semibold text-gray-800">项目经历</span>
              </div>
              <button @click="addProject" class="w-7 h-7 rounded-lg bg-[#e0e5ec] text-[#6d5dfc] text-sm font-bold shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]">+</button>
            </div>
            <div v-for="(proj, i) in data.projects" :key="i" class="p-3 rounded-xl bg-[#e0e5ec] mb-3 shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff]">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs text-gray-400">#{{ i + 1 }}</span>
                <button @click="data.projects.splice(i, 1)" class="text-xs text-gray-400 hover:text-red-500">删除</button>
              </div>
              <div class="grid grid-cols-2 gap-2">
                <input v-model="proj.name" placeholder="项目名" class="px-2 py-1.5 text-xs rounded-lg bg-[#e0e5ec] border-0 shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff] focus:outline-none" />
                <input v-model="proj.role" placeholder="角色" class="px-2 py-1.5 text-xs rounded-lg bg-[#e0e5ec] border-0 shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff] focus:outline-none" />
                <input v-model="proj.time" placeholder="时间" class="col-span-2 px-2 py-1.5 text-xs rounded-lg bg-[#e0e5ec] border-0 shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff] focus:outline-none" />
              </div>
              <textarea v-model="proj.desc" rows="3" placeholder="项目描述（每行一条）" class="w-full mt-2 px-2 py-1.5 text-xs rounded-lg bg-[#e0e5ec] border-0 resize-none shadow-[inset_2px_2px_4px_#b8bcc2,inset_-2px_-2px_4px_#ffffff] focus:outline-none"></textarea>
            </div>
            <div v-if="!data.projects?.length" class="text-xs text-gray-400 text-center py-3">暂无，点 + 添加</div>
          </div>

          <!-- 技能 -->
          <div class="bg-[#e0e5ec] rounded-2xl p-5 shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]">
            <div class="flex items-center gap-2 mb-4">
              <span class="text-base">⚡</span>
              <span class="text-sm font-semibold text-gray-800">专业技能</span>
            </div>
            <div class="flex flex-wrap gap-2 mb-3">
              <span v-for="(s, i) in data.skills" :key="i" class="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-xs bg-[#e0e5ec] text-gray-700 shadow-[2px_2px_4px_#b8bcc2,-2px_-2px_4px_#ffffff]">
                {{ s }}
                <button @click="data.skills.splice(i, 1)" class="text-gray-400 hover:text-red-500 ml-1">×</button>
              </span>
            </div>
            <div class="flex gap-2">
              <input v-model="newSkill" @keyup.enter="addSkill" placeholder="输入技能后回车" class="flex-1 px-3 py-2 text-sm rounded-xl bg-[#e0e5ec] border-0 shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] focus:outline-none" />
              <button @click="addSkill" class="px-3 py-2 text-sm rounded-xl bg-[#6d5dfc] text-white shadow-[3px_3px_6px_#b8bcc2,-3px_-3px_6px_#ffffff]">+</button>
            </div>
          </div>

          <!-- 证书 -->
          <div class="bg-[#e0e5ec] rounded-2xl p-5 shadow-[6px_6px_12px_#b8bcc2,-6px_-6px_12px_#ffffff]">
            <div class="flex items-center gap-2 mb-4">
              <span class="text-base">🏆</span>
              <span class="text-sm font-semibold text-gray-800">证书荣誉</span>
            </div>
            <textarea v-model="certText" rows="4" placeholder="每行一条" class="w-full px-3 py-2 text-sm rounded-xl bg-[#e0e5ec] border-0 resize-none shadow-[inset_3px_3px_6px_#b8bcc2,inset_-3px_-3px_6px_#ffffff] focus:outline-none"></textarea>
          </div>

        </div>

        <!-- 右侧预览 -->
        <div class="preview-area">
          <div class="sticky top-24">
            <div class="bg-[#d1d5db] rounded-2xl p-6 overflow-auto max-h-[calc(100vh-120px)]">
              <div class="shadow-2xl mx-auto">
                <ResumePreview :data="data" :template="currentTemplate" />
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>

  </div>

  <!-- ★ 打印专用区域：Teleport 到 body，只打印这一块 -->
  <Teleport to="body">
    <div class="print-root">
      <ResumePreview :data="data" :template="currentTemplate" />
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import api from '../api'
import ResumePreview from '../components/ResumePreview.vue'

const route = useRoute()
const taskId = route.params.taskId

const STORAGE_KEY = `resume_edit_${taskId}`

const currentTemplate = ref('blue')
const downloading = ref(false)
const newSkill = ref('')
const certText = ref('')

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

async function loadData() {
  // 1. localStorage 优先
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      // 只有非空数据才用 localStorage
      if (parsed.name || parsed.phone || parsed.education?.length || parsed.experience?.length) {
        Object.assign(data.value, parsed)
        certText.value = (data.value.certificates || []).join('\n')
        console.log('[Editor] 从 localStorage 加载成功', data.value)
        return
      }
    }
  } catch (e) {
    console.warn('[Editor] localStorage 加载失败', e)
  }

  // 2. 从后端拉
  try {
    const res = await api.getHistoryDetail(taskId)
    console.log('[Editor] 后端返回数据', res.data)

    const opt = res.data?.result?.diagnosis?.optimized_resume
    if (!opt) {
      console.warn('[Editor] 没有找到 optimized_resume，可能需要先生成优化简历')
      Message.warning('尚未生成优化简历，请先返回报告页生成')
      return
    }

    console.log('[Editor] 优化简历数据', opt)

    data.value.name = opt.name || ''
    data.value.job_intention = opt.job_intention || ''
    data.value.phone = opt.contact || ''
    data.value.email = ''
    data.value.wechat = ''
    data.value.location = ''
    data.value.summary = opt.summary || ''

    if (Array.isArray(opt.education)) {
      data.value.education = opt.education.map(line => ({
        school: typeof line === 'string' ? line : (line.school || ''),
        major: '', degree: '', time: '', courses: '',
      }))
    }
    if (Array.isArray(opt.experience)) {
      data.value.experience = opt.experience.map(line => ({
        company: typeof line === 'string' ? line : (line.company || ''),
        position: '', time: '', desc: '',
      }))
    }
    if (Array.isArray(opt.projects)) {
      data.value.projects = opt.projects.map(line => ({
        name: typeof line === 'string' ? line : (line.name || ''),
        role: '', time: '', desc: '',
      }))
    }
    if (Array.isArray(opt.skills)) {
      data.value.skills = [...opt.skills]
    }
  } catch (e) {
    console.error('[Editor] 加载失败', e)
    Message.error('加载简历数据失败：' + (e.response?.data?.detail || e.message))
  }
}

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
  // 给 Vue 一点时间确保 Teleport 渲染好
  setTimeout(() => {
    window.print()
  }, 150)
}

async function downloadWord() {
  downloading.value = true
  try {
    const wordData = {
      name: data.value.name,
      contact: [data.value.phone, data.value.email].filter(Boolean).join(' | '),
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
    }

    const res = await api.exportDocx({
      optimized_resume: wordData,
      template: 'classic',
    })
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
    Message.success('Word 已下载')
  } catch (e) {
    console.error(e)
    Message.error('下载失败：' + e.message)
  } finally {
    downloading.value = false
  }
}

onMounted(loadData)
</script>

<!-- ★ 全局样式（不加 scoped），用于打印 -->
<style>
/* 平时：打印区域完全隐藏，不占空间 */
.print-root {
  display: none;
}

@media print {
  @page {
    size: A4;
    margin: 0;
  }

  /* 打印时：把 body 里所有直接子元素隐藏 */
  body > * {
    display: none !important;
  }

  /* 只显示 print-root（Teleport 到 body 的那个） */
  body > .print-root {
    display: block !important;
    position: static !important;
    width: 100% !important;
  }

  /* 打印时背景纯白 */
  html, body {
    background: #ffffff !important;
    margin: 0 !important;
    padding: 0 !important;
  }

  /* 打印时去掉阴影、圆角 */
  .print-root,
  .print-root * {
    box-shadow: none !important;
    border-radius: 0 !important;
  }

  /* 简历纸张铺满 A4 */
  .print-root .blue-page {
    width: 210mm !important;
    min-height: 297mm !important;
    margin: 0 auto !important;
    padding: 15mm 15mm !important;
  }

  /* 章节避免跨页断开 */
  .print-root .blue-section,
  .print-root .blue-item {
    page-break-inside: avoid;
  }

  /* 保留颜色 */
  .print-root,
  .print-root * {
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }
}
</style>