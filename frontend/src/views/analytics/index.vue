<template>
  <div class="analytics-page">
    <!-- 顶部筛选区 -->
    <div class="filter-card card">
      <div class="card__header">
        <div class="card__header-title">
          <el-icon class="title-icon"><Filter /></el-icon>
          组合筛选条件
          <el-tag v-if="activeFilterCount > 0" type="warning" effect="light" class="filter-count-tag">
            已选 {{ activeFilterCount }} 项
          </el-tag>
        </div>
        <div class="filter-btns">
          <el-button @click="handleReset">
            <el-icon><RefreshLeft /></el-icon>
            重置条件
          </el-button>
          <el-button type="primary" :loading="isLoading" @click="handleQuery">
            <el-icon><Search /></el-icon>
            组合查询
          </el-button>
        </div>
      </div>
      <div class="card__body">
        <el-form :model="filterForm" label-position="top" class="filter-form">
          <el-row :gutter="20">
            <el-col :xs="24" :sm="12" :md="8" :lg="6" :xl="4">
              <el-form-item label="医院名称">
                <el-select
                  v-model="filterForm.facility"
                  placeholder="全部医院"
                  clearable
                  filterable
                  class="w-full"
                >
                  <el-option
                    v-for="opt in filterOptions.facilities"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>

            <el-col :xs="24" :sm="12" :md="8" :lg="6" :xl="4">
              <el-form-item label="所属科室">
                <el-select
                  v-model="filterForm.department"
                  placeholder="全部科室"
                  clearable
                  filterable
                  class="w-full"
                >
                  <el-option
                    v-for="opt in filterOptions.departments"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>

            <el-col :xs="24" :sm="12" :md="8" :lg="6" :xl="4">
              <el-form-item label="性别">
                <el-radio-group v-model="filterForm.gender" class="w-full">
                  <el-radio-button value="">全部</el-radio-button>
                  <el-radio-button
                    v-for="opt in filterOptions.genders"
                    :key="opt.value"
                    :value="opt.value"
                  >{{ opt.label }}</el-radio-button>
                </el-radio-group>
              </el-form-item>
            </el-col>

            <el-col :xs="24" :sm="12" :md="8" :lg="6" :xl="4">
              <el-form-item label="年龄段">
                <el-select
                  v-model="filterForm.ageGroup"
                  placeholder="全部年龄段"
                  clearable
                  class="w-full"
                >
                  <el-option
                    v-for="opt in filterOptions.ageGroups"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>

            <el-col :xs="24" :sm="12" :md="8" :lg="6" :xl="4">
              <el-form-item label="病情严重程度">
                <el-select
                  v-model="filterForm.severity"
                  placeholder="全部程度"
                  clearable
                  class="w-full"
                >
                  <el-option
                    v-for="opt in filterOptions.severities"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  >
                    <span style="float: left">{{ opt.label }}</span>
                    <el-tag
                      v-if="opt.value === '极重'" type="danger" size="small" effect="light" style="float: right"
                    >高危</el-tag>
                    <el-tag
                      v-else-if="opt.value === '严重'" type="warning" size="small" effect="light" style="float: right"
                    >注意</el-tag>
                  </el-option>
                </el-select>
              </el-form-item>
            </el-col>

            <el-col :xs="24" :sm="12" :md="8" :lg="6" :xl="4">
              <el-form-item label="支付方式">
                <el-select
                  v-model="filterForm.paymentType"
                  placeholder="全部支付方式"
                  clearable
                  filterable
                  class="w-full"
                >
                  <el-option
                    v-for="opt in filterOptions.paymentTypes"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </div>
    </div>

    <!-- 数据概览统计条 -->
    <div class="summary-bar">
      <div class="summary-item">
        <el-icon class="s-icon s-icon--1"><DataLine /></el-icon>
        <div>
          <div class="s-value">{{ pagination.total.toLocaleString() }}</div>
          <div class="s-label">聚合记录数</div>
        </div>
      </div>
      <el-divider direction="vertical" class="s-divider" />
      <div class="summary-item">
        <el-icon class="s-icon s-icon--2"><User /></el-icon>
        <div>
          <div class="s-value">{{ totalPatients.toLocaleString() }}</div>
          <div class="s-label">覆盖患者数</div>
        </div>
      </div>
      <el-divider direction="vertical" class="s-divider" />
      <div class="summary-item">
        <el-icon class="s-icon s-icon--3"><Wallet /></el-icon>
        <div>
          <div class="s-value">${{ totalCharges.toLocaleString() }}</div>
          <div class="s-label">累计总费用</div>
        </div>
      </div>
      <el-divider direction="vertical" class="s-divider" />
      <div class="summary-item">
        <el-icon class="s-icon s-icon--4"><Clock /></el-icon>
        <div>
          <div class="s-value">{{ avgStayAll }} 天</div>
          <div class="s-label">平均住院天数</div>
        </div>
      </div>
    </div>

    <!-- 表格区 -->
    <div class="table-card card">
      <div class="card__header">
        <div class="card__header-title">
          <el-icon class="title-icon"><Grid /></el-icon>
          聚合数据分析结果
          <span class="table-hint">（点击表头可排序）</span>
        </div>
        <div class="export-btns">
          <el-button @click="handleExport('csv')" :disabled="!tableData.length">
            <el-icon><Document /></el-icon>
            导出 CSV
          </el-button>
          <el-button type="success" @click="handleExport('xlsx')" :disabled="!tableData.length">
            <el-icon><Excel /></el-icon>
            导出 Excel
          </el-button>
        </div>
      </div>
      <div class="card__body card__body--no-padding">
        <el-table
          v-loading="isLoading"
          :data="tableData"
          border
          stripe
          style="width: 100%"
          :default-sort="{ prop: 'totalCharges', order: 'descending' }"
          :header-cell-style="{ background: '#fafcff', color: '#1f2937', fontWeight: 600 }"
        >
          <el-table-column type="index" label="序号" width="60" align="center" fixed />

          <el-table-column prop="region" label="区域" width="120" sortable>
            <template #default="{ row }">
              <el-tag size="small" effect="plain" :type="regionTagType(row.region)">{{ row.region }}</el-tag>
            </template>
          </el-table-column>

          <el-table-column prop="facility" label="医院名称" min-width="200" show-overflow-tooltip sortable />
          <el-table-column prop="department" label="科室" width="100" sortable />
          <el-table-column prop="disease" label="疾病诊断" min-width="180" show-overflow-tooltip sortable />

          <el-table-column prop="gender" label="性别" width="70" align="center">
            <template #default="{ row }">
              <el-icon v-if="row.gender === '男'" color="#409eff"><Male /></el-icon>
              <el-icon v-else color="#f56c6c"><Female /></el-icon>
            </template>
          </el-table-column>

          <el-table-column prop="ageGroup" label="年龄段" width="100" sortable />

          <el-table-column prop="severity" label="严重程度" width="100" align="center">
            <template #default="{ row }">
              <el-tag
                size="small"
                effect="light"
                :type="severityTagType(row.severity)"
              >{{ row.severity }}</el-tag>
            </template>
          </el-table-column>

          <el-table-column prop="count" label="出院人数" width="100" align="right" sortable>
            <template #default="{ row }">
              <span class="num-cell">{{ row.count.toLocaleString() }}</span>
            </template>
          </el-table-column>

          <el-table-column prop="avgStay" label="平均住院天数" width="120" align="right" sortable>
            <template #default="{ row }">
              <span class="num-cell">{{ row.avgStay }}</span>
            </template>
          </el-table-column>

          <el-table-column prop="avgCharges" label="平均费用(元)" width="130" align="right" sortable>
            <template #default="{ row }">
              <span class="num-cell num-cell--money">${{ row.avgCharges.toLocaleString() }}</span>
            </template>
          </el-table-column>

          <el-table-column prop="avgCosts" label="平均成本(元)" width="130" align="right" sortable>
            <template #default="{ row }">
              <span class="num-cell num-cell--cost">${{ row.avgCosts.toLocaleString() }}</span>
            </template>
          </el-table-column>

          <el-table-column prop="totalCharges" label="总费用(元)" width="160" align="right" sortable fixed="right">
            <template #default="{ row }">
              <span class="num-cell num-cell--total">${{ row.totalCharges.toLocaleString() }}</span>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-wrap">
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :page-sizes="[20, 50, 100, 200]"
            :total="pagination.total"
            layout="total, sizes, prev, pager, next, jumper"
            background
            @size-change="handleQuery"
            @current-change="handleQuery"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as XLSX from 'xlsx'
