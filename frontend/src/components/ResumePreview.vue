<template>
  <div class="resume-root" :class="`tpl-${template}`">

    <!-- ============ 预览示意（Word 导出按所选模板排版） ============ -->
    <div class="blue-page">
      <header class="blue-header" :class="{ 'has-photo': photoUrl }">
        <div class="blue-header-main">
          <div class="blue-name">{{ data.name || '姓名' }}</div>
          <div class="blue-job">{{ data.job_intention || '求职意向' }}</div>

          <div class="blue-contacts">
          <span v-if="data.phone" class="blue-contact-item">
            <svg class="blue-icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.6 21 3 13.4 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.2.2 2.4.6 3.6.1.4 0 .8-.2 1l-2.3 2.2z"/>
            </svg>
            {{ data.phone }}
          </span>
          <span v-if="data.email" class="blue-contact-item">
            <svg class="blue-icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
            </svg>
            {{ data.email }}
          </span>
          <span v-if="data.location" class="blue-contact-item">
            <svg class="blue-icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C8.1 2 5 5.1 5 9c0 5.3 7 13 7 13s7-7.7 7-13c0-3.9-3.1-7-7-7zm0 9.5c-1.4 0-2.5-1.1-2.5-2.5s1.1-2.5 2.5-2.5 2.5 1.1 2.5 2.5-1.1 2.5-2.5 2.5z"/>
            </svg>
            {{ data.location }}
          </span>
          <span v-if="data.wechat" class="blue-contact-item">
            <svg class="blue-icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M9.5 4C5.4 4 2 6.7 2 10c0 1.9 1 3.6 2.6 4.7L4 17l2.6-1.3c.9.2 1.8.3 2.9.3h.5c-.1-.5-.2-1-.2-1.5 0-3.3 3.2-6 7.2-6h.4C16.7 5.9 13.4 4 9.5 4z"/>
              <path d="M22 14.5c0-2.8-2.7-5-6-5s-6 2.2-6 5 2.7 5 6 5c.7 0 1.4-.1 2-.3L20 20l-.5-1.5c1.5-.8 2.5-2.2 2.5-4z"/>
            </svg>
            {{ data.wechat }}
          </span>
        </div>
          </div>
          <!-- 证件照（一寸照位，与 Word 导出一致） -->
          <img v-if="photoUrl" :src="photoUrl" class="blue-photo" alt="证件照" />
      </header>

      <div class="blue-body">
        <section v-if="data.summary" class="blue-section">
          <h2 class="blue-section-title"><span class="blue-section-bar"></span>自我评价</h2>
          <p class="blue-text">{{ data.summary }}</p>
        </section>

        <section v-if="data.education?.length" class="blue-section">
          <h2 class="blue-section-title"><span class="blue-section-bar"></span>教育背景</h2>
          <div v-for="(edu, i) in data.education" :key="i" class="blue-item">
            <div class="blue-item-head">
              <span class="blue-item-title">{{ edu.school }}</span>
              <span class="blue-item-time">{{ edu.time }}</span>
            </div>
            <div class="blue-item-sub">{{ edu.major }}<span v-if="edu.degree"> · {{ edu.degree }}</span></div>
            <div v-if="edu.courses" class="blue-text-small">主修课程：{{ edu.courses }}</div>
          </div>
        </section>

        <section v-if="data.experience?.length" class="blue-section">
          <h2 class="blue-section-title"><span class="blue-section-bar"></span>工作经验</h2>
          <div v-for="(exp, i) in data.experience" :key="i" class="blue-item">
            <div class="blue-item-head">
              <span class="blue-item-title">{{ exp.company }}</span>
              <span class="blue-item-time">{{ exp.time }}</span>
            </div>
            <div class="blue-item-sub">{{ exp.position }}</div>
            <ul v-if="exp.desc" class="blue-list">
              <li v-for="(line, j) in splitLines(exp.desc)" :key="j">{{ line }}</li>
            </ul>
          </div>
        </section>

        <section v-if="data.projects?.length" class="blue-section">
          <h2 class="blue-section-title"><span class="blue-section-bar"></span>项目经历</h2>
          <div v-for="(proj, i) in data.projects" :key="i" class="blue-item">
            <div class="blue-item-head">
              <span class="blue-item-title">{{ proj.name }}</span>
              <span class="blue-item-time">{{ proj.time }}</span>
            </div>
            <div v-if="proj.role" class="blue-item-sub">{{ proj.role }}</div>
            <ul v-if="proj.desc" class="blue-list">
              <li v-for="(line, j) in splitLines(proj.desc)" :key="j">{{ line }}</li>
            </ul>
          </div>
        </section>

        <section v-if="data.skills?.length" class="blue-section">
          <h2 class="blue-section-title"><span class="blue-section-bar"></span>专业技能</h2>
          <div class="blue-skills">
            <span v-for="(s, i) in data.skills" :key="i" class="blue-skill">{{ s }}</span>
          </div>
        </section>

        <section v-if="data.certificates?.length" class="blue-section">
          <h2 class="blue-section-title"><span class="blue-section-bar"></span>证书荣誉</h2>
          <ul class="blue-list">
            <li v-for="(c, i) in data.certificates" :key="i">{{ c }}</li>
          </ul>
        </section>
      </div>
    </div>

  </div>
