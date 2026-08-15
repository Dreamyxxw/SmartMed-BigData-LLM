import request from '@/utils/request'
import * as mock from './mock'

// ========== Dashboard 数据接口 ==========

// 获取KPI数据
export function getKpiData(params = {}) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(mock.getKpiData(params)), 300)
  })
}

// 获取年龄段分布
export function getAgeGroupData(params = {}) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(mock.getAgeGroupData(params)), 300)
  })
}

// 获取Top10昂贵疾病
export function getTopDiseasesData(params = {}) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(mock.getTopDiseasesData(params)), 300)
  })
}

// 获取科室费用与住院天数对比
export function getDeptCompareData(params = {}) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(mock.getDeptCompareData(params)), 300)
  })
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
  return new Promise((resolve) => {
    setTimeout(() => resolve(mock.getFilterOptions()), 200)
  })
}

// 查询表格数据
export function queryAnalyticsData(params = {}) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(mock.queryAnalyticsData(params)), 500)
  })
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
