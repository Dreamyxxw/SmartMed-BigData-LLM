<template>
  <div class="dashboard-page">
    <!-- 顶部 KPI 卡片 -->
    <div class="kpi-grid">
      <div
        v-for="(kpi, index) in kpiList"
        :key="kpi.key"
        class="kpi-card"
        :class="`kpi-card--${index}`"
      >
        <div class="kpi-card__inner">
          <div class="kpi-card__icon-wrap">
            <el-icon class="kpi-card__icon"><component :is="kpi.icon" /></el-icon>
          </div>
          <div class="kpi-card__info">
            <div class="kpi-card__title">{{ kpi.title }}</div>
            <div class="kpi-card__value">
              <span class="kpi-number" :ref="el => setNumberRef(kpi.key, el)">0</span>
              <span class="kpi-unit">{{ kpi.unit }}</span>
            </div>
            <div class="kpi-card__sub">
              <span :class="kpi.trend > 0 ? 'trend-up' : 'trend-down'">
                <el-icon>
                  <component :is="kpi.trend > 0 ? 'Top' : 'Bottom'" />
                </el-icon>
                {{ Math.abs(kpi.trend) }}%
              </span>
              <span class="trend-label">较上期</span>
            </div>
          </div>
        </div>
        <div class="kpi-card__deco"></div>
      </div>
    </div>

    <!-- 图表矩阵区 -->
    <div class="charts-grid">
      <!-- 图表A：年龄段环形图（可点击联动） -->
      <div class="chart-card card">
        <div class="card__header">
          <div class="card__header-title">
            <el-icon class="title-icon"><PieChart /></el-icon>
            患者年龄段占比分布
            <el-tag
              v-if="selectedAgeGroup"
              type="primary"
              effect="light"
              closable
              class="filter-tag"
              @close="selectedAgeGroup = null"
            >
              已筛选：{{ selectedAgeGroup }}
            </el-tag>
          </div>
          <div class="chart-download-btn">
            <el-button size="small" @click="handleDownloadChart('ageGroupChart', '年龄段分布')">
              <el-icon><Download /></el-icon>下载
            </el-button>
          </div>
        </div>
        <div class="card__body">
          <div ref="ageGroupChartRef" id="ageGroupChart" class="chart-container"></div>
          <div class="chart-tip">
            <el-icon><InfoFilled /></el-icon>
            点击环形图中的年龄段，右侧Top10疾病将自动筛选为该年龄段数据
          </div>
        </div>
      </div>

      <!-- 图表B：Top10最昂贵疾病 -->
      <div class="chart-card card">
        <div class="card__header">
          <div class="card__header-title">
            <el-icon class="title-icon"><Trophy /></el-icon>
            {{ selectedAgeGroup ? `${selectedAgeGroup}人群中` : '全人群' }}Top 10 最昂贵疾病
          </div>
          <div class="chart-download-btn">
            <el-button size="small" @click="handleDownloadChart('topDiseasesChart', 'Top10昂贵疾病')">
              <el-icon><Download /></el-icon>下载
            </el-button>
          </div>
        </div>
        <div class="card__body">
          <div ref="topDiseasesChartRef" id="topDiseasesChart" class="chart-container chart-container--bar"></div>
        </div>
      </div>

      <!-- 图表C：双轴对比图（全宽） -->
      <div class="chart-card card chart-card--full">
        <div class="card__header">
          <div class="card__header-title">
            <el-icon class="title-icon"><TrendCharts /></el-icon>
            各科室总费用与平均住院天数双轴对比
          </div>
          <div class="chart-download-btn">
            <el-button size="small" @click="handleDownloadChart('deptCompareChart', '科室费用对比')">
              <el-icon><Download /></el-icon>下载
            </el-button>
          </div>
        </div>
        <div class="card__body">
          <div ref="deptCompareChartRef" id="deptCompareChart" class="chart-container chart-container--wide"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useGlobalStore } from '@/stores/global'
import { getKpiData, getAgeGroupData, getTopDiseasesData, getDeptCompareData } from '@/api'
import { techColors, downloadChart, animateNumber } from '@/utils/chart'

const globalStore = useGlobalStore()

// ========== KPI ==========
const kpiList = ref([
  { key: 'totalDischarges', title: '总出院人数', value: 0, unit: '人', icon: 'User', trend: 5.2 },
  { key: 'avgTotalCharges', title: '平均住院总费用', value: 0, unit: '元', icon: 'Wallet', trend: 3.8 },
  { key: 'avgTotalCosts', title: '平均总成本', value: 0, unit: '元', icon: 'Money', trend: 2.1 },
  { key: 'avgStayDays', title: '平均住院天数', value: 0, unit: '天', icon: 'Calendar', trend: -4.2 }
])

