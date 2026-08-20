<template>
  <div class="reports-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">
          <el-icon><Document /></el-icon>
          自动化医疗洞察报告
        </h2>
        <p class="page-desc">
          基于静态医疗数据，结合 LLM 自动生成可沉淀的结构化分析报告
        </p>
      </div>
      <div class="header-actions">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索报告标题..."
          style="width: 240px"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select v-model="filterTag" placeholder="按标签筛选" clearable style="width: 160px">
          <el-option
            v-for="tag in tagOptions"
            :key="tag"
            :label="tag"
            :value="tag"
          />
        </el-select>
      </div>
    </div>

    <!-- 报告卡片网格 -->
    <div class="reports-grid" v-loading="isLoading">
      <div
        v-for="report in filteredReports"
        :key="report.id"
        class="report-card"
        @click="handlePreview(report)"
      >
        <div class="report-card__cover" :class="`cover--${report.cover}`">
          <div class="cover-bg"></div>
          <div class="cover-icon">
            <el-icon :size="42">
              <component :is="coverIcon(report.cover)" />
            </el-icon>
          </div>
          <div class="cover-overlay">
            <span class="overlay-text">点击预览</span>
          </div>
        </div>
        <div class="report-card__body">
          <h3 class="report-title" :title="report.title">{{ report.title }}</h3>
          <p class="report-desc">{{ report.description }}</p>
          <div class="report-meta">
            <div class="report-tags">
              <el-tag
                v-for="tag in report.tags"
                :key="tag"
                size="small"
                effect="light"
                :type="tagType(tag)"
              >{{ tag }}</el-tag>
            </div>
            <div class="report-time">
              <el-icon><Clock /></el-icon>
              {{ report.createTime }}
            </div>
          </div>
        </div>
        <div class="report-card__actions" @click.stop>
          <el-button size="small" text type="primary" @click="handlePreview(report)">
            <el-icon><View /></el-icon>
            预览
          </el-button>
          <el-button size="small" text type="success" @click="handleExportPDF(report)">
            <el-icon><Download /></el-icon>
            PDF
          </el-button>
          <el-dropdown trigger="click" @command="(cmd) => handleCardCommand(cmd, report)">
            <el-button size="small" text>
              <el-icon><MoreFilled /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit">
                  <el-icon><Edit /></el-icon> 编辑信息
                </el-dropdown-item>
                <el-dropdown-item command="copy">
                  <el-icon><CopyDocument /></el-icon> 复制报告
                </el-dropdown-item>
                <el-dropdown-item command="delete" divided>
                  <el-icon><Delete /></el-icon> 删除报告
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="filteredReports.length === 0 && !isLoading" class="empty-state">
        <el-empty description="暂无符合条件的报告" :image-size="100">
          <el-button type="primary" @click="showCreateDrawer = true">
            <el-icon><Plus /></el-icon>
            创建第一份报告
          </el-button>
        </el-empty>
      </div>
    </div>

    <!-- 悬浮创建按钮 -->
    <el-button
      class="fab-create"
      type="primary"
      circle
      size="large"
      @click="showCreateDrawer = true"
    >
      <el-icon :size="22"><Plus /></el-icon>
    </el-button>

    <!-- 创建报告抽屉 -->
    <el-drawer
      v-model="showCreateDrawer"
      title="创建新报告"
      direction="rtl"
      size="520px"
      :close-on-click-modal="false"
    >
      <div class="create-form">
        <el-form :model="createForm" label-position="top" label-width="100px">
          <el-form-item label="分析主题" required>
            <el-select v-model="createForm.topic" placeholder="请选择报告主题" class="w-full">
              <el-option-group label="病理分析">
                <el-option label="特定疾病分析" value="特定疾病分析">
                  <span style="float: left">特定疾病分析</span>
                  <span style="float: right; color: #8492a6; font-size: 13px">病理</span>
                </el-option>
                <el-option label="病种趋势对比" value="病种趋势对比" />
              </el-option-group>
              <el-option-group label="财务分析">
                <el-option label="费用构成分析" value="费用构成分析">
                  <span style="float: left">费用构成分析</span>
                  <span style="float: right; color: #8492a6; font-size: 13px">财务</span>
                </el-option>
                <el-option label="成本效益评估" value="成本效益评估" />
              </el-option-group>
              <el-option-group label="区域管理">
                <el-option label="区域医疗评估" value="区域医疗评估">
                  <span style="float: left">区域医疗评估</span>
                  <span style="float: right; color: #8492a6; font-size: 13px">区域分析</span>
                </el-option>
                <el-option label="医院科室排名" value="医院科室排名" />
              </el-option-group>
              <el-option-group label="综合报告">
                <el-option label="季度综合报告" value="季度综合报告" />
                <el-option label="年度综合总结" value="年度综合总结" />
              </el-option-group>
            </el-select>
          </el-form-item>

          <el-form-item label="报告标题">
            <el-input
              v-model="createForm.title"
              placeholder="留空则自动生成标题"
              clearable
            />
          </el-form-item>

          <el-divider content-position="left">分析范围</el-divider>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="分析年份">
                <el-select v-model="createForm.year" class="w-full">
                  <el-option
                    v-for="y in globalStore.yearOptions"
                    :key="y.value"
                    :label="y.label"
                    :value="y.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="分析区域">
                <el-select v-model="createForm.region" class="w-full">
                  <el-option
                    v-for="r in globalStore.regionOptions"
                    :key="r.value"
                    :label="r.label"
                    :value="r.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="附加标签（可选）">
            <el-select
              v-model="createForm.tags"
              multiple
              filterable
              allow-create
              placeholder="输入后回车添加自定义标签"
              class="w-full"
            >
              <el-option label="儿科" value="儿科" />
              <el-option label="老年医学" value="老年医学" />
              <el-option label="心血管" value="心血管" />
              <el-option label="内分泌" value="内分泌" />
              <el-option label="资源管理" value="资源管理" />
            </el-select>
          </el-form-item>

          <el-divider content-position="left">报告生成选项</el-divider>

          <el-form-item label="图表类型">
            <el-checkbox-group v-model="createForm.chartTypes">
              <el-checkbox value="bar" label="bar">柱状图</el-checkbox>
              <el-checkbox value="line" label="line">折线图</el-checkbox>
              <el-checkbox value="pie" label="pie">饼图</el-checkbox>
              <el-checkbox value="table" label="table">数据表格</el-checkbox>
            </el-checkbox-group>
          </el-form-item>

          <el-form-item label="报告详细程度">
            <el-radio-group v-model="createForm.detailLevel">
              <el-radio-button value="summary">精简版</el-radio-button>
              <el-radio-button value="standard">标准版</el-radio-button>
              <el-radio-button value="detailed">详细版</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="附加分析">
            <el-checkbox-group v-model="createForm.extras">
              <el-checkbox value="recommendations" label="recommendations">AI 诊疗建议</el-checkbox>
              <el-checkbox value="predictions" label="predictions">趋势预测</el-checkbox>
              <el-checkbox value="benchmarks" label="benchmarks">同比/环比对比</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <div class="drawer-footer">
          <el-button @click="showCreateDrawer = false">取消</el-button>
          <el-button
            type="primary"
            :loading="isGenerating"
            :disabled="!createForm.topic"
            @click="handleGenerate"
          >
            <el-icon><MagicStick /></el-icon>
            {{ isGenerating ? '正在生成...' : '生成报告' }}
          </el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useGlobalStore } from '@/stores/global'
