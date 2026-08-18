<template>
  <div class="ai-chat-page">
    <!-- 左侧历史记录 -->
    <aside class="history-panel">
      <div class="history-panel__header">
        <div class="panel-title">
          <el-icon><ChatDotRound /></el-icon>
          <span>历史对话</span>
        </div>
        <el-button type="primary" size="small" @click="handleNewChat">
          <el-icon><Plus /></el-icon>
          新建对话
        </el-button>
      </div>

      <div class="history-search">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索历史对话..."
          size="default"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>

      <div class="history-list">
        <div
          v-for="item in filteredHistory"
          :key="item.id"
          class="history-item"
          :class="{ active: currentChatId === item.id }"
          @click="handleSelectHistory(item)"
        >
          <div class="history-item__icon">
            <el-icon><ChatLineSquare /></el-icon>
          </div>
          <div class="history-item__content">
            <div class="history-item__title" :title="item.title">{{ item.title }}</div>
            <div class="history-item__time">{{ item.time }}</div>
          </div>
          <el-dropdown trigger="click" @click.stop @command="(cmd) => handleHistoryCommand(cmd, item)">
            <el-button text size="small" class="history-item__more" @click.stop>
              <el-icon><MoreFilled /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="rename">
                  <el-icon><Edit /></el-icon> 重命名
                </el-dropdown-item>
                <el-dropdown-item command="delete" divided>
                  <el-icon><Delete /></el-icon> 删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <el-empty v-if="filteredHistory.length === 0" description="暂无历史对话" :image-size="80" />
      </div>
    </aside>

    <!-- 右侧聊天区域 -->
    <section class="chat-panel">
      <!-- 聊天头部 -->
      <header class="chat-panel__header">
        <div class="chat-info">
          <div class="chat-avatar ai-avatar">
            <el-icon :size="22"><Cpu /></el-icon>
          </div>
          <div>
            <div class="chat-name">
              SmartMed AI 医疗助手
              <el-tag size="small" type="success" effect="light" class="tag-online">在线</el-tag>
            </div>
            <div class="chat-subtitle">
              基于医疗大数据的智能分析助手 · 可直接渲染图表
            </div>
          </div>
        </div>
        <div class="chat-actions">
          <el-tooltip content="清空对话">
            <el-button text @click="handleClearChat">
              <el-icon :size="18"><Delete /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="导出对话">
            <el-button text @click="handleExportChat">
              <el-icon :size="18"><Download /></el-icon>
            </el-button>
          </el-tooltip>
        </div>
      </header>

      <!-- 消息列表 -->
      <div ref="messagesContainerRef" class="messages-container">
        <!-- 欢迎消息 -->
        <div v-if="messages.length === 0 && !isLoading" class="welcome-block">
          <div class="welcome-avatar">
            <el-icon :size="42"><Cpu /></el-icon>
          </div>
          <h2 class="welcome-title">你好，我是 SmartMed AI 医疗分析助手 👋</h2>
          <p class="welcome-desc">
            我可以帮你从住院数据中挖掘洞察，支持费用分析、患者画像、趋势对比等查询。<br/>
            回答将自动渲染结构化图表，点击下方推荐问题快速开始：
          </p>
        </div>

        <!-- 消息气泡 -->
        <div
          v-for="(msg, idx) in messages"
          :key="msg.id || idx"
          class="message-item"
          :class="msg.role"
        >
          <div v-if="msg.role === 'assistant'" class="msg-avatar ai-avatar">
            <el-icon :size="18"><Cpu /></el-icon>
          </div>

          <div class="msg-content-wrap">
            <template v-if="msg.role === 'assistant'">
              <div v-for="(part, pIdx) in msg.parts" :key="pIdx" class="msg-part">
                <!-- 图表占位符（流式过程中） -->
                <div v-if="part.type === 'text' && part.isChartPlaceholder" class="msg-chart-placeholder">
                  <div class="placeholder-icon">
                    <el-icon :size="24"><TrendCharts /></el-icon>
                  </div>
                  <div class="placeholder-text">{{ part.content }}</div>
                </div>
                <!-- 文本部分 -->
                <div v-else-if="part.type === 'text'" class="msg-text">
                  <pre class="formatted-text" :class="{ 'is-streaming': part.isStreaming }">{{ part.content }}</pre>
                </div>
                <!-- 图表部分（最终渲染） -->
                <div v-else-if="part.type === 'chart'" class="msg-chart">
                  <div class="msg-chart__header">
                    <span class="msg-chart__tag">
                      <el-icon><TrendCharts /></el-icon>
                      数据可视化
                    </span>
                    <el-button size="small" text @click="downloadMsgChart(idx, pIdx)">
                      <el-icon><Download /></el-icon> 下载
                    </el-button>
                  </div>
                  <div
                    :ref="el => setMsgChartRef(idx, pIdx, el)"
                    :id="`msg-chart-${idx}-${pIdx}`"
                    class="msg-chart__body"
                  ></div>
                </div>
              </div>
            </template>

            <template v-else>
              <div class="msg-text msg-user-text">{{ msg.content }}</div>
            </template>
          </div>

          <div v-if="msg.role === 'user'" class="msg-avatar user-avatar">
            <el-icon :size="18"><User /></el-icon>
          </div>
        </div>

        <!-- Loading 状态（仅在还没收到任何 delta 时显示） -->
        <div v-if="isLoading && !hasStreamStarted" class="message-item assistant">
          <div class="msg-avatar ai-avatar">
            <el-icon :size="18"><Cpu /></el-icon>
          </div>
          <div class="msg-content-wrap">
            <div class="msg-loading">
              <div class="dots">
                <span></span><span></span><span></span>
              </div>
              <span class="loading-text">AI 正在分析数据...</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 推荐问题区 -->
      <div v-if="messages.length === 0 && !isLoading" class="suggested-section">
        <div class="suggested-title">
          <el-icon><MagicStick /></el-icon>
          推荐问题
        </div>
        <div class="suggested-chips">
          <el-tag
            v-for="q in suggestedQuestions"
            :key="q.id"
            class="suggest-chip"
            effect="plain"
            @click="handleSendSuggested(q.text)"
          >
            <el-icon><Promotion /></el-icon>
            {{ q.text }}
          </el-tag>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <div v-if="messages.length > 0" class="mini-suggested">
          <el-tag
            v-for="q in suggestedQuestions.slice(0, 3)"
            :key="q.id"
            size="small"
            effect="plain"
            @click="handleSendSuggested(q.text)"
          >
            {{ q.text }}
          </el-tag>
        </div>
        <div class="input-box">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            placeholder="请输入您的医疗数据分析问题，例如：统计各支付方式的总费用..."
            resize="none"
            class="chat-input"
            @keydown.enter.ctrl="handleSend"
          />
          <div class="input-actions">
            <div class="input-tip">
              <el-icon><InfoFilled /></el-icon>
              Ctrl + Enter 发送
            </div>
            <div class="input-btns">
              <el-button :disabled="!inputText.trim() || isLoading" @click="handleSend" type="primary">
                <el-icon><Promotion /></el-icon>
                发送
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useGlobalStore } from '@/stores/global'
import {
  getChatHistory,
  getChatMessages,
  deleteChat,
  renameChat,
  sendChatMessage,
  getSuggestedQuestions,
} from '@/api'
import { downloadChart } from '@/utils/chart'

