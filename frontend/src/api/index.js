import request from '@/utils/request'
import * as mock from './mock'
import { AichatStreamParser } from '@/utils/aichatStreamParser'

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

/** POST/PUT/DELETE：真接口优先，失败降级 Mock */
async function tryMutateOrMock(method, url, data, mockFn, mockArg) {
  try {
    if (method === 'post') return await request.post(url, data)
    if (method === 'put') return await request.put(url, data)
    if (method === 'delete') return await request.delete(url)
    throw new Error(`unsupported method: ${method}`)
  } catch (e) {
    return new Promise((resolve) => {
      setTimeout(() => resolve(mockFn(mockArg)), 100)
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

// ========== AI Chat 接口（对接 Flask + LangChain + Redis smartmed:aichat:*） ==========
// 后端：backend/aichat_routes.py -> /api/aichat/*
// 缓存构建：data/build_aichat_cache.py -> Redis smartmed:aichat:*

// 获取历史会话列表
export function getChatHistory() {
  return tryRealOrMock('/aichat/history', {}, mock.getChatHistory, {})
}

// 获取指定会话的全部消息（历史会话切换时恢复聊天记录）
export function getChatMessages(chatId) {
  return request.get(`/aichat/messages/${chatId}`)
}

// 删除指定会话
export function deleteChat(chatId) {
  return request.delete(`/aichat/chat/${chatId}`)
}

// 重命名会话
export function renameChat(chatId, title) {
  return request.post(`/aichat/chat/${chatId}/rename`, { title })
}

// 获取推荐问题
export function getSuggestedQuestions() {
  return tryRealOrMock('/aichat/suggested', {}, mock.getSuggestedQuestions, {})
}

// ========== AI Chat SSE 流式调用 ==========
// 协议：POST /api/aichat/chat/stream → text/event-stream
//   data: {"event":"delta","text":"<增量token>"}\n\n
//   data: {"event":"done","parts":[...],"chatId":"..."}\n\n
//   data: {"event":"error","message":"..."}\n\n
//
// 调用方式：
//   streamChatMessage(payload, {
//     onDelta: (text) => {},        // 每个 delta token
//     onDone:  ({parts, chatId}) => {},  // 最终 parts
//     onError: (msg) => {},
//   }) -> AbortController（用于中断）
export function streamChatMessage(data, handlers = {}) {
  const { onDelta, onDone, onError, onPlanningDone } = handlers
  const ctrl = new AbortController()
  // 开发环境直连后端（绕过 Vite 代理对 SSE 的缓冲，确保真正的流式效果）
  // 生产环境走相对路径 /api（由 nginx 反代）
  const SSE_BASE = import.meta.env.DEV ? (import.meta.env.VITE_API_BASE || 'http://localhost:5000') : ''
  const url = `${SSE_BASE}/api/aichat/chat/stream`
  console.log('[aichat] SSE connecting to:', url)

  ;(async () => {
    let resp
    try {
      resp = await fetch(url, {
        method: 'POST',
        signal: ctrl.signal,
        // 不带 credentials，避免 CORS 预检复杂化（后端已开 CORS origins=*）
        credentials: 'omit',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify(data || {}),
      })
      console.log('[aichat] SSE response status:', resp.status, 'body:', !!resp.body)
    } catch (e) {
      console.warn('[aichat] SSE fetch failed:', e?.message)
      if (onError) onError(e?.message || '网络请求失败', e)
      return
    }
    if (!resp.ok) {
      console.warn('[aichat] SSE HTTP error:', resp.status)
      if (onError) onError(`HTTP ${resp.status} ${resp.statusText}`, resp)
      return
    }
    if (!resp.body) {
      if (onError) onError('浏览器不支持流式响应（ReadableStream）')
      return
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buf = ''

    // 让出一帧，确保 Vue 有机会渲染
    // 使用 Promise + 微任务 + 宏任务的组合，强制浏览器在每个 delta 后绘制
    const yieldToUI = async () => {
      // 先让 Vue 的微任务队列 flush（Promise 微任务）
      await Promise.resolve()
      // 再让浏览器有机会渲染（setTimeout 宏任务，0ms 足够触发渲染）
      await new Promise(r => setTimeout(r, 0))
    }

    let chunkCount = 0
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        let idx
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const rawEvent = buf.slice(0, idx)
          buf = buf.slice(idx + 2)
          chunkCount++
          _handleSSELines(rawEvent, { onDelta, onDone, onError, onPlanningDone })
          // 每个事件后让出事件循环，Vue 才能逐帧渲染
          await yieldToUI()
        }
      }
      if (buf.trim()) _handleSSELines(buf, { onDelta, onDone, onError, onPlanningDone })
      console.log('[aichat] SSE stream finished, chunks:', chunkCount)
    } catch (e) {
      console.warn('[aichat] SSE stream error:', e?.message)
      if (onError) onError(e?.message || '流式读取中断', e)
    }
  })()

  return ctrl
}

function _handleSSELines(rawEvent, { onDelta, onDone, onError, onPlanningDone }) {
  const lines = rawEvent.split('\n')
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const dataStr = trimmed.startsWith('data:') ? trimmed.slice(5).trim() : trimmed
    if (!dataStr) continue
    let payload
    try {
      payload = JSON.parse(dataStr)
    } catch {
      continue
    }
    switch (payload.event) {
      case 'planning_done':
        if (onPlanningDone) onPlanningDone({ keys: payload.keys || [] })
        break
      case 'delta':
        if (onDelta && typeof payload.text === 'string') onDelta(payload.text)
        break
      case 'done':
        if (onDone) onDone({ parts: payload.parts || [], chatId: payload.chatId })
        break
      case 'error':
        if (onError) onError(payload.message || '未知错误', payload)
        break
    }
  }
}

// 同步发送消息（备用，流式失败时降级）
export async function sendChatMessageSync(data) {
  try {
    return await request.post('/aichat/chat', data, { timeout: 300000 })
  } catch (e) {
    return new Promise((resolve) => {
      setTimeout(() => resolve(mock.sendChatMessage(data)), 1000)
    })
  }
}

// 兼容性 sendChatMessage：内部走流式，对外 Promise<{code:200, data:parts}> 签名不变
// 通过 window 自定义事件 'aichat:parts_update' 广播流式渲染用的 parts（text 实时增长 + chart 占位）
export async function sendChatMessage(data) {
  return new Promise((resolve) => {
    const parser = new AichatStreamParser((renderParts) => {
      try {
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('aichat:parts_update', { detail: { parts: renderParts } }))
        }
      } catch {}
    })

    let resolved = false
    const finalize = (parts, chatId) => {
      if (resolved) return
      resolved = true
      // 通知组件清理占位
      try {
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('aichat:beforeFinalize'))
        }
      } catch {}
      resolve({ code: 200, data: parts, chatId })
    }

    streamChatMessage(data, {
      onDelta: (text) => {
        try { parser.push(text) } catch (e) { console.warn('[aichat] parser error:', e) }
      },
      onDone: ({ parts, chatId }) => finalize(parts, chatId),
      onError: async (msg) => {
        console.warn('[aichat] SSE 流式失败：', msg)
        if (import.meta.env.DEV) {
          // 开发环境：SSE 失败通常是 CORS 或后端未启动，直接报错方便排查
          console.error('[aichat] SSE 直连失败，请确认后端已启动且允许跨域。将使用同步降级：', msg)
        }
        // 降级到同步 API（生产环境兜底）
        try {
          const syncRes = await sendChatMessageSync(data)
          finalize(syncRes.data, syncRes.chatId)
        } catch (e2) {
          finalize([{ type: 'text', content: `⚠️ AI 服务调用失败：${msg}` }], null)
        }
      },
    })
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
// 真接口优先（Flask + Redis smartmed:reports:*），失败降级 Mock
// 缓存构建：python data/build_reports_cache.py

export function getReportMeta() {
  return tryRealOrMock('/reports/meta', {}, mock.getReportMeta)
}

export function getReportStats(params = {}) {
  return tryRealOrMock('/reports/stats', params, () => ({ code: 200, data: null }), params)
}

export function getReportList() {
  return tryRealOrMock('/reports/list', {}, mock.getReportList)
}

export function generateReport(data) {
  return tryMutateOrMock('post', '/reports/generate', data, () => mock.generateReport(data))
}

export function getReportDetail(id) {
  return tryRealOrMock(`/reports/detail/${id}`, {}, () => mock.getReportDetail(id))
}

export function updateReport(id, data) {
  return tryMutateOrMock('put', `/reports/${id}`, data, () => mock.updateReport(id, data))
}

export function deleteReport(id) {
  return tryMutateOrMock('delete', `/reports/${id}`, null, () => mock.deleteReport(id))
}

export function duplicateReport(id) {
  return tryMutateOrMock('post', `/reports/${id}/duplicate`, {}, () => mock.duplicateReport(id))
}
