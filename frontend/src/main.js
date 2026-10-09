import { createApp } from 'vue'
import ArcoVueIcon from '@arco-design/web-vue/es/icon'
import { Modal } from '@arco-design/web-vue'
import '@arco-design/web-vue/es/modal/style/css.js'
import '@arco-design/web-vue/es/message/style/css.js'
import './style.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)
// Arco UI 按需引入：全量 ArcoVue + 全量 arco.css 共 1.15MB+，只用 Modal 组件 + Message/Modal 函数式 API
// 函数式 API（Message/Modal）不需注册组件，import 即可用
app.component('a-modal', Modal)
app.use(ArcoVueIcon)
app.use(router)
app.mount('#app')