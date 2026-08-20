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
        <el-button type="primary" @click="openCreateDialog">
          <el-icon><Plus /></el-icon>
          新建报告
        </el-button>
      </div>
    </div>

    <!-- 标签筛选：按类别分组（类似猎聘多维度筛选） -->
    <div class="tag-filter-panel">
      <div class="tag-filter-panel__header">
        <div class="tag-filter-panel__title">
          <el-icon><Filter /></el-icon>
          筛选报告
        </div>
        <div class="tag-filter-panel__meta">
          <span>{{ filteredReports.length }} / {{ reportList.length }} 份</span>
          <el-button text type="primary" size="small" @click="openTagManageDialog">
            管理标签
          </el-button>
          <el-button
            v-if="selectedTags.length || searchKeyword"
            text
            type="primary"
            size="small"
            @click="resetFilters"
          >清除筛选</el-button>
        </div>
      </div>

      <div class="tag-filter-row tag-filter-row--quick">
        <span class="tag-filter-row__label">快捷</span>
        <div class="tag-filter-row__chips">
          <el-check-tag
            :checked="selectedTags.length === 0"
            @change="clearTagFilter"
          >全部</el-check-tag>
        </div>
      </div>

      <div
        v-for="group in displayTagGroups"
        :key="group.label"
        class="tag-filter-row"
      >
        <span class="tag-filter-row__label">{{ group.label }}</span>
        <div class="tag-filter-row__chips">
          <el-check-tag
            v-for="tag in group.tags"
            :key="`${group.label}-${tag}`"
            :checked="selectedTags.includes(tag)"
            @change="() => toggleFilterTag(tag)"
          >{{ tag }}</el-check-tag>
        </div>
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
              <el-dropdown-menu class="report-card-menu">
                <el-dropdown-item command="rename">
                  <el-icon><EditPen /></el-icon>
                  <span>重命名</span>
                </el-dropdown-item>
                <el-dropdown-item command="editTags">
                  <el-icon><PriceTag /></el-icon>
                  <span>编辑标签</span>
                </el-dropdown-item>
                <el-dropdown-item command="delete" class="is-danger">
                  <el-icon><Delete /></el-icon>
                  <span>删除报告</span>
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
          <el-button type="primary" @click="openCreateDialog">
            <el-icon><Plus /></el-icon>
            创建第一份报告
          </el-button>
        </el-empty>
      </div>
    </div>

    <!-- 创建报告弹窗 -->
    <el-dialog
      v-model="showCreateDialog"
      title="创建新报告"
      width="560px"
      align-center
      :close-on-click-modal="false"
      destroy-on-close
      class="create-report-dialog"
    >
      <div class="create-form">
        <el-form :model="createForm" label-position="top">
          <el-form-item label="分析主题" required>
            <el-select
              v-model="createForm.topic"
              placeholder="选择预设，或直接输入自定义主题后回车"
              class="w-full"
              filterable
              allow-create
              default-first-option
              clearable
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

          <el-form-item label="附加分析">
            <el-checkbox-group v-model="createForm.extras" class="extras-checkbox-group">
              <el-checkbox
                v-for="opt in EXTRA_ANALYSIS_OPTIONS"
                :key="opt.value"
                :label="opt.value"
              >{{ opt.label }}</el-checkbox>
            </el-checkbox-group>
          </el-form-item>

          <el-form-item label="生成备注">
            <el-input
              v-model="createForm.remarks"
              type="textarea"
              :rows="4"
              maxlength="500"
              show-word-limit
              placeholder="用自然语言描述你希望本报告重点分析的方向，例如：「重点对比 Bronx 与 Manhattan 的白血病患者费用差异，并给出控费建议」"
            />
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showCreateDialog = false">取消</el-button>
          <el-button
            type="primary"
            :loading="isGenerating"
            loading-text="正在生成..."
            :disabled="!createForm.topic"
            @click="handleGenerate"
          >
            生成报告
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 自定义标签 / 类别 -->
    <el-dialog
      v-model="showTagManageDialog"
      title="管理标签与类别"
      width="520px"
      align-center
      :close-on-click-modal="false"
    >
      <div class="tag-manage-form">
        <el-form label-position="top">
          <el-form-item label="向已有类别添加标签">
            <div class="tag-manage-inline">
              <el-select v-model="tagManageForm.groupLabel" placeholder="选择类别" class="flex-1">
                <el-option
                  v-for="g in tagGroups"
                  :key="g.label"
                  :label="g.label"
                  :value="g.label"
                />
              </el-select>
              <el-input
                v-model="tagManageForm.tagName"
                placeholder="新标签名"
                class="flex-1"
                maxlength="20"
                @keyup.enter="addTagToExistingGroup"
              />
              <el-button type="primary" @click="addTagToExistingGroup">添加</el-button>
            </div>
          </el-form-item>

          <el-form-item label="新建类别">
            <div class="tag-manage-inline">
              <el-input
                v-model="tagManageForm.newGroupLabel"
                placeholder="类别名称，如：科室方向"
                class="flex-1"
                maxlength="20"
              />
              <el-input
                v-model="tagManageForm.newGroupFirstTag"
                placeholder="首个标签（可选）"
                class="flex-1"
                maxlength="20"
                @keyup.enter="addCustomGroup"
              />
              <el-button type="primary" @click="addCustomGroup">创建</el-button>
            </div>
          </el-form-item>
        </el-form>

        <div class="tag-manage-custom">
          <div class="tag-manage-custom__title">全部类别与标签</div>
          <div v-for="item in allTagManageList" :key="item.label" class="tag-manage-custom__row">
            <div class="tag-manage-custom__label-wrap">
              <span class="tag-manage-custom__label">{{ item.label }}</span>
              <el-button
                text
                type="primary"
                size="small"
                class="tag-manage-custom__rename"
                @click="promptRenameGroup(item.label)"
              >重命名</el-button>
            </div>
            <div class="tag-manage-custom__tags">
              <el-tag
                v-for="t in item.tags"
                :key="item.label + t"
                size="small"
                closable
                class="tag-manage-custom__tag"
                @close="handleRemoveTag(item.label, t)"
                @dblclick="promptRenameTag(item.label, t)"
              >{{ t }}</el-tag>
              <span v-if="!item.tags.length" class="tag-manage-custom__empty">暂无标签</span>
            </div>
            <el-button
              text
              type="danger"
              size="small"
              class="tag-manage-custom__delete"
              @click="handleRemoveGroup(item.label)"
            >删除类别</el-button>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showTagManageDialog = false">关闭</el-button>
        <el-button
          type="danger"
          plain
          :disabled="!hasTagOverrides"
          @click="resetAllTagEdits"
        >恢复默认</el-button>
      </template>
    </el-dialog>

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
import {
  DEFAULT_TAG_GROUPS,
  loadCustomTagConfig,
  saveCustomTagConfig,
  mergeTagGroups,
  emptyTagConfig,
  addTagToConfig,
  addGroupToConfig,
  removeTagFromConfig,
  removeGroupFromConfig,
  renameGroupInConfig,
  renameTagInConfig,
  hasTagConfigOverrides
} from '@/utils/reportTagGroups'
import { useGlobalStore } from '@/stores/global'
import {
  getReportList,
  getReportMeta,
  generateReport,
  deleteReport,
  updateReport
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
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const showTagManageDialog = ref(false)
const searchKeyword = ref('')
const selectedTags = ref([])
const reportList = ref([])
const topicGroups = ref(DEFAULT_TOPIC_GROUPS)
const baseTagGroups = ref([...DEFAULT_TAG_GROUPS])
const customTagConfig = ref(loadCustomTagConfig())
const tagGroups = computed(() => mergeTagGroups(baseTagGroups.value, customTagConfig.value))
const hasTagOverrides = computed(() => hasTagConfigOverrides(customTagConfig.value))
const allTagManageList = computed(() =>
  tagGroups.value.map((g) => ({ label: g.label, tags: [...(g.tags || [])] }))
)
const topicPresets = ref({ ...DEFAULT_PRESETS })
const editingReportId = ref('')

const editForm = reactive({
  title: '',
  description: '',
  tags: []
})

const tagManageForm = reactive({
  groupLabel: '',
  tagName: '',
  newGroupLabel: '',
  newGroupFirstTag: ''
})

const persistCustomTags = () => {
  saveCustomTagConfig(customTagConfig.value)
}

const applyTagConfig = (next) => {
  customTagConfig.value = next
  persistCustomTags()
}

const openTagManageDialog = () => {
  tagManageForm.groupLabel = tagGroups.value[0]?.label || ''
  tagManageForm.tagName = ''
  tagManageForm.newGroupLabel = ''
  tagManageForm.newGroupFirstTag = ''
  showTagManageDialog.value = true
}

const addTagToExistingGroup = () => {
  const label = tagManageForm.groupLabel?.trim()
  const tag = tagManageForm.tagName?.trim()
  if (!label) {
    ElMessage.warning('请选择类别')
    return
  }
  if (!tag) {
    ElMessage.warning('请输入标签名')
    return
  }
  if (tagGroups.value.some((g) => g.label === label && g.tags.includes(tag))) {
    ElMessage.info('该标签已存在')
    return
  }
  applyTagConfig(addTagToConfig(customTagConfig.value, baseTagGroups.value, label, tag))
  tagManageForm.tagName = ''
  ElMessage.success('已添加标签')
}

const addCustomGroup = () => {
  const label = tagManageForm.newGroupLabel?.trim()
  const firstTag = tagManageForm.newGroupFirstTag?.trim()
  if (!label) {
    ElMessage.warning('请输入类别名称')
    return
  }
  if (tagGroups.value.some((g) => g.label === label)) {
    if (firstTag) {
      applyTagConfig(addTagToConfig(customTagConfig.value, baseTagGroups.value, label, firstTag))
      tagManageForm.newGroupLabel = ''
      tagManageForm.newGroupFirstTag = ''
      ElMessage.success('已向已有类别添加标签')
      return
    }
    ElMessage.info('该类别已存在，可直接向其中添加标签')
    tagManageForm.groupLabel = label
    return
  }
  applyTagConfig(addGroupToConfig(customTagConfig.value, label, firstTag))
  tagManageForm.newGroupLabel = ''
  tagManageForm.newGroupFirstTag = ''
  ElMessage.success('已创建类别')
}

const handleRemoveTag = async (groupLabel, tag) => {
  try {
    await ElMessageBox.confirm(`确定删除标签「${tag}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch (_) {
    return
  }
  applyTagConfig(removeTagFromConfig(customTagConfig.value, baseTagGroups.value, groupLabel, tag))
  selectedTags.value = selectedTags.value.filter((t) => t !== tag)
  ElMessage.success('已删除标签')
}

const handleRemoveGroup = async (groupLabel) => {
  try {
    await ElMessageBox.confirm(`确定删除类别「${groupLabel}」及其下所有标签？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch (_) {
    return
  }
  const group = tagGroups.value.find((g) => g.label === groupLabel)
  applyTagConfig(removeGroupFromConfig(customTagConfig.value, baseTagGroups.value, groupLabel))
  if (group?.tags?.length) {
    const removeSet = new Set(group.tags)
    selectedTags.value = selectedTags.value.filter((t) => !removeSet.has(t))
  }
  ElMessage.success('已删除类别')
}

const promptRenameGroup = async (groupLabel) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入新的类别名称', '重命名类别', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: groupLabel,
      inputPattern: /\S+/,
      inputErrorMessage: '类别名称不能为空'
    })
    const next = String(value || '').trim()
    if (!next || next === groupLabel) return
    if (tagGroups.value.some((g) => g.label === next)) {
      ElMessage.warning('该类别名称已存在')
      return
    }
    applyTagConfig(renameGroupInConfig(customTagConfig.value, baseTagGroups.value, groupLabel, next))
    if (tagManageForm.groupLabel === groupLabel) tagManageForm.groupLabel = next
    ElMessage.success('已重命名类别')
  } catch (_) { /* cancelled */ }
}