const globalStore = useGlobalStore()

// ========== 历史记录 ==========
const historyList = ref([])
const currentChatId = ref(null)
const searchKeyword = ref('')

const filteredHistory = computed(() => {
  if (!searchKeyword.value) return historyList.value
  const kw = searchKeyword.value.toLowerCase()
  return historyList.value.filter(h => (h.title || '').toLowerCase().includes(kw))
})

const loadHistory = async () => {
  try {
    const res = await getChatHistory()
    if (res.code === 200) historyList.value = res.data || []
  } catch (e) {
    console.warn('[aichat] 加载历史失败', e)
  }
}

// 选择历史会话：从后端拉取消息并恢复
const handleSelectHistory = async (item) => {
  if (isLoading.value) return
  currentChatId.value = item.id
  disposeAllCharts()
  messages.value = []
  try {
    const res = await getChatMessages(item.id)
    if (res.code === 200 && Array.isArray(res.data)) {
      messages.value = res.data.map((m, i) => ({ ...m, id: `${item.id}-${i}` }))
      // 等待 DOM 渲染完成后渲染所有图表
      nextTick(() => {
        messages.value.forEach((msg, mIdx) => {
          if (msg.role === 'assistant' && Array.isArray(msg.parts)) {
            msg.parts.forEach((part, pIdx) => {
              if (part.type === 'chart') renderMsgChart(part, mIdx, pIdx)
            })
          }
        })
        scrollToBottom()
      })
    }
  } catch (e) {
    ElMessage.warning('加载会话消息失败：' + (e?.message || '未知错误'))
  }
}

