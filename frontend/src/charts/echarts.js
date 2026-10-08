/**
 * echarts 按需注册（全量引入约 1.1MB，按需后仅保留实际用到的图表与组件）
 * LineChart.vue：line + grid/xAxis/yAxis + tooltip(axis) + title(空数据占位)
 * RadarChart.vue：radar(坐标系 RadarComponent + 系列 RadarChart) + legend(多系列对比)
 */
import * as echarts from 'echarts/core'
import { LineChart, RadarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  RadarComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart,
  RadarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  RadarComponent,
  CanvasRenderer,
])

export default echarts
