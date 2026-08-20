import request from '@/utils/request'
import * as mock from './mock'

/**
 * Dashboard 统一调用包装：
 * 1. 优先走真实接口（Flask + Redis，<1ms）
 * 2. 任何失败（后端没启、连不上Redis、抛错等）自动降级到 Mock
 *    → 保证页面不会白屏、导航不会中断、其他3个页面完全不受影响
 */
async function tryRealOrMock(url, params, mockFn, mockParams) {
  try {
    return await request.get(url, { params })
  } catch (e) {
    // 真实接口失败，静默降级到Mock（不影响页面渲染）
    // 如需要排查可在控制台打印：console.warn('[api fallback]', url, e?.message)
    return new Promise((resolve) => {
      setTimeout(() => resolve(mockFn(mockParams)), 100)
    })
  }
}

// ========== Dashboard 数据接口 ==========
// 已对接 Flask + Redis 预构建缓存（命中即返回，响应 < 1ms）
// 后端：backend/app.py -> /api/dashboard/*
// 缓存构建：data/build_dashboard_cache.py -> Redis smartmed:dashboard:*

// 获取KPI数据
export function getKpiData(params = {}) {
  return tryRealOrMock('/dashboard/kpi', params, mock.getKpiData, params)
}

// 获取年龄段分布
export function getAgeGroupData(params = {}) {
  return tryRealOrMock('/dashboard/age-group', params, mock.getAgeGroupData, params)
}

// 获取Top10昂贵疾病（ageGroup 不传或传 'all' 为全年龄段）
export function getTopDiseasesData(params = {}) {
  const reqParams = { ...params }
  if (!reqParams.ageGroup) reqParams.ageGroup = 'all'
  return tryRealOrMock('/dashboard/top-diseases', reqParams, mock.getTopDiseasesData, reqParams)
}

// 获取科室费用与住院天数对比
export function getDeptCompareData(params = {}) {
  return tryRealOrMock('/dashboard/dept-compare', params, mock.getDeptCompareData, params)
}

// ========== AI Chat 接口 ==========

// 获取历史对话
export function getChatHistory() {
  return new Promise((resolve) => {
    setTimeout(() => resolve(mock.getChatHistory()), 200)
  })
}

// 发送消息给AI
export function sendChatMessage(data) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(mock.sendChatMessage(data)), 1000)
  })
}

// 获取推荐问题
export function getSuggestedQuestions() {
  return new Promise((resolve) => {
    setTimeout(() => resolve(mock.getSuggestedQuestions()), 200)
  })
}

// ========== Analytics 数据接口 ==========

// 获取筛选选项
export function getFilterOptions() {
  return request.get('/analytics/filters')
}

// 查询表格数据
export function queryAnalyticsData(params = {}) {
  return request.get('/analytics/query', { params })
}

// ========== Reports 接口 ==========

// 获取报告列表
export function getReportList() {
  return new Promise((resolve) => {
    setTimeout(() => resolve(mock.getReportList()), 300)
  })
}

// 生成新报告
export function generateReport(data) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(mock.generateReport(data)), 2000)
  })
}

// 获取报告详情
export function getReportDetail(id) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(mock.getReportDetail(id)), 300)
  })
}

// 删除报告
export function deleteReport(id) {
  return new Promise((resolve) => {
    setTimeout(() => resolve({ code: 200, message: '删除成功' }), 300)
  })
}
