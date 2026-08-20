<template>
  <div class="report-preview-page">
    <!-- 顶部操作栏 -->
    <div class="preview-toolbar">
      <div class="toolbar-left">
        <el-button @click="handleBack">
          <el-icon><ArrowLeft /></el-icon>
          返回报告列表
        </el-button>
        <el-divider direction="vertical" />
        <div class="breadcrumb-report">
          <el-icon><Document /></el-icon>
          <span class="report-name">{{ reportDetail.title }}</span>
          <el-tag size="small" effect="light" type="success" v-if="reportDetail.id">已生成</el-tag>
        </div>
      </div>
      <div class="toolbar-right">
        <el-tooltip content="重命名">
          <el-button text @click="handleRename">
            <el-icon :size="18"><EditPen /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="打印">
          <el-button text @click="handlePrint">
            <el-icon :size="18"><Printer /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="复制 Markdown">
          <el-button text @click="handleCopyMD">
            <el-icon :size="18"><CopyDocument /></el-icon>
          </el-button>
        </el-tooltip>
        <el-divider direction="vertical" />
        <el-button type="primary" @click="handleExportPDF" :loading="isExporting">
          <el-icon><Download /></el-icon>
          导出 PDF
        </el-button>
      </div>
    </div>

    <!-- 报告主体（可打印区域） -->
    <div class="report-body-wrap" v-loading="isLoading">
      <div ref="reportBodyRef" id="reportBody" class="report-body">
        <div class="loading-wrap">
          <!-- 报告封面 -->
          <div class="md-cover" :class="`cover--${reportDetail.cover}`">
            <div class="cover-inner">
              <div class="cover-badge">
                <el-icon><Document /></el-icon>
                SMARTMED 医疗洞察报告
              </div>
              <h1 class="cover-title">{{ reportDetail.title || '医疗数据分析报告' }}</h1>
              <div class="cover-tags">
                <el-tag
                  v-for="t in reportDetail.tags || []"
                  :key="t"
                  size="large"
                  effect="dark"
                  class="cover-tag"
                >{{ t }}</el-tag>
              </div>
              <div class="cover-meta">
                <div><el-icon><Calendar /></el-icon> 生成日期：{{ reportDetail.createTime || new Date().toLocaleString('zh-CN') }}</div>
                <div><el-icon><OfficeBuilding /></el-icon> 数据来源：{{ reportDetail.year || '2021' }}年 · 智慧医疗分析平台 · 住院数据集</div>
              </div>
            </div>
          </div>

          <!-- Markdown 内容 -->
          <div class="md-content" v-html="renderedMD"></div>

          <!-- 报告页脚 -->
          <div class="md-footer">
            <div class="footer-divider"></div>
            <div class="footer-info">
              <div>© SmartMed BigData Platform · 智慧医疗大数据与 AI 大模型分析平台</div>
              <div>本报告由 AI 自动生成，仅供参考。如需临床决策，请结合专业医疗建议。</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import html2pdf from 'html2pdf.js'
import * as echarts from 'echarts'
import { getReportDetail, updateReport } from '@/api'

const route = useRoute()
const router = useRouter()

const isLoading = ref(false)
const isExporting = ref(false)
const reportDetail = ref({
  id: route.params.id,
  title: '',
  cover: 'finance',
  tags: [],
  createTime: '',
  content: ''
})

const reportBodyRef = ref(null)
const chartInstances = []

const injectChartPlaceholders = (md) => {
  if (!md) return md
  return md.replace(/<!--SMARTMED_CHART:([\s\S]*?)-->/g, (_, json) => {
    const safe = String(json)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
    return `<div class="report-echart" data-chart="${safe}"></div>`
  })
}

const renderedMD = computed(() => {
  if (!reportDetail.value.content) return '<p style="text-align:center;color:#9ca3af;padding:40px">报告内容加载中...</p>'
  try {
    marked.setOptions({
      breaks: true,
      gfm: true
    })
    const withCharts = injectChartPlaceholders(reportDetail.value.content)
    return marked.parse(withCharts)
  } catch (e) {
    console.error('Markdown parse error:', e)
    return reportDetail.value.content
  }
})

const disposeCharts = () => {
  while (chartInstances.length) {
    const inst = chartInstances.pop()
    try {
      inst?.dispose?.()
    } catch (_) { /* ignore */ }
  }
}