const promptRenameTag = async (groupLabel, tag) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入新的标签名称', '重命名标签', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: tag,
      inputPattern: /\S+/,
      inputErrorMessage: '标签名称不能为空'
    })
    const next = String(value || '').trim()
    if (!next || next === tag) return
    const group = tagGroups.value.find((g) => g.label === groupLabel)
    if (group?.tags.includes(next)) {
      ElMessage.warning('该标签已存在')
      return
    }
    applyTagConfig(renameTagInConfig(customTagConfig.value, baseTagGroups.value, groupLabel, tag, next))
    selectedTags.value = selectedTags.value.map((t) => (t === tag ? next : t))
    ElMessage.success('已重命名标签')
  } catch (_) { /* cancelled */ }
}

const resetAllTagEdits = async () => {
  try {
    await ElMessageBox.confirm(
      '确定恢复为系统默认的类别与标签？将清除所有本地修改（含自定义项）。',
      '恢复默认',
      { type: 'warning' }
    )
    customTagConfig.value = emptyTagConfig()
    persistCustomTags()
    selectedTags.value = []
    ElMessage.success('已恢复默认')
  } catch (_) { /* cancelled */ }
}

const displayTagGroups = computed(() => {
  // 筛选栏只展示「当前报告列表」实际用到的标签，不做全量穷举
  const used = new Set()
  reportList.value.forEach((r) => {
    ;(r.tags || []).forEach((t) => {
      const s = String(t || '').trim()
      if (s) used.add(s)
    })
  })
  if (!used.size) return []

  const assigned = new Set()
  const groups = []
  tagGroups.value.forEach((g) => {
    const tags = (g.tags || []).filter((t) => used.has(t))
    if (!tags.length) return
    tags.forEach((t) => assigned.add(t))
    groups.push({ label: g.label, tags })
  })

  const extras = [...used].filter((t) => !assigned.has(t))
  if (extras.length) {
    groups.push({ label: '其他', tags: extras })
  }
  return groups
})

