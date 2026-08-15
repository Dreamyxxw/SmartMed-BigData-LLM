// ECharts 工具函数
import * as echarts from 'echarts'

// 科技蓝主题配色
export const techColors = [
  '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
  '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#1890ff'
]

// 图表下载为图片
export function downloadChart(chartId, fileName = 'chart') {
  const chartDom = document.getElementById(chartId)
  if (!chartDom) {
    console.warn('Chart element not found:', chartId)
    return
  }
  const instance = echarts.getInstanceByDom(chartDom)
  if (!instance) {
    console.warn('ECharts instance not found for:', chartId)
    return
  }
  const url = instance.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#ffffff'
  })
  const link = document.createElement('a')
  link.download = `${fileName}-${Date.now()}.png`
  link.href = url
  link.click()
}

// 数字翻滚动画
export function animateNumber(el, target, duration = 1500) {
  if (!el) return
  const start = 0
  const startTime = performance.now()
  const isDecimal = target % 1 !== 0

  const update = (currentTime) => {
    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / duration, 1)
    const easeOutQuart = 1 - Math.pow(1 - progress, 4)
    const current = start + (target - start) * easeOutQuart

    if (isDecimal) {
      el.textContent = current.toLocaleString('zh-CN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })
    } else {
      el.textContent = Math.round(current).toLocaleString('zh-CN')
    }

    if (progress < 1) {
      requestAnimationFrame(update)
    }
  }
  requestAnimationFrame(update)
}