const renderEmbeddedCharts = () => {
  const el = reportBodyRef.value
  if (!el) return
  disposeCharts()
  el.querySelectorAll('.report-echart').forEach((node) => {
    let payload = null
    try {
      const raw = node.getAttribute('data-chart') || ''
      payload = JSON.parse(
        raw
          .replace(/&quot;/g, '"')
          .replace(/&lt;/g, '<')
          .replace(/&gt;/g, '>')
          .replace(/&amp;/g, '&')
      )
    } catch (e) {
      console.warn('报告图表解析失败', e)
      return
    }
    if (!payload?.categories?.length) return
    node.style.width = '100%'
    node.style.height = '360px'
    node.style.margin = '12px 0 20px'
    const chart = echarts.init(node)
    const isBar = (payload.type || 'bar') === 'bar'
    chart.setOption({
      title: {
        text: payload.title || '',
        left: 'center',
        textStyle: { fontSize: 14, fontWeight: 600, color: '#1f2937' }
      },
      tooltip: { trigger: 'axis' },
      grid: { left: 48, right: 24, top: 48, bottom: 56 },
      xAxis: {
        type: 'category',
        data: payload.categories,
        axisLabel: { rotate: payload.categories.length > 5 ? 30 : 0, color: '#6b7280' }
      },
      yAxis: {
        type: 'value',
        name: payload.valueLabel || '',
        nameTextStyle: { color: '#6b7280' },
        splitLine: { lineStyle: { type: 'dashed', color: '#e5e7eb' } }
      },
      series: [
        {
          type: isBar ? 'bar' : 'bar',
          data: payload.values,
          barMaxWidth: 42,
          itemStyle: {
            color: '#3b82f6',
            borderRadius: [4, 4, 0, 0]
          },
          label: {
            show: true,
            position: 'top',
            color: '#374151',
            fontSize: 11,
            formatter: (p) =>
              typeof p.value === 'number' && p.value >= 1000
                ? p.value.toLocaleString()
                : p.value
          }
        }
      ]
    })
    chartInstances.push(chart)
  })
}

const loadDetail = async () => {
  isLoading.value = true
  try {
    const res = await getReportDetail(route.params.id)
    if (res.code === 200 && res.data) {
      reportDetail.value = res.data
    } else {
      ElMessage.error(res.message || '报告不存在')
    }
  } catch (e) {
    ElMessage.error('报告加载失败，请确认后端已启动且报告已生成成功')
  } finally {
    isLoading.value = false
    nextTick(() => {
      styleTables()
      renderEmbeddedCharts()
    })
  }
}

watch(renderedMD, () => {
  nextTick(() => {
    styleTables()
    renderEmbeddedCharts()
  })
})

// 给 Markdown 渲染出来的表格加样式类
const styleTables = () => {
  const el = reportBodyRef.value
  if (!el) return
  el.querySelectorAll('table').forEach(tbl => {
    tbl.classList.add('md-table')
  })
  el.querySelectorAll('blockquote').forEach(bq => {
    bq.classList.add('md-quote')
  })
}

const handleBack = () => {
  router.push({ name: 'Reports' })
}

const handlePrint = () => {
  window.print()
}

const handleRename = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入新的报告标题', '重命名报告', {
      inputValue: reportDetail.value.title,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '标题不能为空'
    })
    const res = await updateReport(reportDetail.value.id, { title: value.trim() })
    if (res.code === 200) {
      reportDetail.value.title = value.trim()
      ElMessage.success('已重命名')
    }
  } catch (_) { /* cancel */ }
}

const handleCopyMD = async () => {
  try {
    await navigator.clipboard.writeText(reportDetail.value.content)
    ElMessage.success('Markdown 内容已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动选择文本')
  }
}

