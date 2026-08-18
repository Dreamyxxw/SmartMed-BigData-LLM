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
        <el-button type="primary" @click="openCreateDrawer">
          <el-icon><Plus /></el-icon>
          新建报告
        </el-button>
      </div>
    </div>

    <!-- 标签筛选条：点击即可选择 / 取消 -->
    <div class="tag-filter-bar">
      <div class="tag-filter-bar__label">
        <el-icon><PriceTag /></el-icon>
        标签
      </div>
      <div class="tag-filter-bar__chips">
        <el-check-tag
          :checked="selectedTags.length === 0"
          @change="clearTagFilter"
        >全部</el-check-tag>
        <el-check-tag
          v-for="tag in tagOptions"
          :key="tag"
          :checked="selectedTags.includes(tag)"
          @change="() => toggleFilterTag(tag)"
        >{{ tag }}</el-check-tag>
      </div>
      <div class="tag-filter-bar__meta">
        {{ filteredReports.length }} / {{ reportList.length }} 份
        <el-button
          v-if="selectedTags.length || searchKeyword"
          text
          type="primary"
          size="small"
          @click="resetFilters"
        >清除筛选</el-button>
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
                class="clickable-tag"
                :class="{ 'is-active': selectedTags.includes(tag) }"
                @click.stop="toggleFilterTag(tag)"
              >{{ tag }}</el-tag>
            </div>
            <div class="report-time">
              <el-icon><Clock /></el-icon>
              {{ report.updateTime || report.createTime }}
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
                <el-dropdown-item command="rename">
                  <el-icon><EditPen /></el-icon> 重命名
                </el-dropdown-item>
                <el-dropdown-item command="editTags">
                  <el-icon><PriceTag /></el-icon> 编辑标签
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
        <el-empty :description="emptyDescription" :image-size="100">
          <el-button v-if="hasActiveFilter" @click="resetFilters">清除筛选</el-button>
          <el-button type="primary" @click="openCreateDrawer">
            <el-icon><Plus /></el-icon>
            创建第一份报告
          </el-button>
        </el-empty>
      </div>
    </div>

    <!-- 悬浮创建按钮 -->
    <el-tooltip content="新建报告" placement="left">
      <el-button
        class="fab-create"
        type="primary"
        circle
        size="large"
        @click="openCreateDrawer"
      >
        <el-icon :size="22"><Plus /></el-icon>
      </el-button>
    </el-tooltip>

    <!-- 创建报告抽屉 -->
    <el-drawer
      v-model="showCreateDrawer"
      title="创建新报告"
      direction="rtl"
      size="540px"
      :close-on-click-modal="false"
    >
      <div class="create-form">
        <el-form :model="createForm" label-position="top">
          <el-form-item label="分析主题" required>
            <el-select
              v-model="createForm.topic"
              placeholder="请选择报告主题"
              class="w-full"
              filterable
            >
              <el-option-group
                v-for="group in topicGroups"
                :key="group.label"
                :label="group.label"
              >
                <el-option
                  v-for="item in group.items"
                  :key="item.value"
                  :label="item.value"
                  :value="item.value"
                >
                  <span>{{ item.value }}</span>
                  <span class="topic-desc">{{ item.desc }}</span>
                </el-option>
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

          <el-form-item label="报告标签" required>
            <el-select
              v-model="createForm.tags"
              multiple
              filterable
              allow-create
              default-first-option
              placeholder="选择或输入后回车添加标签"
              class="w-full"
            >
              <el-option-group
                v-for="group in tagGroups"
                :key="group.label"
                :label="group.label"
              >
                <el-option
                  v-for="tag in group.tags"
                  :key="tag"
                  :label="tag"
                  :value="tag"
                />
              </el-option-group>
            </el-select>
            <p class="form-hint">选择主题后会自动带出推荐标签，可增删或自定义。</p>
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

          <el-divider content-position="left">报告生成选项</el-divider>

          <el-form-item label="图表类型">
            <el-checkbox-group v-model="createForm.chartTypes">
              <el-checkbox label="bar">柱状图</el-checkbox>
              <el-checkbox label="line">折线图</el-checkbox>
              <el-checkbox label="pie">饼图</el-checkbox>
              <el-checkbox label="table">数据表格</el-checkbox>
            </el-checkbox-group>
          </el-form-item>

          <el-form-item label="报告详细程度">
            <el-radio-group v-model="createForm.detailLevel">
              <el-radio-button label="summary">精简版</el-radio-button>
              <el-radio-button label="standard">标准版</el-radio-button>
              <el-radio-button label="detailed">详细版</el-radio-button>
            </el-radio-group>
            <p class="form-hint">{{ detailLevelHint }}</p>
          </el-form-item>

          <el-form-item label="附加分析">
            <el-checkbox-group v-model="createForm.extras">
              <el-checkbox label="recommendations">AI 诊疗建议</el-checkbox>
              <el-checkbox label="predictions">趋势预测</el-checkbox>
              <el-checkbox label="benchmarks">同比/环比对比</el-checkbox>
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

    <!-- 编辑标签 / 简介 -->
    <el-dialog
      v-model="showEditDialog"
      title="编辑报告信息"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form :model="editForm" label-position="top">
        <el-form-item label="标题">
          <el-input v-model="editForm.title" maxlength="80" show-word-limit />
        </el-form-item>
        <el-form-item label="简介">
          <el-input
            v-model="editForm.description"
            type="textarea"
            :rows="3"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="editForm.tags"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="选择或新建标签"
            class="w-full"
          >
            <el-option-group
              v-for="group in tagGroups"
              :key="group.label"
              :label="group.label"
            >
              <el-option
                v-for="tag in group.tags"
                :key="tag"
                :label="tag"
                :value="tag"
              />
            </el-option-group>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" :loading="isSavingEdit" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
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

