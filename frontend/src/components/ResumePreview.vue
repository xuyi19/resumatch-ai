<template>
  <div class="resume-root" :class="`tpl-${template}`" :style="colorVars">

    <div class="page" :class="{ 'is-sidebar': isSidebar, 'serif': cfg.serif }">

      <!-- ============ sidebar 左侧信息栏 ============ -->
      <aside v-if="isSidebar" class="sb-col">
        <img v-if="photoUrl" :src="photoUrl" class="sb-photo" alt="证件照" />
        <div v-if="contacts.length" class="sb-block">
          <h3 class="sb-block-title">联系方式</h3>
          <p v-for="(c, i) in contacts" :key="'ct'+i" class="sb-text">{{ c }}</p>
        </div>
        <div v-if="data.skills?.length" class="sb-block">
          <h3 class="sb-block-title">技能</h3>
          <p v-for="(s, i) in data.skills" :key="'sk'+i" class="sb-text">· {{ s }}</p>
        </div>
        <div v-if="data.certificates?.length" class="sb-block">
          <h3 class="sb-block-title">证书</h3>
          <p v-for="(c, i) in data.certificates" :key="'ce'+i" class="sb-text">· {{ c }}</p>
        </div>
      </aside>

      <!-- ============ 主栏 ============ -->
      <div class="main-col">

        <!-- 页眉（非 sidebar） -->
        <header v-if="!isSidebar" class="r-header"
          :class="[`hdr-${cfg.header}`, { 'has-photo': photoUrl, 'hdr-border': cfg.headerBorder }]">
          <div class="hdr-main">
            <h1 class="r-name">{{ data.name || '姓名' }}</h1>
            <div v-if="data.job_intention" class="r-intention">{{ data.job_intention }}</div>
            <div v-if="contacts.length" class="r-contacts">
              <span v-for="(c, i) in contacts" :key="i" class="r-contact">{{ c }}</span>
            </div>
          </div>
          <img v-if="photoUrl" :src="photoUrl" class="r-photo" alt="证件照" />
        </header>

        <!-- sidebar 页眉（姓名+意向） -->
        <div v-else class="sb-header">
          <h1 class="r-name">{{ data.name || '姓名' }}</h1>
          <p v-if="data.job_intention" class="sb-intention">{{ data.job_intention }}</p>
        </div>

        <!-- 正文 -->
        <div class="r-body">

          <!-- 个人简介 -->
          <section v-if="data.summary" class="r-section">
            <h2 class="r-title" :class="titleClasses">
              <span v-if="cfg.marker" class="r-marker">{{ cfg.marker }}</span>{{ displayTitle(summaryTitle) }}
            </h2>
            <p class="r-text">{{ data.summary }}</p>
          </section>

          <!-- 教育 / 工作 / 项目 -->
          <section v-for="sec in visibleItemSections" :key="sec.key" class="r-section">
            <h2 class="r-title" :class="titleClasses">
              <span v-if="cfg.marker" class="r-marker">{{ cfg.marker }}</span>{{ displayTitle(sec.title) }}
            </h2>

            <!-- bullet 模式 -->
            <ul v-if="cfg.bullet" class="r-list">
              <li v-for="(item, i) in sec.items" :key="i" class="r-item">
                <div class="r-item-head">
                  <span class="r-item-title">{{ item.title }}</span>
                  <span v-if="item.time" class="r-item-time">{{ item.time }}</span>
                </div>
                <div v-if="item.subtitle" class="r-item-sub">{{ item.subtitle }}</div>
                <ul v-if="item.desc" class="r-desc-list">
                  <li v-for="(line, j) in splitLines(item.desc)" :key="j">{{ line }}</li>
                </ul>
                <div v-if="item.extra" class="r-text-small">{{ item.extra }}</div>
              </li>
            </ul>

            <!-- 非 bullet 模式 -->
            <div v-else class="r-items">
              <div v-for="(item, i) in sec.items" :key="i" class="r-item">
                <div class="r-item-head">
                  <span class="r-item-title">{{ item.title }}</span>
                  <span v-if="item.time" class="r-item-time">{{ item.time }}</span>
                </div>
                <div v-if="item.subtitle" class="r-item-sub">{{ item.subtitle }}</div>
                <p v-for="(line, j) in splitLines(item.desc)" :key="j" class="r-text">{{ line }}</p>
                <div v-if="item.extra" class="r-text-small">{{ item.extra }}</div>
              </div>
            </div>
          </section>

          <!-- 技能（非 sidebar） -->
          <section v-if="data.skills?.length && !isSidebar" class="r-section">
            <h2 class="r-title" :class="titleClasses">
              <span v-if="cfg.marker" class="r-marker">{{ cfg.marker }}</span>{{ displayTitle(skillsTitle) }}
            </h2>
            <div class="r-skills">
              <span v-for="(s, i) in data.skills" :key="i" class="r-skill">{{ s }}</span>
            </div>
          </section>

          <!-- 证书（非 sidebar） -->
          <section v-if="data.certificates?.length && !isSidebar" class="r-section">
            <h2 class="r-title" :class="titleClasses">
              <span v-if="cfg.marker" class="r-marker">{{ cfg.marker }}</span>{{ displayTitle(certsTitle) }}
            </h2>
            <ul v-if="cfg.bullet" class="r-list">
              <li v-for="(c, i) in data.certificates" :key="i">{{ c }}</li>
            </ul>
            <div v-else class="r-items">
              <p v-for="(c, i) in data.certificates" :key="i" class="r-text">{{ c }}</p>
            </div>
          </section>

        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Object, default: () => ({}) },
  template: { type: String, default: 'classic' },
  photoUrl: { type: String, default: '' },
})