const handleNewChat = () => {
  if (isLoading.value) {
    ElMessage.warning('当前正在生成，请稍候')
    return
  }
  currentChatId.value = null
  disposeAllCharts()
  messages.value = []
}

// 历史项下拉菜单命令
const handleHistoryCommand = async (cmd, item) => {
  if (cmd === 'rename') {
    handleRenameChat(item)
  } else if (cmd === 'delete') {
    handleDeleteChat(item)
  }
}

const handleRenameChat = (item) => {
  ElMessageBox.prompt('请输入新的会话标题', '重命名', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputValue: item.title,
    inputPattern: /.+/,
    inputErrorMessage: '标题不能为空',
  }).then(async ({ value }) => {
    try {
      const res = await renameChat(item.id, value)
      if (res.code === 200) {
        item.title = res.data.title
        ElMessage.success('重命名成功')
      }
    } catch (e) {
      ElMessage.error('重命名失败：' + (e?.message || ''))
    }
  }).catch(() => {})
}

const handleDeleteChat = (item) => {
  ElMessageBox.confirm(`确定删除会话「${item.title}」吗？此操作不可恢复。`, '提示', {
    type: 'warning',
    confirmButtonText: '确定删除',
    cancelButtonText: '取消',
  }).then(async () => {
    try {
      const res = await deleteChat(item.id)
      if (res.code === 200) {
        historyList.value = historyList.value.filter(h => h.id !== item.id)
        if (currentChatId.value === item.id) {
          currentChatId.value = null
          disposeAllCharts()
          messages.value = []
        }
        ElMessage.success('删除成功')
      }
    } catch (e) {
      ElMessage.error('删除失败：' + (e?.message || ''))
    }
  }).catch(() => {})
}

// ========== 推荐问题 ==========
const suggestedQuestions = ref([])
const loadSuggested = async () => {
  try {
    const res = await getSuggestedQuestions()
    if (res.code === 200) suggestedQuestions.value = res.data || []
  } catch (e) {
    console.warn('[aichat] 加载推荐问题失败', e)
  }
}

// ========== 聊天消息 ==========
const messages = ref([])
const inputText = ref('')
const isLoading = ref(false)
const hasStreamStarted = ref(false)   // 是否已收到首个 delta（用于切换 loading 与流式渲染）
const messagesContainerRef = ref(null)

// 图表 ref 管理：key = `${msgIdx}-${partIdx}` -> DOM element
const msgChartRefs = reactive({})
const setMsgChartRef = (msgIdx, partIdx, el) => {
  const key = `${msgIdx}-${partIdx}`
  if (el) msgChartRefs[key] = el
  else delete msgChartRefs[key]
}

// ECharts 实例管理（用于统一 dispose）
const chartInstances = []
const chartInstanceMap = new Map()  // key -> instance

const disposeAllCharts = () => {
  chartInstances.forEach(inst => {
    try { inst.dispose() } catch {}
  })
  chartInstances.length = 0
  chartInstanceMap.clear()
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainerRef.value) {
      messagesContainerRef.value.scrollTop = messagesContainerRef.value.scrollHeight
    }
  })
}

