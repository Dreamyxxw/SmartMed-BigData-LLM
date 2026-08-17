import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '@/utils/request'

export const useGlobalStore = defineStore('global', () => {
  // 全局筛选器（默认值在 loadMeta 后会被真实数据覆盖）
  const selectedYear = ref('')
  const selectedRegion = ref('all')
  const sidebarCollapsed = ref(false)

  // 动态选项（从后端 meta 接口加载）
  const yearOptions = ref([])
  const regionOptions = ref([])

  // meta 加载状态
  const metaLoaded = ref(false)

  const toggleSidebar = () => {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  const setFilters = (year, region) => {
    if (year) selectedYear.value = year
    if (region) selectedRegion.value = region
  }

  // 从后端 /api/dashboard/meta 加载真实的年份/地区列表
  const loadMeta = async () => {
    if (metaLoaded.value) return
    try {
      const res = await request.get('/dashboard/meta')
      if (res.code === 200 && res.data) {
        const years = res.data.years || []
        const regions = res.data.regions || []
        const labels = res.data.regionLabels || {}

        yearOptions.value = years.map(y => ({ label: `${y}年`, value: y }))
        // 地区中文 label 优先用 meta 里传回的 regionLabels（按病例数降序）
        regionOptions.value = regions.map(r => ({
          label: labels[r] || r,
          value: r
        }))

        // 默认选中第一个真实年份
        if (years.length > 0 && !selectedYear.value) {
          selectedYear.value = years[0]
        }
        metaLoaded.value = true
      }
    } catch (e) {
      // 后端没启动时用 fallback
      if (yearOptions.value.length === 0) {
        yearOptions.value = [{ label: '2021年', value: '2021' }]
        selectedYear.value = '2021'
      }
      if (regionOptions.value.length === 0) {
        regionOptions.value = [{ label: '全部区域', value: 'all' }]
      }
    }
  }

  return {
    selectedYear,
    selectedRegion,
    sidebarCollapsed,
    yearOptions,
    regionOptions,
    metaLoaded,
    toggleSidebar,
    setFilters,
    loadMeta
  }
})