// ---- 模板配置 ----
const TPL_CONFIG = {
  classic:  { header: 'center', marker: '',      border: true,  headerBorder: true,  bullet: true,  serif: false, upper: false, skillSep: ' · ',
              titles: {} },
  sidebar:  { header: 'sidebar', marker: '▍ ',   border: false, headerBorder: false, bullet: true,  serif: false, upper: false, skillSep: ' · ',
              titles: {} },
  business: { header: 'left',    marker: '',      border: true,  headerBorder: true,  bullet: true,  serif: false, upper: true,  skillSep: ' | ',
              titles: {} },
  elegant:  { header: 'center',  marker: '',      border: true,  headerBorder: true,  bullet: true,  serif: true,  upper: false, skillSep: ' · ',
              titles: {} },
  modern:   { header: 'left',    marker: '▍ ',    border: false, headerBorder: true,  bullet: false, serif: false, upper: false, skillSep: ' / ',
              titles: {} },
  minimal:  { header: 'center',  marker: '',      border: false, headerBorder: false, bullet: false, serif: false, upper: false, skillSep: ' · ',
              titles: {} },
  academic: { header: 'center',  marker: '',      border: false, headerBorder: false, bullet: false, serif: true,  upper: false, skillSep: ' · ',
              titles: {} },
  creative: { header: 'left',    marker: '● ',    border: false, headerBorder: false, bullet: false, serif: false, upper: false, skillSep: ' · ',
              titles: { summary: '关于我', education: '教育', experience: '经历', projects: '项目', skills: '技能', certificates: '证书' } },
  twocol:   { header: 'inline', marker: '',      border: true,  headerBorder: true,  bullet: true,  serif: false, upper: false, skillSep: ' · ',
              titles: {} },
  compact:  { header: 'center',  marker: '— ',    border: false, headerBorder: false, bullet: false, serif: false, upper: false, skillSep: ' · ',
              titles: { summary: '简介', education: '教育', experience: '工作', projects: '项目' } },
}

// ---- 模板色彩（与 docx_generator TEMPLATES 同步） ----
const TPL_COLORS = {
  classic:  { name: '#1F2937', section: '#0D9488', text: '#374151', line: '#E5E7EB' },
  sidebar:  { name: '#111827', section: '#0D9488', text: '#374151', line: '#E5E7EB', sbFill: '#EEF2F5' },
  business: { name: '#0C294E', section: '#1E40AF', text: '#1F2937', line: '#1E40AF' },
  elegant:  { name: '#1A1A1A', section: '#B4860B', text: '#3F3F46', line: '#D4AF37' },
  modern:   { name: '#0F172A', section: '#14B8A6', text: '#333333', line: '#14B8A6' },
  minimal:  { name: '#000000', section: '#666666', text: '#333333', line: '#EEEEEE' },
  academic: { name: '#000000', section: '#444444', text: '#222222', line: '#999999' },
  creative: { name: '#7C2D12', section: '#C2410C', text: '#444444', line: '#FED7AA' },
  twocol:   { name: '#1F2937', section: '#0D9488', text: '#374151', line: '#E5E7EB' },
  compact:  { name: '#000000', section: '#000000', text: '#333333', line: '#CCCCCC' },
}

const cfg = computed(() => TPL_CONFIG[props.template] || TPL_CONFIG.classic)
const isSidebar = computed(() => props.template === 'sidebar')

const colorVars = computed(() => {
  const c = TPL_COLORS[props.template] || TPL_COLORS.classic
  return `--name:${c.name};--section:${c.section};--text:${c.text};--line:${c.line};--sb-fill:${c.sbFill || '#EEF2F5'}`
})