watch(displayTagGroups, (groups) => {
  const available = new Set()
  groups.forEach((g) => (g.tags || []).forEach((t) => available.add(t)))
  if (selectedTags.value.some((t) => !available.has(t))) {
    selectedTags.value = selectedTags.value.filter((t) => available.has(t))
  }
})

const hasActiveFilter = computed(() => selectedTags.value.length > 0 || !!searchKeyword.value)

const emptyDescription = computed(() =>
  hasActiveFilter.value ? '暂无符合条件的报告' : '还没有洞察报告，点击下方开始创建'
)

const REPORT_DETAIL_LEVEL = 'detailed'

const EXTRA_ANALYSIS_OPTIONS = [
  { value: 'benchmarks', label: '同比/环比对比' },
  { value: 'predictions', label: '趋势预测' },
  { value: 'cost_drivers', label: '费用驱动因素' },
  { value: 'regional_compare', label: '区域对照' },
  { value: 'risk_alert', label: '风险预警' },
  { value: 'resource_load', label: '资源负荷分析' },
  { value: 'cohort_profile', label: '人群结构画像' },
  { value: 'quality_improve', label: '质量改进方向' }
]

const DEFAULT_EXTRAS = ['benchmarks', 'predictions', 'cost_drivers', 'quality_improve']

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
  remarks: '',
  year: globalStore.selectedYear,
  region: globalStore.selectedRegion,
  tags: [],
  extras: [...DEFAULT_EXTRAS]
})