// 把后端传来的 option 中的 __func__ 标记还原为真实 JS 函数
const restoreFuncs = (obj) => {
  if (obj === null || obj === undefined) return obj
  if (Array.isArray(obj)) return obj.map(restoreFuncs)
  if (typeof obj === 'object') {
    // __func__ 标记：后端传来 { __func__: "function(params) {...}" }
    if (obj.__func__ && typeof obj.__func__ === 'string') {
      try {
        // eslint-disable-next-line no-new-func
        return new Function(`return (${obj.__func__})`)()
      } catch (e) {
        console.warn('[aichat] 函数还原失败，使用默认值:', e)
        return null
      }
    }
    const result = {}
    for (const k in obj) {
      result[k] = restoreFuncs(obj[k])
    }
    return result
  }
  return obj
}

// 渲染单条消息内的某个图表
const renderMsgChart = (part, msgIdx, partIdx) => {
  nextTick(() => {
    const key = `${msgIdx}-${partIdx}`
    const el = msgChartRefs[key]
    if (!el || !part.option) return
    // 若已有旧实例先 dispose
    const oldInst = chartInstanceMap.get(key)
    if (oldInst) {
      try { oldInst.dispose() } catch {}
      chartInstanceMap.delete(key)
    }
    const instance = echarts.init(el)
    // 还原函数标记后再传给 ECharts
    const option = restoreFuncs(part.option)
    instance.setOption(option)
    chartInstances.push(instance)
    chartInstanceMap.set(key, instance)

    // 监听容器尺寸变化
    const ro = new ResizeObserver(() => instance.resize())
    ro.observe(el)
  })
}

const downloadMsgChart = (msgIdx, partIdx) => {
  const chartId = `msg-chart-${msgIdx}-${partIdx}`
  downloadChart(chartId, 'AI-chart')
}

const handleSendSuggested = async (text) => {
  inputText.value = text
  await handleSend()
}

// ========== 流式 parts 合并：最终 parts 直接替换流式 parts ==========
function mergeFinalParts(streamParts, finalParts) {
  if (finalParts && finalParts.length > 0) {
    return finalParts.map(p => ({ ...p }))
  }
  return streamParts || []
}

