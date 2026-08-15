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
          <el-dropdown trigger="click" @click.stop>
            <el-button text size="small" class="history-item__more">
              <el-icon><MoreFilled /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item>
                  <el-icon><Edit /></el-icon> 重命名
                </el-dropdown-item>
                <el-dropdown-item divided>
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
        <div v-if="messages.length === 0" class="welcome-block">
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
          :key="idx"
          class="message-item"
          :class="msg.role"
        >
          <div v-if="msg.role === 'assistant'" class="msg-avatar ai-avatar">
            <el-icon :size="18"><Cpu /></el-icon>
          </div>

          <div class="msg-content-wrap">
            <template v-if="msg.role === 'assistant'">
              <div v-for="(part, pIdx) in msg.parts" :key="pIdx" class="msg-part">
                <!-- 文本部分 -->
                <div v-if="part.type === 'text'" class="msg-text">
                  <pre class="formatted-text">{{ part.content }}</pre>
                </div>
                <!-- 图表部分 -->
                <div v-else-if="part.type === 'chart'" class="msg-chart">
                  <div class="msg-chart__header">
                    <span class="msg-chart__tag">
                      <el-icon><TrendCharts /></el-icon>
                      数据可视化
                    </span>
                    <el-button size="small" text @click="downloadMsgChart(part, idx, pIdx)">
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

        <!-- Loading 状态 -->
        <div v-if="isLoading" class="message-item assistant">
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
      <div v-if="messages.length === 0" class="suggested-section">
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
import { ref, reactive, computed, onMounted, nextTick, watch, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { ElMessageBox } from 'element-plus'
import { useGlobalStore } from '@/stores/global'
import { getChatHistory, sendChatMessage, getSuggestedQuestions } from '@/api'
import { downloadChart } from '@/utils/chart'

const globalStore = useGlobalStore()

// ========== 历史记录 ==========
const historyList = ref([])
const currentChatId = ref(null)
const searchKeyword = ref('')

const filteredHistory = computed(() => {
  if (!searchKeyword.value) return historyList.value
  const kw = searchKeyword.value.toLowerCase()
  return historyList.value.filter(h => h.title.toLowerCase().includes(kw))
})

const loadHistory = async () => {
  const res = await getChatHistory()
  if (res.code === 200) historyList.value = res.data
}

const handleSelectHistory = (item) => {
  currentChatId.value = item.id
  // 真实环境：根据 chatId 加载对应消息，这里模拟清空
  messages.value = []
}

const handleNewChat = () => {
  currentChatId.value = null
  messages.value = []
}

// ========== 推荐问题 ==========
const suggestedQuestions = ref([])
const loadSuggested = async () => {
  const res = await getSuggestedQuestions()
  if (res.code === 200) suggestedQuestions.value = res.data
}

// ========== 聊天消息 ==========
const messages = ref([])
const inputText = ref('')
const isLoading = ref(false)
const messagesContainerRef = ref(null)

const msgChartRefs = reactive({})
const setMsgChartRef = (msgIdx, partIdx, el) => {
  const key = `${msgIdx}-${partIdx}`
  if (el) msgChartRefs[key] = el
  else delete msgChartRefs[key]
}

const chartInstances = []

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainerRef.value) {
      messagesContainerRef.value.scrollTop = messagesContainerRef.value.scrollHeight
    }
  })
}

const renderMsgChart = (part, msgIdx, partIdx) => {
  nextTick(() => {
    const key = `${msgIdx}-${partIdx}`
    const el = msgChartRefs[key]
    if (!el || !part.option) return
    const instance = echarts.init(el)
    instance.setOption(part.option)
    chartInstances.push(instance)

    const ro = new ResizeObserver(() => instance.resize())
    ro.observe(el)
  })
}

const downloadMsgChart = (part, msgIdx, partIdx) => {
  const chartId = `msg-chart-${msgIdx}-${partIdx}`
  downloadChart(chartId, `AI-${part.chartType || 'chart'}`)
}

const handleSendSuggested = async (text) => {
  inputText.value = text
  await handleSend()
}

const handleSend = async () => {
  const content = inputText.value.trim()
  if (!content || isLoading.value) return

  messages.value.push({
    role: 'user',
    content
  })
  inputText.value = ''
  scrollToBottom()

  isLoading.value = true
  try {
    const res = await sendChatMessage({
      message: content,
      year: globalStore.selectedYear,
      region: globalStore.selectedRegion,
      chatId: currentChatId.value
    })

    if (res.code === 200) {
      const msgIdx = messages.value.length
      const aiMsg = {
        role: 'assistant',
        parts: res.data
      }
      messages.value.push(aiMsg)
      scrollToBottom()

      // 渲染所有图表部分
      res.data.forEach((part, pIdx) => {
        if (part.type === 'chart') {
          renderMsgChart(part, msgIdx, pIdx)
        }
      })
    }
  } finally {
    isLoading.value = false
  }
}

const handleClearChat = () => {
  ElMessageBox.confirm('确定要清空当前对话吗？此操作不可恢复。', '提示', {
    type: 'warning',
    confirmButtonText: '确定清空',
    cancelButtonText: '取消'
  }).then(() => {
    messages.value = []
    chartInstances.forEach(inst => inst.dispose())
    chartInstances.length = 0
    ElMessage.success('对话已清空')
  }).catch(() => {})
}

const handleExportChat = () => {
  ElMessage.info('导出功能开发中...')
}

// ========== 生命周期 ==========
onMounted(() => {
  loadHistory()
  loadSuggested()
})

onBeforeUnmount(() => {
  chartInstances.forEach(inst => inst.dispose())
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