const safeFilename = (name) =>
  String(name || '医疗洞察报告').replace(/[\\/:*?"<>|]/g, '_').slice(0, 80)

const prepareExportNode = (doc) => {
  const root = doc.getElementById('reportBody') || doc.querySelector('.report-body')
  if (root) {
    root.style.width = '900px'
    root.style.maxWidth = '900px'
    root.style.boxShadow = 'none'
    root.style.borderRadius = '0'
    root.style.overflow = 'visible'
  }
  doc.querySelectorAll('.el-loading-mask, .el-loading-spinner').forEach((n) => n.remove())
  doc.querySelectorAll('canvas').forEach((c) => {
    if (!c.width || !c.height) c.remove()
  })
  doc.querySelectorAll('svg').forEach((svg) => {
    if (!svg.getAttribute('width')) svg.setAttribute('width', '18')
    if (!svg.getAttribute('height')) svg.setAttribute('height', '18')
  })
  doc.querySelectorAll('*').forEach((el) => {
    if (!el.style) return
    el.style.backdropFilter = 'none'
    el.style.webkitBackdropFilter = 'none'
    el.style.boxShadow = 'none'
  })
}

const handleExportPDF = async () => {
  if (!reportBodyRef.value) return
  isExporting.value = true
  const el = reportBodyRef.value
  el.classList.add('pdf-exporting')

  const opt = {
    margin: [10, 10, 12, 10],
    filename: `${safeFilename(reportDetail.value.title)}.pdf`,
    image: { type: 'jpeg', quality: 0.95 },
    html2canvas: {
      scale: 1.5,
      useCORS: true,
      logging: false,
      backgroundColor: '#ffffff',
      scrollX: 0,
      scrollY: 0,
      windowWidth: 900,
      ignoreElements: (node) => {
        if (!node || !node.tagName) return false
        if (node.classList?.contains('el-loading-mask')) return true
        if (node.tagName === 'CANVAS' && (!node.width || !node.height)) return true
        return false
      },
      onclone: prepareExportNode
    },
    jsPDF: {
      unit: 'mm',
      format: 'a4',
      orientation: 'portrait',
      compress: true
    },
    pagebreak: { mode: ['css', 'legacy'], avoid: ['tr', 'img'] }
  }

  try {
    await html2pdf().set(opt).from(el).save()
    ElMessage.success('PDF 已下载，可直接作为附件发送')
  } catch (err) {
    console.error(err)
    ElMessage.error('PDF 导出仍失败，已改为打开打印窗口，请在目标打印机中选择“另存为 PDF”')
    window.print()
  } finally {
    el.classList.remove('pdf-exporting')
    isExporting.value = false
  }
}

onMounted(loadDetail)
onBeforeUnmount(disposeCharts)
</script>

<style lang="scss" scoped>
.report-preview-page {
  display: flex;
  flex-direction: column;
  gap: $spacing-lg;
  // 抵消 layout/main-content 的内边距，使顶栏贴齐内容区上沿
  margin: (-$spacing-lg) (-$spacing-lg) 0;
}

// ========== 顶部栏 ==========
.preview-toolbar {
  background: $bg-card;
  border-radius: 0 0 $radius-xl $radius-xl;
  padding: 12px $spacing-lg;
  box-shadow: $shadow-card;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  position: sticky;
  top: (-$spacing-lg);
  z-index: 10;
}

.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.breadcrumb-report {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 4px;

  .el-icon {
    color: $primary-color;
    font-size: 18px;
  }

  .report-name {
    font-size: 15px;
    font-weight: 600;
    color: $text-primary;
    max-width: 420px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .el-tag {
    margin-left: 8px;
  }
}

// ========== 报告主体 ==========
.report-body-wrap {
  background: $bg-page;
  padding: $spacing-lg;
  border-radius: $radius-xl;
}

.report-body {
  max-width: 900px;
  margin: 0 auto;
  background: #fff;
  border-radius: $radius-lg;
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
}

.loading-wrap {
  padding: 0;
}

// ========== 封面 ==========
.md-cover {
  padding: 80px 60px 60px;
  color: #fff;
  position: relative;
  overflow: hidden;

  &.cover--finance { background: linear-gradient(135deg, #f59e0b 0%, #d97706 50%, #b45309 100%); }
  &.cover--pathology { background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 50%, #6d28d9 100%); }
  &.cover--region { background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 50%, #0369a1 100%); }

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: rgba(255, 255, 255, 0.08);
    pointer-events: none;
  }

  .cover-inner {
    position: relative;
    z-index: 2;
  }

  .cover-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    background: rgba(255, 255, 255, 0.22);
    border-radius: 20px;
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.5px;
    margin-bottom: 28px;
    border: 1px solid rgba(255, 255, 255, 0.3);
  }

  .cover-title {
    font-size: 36px;
    font-weight: 700;
    line-height: 1.3;
    margin: 0 0 24px;
    text-shadow: 0 2px 20px rgba(0, 0, 0, 0.2);
  }

  .cover-tags {
    margin-bottom: 40px;

    .cover-tag {
      margin-right: 8px;
      margin-bottom: 6px;
      background: rgba(255, 255, 255, 0.2) !important;
      border-color: rgba(255, 255, 255, 0.4) !important;
      color: #fff !important;
    }
  }

  .cover-meta {
    display: flex;
    flex-direction: column;
    gap: 10px;
    font-size: 14px;
    opacity: 0.92;
    padding-top: 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.25);

    > div {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .el-icon {
      font-size: 16px;
    }
  }
}

// ========== Markdown 内容 ==========
:deep(.md-content) {
  padding: 48px 60px;
  color: $text-primary;
  font-size: 15px;
  line-height: 1.8;

  .report-echart {
    width: 100%;
    height: 360px;
    margin: 8px 0 24px;
    background: #fafcff;
    border: 1px solid #e8eef7;
    border-radius: 8px;
  }

  h1 {
    font-size: 28px;
    font-weight: 700;
    margin: 32px 0 16px;
    padding-bottom: 10px;
    border-bottom: 2px solid $primary-color;
    color: $primary-dark;
  }

  h2 {
    font-size: 22px;
    font-weight: 700;
    margin: 28px 0 14px;
    padding-left: 14px;
    border-left: 4px solid $primary-color;
    color: $text-primary;
  }

  h3 {
    font-size: 18px;
    font-weight: 600;
    margin: 22px 0 10px;
    color: $text-regular;
  }

  h4, h5, h6 {
    font-weight: 600;
    margin: 18px 0 8px;
  }

  p {
    margin: 0 0 14px;
    text-align: justify;
  }

  ul, ol {
    margin: 0 0 14px 24px;
    li { margin-bottom: 6px; }
  }

  blockquote {
    margin: 18px 0;
    padding: 14px 20px;
    background: $primary-bg;
    border-left: 4px solid $primary-color;
    border-radius: 0 $radius-md $radius-md 0;
    color: $primary-dark;

    p { margin: 0; }
  }

  code {
    background: #f3f4f6;
    padding: 2px 8px;
    border-radius: 4px;
    font-family: Consolas, Monaco, monospace;
    font-size: 13px;
    color: #e11d48;
  }

  pre {
    background: #1f2937;
    color: #e5e7eb;
    padding: 18px 22px;
    border-radius: $radius-md;
    overflow-x: auto;
    margin: 18px 0;

    code {
      background: transparent;
      color: inherit;
      padding: 0;
      font-size: 13px;
    }
  }

  hr {
    margin: 28px 0;
    border: none;
    border-top: 1px dashed $border-color;
  }

  a {
    color: $primary-color;
    text-decoration: none;
    border-bottom: 1px solid rgba(24, 144, 255, 0.3);
    transition: all 0.2s;

    &:hover {
      color: $primary-dark;
      border-bottom-color: $primary-dark;
    }
  }

  img {
    max-width: 100%;
    border-radius: $radius-md;
    margin: 14px 0;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
    font-size: 14px;

    thead th {
      background: $primary-color;
      color: #fff;
      padding: 12px 16px;
      text-align: left;
      font-weight: 600;
      border: 1px solid darken($primary-color, 5%);

      &:first-child { border-radius: $radius-sm 0 0 0; }
      &:last-child { border-radius: 0 $radius-sm 0 0; }
    }

    tbody td {
      padding: 11px 16px;
      border: 1px solid $border-color;
      color: $text-regular;
    }

    tbody tr {
      transition: background 0.2s;

      &:nth-child(even) {
        background: #fafcff;
      }

      &:hover {
        background: $primary-bg;
      }
    }
  }
}

// ========== 页脚 ==========
.md-footer {
  padding: 30px 60px 40px;
  background: #fafcff;

  .footer-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent 0%, $border-color 50%, transparent 100%);
    margin-bottom: 20px;
  }

  .footer-info {
    text-align: center;
    font-size: 12px;
    color: $text-secondary;
    line-height: 1.8;
  }
}

.report-body.pdf-exporting {
  box-shadow: none !important;
  overflow: visible !important;

  :deep(.md-cover) {
    &::before {
      display: none !important;
    }
  }

  :deep(.cover-badge) {
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
  }

  :deep(.md-content table),
  :deep(.md-content img),
  :deep(.md-content h2) {
    break-inside: avoid;
    page-break-inside: avoid;
  }
}

// ========== 打印 & PDF 专用样式 ==========
@media print {
  .report-preview-page {
    margin: 0;
    gap: 0;
  }

  .preview-toolbar {
    display: none !important;
  }

  .report-body-wrap {
    padding: 0;
    background: #fff;
    border-radius: 0;
  }

  .report-body {
    box-shadow: none;
    border-radius: 0;
  }

  :deep(.md-cover) {
    height: 100vh;
    page-break-after: always;
    padding: 100px 60px;
    display: flex;
    align-items: center;
  }
}
</style>