const titleClasses = computed(() => ({
  'has-border': cfg.value.border,
  'no-border': !cfg.value.border,
  'upper': cfg.value.upper,
}))

// ---- 联系方式 ----
const contacts = computed(() => {
  const items = []
  if (props.data.phone)     items.push(`电话：${props.data.phone}`)
  if (props.data.email)     items.push(`邮箱：${props.data.email}`)
  if (props.data.wechat)    items.push(`微信：${props.data.wechat}`)
  if (props.data.location)  items.push(`现居：${props.data.location}`)
  return items
})

// ---- 标题文案 ----
const summaryTitle = computed(() => cfg.value.titles?.summary || '个人简介')
const skillsTitle  = computed(() => cfg.value.titles?.skills || '技能')
const certsTitle   = computed(() => cfg.value.titles?.certificates || '证书')

function displayTitle(title) {
  return cfg.value.upper ? title.toUpperCase() : title
}

// ---- 教育/工作/项目统一结构化 ----
const itemSections = computed(() => [
  {
    key: 'education',
    title: cfg.value.titles?.education || '教育经历',
    items: (props.data.education || []).map(e => ({
      title: e.school,
      time: e.time,
      subtitle: [e.major, e.degree].filter(Boolean).join(' · '),
      desc: '',
      extra: e.courses ? `主修课程：${e.courses}` : '',
    })),
  },
  {
    key: 'experience',
    title: cfg.value.titles?.experience || '工作经历',
    items: (props.data.experience || []).map(e => ({
      title: e.company,
      time: e.time,
      subtitle: e.position,
      desc: e.desc,
      extra: '',
    })),
  },
  {
    key: 'projects',
    title: cfg.value.titles?.projects || '项目经历',
    items: (props.data.projects || []).map(p => ({
      title: p.name,
      time: p.time,
      subtitle: p.role,
      desc: p.desc,
      extra: '',
    })),
  },
])

const visibleItemSections = computed(() =>
  itemSections.value.filter(s => s.items.length > 0)
)

function splitLines(text) {
  if (!text) return []
  return text.split('\n').map(l => l.replace(/^[-•·]\s*/, '').trim()).filter(Boolean)
}
</script>

<style scoped>
.resume-root {
  width: 100%;
  display: flex;
  justify-content: center;
}

/* ============ 基础页面 ============ */
.page {
  width: 210mm;
  min-height: 297mm;
  background: #fff;
  padding: 18mm 16mm;
  font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: var(--text);
  font-size: 11pt;
  line-height: 1.6;
  box-sizing: border-box;
}

.page.serif {
  font-family: 'Times New Roman', '宋体', 'SimSun', serif;
}

/* ============ sidebar 双栏 ============ */
.page.is-sidebar {
  display: flex;
  padding: 0;
}

.sb-col {
  width: 32%;
  background: var(--sb-fill);
  padding: 16mm 8mm;
  box-sizing: border-box;
}

.main-col {
  flex: 1;
  padding: 16mm 14mm;
  box-sizing: border-box;
}

.sb-photo {
  width: 28mm;
  height: 38mm;
  object-fit: cover;
  border-radius: 2px;
  margin: 0 auto 10mm;
  display: block;
}

.sb-block {
  margin-bottom: 8mm;
}

.sb-block-title {
  font-size: 11pt;
  font-weight: 700;
  color: var(--section);
  border-bottom: 1px solid var(--line);
  padding-bottom: 4px;
  margin-bottom: 6px;
}

.sb-text {
  font-size: 9.5pt;
  color: var(--text);
  line-height: 1.7;
  margin: 2px 0;
}

.sb-header {
  margin-bottom: 6mm;
  padding-bottom: 4mm;
  border-bottom: 2px solid var(--line);
}

.sb-intention {
  font-size: 11pt;
  color: var(--section);
  margin-top: 4px;
}

/* ============ 页眉 ============ */
.r-header {
  margin-bottom: 16px;
  padding-bottom: 10px;
}

.r-header.hdr-border {
  border-bottom: 3px solid var(--line);
}

/* 无照片时按 mode 排列 */
.r-header:not(.has-photo).hdr-center {
  text-align: center;
}
.r-header:not(.has-photo).hdr-left {
  text-align: left;
}
.r-header:not(.has-photo).hdr-inline {
  display: flex;
  align-items: baseline;
  gap: 20px;
}

/* 有照片时统一为 flex 左右布局 */
.r-header.has-photo {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
}
.r-header.has-photo .hdr-main {
  flex: 1;
  min-width: 0;
}
.r-header.has-photo.hdr-center .hdr-main {
  text-align: center;
}
.r-header.has-photo.hdr-left .hdr-main,
.r-header.has-photo.hdr-inline .hdr-main {
  text-align: left;
}

