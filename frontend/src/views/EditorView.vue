<template>
  <div class="min-h-screen bg-[#e0e5ec]">

    <!-- 屏幕界面 -->
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
              <option v-for="t in templateList" :key="t.id" :value="t.id">
                {{ t.name }} · {{ t.desc }}
              </option>
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
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <span class="text-base">👤</span>
                <span class="text-sm font-semibold text-gray-800">基本信息</span>
              </div>
              <!-- 证件照：上传后嵌入导出的 Word（右上角一寸照位） -->
              <div class="flex items-center gap-3">
                <div v-if="photoUrl"
                  class="relative w-[64px] h-[86px] rounded-lg overflow-hidden border border-[#b8bcc2]/50">
                  <img :src="photoUrl" class="w-full h-full object-cover" alt="证件照" />
                  <button @click="removePhoto"
                    class="absolute inset-x-0 bottom-0 bg-black/50 text-white text-[10px] py-0.5">
                    移除
                  </button>
                </div>
                <label v-else
                  class="w-[64px] h-[86px] rounded-lg border border-dashed border-[#b8bcc2]
                    flex flex-col items-center justify-center cursor-pointer text-gray-400
                    hover:text-[#6d5dfc] hover:border-[#6d5dfc] transition-colors">
                  <span class="text-lg leading-none">📷</span>
                  <span class="text-[10px] mt-1">证件照</span>
                  <input type="file" accept="image/jpeg,image/png" class="hidden"
                    @change="onPhotoChange" />
                </label>
                <div v-if="photoUploading" class="text-xs text-gray-400">上传中…</div>
              </div>
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
              <div class="text-xs text-gray-500 mb-3 text-center">
                预览按所选模板实时排版 · 导出 Word 版式一致
              </div>
              <div class="shadow-2xl mx-auto">
                <ResumePreview :data="data" :template="currentTemplate" :photo-url="photoUrl" />
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>

  </div>

  <!-- 打印专用区域 -->
  <Teleport to="body">
    <div class="print-root">
      <ResumePreview :data="data" :template="currentTemplate" :photo-url="photoUrl" />
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
const SESSION_KEY = `resume_optimized_${taskId}`

const currentTemplate = ref('classic')
const downloading = ref(false)
const newSkill = ref('')
const certText = ref('')

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
  setTimeout(() => window.print(), 150)
}

async function downloadWord() {
  downloading.value = true
  try {
    const contacts = [
      data.value.phone && `电话：${data.value.phone}`,
      data.value.email && `邮箱：${data.value.email}`,
      data.value.wechat && `微信：${data.value.wechat}`,
      data.value.location && `现居：${data.value.location}`,
    ].filter(Boolean)

    const wordData = {
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

    const res = await api.exportDocx({
      optimized_resume: wordData,
      template: currentTemplate.value,
      photo_id: photoId.value || undefined,
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

onMounted(() => {
  loadData()
  // 模板目录以后端为准（与 Word 导出实现保持同步）
  api.listTemplates().then(res => {
    if (res.data?.items?.length) templateList.value = res.data.items
  }).catch(() => { /* 用内置兜底列表 */ })
})
</script>

<!-- 打印样式（全局） -->
<style>
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
}
</style>