import { useGlobalStore } from '@/stores/global'
import { getFilterOptions, queryAnalyticsData } from '@/api'

const globalStore = useGlobalStore()

const isLoading = ref(false)

// ========== 筛选表单 ==========
const filterForm = reactive({
  facility: '',
  department: '',
  gender: '',
  ageGroup: '',
  severity: '',
  paymentType: ''
})

const filterOptions = reactive({
  facilities: [],
  departments: [],
  genders: [],
  ageGroups: [],
  severities: [],
  paymentTypes: [],
  regions: []
})

const activeFilterCount = computed(() => {
  return Object.values(filterForm).filter(v => v && v !== '').length
})

const loadFilterOptions = async () => {
  const res = await getFilterOptions()
  if (res.code === 200) Object.assign(filterOptions, res.data)
}

const handleReset = () => {
  Object.keys(filterForm).forEach(k => filterForm[k] = '')
  handleQuery()
  ElMessage.success('筛选条件已重置')
}

// ========== 表格数据 ==========
const tableData = ref([])
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const totalPatients = computed(() => tableData.value.reduce((s, r) => s + r.count, 0))
const totalCharges = computed(() => Math.round(tableData.value.reduce((s, r) => s + r.totalCharges, 0)))
const avgStayAll = computed(() => {
  if (!tableData.value.length) return '-'
  const weighted = tableData.value.reduce((s, r) => s + r.avgStay * r.count, 0)
  return (weighted / totalPatients.value).toFixed(1)
})