const numberRefs = reactive({})
const setNumberRef = (key, el) => {
  if (el) numberRefs[key] = el
}

// ========== 图表 refs ==========
const ageGroupChartRef = ref(null)
const topDiseasesChartRef = ref(null)
const deptCompareChartRef = ref(null)

let ageGroupChartInstance = null
let topDiseasesChartInstance = null
let deptCompareChartInstance = null

// ========== 联动状态 ==========
const selectedAgeGroup = ref(null)

// ========== KPI 数据加载 ==========
const loadKpiData = async () => {
  const params = {
    year: globalStore.selectedYear,
    region: globalStore.selectedRegion
  }
  const res = await getKpiData(params)
  if (res.code === 200) {
    const data = res.data
    nextTick(() => {
      kpiList.value.forEach(kpi => {
        kpi.value = data[kpi.key]
        if (numberRefs[kpi.key]) {
          animateNumber(numberRefs[kpi.key], kpi.value, 1800)
        }
      })
    })
  }
}

// ========== 年龄段环形图 ==========
const renderAgeGroupChart = async () => {
  if (!ageGroupChartRef.value) return
  const params = {
    year: globalStore.selectedYear,
    region: globalStore.selectedRegion
  }
  const res = await getAgeGroupData(params)
  if (res.code !== 200) return

  if (!ageGroupChartInstance) {
    ageGroupChartInstance = echarts.init(ageGroupChartRef.value)
    ageGroupChartInstance.on('click', (params) => {
      if (params.componentType === 'series') {
        selectedAgeGroup.value = selectedAgeGroup.value === params.name ? null : params.name
      }
    })
    window.addEventListener('resize', handleResizeAgeGroup)
  }

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}<br/>人数：{c} 人 ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      itemWidth: 12,
      itemHeight: 12,
      textStyle: { fontSize: 13, color: '#4b5563' },
      formatter: (name) => {
        const item = res.data.find(d => d.name === name)
        return item ? `${name}  ${item.value.toLocaleString()}` : name
      }
    },
    color: techColors,
    series: [
      {
        name: '年龄段',
        type: 'pie',
        radius: ['45%', '72%'],
        center: ['38%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: true,
          position: 'outside',
          formatter: '{b}\n{d}%',
          fontSize: 12,
          color: '#6b7280',
          lineHeight: 16
        },
        labelLine: {
          show: true,
          length: 10,
          length2: 12
        },
        emphasis: {
          scale: true,
          scaleSize: 8,
          label: {
            fontSize: 14,
            fontWeight: 'bold',
            color: '#1890ff'
          },
          itemStyle: {
            shadowBlur: 16,
            shadowColor: 'rgba(24, 144, 255, 0.4)'
          }
        },
        data: res.data.map(item => ({
          ...item,
          selected: selectedAgeGroup.value === item.name,
          itemStyle: selectedAgeGroup.value && selectedAgeGroup.value !== item.name
            ? { opacity: 0.35 }
            : {}
        })),
        animationType: 'scale',
        animationEasing: 'elasticOut',
        animationDuration: 1200
      }
    ]
  }
  ageGroupChartInstance.setOption(option, true)
}

const handleResizeAgeGroup = () => ageGroupChartInstance?.resize()

// ========== Top10 疾病横向柱状图 ==========
const renderTopDiseasesChart = async () => {
  if (!topDiseasesChartRef.value) return
  const params = {
    year: globalStore.selectedYear,
    region: globalStore.selectedRegion,
    ageGroup: selectedAgeGroup.value
  }
  const res = await getTopDiseasesData(params)
  if (res.code !== 200) return

  if (!topDiseasesChartInstance) {
    topDiseasesChartInstance = echarts.init(topDiseasesChartRef.value)
    window.addEventListener('resize', handleResizeTopDiseases)
  }

  const data = res.data.slice().reverse()
  const maxVal = Math.max(...data.map(d => d.value))

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const p = params[0]
        return `${p.name}<br/>平均费用：<b>$${p.value.toLocaleString()}</b>`
      }
    },
    grid: {
      left: '3%',
      right: '6%',
      bottom: '3%',
      top: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      name: '费用(元)',
      nameTextStyle: { fontSize: 11, color: '#9ca3af' },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#9ca3af',
        fontSize: 11,
        formatter: (v) => v >= 1000 ? (v / 1000) + 'k' : v
      },
      splitLine: {
        lineStyle: { color: '#f3f4f6', type: 'dashed' }
      }
    },
    yAxis: {
      type: 'category',
      data: data.map(d => d.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#4b5563',
        fontSize: 12,
        fontWeight: 500
      }
    },
    series: [
      {
        name: '平均费用',
        type: 'bar',
        barWidth: 14,
        data: data.map((d, idx) => ({
          value: d.value,
          itemStyle: {
            borderRadius: [0, 7, 7, 0],
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: techColors[idx % techColors.length] + 'CC' },
              { offset: 1, color: techColors[idx % techColors.length] }
            ])
          }
        })),
        label: {
          show: true,
          position: 'right',
          formatter: (p) => '$' + (p.value / 1000).toFixed(1) + 'k',
          color: '#4b5563',
          fontSize: 11,
          fontWeight: 600
        },
        showBackground: true,
        backgroundStyle: {
          color: 'rgba(243, 244, 246, 0.6)',
          borderRadius: [0, 7, 7, 0]
        },
        animationDelay: (idx) => idx * 80,
        animationEasing: 'cubicOut'
      }
    ]
  }
  topDiseasesChartInstance.setOption(option, true)
}