import {
  getReportList,
  getReportMeta,
  generateReport,
  deleteReport,
  updateReport,
  duplicateReport
} from '@/api'

const router = useRouter()
const globalStore = useGlobalStore()

const isLoading = ref(false)
const isGenerating = ref(false)
const showCreateDrawer = ref(false)
const searchKeyword = ref('')
const filterTag = ref('')
const reportList = ref([])
const metaTags = ref(['财务', '病理', '区域分析', '年度报告', '综合', '资源管理'])

const tagOptions = computed(() => {
  const set = new Set(metaTags.value)
  reportList.value.forEach((r) => (r.tags || []).forEach((t) => set.add(t)))
  return Array.from(set)
})

const filteredReports = computed(() => {
  let list = reportList.value
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    list = list.filter(
      (r) =>
        (r.title || '').toLowerCase().includes(kw) ||
        (r.description || '').toLowerCase().includes(kw)
    )
  }
  if (filterTag.value) {
    list = list.filter((r) => (r.tags || []).includes(filterTag.value))
  }
  return list
})

const createForm = reactive({
  topic: '',
  title: '',
  year: globalStore.selectedYear,
  region: globalStore.selectedRegion,
  tags: [],
  chartTypes: ['bar', 'line', 'table'],
  detailLevel: 'standard',
  extras: ['recommendations', 'benchmarks']
})

