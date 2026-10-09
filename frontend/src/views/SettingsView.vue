<template>
  <div class="max-w-4xl mx-auto px-6 md:px-10 py-8 md:py-10">

    <div class="mb-8">
      <h1 class="text-2xl font-semibold tracking-tight mb-1.5">
        <span class="bg-gradient-to-r from-ink to-accent bg-clip-text text-transparent">设置</span>
      </h1>
      <div class="h-0.5 w-14 rounded-full bg-gradient-to-r from-accent to-accent-hover/0"></div>
      <p class="text-sm text-ink-sub">配置大模型 API，Key 仅保存在本机，不上传服务器</p>
    </div>

    <div class="space-y-5">

      <!-- 服务端预置提示（零配置分发） -->
      <div v-if="serverManaged"
        class="p-4 rounded-lg text-sm bg-ok/10 border border-ok/30 text-ok leading-relaxed">
        ✓ 本程序已由分发者预置 API Key，<strong>无需填写即可直接使用</strong>。
        如需更换为自有 Key，可点「修改配置」弹窗填写并保存。
      </div>

      <!-- 状态卡片（紧凑入口，配置表单收进弹窗） -->
      <div class="bg-panel border-2 border-ink/80 shadow-[3px_3px_0_0] shadow-ink/15 rounded-lg p-5">
        <div class="flex items-center justify-between gap-4">
          <div class="flex items-center gap-3.5 min-w-0">
            <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
              :class="hasConfig ? 'bg-ok/10 text-ok' : 'bg-warn/10 text-warn'">
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path v-if="hasConfig" d="M20 6L9 17l-5-5" />
                <path v-else d="M12 8v4.5M12 16h.01M12 3a9 9 0 100 18 9 9 0 000-18z" />
              </svg>
            </div>
            <div class="min-w-0">
              <div class="font-semibold text-sm mb-0.5">
                {{ hasConfig ? 'API 已配置' : '尚未配置 API' }}
              </div>
              <div class="text-xs text-ink-faint font-mono truncate">
                {{ hasConfig
                  ? `${currentVendorName || '自定义'} · ${form.model || '未设置模型'}`
                  : '选择厂商 → 贴 Key → 测试 → 保存，即可启用 AI 功能' }}
              </div>
            </div>
          </div>
          <div class="flex items-center gap-3 shrink-0">
            <span v-if="hasConfig" class="w-2.5 h-2.5 rounded-full bg-ok" title="已配置" />
            <button @click="showApiModal = true"
              class="px-4 py-2 text-sm font-medium rounded-md
                bg-accent text-white hover:bg-accent-hover
                shadow-[0_1px_0_rgba(255,255,255,0.25)_inset]
                transition-colors">
              {{ hasConfig ? '修改配置' : '立即配置' }}
            </button>
          </div>
        </div>
      </div>

      <!-- API 配置弹窗（原内联表单收进 Modal，页面更紧凑） -->
      <Teleport to="body">
        <div v-if="showApiModal"
          class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/40"
          @click.self="showApiModal = false"
          @keydown.esc="showApiModal = false">
          <div class="w-full max-w-lg max-h-[88vh] overflow-y-auto bg-panel border-2 border-ink/80
            rounded-xl shadow-[3px_3px_0_0] shadow-ink/20 p-5">
            <div class="flex items-center justify-between mb-4">
              <h2 class="text-base font-semibold">API 配置</h2>
              <button @click="showApiModal = false"
                class="w-7 h-7 rounded-md flex items-center justify-center text-ink-faint
                  hover:text-ink hover:bg-inset transition-colors">✕</button>
            </div>

        <div class="space-y-5">

          <!-- A6：厂商预设 -->
          <div>
            <label class="text-xs font-medium text-ink-sub block mb-2.5">
              服务商预设 <span class="text-ink-faint font-normal">（自动填入接口地址与推荐模型）</span>
            </label>
            <div class="grid grid-cols-3 sm:grid-cols-5 gap-2">
              <button v-for="v in VENDORS" :key="v.id" @click="applyVendor(v)"
                class="px-2 py-2 text-xs font-medium rounded-md border transition-colors"
                :class="vendorId === v.id
                  ? 'bg-accent/10 border-accent/50 text-accent'
                  : 'bg-inset border-line text-ink-sub hover:text-ink hover:border-line-strong'">
                {{ v.name }}
              </button>
            </div>
            <div v-if="currentVendor" class="flex items-center gap-3 mt-2.5 text-xs">
              <span :class="currentVendor.embedding
                ? 'text-ok' : 'text-ink-faint'"
                :title="currentVendor.embedding
                  ? '该厂商支持向量检索（RAG 证据召回更准）'
                  : '该厂商不支持向量接口，RAG 检索将自动回退为关键词检索'">
                {{ currentVendor.embedding ? '✓ 支持向量检索' : '○ 仅关键词检索' }}
              </span>
              <a v-if="currentVendor.keyUrl" :href="currentVendor.keyUrl" target="_blank"
                rel="noopener" class="text-accent hover:underline">
                前往控制台创建 API Key ↗
              </a>
              <span v-if="currentVendor.note" class="text-ink-faint">
                {{ currentVendor.note }}
              </span>
            </div>
          </div>

          <!-- API Key -->
          <div>
            <label class="text-xs font-medium text-ink-sub block mb-2.5">
              API Key <span class="text-bad">*</span>
            </label>
            <div class="relative">
              <input v-model="form.api_key" :type="showKey ? 'text' : 'password'"
                placeholder="sk-..."
                class="w-full px-3.5 py-2.5 pr-11 text-sm bg-inset rounded-md border border-line
                  font-mono focus:outline-none focus:border-accent transition-colors" />
              <button @click="showKey = !showKey"
                class="absolute right-2.5 top-1/2 -translate-y-1/2 w-7 h-7 rounded
                  flex items-center justify-center text-ink-faint hover:text-ink
                  transition-colors">
                {{ showKey ? '🙈' : '👁' }}
              </button>
            </div>
            <div class="text-xs text-ink-faint mt-1.5">
              仅保存在本机 localStorage，不会上传服务器
            </div>
          </div>

          <!-- Base URL -->
          <div>
            <label class="text-xs font-medium text-ink-sub block mb-2.5">Base URL</label>
            <input v-model="form.base_url" type="text"
              placeholder="https://api.deepseek.com/v1"
              class="w-full px-3.5 py-2.5 text-sm bg-inset rounded-md border border-line
                font-mono focus:outline-none focus:border-accent transition-colors" />
          </div>

          <!-- 模型：推荐列表 + 可手填 -->
          <div>
            <label class="text-xs font-medium text-ink-sub block mb-2.5">
              模型名称
              <span v-if="currentVendor?.models?.length"
                class="text-ink-faint font-normal">（下方为推荐，可自行修改）</span>
            </label>
            <input v-model="form.model" type="text" list="vendor-models"
              placeholder="deepseek-chat"
              class="w-full px-3.5 py-2.5 text-sm bg-inset rounded-md border border-line
                font-mono focus:outline-none focus:border-accent transition-colors" />
            <datalist id="vendor-models">
              <option v-for="m in currentVendor?.models || []" :key="m" :value="m" />
            </datalist>
            <div v-if="currentVendor?.models?.length" class="flex flex-wrap gap-1.5 mt-2">
              <button v-for="m in currentVendor.models" :key="m"
                @click="form.model = m"
                class="px-2 py-0.5 rounded text-[11px] font-mono border transition-colors"
                :class="form.model === m
                  ? 'border-accent/50 text-accent bg-accent/10'
                  : 'border-line text-ink-faint hover:text-ink hover:border-line-strong'">
                {{ m }}
              </button>
            </div>
          </div>
        </div>

        <!-- 测试结果 -->
        <div v-if="testResult" class="mt-5 p-3.5 rounded-md text-sm border"
          :class="testResult.success
            ? 'bg-ok/10 text-ok border-ok/30'
            : 'bg-bad/10 text-bad border-bad/30'">
          <div>{{ testResult.message }}</div>
          <div v-if="testResult.raw" class="text-xs opacity-70 mt-1.5 font-mono break-all">
            {{ testResult.raw }}
          </div>
        </div>

        <div class="flex flex-wrap gap-2.5 mt-6">
          <button @click="clearSettings"
            class="px-4 py-2.5 text-sm font-medium rounded-md text-ink-sub
              border border-line hover:border-bad/50 hover:text-bad transition-colors">
            清空
          </button>
          <button @click="testConnection" :disabled="testing || !form.api_key"
            class="px-4 py-2.5 text-sm font-medium rounded-md text-ink
              border border-line-strong hover:border-accent hover:text-accent
              disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            {{ testing ? '测试中…' : '测试连接' }}
          </button>
          <button @click="saveSettings" :disabled="!form.api_key"
            class="flex-1 min-w-[120px] px-4 py-2.5 text-sm font-medium rounded-md
              bg-accent text-white hover:bg-accent-hover
              disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            保存配置
          </button>
        </div>
          </div>
        </div>
      </Teleport>

      <!-- M19：招聘数据源（岗位一键获取/推荐） -->
      <div class="bg-panel border-2 border-ink/80 shadow-[3px_3px_0_0] shadow-ink/20 rounded-lg p-5 md:p-7">
        <h2 class="text-base font-semibold mb-1">
          招聘数据源
          <span class="text-xs text-ink-faint font-normal">（分析页「一键获取岗位」的数据来源）</span>
        </h2>
        <p class="text-xs text-ink-faint mb-5">接入方式与模型 API 一致：选预设 → 贴 Key → 测试 → 保存</p>

        <div>
          <label class="text-xs font-medium text-ink-sub block mb-2.5">数据源预设</label>
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <button v-for="s in JOB_SOURCES" :key="s.id" @click="applyJobSource(s)"
              class="px-2 py-2 text-xs font-medium rounded-md border transition-colors"
              :class="jobProvider === s.id
                ? 'bg-accent/10 border-accent/50 text-accent'
                : 'bg-inset border-line text-ink-sub hover:text-ink hover:border-line-strong'">
              {{ s.name }}
            </button>
          </div>
          <div v-if="currentJobSource" class="flex items-center gap-3 mt-2.5 text-xs flex-wrap">
            <span class="text-ink-faint">{{ currentJobSource.note }}</span>
            <a v-if="currentJobSource.keyUrl" :href="currentJobSource.keyUrl" target="_blank"
              rel="noopener" class="text-accent hover:underline">
              {{ currentJobSource.keyUrlText }}
            </a>
          </div>
        </div>

        <div v-if="currentJobSource?.needId" class="mt-4">
          <label class="text-xs font-medium text-ink-sub block mb-2.5">
            {{ currentJobSource.idLabel }} <span class="text-bad">*</span>
          </label>
          <input v-model="jobForm.api_id" type="text" placeholder="App ID"
            class="w-full px-3.5 py-2.5 text-sm bg-inset rounded-md border border-line
              font-mono focus:outline-none focus:border-accent transition-colors" />
        </div>

        <div v-if="currentJobSource?.keyLabel" class="mt-4">
          <label class="text-xs font-medium text-ink-sub block mb-2.5">
            {{ currentJobSource.keyLabel }} <span class="text-bad">*</span>
          </label>
          <input v-model="jobForm.api_key" type="password" :placeholder="currentJobSource.keyPlaceholder"
            class="w-full px-3.5 py-2.5 text-sm bg-inset rounded-md border border-line
              font-mono focus:outline-none focus:border-accent transition-colors" />
          <div class="text-xs text-ink-faint mt-1.5">
            仅保存在本机 localStorage，不会上传服务器
          </div>
        </div>

        <div v-if="jobTestResult" class="mt-4 p-3.5 rounded-md text-sm border"
          :class="jobTestResult.success
            ? 'bg-ok/10 text-ok border-ok/30'
            : 'bg-bad/10 text-bad border-bad/30'">
          <div>{{ jobTestResult.message }}</div>
          <div v-if="jobTestResult.raw" class="text-xs opacity-70 mt-1.5 font-mono break-all">
            {{ jobTestResult.raw }}
          </div>
        </div>

        <div class="flex flex-wrap gap-2.5 mt-5">
          <button @click="clearJobSource"
            class="px-4 py-2.5 text-sm font-medium rounded-md text-ink-sub
              border border-line hover:border-bad/50 hover:text-bad transition-colors">
            清空
          </button>
          <button @click="testJob" :disabled="jobTesting || currentJobSource?.id === 'mock'"
            class="px-4 py-2.5 text-sm font-medium rounded-md text-ink
              border border-line-strong hover:border-accent hover:text-accent
              disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            {{ jobTesting ? '测试中…' : '测试连接' }}
          </button>
          <button @click="saveJobSourceCfg" :disabled="!jobSourceReady"
            class="flex-1 min-w-[120px] px-4 py-2.5 text-sm font-medium rounded-md
              bg-accent text-white hover:bg-accent-hover
              disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            保存配置
          </button>
        </div>
      </div>

      <!-- 获取 Key 指引 -->
      <div class="bg-panel border-2 border-ink/80 shadow-[3px_3px_0_0] shadow-ink/20 rounded-lg p-5 md:p-7">
        <h2 class="text-base font-semibold mb-4">获取 Key 三步指引</h2>
        <div class="space-y-3.5 text-sm text-ink-sub leading-relaxed">
          <div class="flex gap-3">
            <span class="text-accent font-mono text-xs shrink-0 pt-0.5">01</span>
            <span>点上方「立即配置 / 修改配置」打开配置弹窗，选择厂商后点击「前往控制台创建 API Key」
              注册并生成 Key（智谱 glm-4-flash 免费、硅基流动有免费额度、Ollama 本地免费）</span>
          </div>
          <div class="flex gap-3">
            <span class="text-accent font-mono text-xs shrink-0 pt-0.5">02</span>
            <span>粘贴 Key，点「测试连接」——出错时会给出明确原因
              （Key 无效 / 余额不足 / 模型名不存在 / 网络不通）</span>
          </div>
          <div class="flex gap-3">
            <span class="text-accent font-mono text-xs shrink-0 pt-0.5">03</span>
            <span>点「保存配置」，回到工作台即可开始诊断</span>
          </div>
        </div>

        <!-- 厂商控制台直达（keyUrl 来自 VENDORS 预设） -->
        <div class="mt-5 flex flex-wrap items-center gap-2">
          <span class="text-xs text-ink-faint shrink-0">控制台直达：</span>
          <a v-for="v in keyVendors" :key="v.id" :href="v.keyUrl" target="_blank" rel="noopener"
            :title="v.note || v.name"
            class="px-2.5 py-1 rounded-md border border-line text-xs text-ink-sub
              hover:border-accent hover:text-accent transition-colors">
            {{ v.name }} ↗
          </a>
        </div>

        <div class="mt-5 p-3.5 rounded-md text-xs bg-warn/10 border border-warn/30
          text-warn leading-relaxed">
          <strong>提示：</strong>换厂商只需点对应预设按钮再贴新 Key；选「Ollama 本地」可零成本诊断
          （Key 填任意字符，如 ollama，需先在本机 ollama pull 模型）。
        </div>
      </div>

      <!-- M22 C1 数据与隐私 -->
      <div class="bg-panel border-2 border-ink/80 shadow-[3px_3px_0_0] shadow-ink/20 rounded-lg p-5 md:p-7">
        <h2 class="text-base font-semibold mb-2">数据与隐私</h2>
        <p class="text-sm text-ink-sub leading-relaxed mb-4">
          简历与诊断数据全部保存在你自己的电脑上（程序目录 data/ 下，SQLite 本地库），
          不上传任何服务器；JD 文本仅用于当次诊断分析。诊断过程中需要把简历内容与 JD
          发给你所配置的 LLM 服务商（如智谱/DeepSeek）用于生成结果，此外无任何第三方。
        </p>
        <div class="flex items-center gap-3 flex-wrap">
          <button @click="confirmClearData" :disabled="clearingData"
            class="px-4 py-2.5 text-sm font-medium rounded-md
              border border-bad/50 text-bad hover:bg-bad/10
              disabled:opacity-40 transition-colors">
            {{ clearingData ? '正在清空...' : '清空我的全部数据' }}
          </button>
          <span class="text-xs text-ink-faint">
            将删除：诊断记录、简历库、导出历史、会话、证件照与快照，不可恢复
          </span>
        </div>
      </div>

      <!-- M59 数据备份与恢复 -->
      <div class="bg-panel border-2 border-ink/80 shadow-[3px_3px_0_0] shadow-ink/20 rounded-lg p-5 md:p-7">
        <h2 class="text-base font-semibold mb-2">💾 数据备份</h2>
        <p class="text-sm text-ink-sub leading-relaxed mb-4">
          一键导出全部本地数据的 JSON 快照，用于备份或换机迁移；导入以新增方式合并，
          不覆盖、不删除现有数据。
        </p>

        <!-- 各表条数统计 -->
        <div class="grid grid-cols-3 sm:grid-cols-6 gap-2 mb-5">
          <div v-for="it in backupStatItems" :key="it.key"
            class="bg-inset border border-line rounded-md px-2 py-2.5 text-center">
            <div class="text-lg font-semibold leading-none mb-1 font-mono">{{ it.count }}</div>
            <div class="text-[11px] text-ink-faint">{{ it.label }}</div>
          </div>
        </div>

        <div class="flex items-center gap-2.5 flex-wrap">
          <button @click="exportBackup" :disabled="exportingBackup"
            class="px-4 py-2.5 text-sm font-medium rounded-md
              bg-accent text-white hover:bg-accent-hover
              disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            {{ exportingBackup ? '导出中…' : '⬇ 导出备份' }}
          </button>
          <button @click="pickImportFile" :disabled="importingBackup"
            class="px-4 py-2.5 text-sm font-medium rounded-md text-ink
              border border-line-strong hover:border-accent hover:text-accent
              disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            {{ importingBackup ? '导入中…' : '⬆ 导入恢复' }}
          </button>
          <input ref="backupFileInput" type="file" accept=".json,application/json"
            class="hidden" @change="onImportFilePicked" />
        </div>

        <p class="text-xs text-ink-faint mt-4 leading-relaxed">
          备份包含：简历 / 简历版本 / 岗位库 / 诊断历史 / 面试与刷题会话 / 导出记录；
          不含 LLM 配置（API Key 仅存本机，不落备份文件）
        </p>
      </div>

      <!-- M71 导出位置 -->
      <div class="bg-panel border-2 border-ink/80 shadow-[3px_3px_0_0] shadow-ink/20 rounded-lg p-5 md:p-7">
        <h2 class="text-base font-semibold mb-2">📁 导出位置</h2>
        <p v-if="isWeb" class="text-sm text-ink-sub leading-relaxed mb-4">
          网页版文件直接下载到浏览器下载目录，无需设置；下面的配置仅桌面版生效。
        </p>
        <p v-else class="text-sm text-ink-sub leading-relaxed mb-4">
          桌面版所有导出统一保存到下面的目录，并按类型自动归入子文件夹，不再散落各处。
        </p>

        <!-- 当前生效目录 -->
        <div class="flex items-center gap-3 flex-wrap mb-4">
          <code
            class="text-xs font-mono bg-inset border border-line rounded px-2.5 py-1.5 break-all min-w-0 flex-1">
            {{ exportRoot || '加载中…' }}
          </code>
          <button @click="openExportDir" :disabled="!isDesktop || openingExportDir"
            :title="isDesktop ? '在资源管理器中打开' : '仅桌面版支持'"
            class="px-4 py-2 text-sm font-medium rounded-md text-ink shrink-0
              border border-line-strong hover:border-accent hover:text-accent
              disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            {{ openingExportDir ? '打开中…' : '📂 打开' }}
          </button>
        </div>

        <!-- 自定义目录 -->
        <div class="flex items-center gap-2.5 flex-wrap">
          <input v-model="exportRootInput" type="text"
            placeholder="输入新的导出目录绝对路径；留空保存 = 恢复默认"
            class="flex-1 min-w-[240px] px-3.5 py-2.5 text-sm bg-inset rounded-md border border-line
              font-mono focus:outline-none focus:border-accent transition-colors" />
          <button @click="saveExportRoot" :disabled="savingExportRoot"
            class="px-4 py-2.5 text-sm font-medium rounded-md shrink-0
              bg-accent text-white hover:bg-accent-hover
              disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            {{ savingExportRoot ? '保存中…' : '保存' }}
          </button>
        </div>
        <div class="text-xs text-ink-faint mt-1.5">
          默认目录为程序目录下的 data/exports；桌面版导出无需每次另存为，自动按类型归档
        </div>

        <p class="text-xs text-ink-faint mt-3 leading-relaxed">
          分类规则：简历 →「简历」 · 投递材料包 →「投递材料包」 · 面试报告 →「面试报告」 ·
          诊断报告 →「诊断报告」 · 数据备份 →「数据备份」
        </p>
      </div>

      <!-- M60 跟进提醒 -->
      <div class="bg-panel border-2 border-ink/80 shadow-[3px_3px_0_0] shadow-ink/20 rounded-lg p-5 md:p-7">
        <h2 class="text-base font-semibold mb-2">🔔 跟进提醒</h2>
        <p class="text-sm text-ink-sub leading-relaxed mb-4">
          岗位标记「已投递」后超过下面的天数仍停留在「已投递」状态，工作台会出现「📌 求职跟进」提醒；
          把岗位流转到面试中 / Offer / 已结束，提醒自动消失。
        </p>
        <div class="flex items-center gap-2.5 flex-wrap">
          <label for="followup-days" class="text-xs text-ink-sub shrink-0">提醒阈值</label>
          <input id="followup-days" v-model.number="followupDaysInput" type="number" min="1" max="30"
            class="w-24 px-3 py-2 text-sm bg-inset rounded-md border border-line
              focus:outline-none focus:border-accent transition-colors" />
          <span class="text-xs text-ink-faint">天（1~30，默认 7）</span>
          <button @click="saveFollowupDays" :disabled="savingFollowupDays"
            class="px-4 py-2 text-sm font-medium rounded-md shrink-0
              bg-accent text-white hover:bg-accent-hover disabled:opacity-40 transition-colors">
            {{ savingFollowupDays ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import api from '../api'
import { useAppMode } from '../composables/useAppMode'
import { useKeyGuide } from '../composables/useKeyGuide'
import { JOB_SOURCES, loadJobSource, saveJobSource } from '../data/jobSources'

const guide = useKeyGuide()
const { isDesktop, isWeb } = useAppMode()

const form = reactive({ api_key: '', base_url: '', model: '' })
const showKey = ref(false)
const showApiModal = ref(false) // API 配置弹窗（原内联表单收进 Modal）
const testing = ref(false)
const testResult = ref(null)
const serverManaged = ref(false)
const vendorId = ref('custom')

/**
 * A6 主流厂商预设（OpenAI 兼容协议，后端 ChatOpenAI + base_url 零改动直连）
 * embedding：是否提供向量接口（影响 RAG 证据检索是否回退关键词）
 */
const VENDORS = [
  {
    id: 'zhipu', name: '智谱 GLM',
    base_url: 'https://open.bigmodel.cn/api/paas/v4/',
    models: ['glm-4-flash', 'glm-4-air', 'glm-4-plus'],
    embedding: true, keyUrl: 'https://open.bigmodel.cn/usercenter/apikeys',
    note: 'glm-4-flash 免费',
  },
  {
    id: 'deepseek', name: 'DeepSeek',
    base_url: 'https://api.deepseek.com/v1',
    models: ['deepseek-chat', 'deepseek-reasoner'],
    embedding: false, keyUrl: 'https://platform.deepseek.com/api_keys',
    note: '性价比高',
  },
  {
    id: 'qwen', name: '通义千问',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen-turbo', 'qwen-plus', 'qwen-max'],
    embedding: true, keyUrl: 'https://bailian.console.aliyun.com/?apiKey=1',
    note: '',
  },
  {
    id: 'kimi', name: 'Kimi',
    base_url: 'https://api.moonshot.cn/v1',
    models: ['kimi-k2-0711-preview', 'moonshot-v1-8k', 'moonshot-v1-32k'],
    embedding: false, keyUrl: 'https://platform.moonshot.cn/console/api-keys',
    note: '',
  },
  {
    id: 'doubao', name: '豆包',
    base_url: 'https://ark.cn-beijing.volces.com/api/v3',
    models: ['doubao-seed-1-6-250615', 'doubao-1-5-pro-32k-250115'],
    embedding: true, keyUrl: 'https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey',
    note: '模型名需在方舟控制台开通',
  },
  {
    id: 'openai', name: 'OpenAI',
    base_url: 'https://api.openai.com/v1',
    models: ['gpt-4o-mini', 'gpt-4o'],
    embedding: true, keyUrl: 'https://platform.openai.com/api-keys',
    note: '国内访问需网络代理',
  },
  {
    id: 'siliconflow', name: '硅基流动',
    base_url: 'https://api.siliconflow.cn/v1',
    models: ['deepseek-ai/DeepSeek-V3', 'Qwen/Qwen2.5-7B-Instruct'],
    embedding: true, keyUrl: 'https://cloud.siliconflow.cn/account/ak',
    note: '聚合平台，含免费模型',
  },
  {
    id: 'openrouter', name: 'OpenRouter',
    base_url: 'https://openrouter.ai/api/v1',
    models: ['deepseek/deepseek-chat', 'openai/gpt-4o-mini'],
    embedding: false, keyUrl: 'https://openrouter.ai/keys',
    note: '聚合平台',
  },
  {
    id: 'ollama', name: 'Ollama 本地',
    base_url: 'http://localhost:11434/v1',
    models: ['qwen2.5:7b', 'llama3.1:8b'],
    embedding: true, keyUrl: 'https://ollama.com/download',
    note: '本地免费，Key 填 ollama 即可',
    freeKey: 'ollama',
  },
  {
    id: 'custom', name: '自定义',
    base_url: '', models: [], embedding: null, keyUrl: '',
    note: '任意 OpenAI 兼容接口',
  },
]

const currentVendor = computed(() => VENDORS.find((v) => v.id === vendorId.value))
/* 获取 Key 指引卡：可直达控制台的厂商（排除自定义） */
const keyVendors = VENDORS.filter((v) => v.keyUrl && v.id !== 'custom')
const currentVendorName = computed(() =>
  currentVendor.value?.id === 'custom' ? '' : currentVendor.value?.name,
)
const hasConfig = computed(() => !!form.api_key)

async function checkServerDefault() {
  try {
    const res = await api.llmDefault()
    serverManaged.value = !!res.data?.server_key_configured
  } catch (e) {
    serverManaged.value = false
  }
}

function loadConfig() {
  try {
    const cfg = JSON.parse(localStorage.getItem('llm_config') || '{}')
    Object.assign(form, {
      api_key: cfg.api_key || '',
      base_url: cfg.base_url || '',
      model: cfg.model || '',
    })
    // 回显厂商：按 base_url 匹配预设
    const hit = VENDORS.find((v) => v.base_url && v.base_url === cfg.base_url)
    vendorId.value = hit?.id || 'custom'
  } catch (e) {}
}

function applyVendor(v) {
  vendorId.value = v.id
  if (v.id === 'custom') return
  form.base_url = v.base_url
  if (v.freeKey && !form.api_key) form.api_key = v.freeKey
  form.model = v.models[0] || ''
  testResult.value = null
}

function saveSettings() {
  if (!form.api_key.trim()) {
    Message.warning('请填写 API Key')
    return
  }
  try {
    localStorage.setItem('llm_config', JSON.stringify({ ...form }))
  } catch (e) {
    // 隐私模式 / 存储不可用时给出明确反馈，而非静默抛错
    Message.error('本机存储不可用，配置未能保存')
    return
  }
  Message.success('配置已保存')
  testResult.value = { success: true, message: '✓ 配置已保存到本机' }
  showApiModal.value = false
  // 保存后刷新引导状态（小红点消失）
  guide.refresh()
}

function clearSettings() {
  try { localStorage.removeItem('llm_config') } catch (e) { /* 清理失败不阻断表单重置 */ }
  form.api_key = ''
  form.base_url = ''
  form.model = ''
  testResult.value = null
  vendorId.value = 'custom'
  Message.success('已清空配置')
  guide.refresh()
}

async function testConnection() {
  if (!form.api_key) return
  testing.value = true
  testResult.value = null

  try {
    const res = await api.testLLM({
      api_key: form.api_key,
      base_url: form.base_url,
      model: form.model,
    })
    if (res.data.success) {
      testResult.value = {
        success: true,
        message: `✓ 连接成功！模型：${res.data.model}，响应：${res.data.response || 'OK'}`,
      }
    } else {
      testResult.value = {
        success: false,
        message: `✗ ${res.data.error}`,
        raw: res.data.raw,
      }
    }
  } catch (e) {
    testResult.value = {
      success: false,
      message: '✗ 测试失败：' + (e.response?.data?.detail || e.message),
    }
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  loadConfig()
  checkServerDefault()
  loadJobSourceCfg()
  loadBackupStats()
  loadExportRoot()
  loadFollowupDays()
  // Esc 关闭 API 配置弹窗（Teleport 到 body，@keydown.esc 不可靠）
  window.addEventListener('keydown', onGlobalKey)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onGlobalKey)
})

function onGlobalKey(e) {
  if (e.key === 'Escape' && showApiModal.value) showApiModal.value = false
}

/* ================================ M19：招聘数据源 ================================ */

const jobForm = reactive({ api_key: '', api_id: '' })
const jobProvider = ref('mock')
const jobTesting = ref(false)
const jobTestResult = ref(null)

// M22 C1：清空全部数据（二次确认）
const clearingData = ref(false)

function confirmClearData() {
  Modal.warning({
    title: '确认清空全部数据？',
    content: '诊断记录、简历库、导出历史、会话、证件照与快照将被永久删除，不可恢复。',
    okText: '确认清空',
    cancelText: '取消',
    hideCancel: false,
    onOk: async () => {
      clearingData.value = true
      try {
        await api.clearAllData()
        Message.success('已清空全部数据')
      } catch (e) {
        Message.error(e.response?.data?.detail || '清空失败')
      } finally {
        clearingData.value = false
      }
    },
  })
}

const currentJobSource = computed(() => JOB_SOURCES.find((s) => s.id === jobProvider.value))

const jobSourceReady = computed(() => {
  const s = currentJobSource.value
  if (!s) return false
  // mock / ai 无需任何 Key
  if (s.id === 'mock' || s.id === 'ai') return true
  if (s.needId && !jobForm.api_id.trim()) return false
  return !!jobForm.api_key.trim()
})

function loadJobSourceCfg() {
  const cfg = loadJobSource()
  jobProvider.value = JOB_SOURCES.some((s) => s.id === cfg.provider) ? cfg.provider : 'mock'
  jobForm.api_key = cfg.api_key || ''
  jobForm.api_id = cfg.api_id || ''
}

function applyJobSource(s) {
  jobProvider.value = s.id
  jobTestResult.value = null
}

function saveJobSourceCfg() {
  if (!jobSourceReady.value) {
    Message.warning('请补全数据源所需信息')
    return
  }
  saveJobSource({
    provider: jobProvider.value,
    api_key: jobForm.api_key.trim(),
    api_id: jobForm.api_id.trim(),
  })
  jobTestResult.value = { success: true, message: '✓ 数据源已保存，回到分析页即可一键获取岗位' }
}

function clearJobSource() {
  saveJobSource({ provider: 'mock', api_key: '', api_id: '' })
  jobProvider.value = 'mock'
  jobForm.api_key = ''
  jobForm.api_id = ''
  jobTestResult.value = null
}

async function testJob() {
  jobTesting.value = true
  jobTestResult.value = null
  let llmCfg = {}
  try { llmCfg = JSON.parse(localStorage.getItem('llm_config') || '{}') } catch (e) {}
  try {
    const res = await api.testJobProvider({
      provider: jobProvider.value,
      api_key: jobForm.api_key.trim(),
      api_id: jobForm.api_id.trim(),
      llm_config: llmCfg,
    })
    jobTestResult.value = res.data.success
      ? { success: true, message: `✓ 连接成功（${res.data.provider}），获取到 ${res.data.sample_count} 条岗位${res.data.note ? ` · ${res.data.note}` : ''}` }
      : { success: false, message: `✗ ${res.data.error}`, raw: res.data.raw }
  } catch (e) {
    jobTestResult.value = {
      success: false,
      message: '✗ 测试失败：' + (e.response?.data?.detail || e.message),
    }
  } finally {
    jobTesting.value = false
  }
}

/* ================================ M59：数据备份与恢复 ================================ */

const backupStats = ref(null)
const exportingBackup = ref(false)
const importingBackup = ref(false)
const backupFileInput = ref(null)

const BACKUP_STAT_LABELS = [
  { key: 'resumes', label: '简历' },
  { key: 'resume_versions', label: '简历版本' },
  { key: 'saved_jobs', label: '岗位库' },
  { key: 'diagnoses', label: '诊断历史' },
  { key: 'conversations', label: '面试/刷题' },
  { key: 'export_history', label: '导出记录' },
]

const backupStatItems = computed(() =>
  BACKUP_STAT_LABELS.map((it) => ({
    ...it,
    count: backupStats.value ? (backupStats.value[it.key] ?? '—') : '—',
  })),
)

async function loadBackupStats() {
  try {
    const res = await api.backupStats()
    backupStats.value = res.data || null
  } catch (e) {
    backupStats.value = null // 静默失败，展示「—」
  }
}

function backupFilename() {
  const p = (n) => String(n).padStart(2, '0')
  const d = new Date()
  return `知岗备份_${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}.json`
}

async function exportBackup() {
  exportingBackup.value = true
  try {
    if (isDesktop.value) {
      // M71 桌面态：服务端直写「数据备份」子目录，返回实际保存路径
      const res = await api.exportBackupToPath()
      const saved = res.data?.save_path
      if (saved) {
        Message.success(`备份已保存到：${saved}`)
        await loadBackupStats()
        return
      }
      // 后端未支持直写（旧版本）时退回 blob 下载
    }
    const res = await api.exportBackup()
    const url = URL.createObjectURL(new Blob([res.data], { type: 'application/json' }))
    const a = document.createElement('a')
    a.href = url
    a.download = backupFilename()
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    Message.success('备份已导出（见浏览器下载目录）')
  } catch (e) {
    Message.error('导出失败：' + (e.response?.data?.detail || e.message))
  } finally {
    exportingBackup.value = false
  }
}

function pickImportFile() {
  backupFileInput.value?.click()
}

function onImportFilePicked(e) {
  const file = e.target.files?.[0]
  e.target.value = '' // 清空以便可重复选择同一文件
  if (!file) return
  Modal.confirm({
    title: '确认导入备份？',
    content: '导入会以新增方式合并，不覆盖、不删除现有数据；同一份备份重复导入会产生重复记录。',
    okText: '开始导入',
    cancelText: '取消',
    hideCancel: false,
    onOk: () => doImportBackup(file),
  })
}

async function doImportBackup(file) {
  importingBackup.value = true
  try {
    let payload
    try {
      payload = JSON.parse(await file.text())
    } catch (err) {
      throw new Error('文件不是有效的 JSON')
    }
    const res = await api.importBackup(payload)
    const n = res.data?.imported || {}
    Message.success(
      `导入完成：简历 ${n.resumes ?? 0} · 版本 ${n.resume_versions ?? 0} · 岗位 ${n.saved_jobs ?? 0} · ` +
      `诊断 ${n.diagnoses ?? 0} · 会话 ${n.conversations ?? 0} · 导出记录 ${n.export_history ?? 0}`,
    )
    await loadBackupStats()
  } catch (e) {
    Message.error(e.response?.data?.detail || e.message || '导入失败')
  } finally {
    importingBackup.value = false
  }
}

/* ================================ M71：导出位置 ================================ */

const exportRoot = ref('')
const exportRootInput = ref('')
const savingExportRoot = ref(false)
const openingExportDir = ref(false)

async function loadExportRoot() {
  try {
    const res = await api.getExportRoot()
    exportRoot.value = res.data?.export_root || ''
    // 自定义目录回显到输入框；默认目录留空（占位符提示恢复默认语义）
    exportRootInput.value = res.data?.is_default ? '' : exportRoot.value
  } catch (e) {
    exportRoot.value = '' // 静默失败，展示「加载中…」的前态即可
  }
}

async function saveExportRoot() {
  savingExportRoot.value = true
  try {
    const res = await api.setExportRoot(exportRootInput.value.trim())
    exportRoot.value = res.data?.export_root || ''
    exportRootInput.value = res.data?.is_default ? '' : exportRoot.value
    Message.success(res.data?.is_default
      ? '已恢复默认导出目录（data/exports）'
      : `导出目录已保存：${exportRoot.value}`)
  } catch (e) {
    Message.error(e.response?.data?.detail || '保存失败')
  } finally {
    savingExportRoot.value = false
  }
}

async function openExportDir() {
  if (!isDesktop.value) {
    Message.info('仅桌面版支持打开本地目录')
    return
  }
  openingExportDir.value = true
  try {
    await api.openExportDir('')
  } catch (e) {
    Message.error(e.response?.data?.detail || '打开目录失败')
  } finally {
    openingExportDir.value = false
  }
}

/* ================================ M60：跟进提醒 ================================ */

const followupDaysInput = ref(7)
const savingFollowupDays = ref(false)

async function loadFollowupDays() {
  try {
    const res = await api.getFollowupDays()
    followupDaysInput.value = res.data?.days ?? 7
  } catch (e) { /* 静默失败，展示默认值 */ }
}

async function saveFollowupDays() {
  const days = Number(followupDaysInput.value)
  if (!Number.isInteger(days) || days < 1 || days > 30) {
    Message.warning('请输入 1~30 的整数')
    return
  }
  savingFollowupDays.value = true
  try {
    await api.setFollowupDays(days)
    Message.success(`已保存：投递 ${days} 天未流转将提醒跟进`)
  } catch (e) {
    Message.error(e.response?.data?.detail || '保存失败')
  } finally {
    savingFollowupDays.value = false
  }
}
</script>