// ========== 流式发送主流程 ==========
const handleSend = async () => {
  const content = inputText.value.trim()
  if (!content || isLoading.value) return

  // 1. push 用户消息
  messages.value.push({ id: `u-${Date.now()}`, role: 'user', content })
  inputText.value = ''
  scrollToBottom()

  isLoading.value = true
  hasStreamStarted.value = false

  // 2. 监听流式 parts_update 事件，实时更新占位 assistant 消息
  // 占位消息会在第一个 delta 到来前由 _onStreamPartsUpdate 自动插入
  let placeholderIdx = -1

  const onPartsUpdate = (evt) => {
    const parts = evt?.detail?.parts
    if (!Array.isArray(parts)) return
    if (!hasStreamStarted.value) {
      hasStreamStarted.value = true
    }
    // 确保 messages 里有占位 assistant 消息
    if (placeholderIdx < 0) {
      const len = messages.value.length
      const last = messages.value[len - 1]
      if (last && last.role === 'assistant') {
        placeholderIdx = len - 1
      } else {
        messages.value.push({ id: `a-${Date.now()}`, role: 'assistant', parts: [] })
        placeholderIdx = len
      }
    }
    // 更新占位消息的 parts（即使 parts 为空也更新，确保占位出现）
    messages.value[placeholderIdx].parts = parts.map(p => ({ ...p }))
    scrollToBottom()
  }

  const onBeforeFinalize = () => {
    // 不再删除占位消息，只做标记。最终在 handleSend 中替换其内容。
    // 这样即使后端解析返回空 parts，流式内容也不会丢失。
    // 如果 placeholderIdx 仍有效，保留占位消息，后续会被替换或清空。
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('aichat:parts_update', onPartsUpdate)
    window.addEventListener('aichat:beforeFinalize', onBeforeFinalize)
  }

  try {
    const res = await sendChatMessage({
      message: content,
      year: globalStore.selectedYear,
      region: globalStore.selectedRegion,
      chatId: currentChatId.value,
    })

    if (res.code === 200) {
      const finalParts = res.data && res.data.length > 0
        ? res.data
        : [{ type: 'text', content: '抱歉，AI 未能返回有效内容' }]

      if (placeholderIdx >= 0 && placeholderIdx < messages.value.length
          && messages.value[placeholderIdx]?.role === 'assistant') {
        // 替换占位消息：将流式 parts 中的 chart 占位符替换为真实 chart
        const streamParts = messages.value[placeholderIdx].parts
        const mergedParts = mergeFinalParts(streamParts, finalParts)
        messages.value[placeholderIdx].parts = mergedParts
        messages.value[placeholderIdx].id = `a-${Date.now()}`
      } else {
        messages.value.push({
          id: `a-${Date.now()}`,
          role: 'assistant',
          parts: finalParts.map(p => ({ ...p })),
        })
        placeholderIdx = messages.value.length - 1
      }

      if (res.chatId) {
        currentChatId.value = res.chatId
      }
      scrollToBottom()

      // 渲染所有图表
      const targetIdx = placeholderIdx >= 0 ? placeholderIdx : messages.value.length - 1
      nextTick(() => {
        const parts = messages.value[targetIdx].parts
        parts.forEach((part, pIdx) => {
          if (part.type === 'chart') renderMsgChart(part, targetIdx, pIdx)
        })
      })
      loadHistory()
    }
  } catch (e) {
    console.error('[aichat] 发送失败', e)
    ElMessage.error('发送失败：' + (e?.message || '未知错误'))
  } finally {
    isLoading.value = false
    hasStreamStarted.value = false
    if (typeof window !== 'undefined') {
      window.removeEventListener('aichat:parts_update', onPartsUpdate)
      window.removeEventListener('aichat:beforeFinalize', onBeforeFinalize)
    }
  }
}

const handleClearChat = () => {
  if (messages.value.length === 0) {
    ElMessage.info('当前没有对话')
    return
  }
  ElMessageBox.confirm('确定要清空当前对话吗？此操作不可恢复。', '提示', {
    type: 'warning',
    confirmButtonText: '确定清空',
    cancelButtonText: '取消',
  }).then(() => {
    disposeAllCharts()
    messages.value = []
    ElMessage.success('对话已清空')
  }).catch(() => {})
}