watch(showCreateDrawer, (open) => {
  if (open) {
    createForm.year = globalStore.selectedYear || createForm.year
    createForm.region = globalStore.selectedRegion || 'all'
  }
})

const loadReports = async () => {
  isLoading.value = true
  try {
    const res = await getReportList()
    if (res.code === 200) reportList.value = res.data || []
  } catch (e) {
    reportList.value = []
  } finally {
    isLoading.value = false
  }
}

const loadMeta = async () => {
  try {
    const res = await getReportMeta()
    if (res.code === 200 && res.data) {
      if (Array.isArray(res.data.tags) && res.data.tags.length) {
        metaTags.value = res.data.tags
      }
    }
  } catch (_) { /* 后端未就绪时用默认标签 */ }
}

const handlePreview = (report) => {
  router.push({ name: 'ReportPreview', params: { id: report.id } })
}

const handleExportPDF = (report) => {
  ElMessage.info(`正在打开《${report.title}》预览页，可在预览页导出 PDF`)
  router.push({ name: 'ReportPreview', params: { id: report.id } })
}

const handleGenerate = async () => {
  if (!createForm.topic) {
    ElMessage.warning('请选择分析主题')
    return
  }
  isGenerating.value = true
  try {
    const res = await generateReport({
      topic: createForm.topic,
      title: createForm.title,
      year: createForm.year || globalStore.selectedYear,
      region: createForm.region || globalStore.selectedRegion || 'all',
      tags: createForm.tags,
      chartTypes: createForm.chartTypes,
      detailLevel: createForm.detailLevel,
      extras: createForm.extras
    })
    if (res.code === 200) {
      ElMessage.success(`报告《${res.data.title}》生成成功！`)
      showCreateDrawer.value = false
      createForm.topic = ''
      createForm.title = ''
      createForm.tags = []
      await loadReports()
      if (res.data?.id) {
        router.push({ name: 'ReportPreview', params: { id: res.data.id } })
      }
    }
  } catch (_) {
    // 错误已由 request 拦截器提示
  } finally {
    isGenerating.value = false
  }
}

const handleCardCommand = async (cmd, report) => {
  if (cmd === 'edit') {
    try {
      const { value } = await ElMessageBox.prompt('修改报告标题', '编辑信息', {
        inputValue: report.title,
        confirmButtonText: '保存',
        cancelButtonText: '取消',
        inputPattern: /\S+/,
        inputErrorMessage: '标题不能为空'
      })
      const res = await updateReport(report.id, { title: value })
      if (res.code === 200) {
        ElMessage.success('已更新')
        await loadReports()
      }
    } catch (_) { /* cancel */ }
    return
  }

  if (cmd === 'copy') {
    try {
      const res = await duplicateReport(report.id)
      if (res.code === 200) {
        ElMessage.success('已复制报告')
        await loadReports()
      }
    } catch (_) { /* handled */ }
    return
  }

  if (cmd === 'delete') {
    try {
      await ElMessageBox.confirm(`确定删除「${report.title}」吗？`, '删除报告', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      })
      const res = await deleteReport(report.id)
      if (res.code === 200) {
        ElMessage.success('已删除')
        await loadReports()
      }
    } catch (_) { /* cancel */ }
  }
}

const coverIcon = (cover) => {
  const map = { finance: 'Wallet', pathology: 'Notebook', region: 'Location' }
  return map[cover] || 'Document'
}

const tagType = (tag) => {
  if (['财务', '季度报告', '年度报告'].includes(tag)) return 'warning'
  if (['病理', '老年医学', '心血管', '内分泌'].includes(tag)) return 'danger'
  if (['区域分析', '资源管理'].includes(tag)) return 'info'
  if (['综合'].includes(tag)) return ''
  return 'primary'
}

onMounted(async () => {
  try {
    await globalStore.loadMeta()
  } catch (_) { /* ignore */ }
  await Promise.all([loadMeta(), loadReports()])
})
</script>

<style lang="scss" scoped>
.reports-page {
  position: relative;
}