const handleQuery = async () => {
  isLoading.value = true
  try {
    const res = await queryAnalyticsData({
      ...filterForm,
      year: globalStore.selectedYear,
      region: globalStore.selectedRegion === 'all' ? '' : globalStore.selectedRegion,
      page: pagination.page,
      pageSize: pagination.pageSize
    })
    if (res.code === 200) {
      tableData.value = res.data.list
      pagination.total = res.data.total
    }
  } finally {
    isLoading.value = false
  }
}

// ========== 工具函数 ==========
const regionTagType = (r) => {
  const map = { Manhattan: '', Brooklyn: 'success', Queens: 'warning', Bronx: 'danger', 'Staten Island': 'info' }
  return map[r] || ''
}

const severityTagType = (s) => {
  const map = { '轻微': '', '中度': 'info', '严重': 'warning', '极重': 'danger' }
  return map[s] || ''
}

// ========== 导出 ==========
const TABLE_HEADERS = {
  id: '序号', region: '区域', facility: '医院名称', department: '科室',
  disease: '疾病诊断', gender: '性别', ageGroup: '年龄段',
  severity: '严重程度', count: '出院人数', avgStay: '平均住院天数',
  avgCharges: '平均费用(元)', avgCosts: '平均成本(元)', totalCharges: '总费用(元)'
}

const handleExport = async (type) => {
  if (!tableData.value.length) {
    ElMessage.warning('没有可导出的数据')
    return
  }

  // 如果数据量大，先导出当前筛选下的全部数据（示例：请求全部）
  let exportData = tableData.value

  // 如果总数据大于当前页，提示用户并可选导出全部（这里直接导出当前页数据，实际可以请求后端）
  if (pagination.total > pagination.pageSize) {
    ElMessage.info(`正在导出当前页 ${exportData.length} 条数据...`)
  }

  const exportRows = exportData.map(row => {
    const mapped = {}
    Object.keys(TABLE_HEADERS).forEach(k => { mapped[TABLE_HEADERS[k]] = row[k] })
    return mapped
  })

  const ws = XLSX.utils.json_to_sheet(exportRows)
  // 设置列宽
  ws['!cols'] = Object.values(TABLE_HEADERS).map(h => ({ wch: Math.max(h.length * 2, 12) }))

  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, '医疗数据分析')

  const timestamp = new Date().toISOString().slice(0, 10)
  const filename = `医疗数据分析_${globalStore.selectedYear}_${timestamp}`

  if (type === 'csv') {
    XLSX.writeFile(wb, `${filename}.csv`, { bookType: 'csv' })
  } else {
    XLSX.writeFile(wb, `${filename}.xlsx`, { bookType: 'xlsx' })
  }

  ElMessage.success('导出成功！')
}

// ========== 全局筛选联动 ==========
watch(
  () => [globalStore.selectedYear, globalStore.selectedRegion],
  () => { pagination.page = 1; handleQuery() }
)

onMounted(() => {
  loadFilterOptions()
  handleQuery()
})
</script>

<style lang="scss" scoped>
.analytics-page {
  display: flex;
  flex-direction: column;
  gap: $spacing-lg;
}

.filter-card {
  .filter-btns {
    display: flex;
    gap: 8px;
  }

  .filter-count-tag {
    margin-left: 8px;
    font-weight: normal;
  }
}

.filter-form {
  :deep(.el-form-item) {
    margin-bottom: $spacing-md;
  }
  :deep(.el-form-item__label) {
    font-weight: 600;
    color: $text-regular;
    padding-bottom: 6px;
  }
}

.w-full {
  width: 100%;
}

// ========== 统计概览条 ==========
.summary-bar {
  background: $bg-card;
  border-radius: $radius-xl;
  padding: 16px 24px;
  box-shadow: $shadow-card;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 200px;

  .s-icon {
    width: 48px;
    height: 48px;
    border-radius: $radius-md;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    color: #fff;
    flex-shrink: 0;

    &--1 { background: $gradient-blue; }
    &--2 { background: $gradient-primary; }
    &--3 { background: $gradient-orange; }
    &--4 { background: $gradient-green; }
  }

  .s-value {
    font-size: 20px;
    font-weight: 700;
    color: $text-primary;
    line-height: 1.2;
    font-family: 'SF Mono', Consolas, monospace;
  }

  .s-label {
    font-size: 12px;
    color: $text-secondary;
    margin-top: 3px;
  }
}

.s-divider {
  margin: 0 8px;
  height: 36px;
}

// ========== 表格区 ==========
.table-card {
  .card__body--no-padding {
    padding: 0;
  }

  .export-btns {
    display: flex;
    gap: 8px;
  }

  .table-hint {
    font-size: 12px;
    color: $text-placeholder;
    font-weight: normal;
    margin-left: 8px;
  }
}

.num-cell {
  font-family: 'SF Mono', Consolas, monospace;
  font-weight: 500;

  &--money {
    color: $primary-dark;
  }
  &--cost {
    color: $warning-color;
  }
  &--total {
    color: $danger-color;
    font-weight: 700;
  }
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: $spacing-md $spacing-lg;
  border-top: 1px solid $border-color-light;
  background: #fafcff;
  border-radius: 0 0 $radius-lg $radius-lg;
}
</style>