const handleResizeTopDiseases = () => topDiseasesChartInstance?.resize()

// ========== 科室双轴对比图 ==========
const renderDeptCompareChart = async () => {
  if (!deptCompareChartRef.value) return
  const params = {
    year: globalStore.selectedYear,
    region: globalStore.selectedRegion
  }
  const res = await getDeptCompareData(params)
  if (res.code !== 200) return

  if (!deptCompareChartInstance) {
    deptCompareChartInstance = echarts.init(deptCompareChartRef.value)
    window.addEventListener('resize', handleResizeDeptCompare)
  }

  const data = res.data

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: ['总费用(万元)', '平均住院天数(天)', '出院人数'],
      top: 0,
      right: 20,
      textStyle: { fontSize: 13, color: '#4b5563' },
      itemWidth: 16,
      itemHeight: 10
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '14%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: data.map(d => d.name),
      axisPointer: { type: 'shadow' },
      axisLine: { lineStyle: { color: '#e5e7eb' } },
      axisLabel: { color: '#4b5563', fontSize: 13, fontWeight: 500 }
    },
    yAxis: [
      {
        type: 'value',
        name: '总费用(万元)',
        position: 'left',
        nameTextStyle: { fontSize: 11, color: '#9ca3af' },
        axisLine: { show: true, lineStyle: { color: '#1890ff' } },
        axisLabel: {
          color: '#1890ff',
          fontSize: 11,
          formatter: (v) => v / 100
        },
        splitLine: { lineStyle: { color: '#f3f4f6', type: 'dashed' } }
      },
      {
        type: 'value',
        name: '天数 / 人数',
        position: 'right',
        nameTextStyle: { fontSize: 11, color: '#9ca3af' },
        axisLine: { show: true, lineStyle: { color: '#91cc75' } },
        axisLabel: { color: '#91cc75', fontSize: 11 },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '总费用(万元)',
        type: 'bar',
        barWidth: '28%',
        yAxisIndex: 0,
        data: data.map(d => Math.round(d.totalCharges / 100)),
        itemStyle: {
          borderRadius: [6, 6, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#69b1ff' },
            { offset: 1, color: '#1890ff' }
          ])
        }
      },
      {
        name: '平均住院天数(天)',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        data: data.map(d => d.avgStayDays),
        lineStyle: { width: 3, color: '#91cc75' },
        itemStyle: { color: '#91cc75', borderWidth: 2, borderColor: '#fff' }
      },
      {
        name: '出院人数',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'diamond',
        symbolSize: 8,
        data: data.map(d => d.count),
        lineStyle: { width: 2.5, color: '#faad14', type: 'dashed' },
        itemStyle: { color: '#faad14', borderWidth: 2, borderColor: '#fff' }
      }
    ],
    animationDuration: 1000
  }
  deptCompareChartInstance.setOption(option, true)
}

const handleResizeDeptCompare = () => deptCompareChartInstance?.resize()

// ========== 下载图表 ==========
const handleDownloadChart = (chartId, fileName) => {
  downloadChart(chartId, fileName)
}

// ========== 监听筛选变化 ==========
watch(
  () => [globalStore.selectedYear, globalStore.selectedRegion],
  () => {
    loadKpiData()
    renderAgeGroupChart()
    renderTopDiseasesChart()
    renderDeptCompareChart()
  }
)

watch(selectedAgeGroup, () => {
  renderAgeGroupChart()
  renderTopDiseasesChart()
})