watch(
  () => createForm.topic,
  (topic) => {
    if (!topic) return
    const preset = topicPresets.value[topic]
    if (preset && preset.length) {
      createForm.tags = [...preset]
      return
    }
    // 自定义主题：按关键词推断初始标签，可再改
    const guessed = []
    if (/病理|疾病|病种|白血病|肿瘤|感染/.test(topic)) guessed.push('病理')
    if (/区域|城市|科室/.test(topic)) guessed.push('区域分析')
    if (/费用|成本|财务/.test(topic)) guessed.push('财务')
    if (/对比|差异/.test(topic)) guessed.push('综合')
    if (guessed.length) createForm.tags = [...new Set(guessed)]
  }
)

const openCreateDialog = () => {
  createForm.topic = ''
  createForm.title = ''
  createForm.remarks = ''
  createForm.tags = []
  createForm.year = globalStore.selectedYear || createForm.year
  createForm.region = globalStore.selectedRegion || 'all'
  createForm.extras = [...DEFAULT_EXTRAS]
  showCreateDialog.value = true
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
        baseTagGroups.value = res.data.tagGroups
      } else {
        baseTagGroups.value = [...DEFAULT_TAG_GROUPS]
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
      remarks: createForm.remarks.trim(),
      year: createForm.year || globalStore.selectedYear,
      region: createForm.region || globalStore.selectedRegion || 'all',
      tags: createForm.tags,
      detailLevel: REPORT_DETAIL_LEVEL,
      extras: createForm.extras
    })
    if (res.code === 200) {
      ElMessage.success(`报告《${res.data.title}》生成成功！`)
      showCreateDialog.value = false
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
  if (['综合'].includes(tag)) return 'info'
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

// ========== 标签筛选（分组） ==========
.tag-filter-panel {
  margin-bottom: $spacing-lg;
  background: $bg-card;
  border-radius: $radius-lg;
  box-shadow: $shadow-card;
  overflow: hidden;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid $border-color-light;
    background: #fafcff;
  }

  &__title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    font-weight: 700;
    color: $text-primary;

    .el-icon {
      color: $primary-color;
    }
  }

  &__meta {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: $text-placeholder;
  }
}

