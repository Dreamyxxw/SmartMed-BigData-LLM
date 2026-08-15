import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useGlobalStore = defineStore('global', () => {
  // 全局筛选器
  const selectedYear = ref('2024')
  const selectedRegion = ref('all')
  const sidebarCollapsed = ref(false)

  const yearOptions = ref([
    { label: '2021年', value: '2021' },
    { label: '2022年', value: '2022' },
    { label: '2023年', value: '2023' },
    { label: '2024年', value: '2024' }
  ])

  const regionOptions = ref([
    { label: '全部区域', value: 'all' },
    { label: '曼哈顿 (Manhattan)', value: 'Manhattan' },
    { label: '布鲁克林 (Brooklyn)', value: 'Brooklyn' },
    { label: '皇后区 (Queens)', value: 'Queens' },
    { label: '布朗克斯 (Bronx)', value: 'Bronx' },
    { label: '史泰登岛 (Staten Island)', value: 'Staten Island' }
  ])

  const toggleSidebar = () => {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  const setFilters = (year, region) => {
    if (year) selectedYear.value = year
    if (region) selectedRegion.value = region
  }

  return {
    selectedYear,
    selectedRegion,
    sidebarCollapsed,
    yearOptions,
    regionOptions,
    toggleSidebar,
    setFilters
  }
})
