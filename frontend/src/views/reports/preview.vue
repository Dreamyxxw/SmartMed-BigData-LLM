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
        <el-button @click="handleExportPDF('html')" :loading="isExporting">
          <el-icon><Download /></el-icon>
          导出 PDF
        </el-button>
        <el-button type="primary" @click="handleShare">
          <el-icon><Share /></el-icon>
          分享报告
        </el-button>
      </div>
    </div>

    <!-- 报告主体（可打印区域） -->
    <div class="report-body-wrap">
      <div ref="reportBodyRef" id="reportBody" class="report-body">
        <div v-loading="isLoading" class="loading-wrap">
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
                <div><el-icon><OfficeBuilding /></el-icon> 数据来源：智慧医疗分析平台 · 住院数据集</div>
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
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import html2pdf from 'html2pdf.js'
import { getReportDetail } from '@/api'

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

const renderedMD = computed(() => {
  if (!reportDetail.value.content) return '<p style="text-align:center;color:#9ca3af;padding:40px">报告内容加载中...</p>'
  try {
    marked.setOptions({
      breaks: true,
      gfm: true
    })
    return marked.parse(reportDetail.value.content)
  } catch (e) {
    console.error('Markdown parse error:', e)
    return reportDetail.value.content
  }
})

const loadDetail = async () => {
  isLoading.value = true
  try {
    const res = await getReportDetail(route.params.id)
    if (res.code === 200) reportDetail.value = res.data
  } catch (e) {
    ElMessage.error('报告加载失败，请确认缓存已构建且报告存在')
  } finally {
    isLoading.value = false
    nextTick(styleTables)
  }
}

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

const handleCopyMD = async () => {
  try {
    await navigator.clipboard.writeText(reportDetail.value.content)
    ElMessage.success('Markdown 内容已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动选择文本')
  }
}

const handleShare = () => {
  const url = window.location.href
  navigator.clipboard?.writeText(url).then(() => {
    ElMessage.success('报告链接已复制到剪贴板')
  }).catch(() => {
    ElMessage.info(`分享链接：${url}`)
  })
}

const handleExportPDF = async () => {
  if (!reportBodyRef.value) return
  isExporting.value = true

  const opt = {
    margin: [8, 8, 8, 8],
    filename: `${reportDetail.value.title || '医疗洞察报告'}.pdf`,
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: {
      scale: 2,
      useCORS: true,
      logging: false,
      letterRendering: true
    },
    jsPDF: {
      unit: 'mm',
      format: 'a4',
      orientation: 'portrait',
      compress: true
    },
    pagebreak: { mode: ['avoid-all', 'css', 'legacy'] }
  }

  try {
    await html2pdf().set(opt).from(reportBodyRef.value).save()
    ElMessage.success('PDF 导出成功！')
  } catch (err) {
    console.error(err)
    ElMessage.error('PDF 导出失败：' + err.message)
  } finally {
    isExporting.value = false
  }
}

onMounted(loadDetail)
</script>

<style lang="scss" scoped>
.report-preview-page {
  display: flex;
  flex-direction: column;
  gap: $spacing-lg;
}

// ========== 顶部栏 ==========
.preview-toolbar {
  background: $bg-card;
  border-radius: $radius-xl;
  padding: 12px $spacing-lg;
  box-shadow: $shadow-card;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  position: sticky;
  top: 0;
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
    background-image:
      radial-gradient(circle at 15% 20%, rgba(255,255,255,0.2) 0%, transparent 45%),
      radial-gradient(circle at 85% 80%, rgba(255,255,255,0.15) 0%, transparent 45%);
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
    background: rgba(255, 255, 255, 0.18);
    backdrop-filter: blur(8px);
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

// ========== 打印 & PDF 专用样式 ==========
@media print {
  .preview-toolbar {
    display: none !important;
  }

  .report-preview-page {
    gap: 0;
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
