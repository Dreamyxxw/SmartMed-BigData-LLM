/**
 * AI Chat 流式渲染器 — 对象级流式（Object-Level Streaming）
 * ============================================================
 *
 * 核心思路：
 *   LLM 输出格式: [ {type:"text", content:"..."}, {type:"chart", option:{...}}, ... ]
 *
 *   1. 按 rawBuf 中的出现顺序扫描 "type":"text" 和 "type":"chart"
 *   2. text 类型 → 提取已完成的 "content":"..." → 完整显示
 *   3. chart 类型 → 显示 "📊 正在渲染图表..." 占位符
 *   4. 最后一个未完成的 content → 打字机效果（逐字显示）
 *   5. 不显示原始 JSON 字符串
 */

export class AichatStreamParser {
  constructor(onPartsUpdate) {
    this.onPartsUpdate = onPartsUpdate || (() => {})
    this.reset()
  }

  reset() {
    this.rawBuf = ''
    this.streamingText = ''
    this.parts = []
    this.lastFingerprint = ''
  }

  push(delta) {
    if (!delta) return
    this.rawBuf += delta
    this._parse()
    this._report()
  }

  _parse() {
    const buf = this.rawBuf

    // 1. 按顺序扫描所有 "type":"text" 和 "type":"chart"
    const parts = []
    const typeRegex = /"type"\s*:\s*"(text|chart)"/g
    let m
    while ((m = typeRegex.exec(buf)) !== null) {
      if (m[1] === 'text') {
        // 在 m.index 后面找已完成的 "content":"..."
        const afterType = buf.slice(m.index)
        const contentMatch = afterType.match(/"content"\s*:\s*"((?:[^"\\]|\\.)*)"/)
        if (contentMatch) {
          try {
            const decoded = JSON.parse('"' + contentMatch[1] + '"')
            parts.push({ type: 'text', content: decoded })
          } catch {
            // 解码失败，跳过
          }
        }
      } else if (m[1] === 'chart') {
        parts.push({ type: 'text', content: '📊 正在渲染图表...', isChartPlaceholder: true })
      }
    }
    this.parts = parts

    // 2. 检测最后一个未完成的 content（打字机效果）
    // 找到最后一个 "content":" 的位置（未闭合的引号）
    this.streamingText = ''
    const lastContentKey = buf.lastIndexOf('"content"')
    if (lastContentKey >= 0) {
      const afterKey = buf.slice(lastContentKey + 9) // skip "content"
      const colonMatch = afterKey.match(/^\s*:\s*"/)
      if (colonMatch) {
        const textStart = colonMatch[0].length
        let i = textStart
        let completed = false
        while (i < afterKey.length) {
          if (afterKey[i] === '\\' && i + 1 < afterKey.length) {
            i += 2
            continue
          }
          if (afterKey[i] === '"') {
            completed = true
            break
          }
          i++
        }
        // 只有未完成的 content 才显示为 streaming
        if (!completed) {
          const rawText = afterKey.slice(textStart, i)
          try {
            this.streamingText = JSON.parse('"' + rawText + '"')
          } catch {
            this.streamingText = rawText
          }
        }
      }
    }
  }

  _report() {
    // 用指纹判断是否需要报告
    const fingerprint = `${this.parts.length}|${this.streamingText.length}`
    if (fingerprint === this.lastFingerprint) return
    this.lastFingerprint = fingerprint
    this.onPartsUpdate(this._getRenderParts())
  }

  _getRenderParts() {
    const parts = [...this.parts]

    // 当前正在接收的 text（打字机效果）
    if (this.streamingText) {
      parts.push({ type: 'text', content: this.streamingText, isStreaming: true })
    }

    return parts
  }

  getCompletedObjects() {
    return this.parts.map(p => ({ ...p }))
  }
}