.tag-filter-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid $border-color-light;

  &:last-child {
    border-bottom: none;
  }

  &--quick {
    background: #fcfdff;
  }

  &__label {
    flex-shrink: 0;
    width: 72px;
    padding-top: 4px;
    font-size: 13px;
    font-weight: 700;
    color: $text-primary;
    line-height: 22px;
  }

  &__chips {
    flex: 1;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    min-width: 0;
  }
}

:deep(.el-check-tag) {
  border-radius: $radius-pill;
  font-size: 13px;
  line-height: 22px;
  padding: 2px 12px;
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

:deep(.report-card-menu.el-dropdown-menu) {
  padding: 4px 0;
  min-width: 132px;

  .el-dropdown-menu__item {
    display: flex;
    align-items: center;
    gap: 8px;
    line-height: 22px;
    padding: 8px 16px;

    .el-icon {
      margin: 0;
      font-size: 16px;
      flex-shrink: 0;
    }

    span {
      line-height: 22px;
    }

    &.is-danger {
      color: $danger-color;

      &:not(.is-disabled):hover {
        color: $danger-color;
        background: rgba(245, 108, 108, 0.08);
      }
    }
  }
}

.empty-state {
  grid-column: 1 / -1;
  padding: 60px 0;
}

.extras-checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;

  :deep(.el-checkbox) {
    margin-right: 0;
    min-width: calc(50% - 8px);
  }
}

// ========== 创建表单 ==========
.create-form {
  padding: 0 4px;
  max-height: min(70vh, 640px);
  overflow-y: auto;

  :deep(.el-form-item__label) {
    font-weight: 600;
    color: $text-regular;
  }
}

:deep(.create-report-dialog) {
  .el-dialog__body {
    padding-top: 8px;
    padding-bottom: 8px;
  }
}

.topic-desc {
  float: right;
  color: #8492a6;
  font-size: 12px;
  margin-left: 12px;
}

.tag-manage-inline {
  display: flex;
  gap: 8px;
  width: 100%;

  .flex-1 {
    flex: 1;
    min-width: 0;
  }
}

.tag-manage-custom {
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid $border-color-light;

  &__title {
    font-size: 13px;
    font-weight: 600;
    color: $text-regular;
    margin-bottom: 10px;
  }

  &__row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
  }

  &__tags {
    flex: 1;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    min-width: 0;
  }

  &__empty {
    font-size: 12px;
    color: $text-placeholder;
  }

  &__delete {
    flex-shrink: 0;
    margin-left: auto;
  }

  &__label-wrap {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    min-width: 72px;
  }

  &__rename {
    padding: 0;
    height: auto;
    font-size: 11px;
  }

  &__tag {
    cursor: pointer;
    user-select: none;
  }

  &__label {
    font-size: 12px;
    font-weight: 600;
    color: $text-secondary;
    line-height: 1.4;
  }
}

.w-full {
  width: 100%;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