const DEFAULT_TOPIC_GROUPS = [
  {
    label: '病理洞察',
    items: [
      { value: '特定疾病分析', desc: '高发/高费用诊断分布' },
      { value: '病种趋势对比', desc: '病种人次与均费对比' },
      { value: '病情严重程度分析', desc: 'APR 病情分层与资源消耗' },
      { value: '死亡风险分层分析', desc: 'APR 死亡风险与高危人群' },
      { value: '出院转归分析', desc: '回家/转院/死亡等结局' },
      { value: '急诊入院路径分析', desc: '急诊 vs 择期入院负荷' },
      { value: '人群病理画像', desc: '年龄、性别与病种交叉' },
      { value: '手术与内科路径对比', desc: '手术/内科路径费用与住院日' }
    ]
  },
  {
    label: '财务分析',
    items: [
      { value: '费用构成分析', desc: '支付方式与科室费用结构' },
      { value: '成本效益评估', desc: 'Charges vs Costs 效率' }
    ]
  },
  {
    label: '区域管理',
    items: [
      { value: '区域医疗评估', desc: '各区出院量与均费对比' },
      { value: '医院科室排名', desc: '科室负荷与资源占用' }
    ]
  },
  {
    label: '综合报告',
    items: [
      { value: '季度综合报告', desc: '多维指标一页总览' },
      { value: '年度综合总结', desc: '年度 KPI 与分布底稿' }
    ]
  }
]

const DEFAULT_TAG_GROUPS = [
  { label: '报告类别', tags: ['财务', '病理', '区域分析', '综合'] },
  { label: '病理维度', tags: ['病种分布', '严重程度', '死亡风险', '急诊入院', '出院转归', '人群画像', '手术路径'] },
  { label: '病种方向', tags: ['心血管', '肿瘤', '感染', '内分泌', '老年医学', '儿科'] },
  { label: '管理维度', tags: ['费用构成', '成本效益', '资源管理', '年度报告'] }
]

const DEFAULT_PRESETS = {
  特定疾病分析: ['病理', '病种分布'],
  病种趋势对比: ['病理', '病种分布'],
  病情严重程度分析: ['病理', '严重程度'],
  死亡风险分层分析: ['病理', '死亡风险'],
  出院转归分析: ['病理', '出院转归'],
  急诊入院路径分析: ['病理', '急诊入院'],
  人群病理画像: ['病理', '人群画像'],
  '手术与内科路径对比': ['病理', '手术路径'],
  费用构成分析: ['财务', '费用构成'],
  成本效益评估: ['财务', '成本效益'],
  区域医疗评估: ['区域分析', '资源管理'],
  医院科室排名: ['区域分析', '资源管理'],
  季度综合报告: ['年度报告', '综合'],
  年度综合总结: ['年度报告', '综合']
}

const router = useRouter()
const globalStore = useGlobalStore()

const isLoading = ref(false)
const isGenerating = ref(false)
const isSavingEdit = ref(false)
const showCreateDrawer = ref(false)
const showEditDialog = ref(false)
const searchKeyword = ref('')
const selectedTags = ref([])
const reportList = ref([])
const topicGroups = ref(DEFAULT_TOPIC_GROUPS)
const tagGroups = ref(DEFAULT_TAG_GROUPS)
const topicPresets = ref({ ...DEFAULT_PRESETS })
const editingReportId = ref('')

const editForm = reactive({
  title: '',
  description: '',
  tags: []
})

const tagOptions = computed(() => {
  const set = new Set()
  tagGroups.value.forEach((g) => (g.tags || []).forEach((t) => set.add(t)))
  reportList.value.forEach((r) => (r.tags || []).forEach((t) => set.add(t)))
  return Array.from(set)
})

const hasActiveFilter = computed(() => selectedTags.value.length > 0 || !!searchKeyword.value)

const emptyDescription = computed(() =>
  hasActiveFilter.value ? '暂无符合条件的报告' : '还没有洞察报告，点击下方开始创建'
)

const detailLevelHint = computed(() => {
  const map = {
    summary: '精简版：核心 KPI 与主题主表，适合快速汇报。',
    standard: '标准版：在精简版基础上补充对照维度（默认）。',
    detailed: '详细版：追加入院类型、性别等补充章节。'
  }
  return map[createForm.detailLevel] || map.standard
})