.r-name {
  font-size: 22pt;
  font-weight: 700;
  color: var(--name);
  letter-spacing: 1px;
  margin-bottom: 4px;
}

.tpl-modern .r-name    { font-size: 26pt; }
.tpl-creative .r-name { font-size: 28pt; }
.tpl-business .r-name { font-size: 24pt; }
.tpl-minimal .r-name  { font-size: 20pt; }
.tpl-academic .r-name { font-size: 20pt; }
.tpl-elegant .r-name  { font-size: 21pt; }
.tpl-twocol .r-name   { font-size: 22pt; }
.tpl-compact .r-name  { font-size: 18pt; }
.tpl-sidebar .sb-header .r-name { font-size: 26pt; }

.r-intention {
  font-size: 12pt;
  color: var(--section);
  margin-bottom: 8px;
}

.r-contacts {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  font-size: 10pt;
  color: #6B7280;
}

.r-header.hdr-inline:not(.has-photo) .r-contacts {
  margin-left: 0;
}

.r-contact {
  display: inline-flex;
  align-items: center;
}

.r-contact::after {
  content: '·';
  margin-left: 14px;
  color: #D1D5DB;
}

.r-contact:last-child::after {
  content: '';
  margin: 0;
}

.r-header.hdr-center .r-contacts {
  justify-content: center;
}

.r-photo {
  width: 25mm;
  height: 35mm;
  object-fit: cover;
  border: 1px solid #D1D5DB;
  flex-shrink: 0;
}

/* ============ 标题 ============ */
.r-title {
  font-size: 13pt;
  font-weight: 700;
  color: var(--section);
  margin-bottom: 10px;
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
}

.r-title.has-border {
  border-bottom: 2px solid var(--line);
  padding-bottom: 6px;
}

.r-marker {
  margin-right: 4px;
  font-size: 14pt;
}

.tpl-compact .r-title {
  font-size: 11pt;
}
.tpl-minimal .r-title {
  font-size: 11pt;
  color: var(--section);
}

/* ============ 正文条目 ============ */
.r-section {
  margin-bottom: 16px;
}

.r-item {
  margin-bottom: 10px;
}

.r-item:last-child {
  margin-bottom: 0;
}

.r-item-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 2px;
}

.r-item-title {
  font-size: 11.5pt;
  font-weight: 600;
  color: #1F2937;
}

.r-item-time {
  font-size: 9.5pt;
  color: #6B7280;
  font-family: 'SF Mono', Consolas, monospace;
}

.r-item-sub {
  font-size: 10pt;
  color: #4B5563;
  margin-bottom: 4px;
}

.r-text {
  font-size: 10.5pt;
  color: var(--text);
  line-height: 1.75;
  text-align: justify;
}

.r-text-small {
  font-size: 10pt;
  color: #4B5563;
  line-height: 1.6;
  margin-top: 2px;
}

/* bullet 列表 */
.r-list {
  padding-left: 0;
  list-style: none;
  margin: 4px 0 0 0;
}

.r-list > .r-item {
  padding-left: 14px;
  position: relative;
}

.r-list > .r-item::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 9px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--section);
}

.r-desc-list {
  padding-left: 0;
  list-style: none;
  margin: 4px 0 0 0;
}

.r-desc-list li {
  font-size: 10.5pt;
  color: var(--text);
  line-height: 1.7;
  padding-left: 14px;
  position: relative;
  margin-bottom: 2px;
  text-align: justify;
}

.r-desc-list li::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 9px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #9CA3AF;
}

/* 非 bullet 段落模式 */
.r-items .r-text {
  margin-bottom: 4px;
}

.tpl-modern .r-items .r-item,
.tpl-creative .r-items .r-item {
  padding-left: 6mm;
}

.tpl-compact .r-item {
  margin-bottom: 6px;
}

.tpl-compact .r-text {
  font-size: 10pt;
  line-height: 1.5;
}

/* ============ 技能标签 ============ */
.r-skills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.r-skill {
  display: inline-block;
  padding: 3px 10px;
  font-size: 9.5pt;
  color: var(--section);
  background: color-mix(in srgb, var(--section) 10%, #fff);
  border: 1px solid color-mix(in srgb, var(--section) 30%, #fff);
  border-radius: 4px;
}

/* ============ 证书列表（非 bullet） ============ */
.r-items .r-text {
  margin-bottom: 4px;
}

/* ============ 打印 ============ */
@media print {
  @page { size: A4; margin: 0; }
  .page {
    box-shadow: none;
    margin: 0;
    width: 210mm;
    min-height: 297mm;
  }
  .r-section,
  .r-item {
    page-break-inside: avoid;
  }
}
</style>