// ========== 生命周期 ==========
onMounted(async () => {
  await nextTick()
  loadKpiData()
  renderAgeGroupChart()
  renderTopDiseasesChart()
  renderDeptCompareChart()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResizeAgeGroup)
  window.removeEventListener('resize', handleResizeTopDiseases)
  window.removeEventListener('resize', handleResizeDeptCompare)
  ageGroupChartInstance?.dispose()
  topDiseasesChartInstance?.dispose()
  deptCompareChartInstance?.dispose()
})
</script>

<style lang="scss" scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: $spacing-lg;
}

// ========== KPI 卡片 ==========
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: $spacing-lg;
}

.kpi-card {
  position: relative;
  background: $bg-card;
  border-radius: $radius-xl;
  padding: 20px 24px;
  box-shadow: $shadow-card;
  overflow: hidden;
  transition: all 0.3s ease;

  &:hover {
    transform: translateY(-4px);
    box-shadow: $shadow-card-hover;
  }

  &__inner {
    position: relative;
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 18px;
  }

  &__icon-wrap {
    width: 56px;
    height: 56px;
    border-radius: $radius-lg;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  &__icon {
    font-size: 28px;
    color: #fff;
  }

  &__info {
    flex: 1;
    min-width: 0;
  }

  &__title {
    font-size: 13px;
    color: $text-secondary;
    margin-bottom: 8px;
    font-weight: 500;
  }

  &__value {
    display: flex;
    align-items: baseline;
    gap: 4px;
    margin-bottom: 6px;
  }

  &__sub {
    font-size: 12px;
    color: $text-secondary;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  &__deco {
    position: absolute;
    right: -20px;
    bottom: -20px;
    width: 120px;
    height: 120px;
    border-radius: 50%;
    opacity: 0.08;
    z-index: 1;
  }

  // 每个卡片独立配色
  &--0 {
    .kpi-card__icon-wrap { background: $gradient-blue; }
    &::before {
      content: '';
      position: absolute;
      top: 0; left: 0;
      width: 4px; height: 100%;
      background: $gradient-blue;
      border-radius: 4px 0 0 4px;
    }
    .kpi-card__deco { background: #1890ff; }
    .trend-up { color: $success-color; }
  }
  &--1 {
    .kpi-card__icon-wrap { background: $gradient-orange; }
    &::before {
      content: '';
      position: absolute;
      top: 0; left: 0;
      width: 4px; height: 100%;
      background: $gradient-orange;
      border-radius: 4px 0 0 4px;
    }
    .kpi-card__deco { background: #faad14; }
    .trend-up { color: $success-color; }
  }
  &--2 {
    .kpi-card__icon-wrap { background: $gradient-green; }
    &::before {
      content: '';
      position: absolute;
      top: 0; left: 0;
      width: 4px; height: 100%;
      background: $gradient-green;
      border-radius: 4px 0 0 4px;
    }
    .kpi-card__deco { background: #52c41a; }
    .trend-up { color: $success-color; }
  }
  &--3 {
    .kpi-card__icon-wrap { background: $gradient-primary; }
    &::before {
      content: '';
      position: absolute;
      top: 0; left: 0;
      width: 4px; height: 100%;
      background: $gradient-primary;
      border-radius: 4px 0 0 4px;
    }
    .kpi-card__deco { background: #722ed1; }
    .trend-down { color: $success-color; }
    .trend-up { color: $danger-color; }
  }
}

.kpi-number {
  font-size: 28px;
  font-weight: 700;
  color: $text-primary;
  line-height: 1.1;
  font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
}

.kpi-unit {
  font-size: 13px;
  color: $text-secondary;
  font-weight: 500;
}

.trend-up, .trend-down {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-weight: 600;
  font-size: 12px;
}

.trend-up { color: $danger-color; }
.trend-down { color: $success-color; }

.trend-label {
  color: $text-placeholder;
}

// ========== 图表矩阵 ==========
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: $spacing-lg;
}

.chart-card {
  display: flex;
  flex-direction: column;
  min-height: 420px;

  &--full {
    grid-column: 1 / -1;
    min-height: 380px;
  }
}

.chart-container {
  width: 100%;
  height: 330px;

  &--bar {
    height: 330px;
  }
  &--wide {
    height: 300px;
  }
}

.filter-tag {
  margin-left: 8px;
  font-weight: normal;
}

.chart-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding: 8px 12px;
  background: rgba(24, 144, 255, 0.06);
  border-radius: $radius-sm;
  font-size: 12px;
  color: $primary-dark;

  .el-icon {
    font-size: 14px;
    flex-shrink: 0;
  }
}

// ========== 响应式 ==========
@media (max-width: 1400px) {
  .kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 1000px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
}
</style>