const filteredReports = computed(() => {
  let list = reportList.value
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    list = list.filter(
      (r) =>
        (r.title || '').toLowerCase().includes(kw) ||
        (r.description || '').toLowerCase().includes(kw) ||
        (r.tags || []).some((t) => String(t).toLowerCase().includes(kw))
    )
  }
  if (selectedTags.value.length) {
    list = list.filter((r) =>
      selectedTags.value.every((tag) => (r.tags || []).includes(tag))
    )
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

watch(
  () => createForm.topic,
  (topic) => {
    if (!topic) return
    const preset = topicPresets.value[topic]
    if (preset && preset.length) createForm.tags = [...preset]
  }
)

const openCreateDrawer = () => {
  createForm.topic = ''
  createForm.title = ''
  createForm.tags = []
  createForm.year = globalStore.selectedYear || createForm.year
  createForm.region = globalStore.selectedRegion || 'all'
  createForm.chartTypes = ['bar', 'line', 'table']
  createForm.detailLevel = 'standard'
  createForm.extras = ['recommendations', 'benchmarks']
  showCreateDrawer.value = true
}

const toggleFilterTag = (tag) => {
  const idx = selectedTags.value.indexOf(tag)
  if (idx >= 0) selectedTags.value = selectedTags.value.filter((t) => t !== tag)
  else selectedTags.value = [...selectedTags.value, tag]
}

const clearTagFilter = () => {
  selectedTags.value = []
}

const resetFilters = () => {
  selectedTags.value = []
  searchKeyword.value = ''
}

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
      if (Array.isArray(res.data.topicGroups) && res.data.topicGroups.length) {
        topicGroups.value = res.data.topicGroups
      }
      if (Array.isArray(res.data.tagGroups) && res.data.tagGroups.length) {
        tagGroups.value = res.data.tagGroups
      }
      if (res.data.topicPresets && typeof res.data.topicPresets === 'object') {
        const mapped = {}
        Object.entries(res.data.topicPresets).forEach(([k, v]) => {
          mapped[k] = Array.isArray(v) ? v : (v?.tags || DEFAULT_PRESETS[k] || [])
        })
        topicPresets.value = { ...DEFAULT_PRESETS, ...mapped }
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
  if (!createForm.tags.length) {
    ElMessage.warning('请至少选择一个标签')
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

const openEditDialog = (report) => {
  editingReportId.value = report.id
  editForm.title = report.title || ''
  editForm.description = report.description || ''
  editForm.tags = [...(report.tags || [])]
  showEditDialog.value = true
}

const saveEdit = async () => {
  if (!editForm.title.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }
  isSavingEdit.value = true
  try {
    const res = await updateReport(editingReportId.value, {
      title: editForm.title.trim(),
      description: editForm.description,
      tags: editForm.tags
    })
    if (res.code === 200) {
      ElMessage.success('已保存')
      showEditDialog.value = false
      await loadReports()
    }
  } catch (_) { /* handled */ } finally {
    isSavingEdit.value = false
  }
}

const handleCardCommand = async (cmd, report) => {
  if (cmd === 'rename') {
    try {
      const { value } = await ElMessageBox.prompt('请输入新的报告标题', '重命名报告', {
        inputValue: report.title,
        confirmButtonText: '保存',
        cancelButtonText: '取消',
        inputPattern: /\S+/,
        inputErrorMessage: '标题不能为空'
      })
      const res = await updateReport(report.id, { title: value.trim() })
      if (res.code === 200) {
        ElMessage.success('已重命名')
        await loadReports()
      }
    } catch (_) { /* cancel */ }
    return
  }

  if (cmd === 'editTags') {
    openEditDialog(report)
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
      await ElMessageBox.confirm(`确定删除「${report.title}」吗？删除后不可恢复。`, '删除报告', {
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
  if (['财务', '季度报告', '年度报告', '费用构成', '成本效益'].includes(tag)) return 'warning'
  if (['病理', '严重程度', '死亡风险', '急诊入院', '出院转归', '病种分布', '人群画像', '手术路径'].includes(tag)) return 'danger'
  if (['心血管', '肿瘤', '感染', '内分泌', '老年医学', '儿科'].includes(tag)) return 'danger'
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
  margin-bottom: 14px;
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
  align-items: center;
}

// ========== 标签筛选 ==========
.tag-filter-bar {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: $spacing-lg;
  padding: 12px 14px;
  background: $bg-card;
  border-radius: $radius-lg;
  box-shadow: $shadow-card;

  &__label {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    font-weight: 600;
    color: $text-regular;
    padding-top: 4px;
  }

  &__chips {
    flex: 1;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  &__meta {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: $text-placeholder;
    padding-top: 4px;
    white-space: nowrap;
  }
}

:deep(.el-check-tag) {
  border-radius: $radius-pill;
}

.clickable-tag {
  cursor: pointer;
  transition: transform 0.15s;

  &:hover {
    transform: translateY(-1px);
  }

  &.is-active {
    outline: 1px solid $primary-color;
  }
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

.topic-desc {
  float: right;
  color: #8492a6;
  font-size: 12px;
  margin-left: 12px;
}

.form-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: $text-placeholder;
  line-height: 1.4;
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