</template>

<script setup>
defineProps({
  data: { type: Object, default: () => ({}) },
  template: { type: String, default: 'blue' },
  photoUrl: { type: String, default: '' },
})

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

/* ============ 蓝色专业 ============ */
.blue-page {
  width: 210mm;
  min-height: 297mm;
  background: #fff;
  padding: 18mm 16mm;
  font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: #2D3748;
  font-size: 11pt;
  line-height: 1.6;
  box-sizing: border-box;
}

.blue-header {
  padding-bottom: 12px;
  border-bottom: 3px solid #1E3A8A;
  margin-bottom: 20px;
}

.blue-header.has-photo {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.blue-header-main {
  flex: 1;
  min-width: 0;
}

.blue-photo {
  width: 25mm;
  height: 35mm;
  object-fit: cover;
  border: 1px solid #D1D5DB;
  flex-shrink: 0;
}

.blue-name {
  font-size: 26pt;
  font-weight: 700;
  color: #1E3A8A;
  letter-spacing: 1px;
  margin-bottom: 4px;
}

.blue-job {
  font-size: 12pt;
  color: #4B5563;
  margin-bottom: 12px;
}

.blue-contacts {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 10pt;
  color: #4B5563;
}

.blue-contact-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.blue-icon {
  width: 14px;
  height: 14px;
  color: #3B82F6;
  flex-shrink: 0;
}

.blue-section {
  margin-bottom: 18px;
}

.blue-section-title {
  display: flex;
  align-items: center;
  font-size: 13pt;
  font-weight: 700;
  color: #1E3A8A;
  margin-bottom: 10px;
  letter-spacing: 0.5px;
}

.blue-section-bar {
  display: inline-block;
  width: 4px;
  height: 16px;
  background: #3B82F6;
  margin-right: 8px;
  border-radius: 2px;
}

.blue-item {
  margin-bottom: 12px;
}

.blue-item:last-child {
  margin-bottom: 0;
}

.blue-item-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 2px;
}

.blue-item-title {
  font-size: 11.5pt;
  font-weight: 600;
  color: #1F2937;
}

.blue-item-time {
  font-size: 9.5pt;
  color: #6B7280;
  font-family: 'SF Mono', Consolas, monospace;
}

.blue-item-sub {
  font-size: 10pt;
  color: #4B5563;
  margin-bottom: 4px;
}

.blue-text {
  font-size: 10.5pt;
  color: #374151;
  line-height: 1.75;
  text-align: justify;
}

.blue-text-small {
  font-size: 10pt;
  color: #4B5563;
  line-height: 1.7;
  margin-top: 2px;
}

.blue-list {
  padding-left: 0;
  list-style: none;
  margin: 4px 0 0 0;
}

.blue-list li {
  font-size: 10.5pt;
  color: #374151;
  line-height: 1.7;
  padding-left: 14px;
  position: relative;
  margin-bottom: 2px;
  text-align: justify;
}

.blue-list li::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 9px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #3B82F6;
}

.blue-skills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.blue-skill {
  display: inline-block;
  padding: 3px 10px;
  font-size: 9.5pt;
  color: #1E3A8A;
  background: #EFF6FF;
  border: 1px solid #BFDBFE;
  border-radius: 4px;
}

@media print {
  @page { size: A4; margin: 0; }
  .blue-page {
    box-shadow: none;
    margin: 0;
    width: 210mm;
    min-height: 297mm;
  }
}
</style>