const handleExportChat = () => {
  if (messages.value.length === 0) {
    ElMessage.info('当前没有对话可导出')
    return
  }
  // 导出为文本文件
  const lines = []
  messages.value.forEach(msg => {
    if (msg.role === 'user') {
      lines.push(`【用户】 ${msg.content}`)
      lines.push('')
    } else if (msg.role === 'assistant') {
      lines.push('【AI助手】')
      ;(msg.parts || []).forEach(part => {
        if (part.type === 'text') {
          lines.push(part.content)
        } else if (part.type === 'chart') {
          lines.push(`[图表: ${part.chartType || 'chart'}]`)
        }
      })
      lines.push('')
    }
  })
  const text = lines.join('\n')
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `AI对话_${new Date().toISOString().slice(0, 10)}.txt`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

// ========== 生命周期 ==========
onMounted(() => {
  loadHistory()
  loadSuggested()
})

onBeforeUnmount(() => {
  disposeAllCharts()
})
</script>

<style lang="scss" scoped>
.ai-chat-page {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: $spacing-lg;
  height: calc(100vh - #{$header-height} - #{$spacing-lg} * 2);
  min-height: 620px;
}

// ========== 左侧历史面板 ==========
.history-panel {
  background: $bg-card;
  border-radius: $radius-xl;
  box-shadow: $shadow-card;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  &__header {
    padding: $spacing-md $spacing-md $spacing-sm;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid $border-color-light;
  }
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: $text-primary;

  .el-icon {
    color: $primary-color;
    font-size: 18px;
  }
}

.history-search {
  padding: $spacing-sm $spacing-md;
  border-bottom: 1px solid $border-color-light;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: $spacing-sm;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: $radius-md;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 4px;

  &:hover {
    background: $bg-page;
  }

  &.active {
    background: $primary-bg;

    .history-item__icon {
      color: $primary-color;
      background: rgba(24, 144, 255, 0.12);
    }
    .history-item__title {
      color: $primary-dark;
      font-weight: 600;
    }
  }

  &__icon {
    width: 34px;
    height: 34px;
    border-radius: $radius-sm;
    background: $bg-page;
    color: $text-secondary;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  &__content {
    flex: 1;
    min-width: 0;
  }

  &__title {
    font-size: 13px;
    color: $text-regular;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-weight: 500;
  }

  &__time {
    font-size: 11px;
    color: $text-placeholder;
    margin-top: 3px;
  }

  &__more {
    opacity: 0;
    transition: opacity 0.2s;
  }

  &:hover &__more {
    opacity: 1;
  }
}

// ========== 右侧聊天面板 ==========
.chat-panel {
  background: $bg-card;
  border-radius: $radius-xl;
  box-shadow: $shadow-card;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  &__header {
    padding: $spacing-md $spacing-lg;
    border-bottom: 1px solid $border-color-light;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }
}

.chat-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ai-avatar {
  background: $gradient-tech;
  color: #fff;
  box-shadow: 0 4px 12px rgba(14, 165, 233, 0.3);
}

.user-avatar {
  background: linear-gradient(135deg, #a78bfa 0%, #7c3aed 100%);
  color: #fff;
}

.chat-name {
  font-size: 15px;
  font-weight: 600;
  color: $text-primary;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tag-online {
  font-size: 10px;
}

.chat-subtitle {
  font-size: 12px;
  color: $text-secondary;
  margin-top: 2px;
}

.chat-actions {
  display: flex;
  gap: 4px;
}

// ========== 消息容器 ==========
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: $spacing-lg;
  background: linear-gradient(180deg, #fafcff 0%, #f0f5fa 100%);
}

// ========== 欢迎区 ==========
.welcome-block {
  text-align: center;
  padding: 40px 20px;

  .welcome-avatar {
    width: 72px;
    height: 72px;
    border-radius: 50%;
    margin: 0 auto 20px;
    background: $gradient-tech;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 8px 24px rgba(14, 165, 233, 0.35);
    animation: pulse 2s infinite;
  }

  .welcome-title {
    font-size: 22px;
    font-weight: 700;
    color: $text-primary;
    margin-bottom: 12px;
  }

  .welcome-desc {
    font-size: 14px;
    color: $text-secondary;
    line-height: 1.8;
  }
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 8px 24px rgba(14, 165, 233, 0.35); }
  50% { box-shadow: 0 8px 32px rgba(14, 165, 233, 0.55); }
}

// ========== 消息项 ==========
.message-item {
  display: flex;
  gap: 12px;
  margin-bottom: $spacing-lg;
  max-width: 100%;

  &.user {
    flex-direction: row-reverse;

    .msg-content-wrap {
      align-items: flex-end;
    }

    .msg-user-text {
      background: $gradient-blue;
      color: #fff;
      border-radius: $radius-lg 4px $radius-lg $radius-lg;
    }
  }

  &.assistant {
    .msg-text {
      background: #fff;
      border: 1px solid $border-color-light;
    }
  }
}

.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.msg-content-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: calc(100% - 60px);
}

.msg-part {
  width: 100%;
}

.msg-text {
  padding: 12px 16px;
  border-radius: 4px $radius-lg $radius-lg $radius-lg;
  font-size: 14px;
  line-height: 1.7;
  color: $text-regular;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-user-text {
  padding: 10px 16px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.formatted-text {
  font-family: inherit;
  white-space: pre-wrap;
  margin: 0;

  &.is-streaming::after {
    content: '▋';
    display: inline-block;
    margin-left: 1px;
    animation: blink 0.6s step-end infinite;
    color: $primary-color;
  }
}

@keyframes blink {
  50% { opacity: 0; }
}

// ========== 图表占位符（流式过程中） ==========
.msg-chart-placeholder {
  background: linear-gradient(135deg, #f0f7ff 0%, #f5f0ff 100%);
  border: 1px dashed $primary-color;
  border-radius: $radius-lg;
  padding: 20px 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 300px;

  .placeholder-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: $primary-color;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: pulse 1.5s ease-in-out infinite;
  }

  .placeholder-text {
    font-size: 14px;
    color: $primary-dark;
    font-weight: 500;
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

// ========== 消息内图表 ==========
.msg-chart {
  background: #fff;
  border: 1px solid $border-color-light;
  border-radius: $radius-lg;
  overflow: hidden;
  min-width: 460px;

  &__header {
    padding: 8px 14px;
    background: #fafcff;
    border-bottom: 1px solid $border-color-light;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  &__tag {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: $primary-dark;
    font-weight: 600;

    .el-icon {
      font-size: 14px;
    }
  }

  &__body {
    width: 100%;
    height: 260px;
  }
}

// ========== Loading ==========
.msg-loading {
  background: #fff;
  border: 1px solid $border-color-light;
  border-radius: 4px $radius-lg $radius-lg $radius-lg;
  padding: 14px 20px;
  display: flex;
  align-items: center;
  gap: 12px;

  .dots {
    display: inline-flex;
    gap: 5px;

    span {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: $primary-color;
      animation: dotBounce 1.4s infinite ease-in-out both;

      &:nth-child(1) { animation-delay: -0.32s; }
      &:nth-child(2) { animation-delay: -0.16s; }
    }
  }

  .loading-text {
    font-size: 13px;
    color: $text-secondary;
  }
}

@keyframes dotBounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

// ========== 推荐问题区 ==========
.suggested-section {
  padding: 0 $spacing-lg $spacing-md;
  background: linear-gradient(180deg, #f0f5fa 0%, #fff 100%);
  border-top: 1px solid $border-color-light;
  flex-shrink: 0;
}

.suggested-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: $text-secondary;
  margin: 16px 0 12px;

  .el-icon {
    color: $warning-color;
  }
}

.suggested-chips {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.suggest-chip {
  margin: 0 !important;
  justify-content: flex-start;
  padding: 10px 14px !important;
  height: auto !important;
  font-size: 13px !important;
  min-height: 42px;
  text-align: left;
  transition: all 0.2s;
  background: #fff !important;
  border-color: $border-color !important;

  &:hover {
    border-color: $primary-color !important;
    background: $primary-bg !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 10px rgba(24, 144, 255, 0.12);
  }

  .el-icon {
    color: $primary-color;
    flex-shrink: 0;
  }
}

// ========== 输入区 ==========
.input-area {
  padding: $spacing-md $spacing-lg $spacing-lg;
  border-top: 1px solid $border-color-light;
  background: #fff;
  flex-shrink: 0;
}

.mini-suggested {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;

  .el-tag {
    cursor: pointer;
    transition: all 0.2s;
    &:hover {
      border-color: $primary-color;
      color: $primary-color;
    }
  }
}

.input-box {
  background: #fff;
  border: 1.5px solid $border-color;
  border-radius: $radius-lg;
  padding: 10px 12px 0;
  transition: all 0.2s;

  &:focus-within {
    border-color: $primary-color;
    box-shadow: 0 0 0 3px rgba(24, 144, 255, 0.1);
  }
}

.chat-input {
  :deep(.el-textarea__inner) {
    border: none;
    padding: 0;
    box-shadow: none;
    font-size: 14px;
    line-height: 1.6;
    resize: none;
    font-family: inherit;
  }
}

.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 8px;
  border-top: 1px solid $border-color-light;
}

.input-tip {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: $text-placeholder;

  .el-icon {
    font-size: 13px;
  }
}
</style>