// ========== 页头 ==========
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: $spacing-lg;
  gap: 16px;
  flex-wrap: wrap;

  .page-title {
    font-size: 22px;
    font-weight: 700;
    color: $text-primary;
    margin: 0 0 6px;
    display: flex;
    align-items: center;
    gap: 10px;

    .el-icon {
      color: $primary-color;
    }
  }

  .page-desc {
    font-size: 13px;
    color: $text-secondary;
    margin: 0;
  }
}

.header-actions {
  display: flex;
  gap: 10px;
}

// ========== 报告卡片网格 ==========
.reports-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: $spacing-lg;
}

.report-card {
  background: $bg-card;
  border-radius: $radius-xl;
  box-shadow: $shadow-card;
  overflow: hidden;
  transition: all 0.3s ease;
  cursor: pointer;
  display: flex;
  flex-direction: column;

  &:hover {
    transform: translateY(-6px);
    box-shadow: 0 14px 36px rgba(24, 144, 255, 0.18);

    .cover-overlay {
      opacity: 1;
    }
  }

  &__cover {
    height: 160px;
    position: relative;
    overflow: hidden;

    .cover-bg {
      position: absolute;
      inset: 0;
    }

    &.cover--finance .cover-bg { background: $gradient-orange; }
    &.cover--pathology .cover-bg { background: $gradient-primary; }
    &.cover--region .cover-bg { background: $gradient-blue; }

    .cover-bg::before {
      content: '';
      position: absolute;
      inset: 0;
      background-image:
        radial-gradient(circle at 20% 30%, rgba(255,255,255,0.25) 0%, transparent 40%),
        radial-gradient(circle at 80% 70%, rgba(255,255,255,0.15) 0%, transparent 40%);
    }
    .cover-bg::after {
      content: '';
      position: absolute;
      inset: 0;
      background-image:
        linear-gradient(135deg, transparent 25%, rgba(255,255,255,0.06) 25%, rgba(255,255,255,0.06) 50%, transparent 50%, transparent 75%, rgba(255,255,255,0.06) 75%);
      background-size: 28px 28px;
      opacity: 0.5;
    }

    .cover-icon {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      color: #fff;
      z-index: 2;
      text-shadow: 0 2px 12px rgba(0, 0, 0, 0.2);
    }

    .cover-overlay {
      position: absolute;
      inset: 0;
      background: rgba(0, 0, 0, 0.4);
      z-index: 3;
      display: flex;
      align-items: center;
      justify-content: center;
      opacity: 0;
      transition: opacity 0.3s;

      .overlay-text {
        color: #fff;
        font-weight: 600;
        font-size: 15px;
        padding: 8px 20px;
        border: 2px solid #fff;
        border-radius: 20px;
      }
    }
  }

  &__body {
    padding: 16px 18px 14px;
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  .report-title {
    font-size: 15px;
    font-weight: 600;
    color: $text-primary;
    line-height: 1.45;
    margin: 0 0 8px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .report-desc {
    font-size: 12.5px;
    color: $text-secondary;
    line-height: 1.6;
    margin: 0 0 12px;
    flex: 1;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .report-meta {
    border-top: 1px solid $border-color-light;
    padding-top: 12px;
  }

  .report-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-bottom: 8px;
  }

  .report-time {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 12px;
    color: $text-placeholder;

    .el-icon {
      font-size: 13px;
    }
  }

  &__actions {
    display: flex;
    justify-content: space-around;
    padding: 10px 8px;
    background: #fafcff;
    border-top: 1px solid $border-color-light;
  }
}

.empty-state {
  grid-column: 1 / -1;
  padding: 60px 0;
}

// ========== 悬浮按钮 ==========
.fab-create {
  position: fixed;
  right: 36px;
  bottom: 40px;
  width: 60px !important;
  height: 60px !important;
  box-shadow: 0 8px 24px rgba(24, 144, 255, 0.45);
  z-index: 100;
  transition: all 0.3s;

  &:hover {
    transform: scale(1.08) rotate(90deg);
    box-shadow: 0 12px 32px rgba(24, 144, 255, 0.55);
  }
}

// ========== 创建表单 ==========
.create-form {
  padding: 8px 8px 0;

  :deep(.el-form-item__label) {
    font-weight: 600;
    color: $text-regular;
  }
}

.w-full {
  width: 100%;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
