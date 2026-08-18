// ========== Mock 数据 - 模拟 hospital.xlsx 数据结构 ==========

// 模拟NYC医院数据的关键字段
const AGE_GROUPS = ['0-17岁', '18-29岁', '30-49岁', '50-69岁', '70岁以上']
const REGIONS = ['Manhattan', 'Brooklyn', 'Queens', 'Bronx', 'Staten Island']
const DEPARTMENTS = ['内科', '外科', '妇产科', '儿科', '心内科', '骨科', '神经科', '急诊科', '肿瘤科', '泌尿科']
const FACILITIES = [
  '纽约长老会医院', '纽约大学朗格尼医学中心', '西奈山医院',
  '贝尔维尤医院中心', '长岛犹太医疗中心', '蒙特菲奥里医疗中心'
]
const SEVERITIES = ['轻微', '中度', '严重', '极重']
const GENDERS = ['男', '女']
const PAYMENT_TYPES = ['医疗保险', '医疗补助', '自费', '商业保险', '其他']

const DISEASES = [
  { name: '充血性心力衰竭', baseCost: 25000 },
  { name: '败血症', baseCost: 32000 },
  { name: '急性心肌梗死', baseCost: 45000 },
  { name: '慢性阻塞性肺疾病', baseCost: 18000 },
  { name: '脑卒中', baseCost: 38000 },
  { name: '糖尿病伴并发症', baseCost: 22000 },
  { name: '肾功能衰竭', baseCost: 40000 },
  { name: '肺炎', baseCost: 15000 },
  { name: '消化道出血', baseCost: 28000 },
  { name: '髋关节置换术', baseCost: 52000 },
  { name: '膝关节置换术', baseCost: 48000 },
  { name: '冠状动脉搭桥', baseCost: 65000 },
  { name: '结肠癌切除术', baseCost: 42000 },
  { name: '胆囊切除术', baseCost: 16000 },
  { name: '子宫切除术', baseCost: 20000 }
]

// ========== Dashboard Mock ==========

export function getKpiData(params = {}) {
  const multiplier = params.region && params.region !== 'all' ? 0.25 : 1
  return {
    code: 200,
    data: {
      totalDischarges: Math.round(125680 * multiplier),
      avgTotalCharges: parseFloat((45680.52 * multiplier).toFixed(2)),
      avgTotalCosts: parseFloat((18920.35 * multiplier).toFixed(2)),
      avgStayDays: parseFloat((6.8 * multiplier).toFixed(1))
    }
  }
}

export function getAgeGroupData(params = {}) {
  const base = [
    { name: '0-17岁', value: 8520 },
    { name: '18-29岁', value: 15340 },
    { name: '30-49岁', value: 32680 },
    { name: '50-69岁', value: 41250 },
    { name: '70岁以上', value: 27890 }
  ]
  if (params.region && params.region !== 'all') {
    base.forEach(item => item.value = Math.round(item.value * 0.25))
  }
  return { code: 200, data: base }
}

export function getTopDiseasesData(params = {}) {
  const ageFilter = params.ageGroup
  let diseases = [...DISEASES]
  if (ageFilter === '70岁以上') {
    diseases = DISEASES.filter(d => ['充血性心力衰竭', '脑卒中', '慢性阻塞性肺疾病', '肾功能衰竭', '髋关节置换术', '膝关节置换术', '糖尿病伴并发症', '肺炎', '结肠癌切除术', '急性心肌梗死'].includes(d.name))
  } else if (ageFilter === '50-69岁') {
    diseases = DISEASES.filter(d => ['糖尿病伴并发症', '急性心肌梗死', '膝关节置换术', '慢性阻塞性肺疾病', '结肠癌切除术', '胆囊切除术', '充血性心力衰竭', '肺炎', '子宫切除术', '冠状动脉搭桥'].includes(d.name))
  } else if (ageFilter === '0-17岁') {
    diseases = [
      { name: '肺炎', baseCost: 12000 },
      { name: '急性阑尾炎', baseCost: 14000 },
      { name: '哮喘', baseCost: 9000 },
      { name: '病毒性脑炎', baseCost: 22000 },
      { name: '骨折', baseCost: 16000 },
      { name: '先天性心脏病', baseCost: 45000 },
      { name: '急性肠胃炎', baseCost: 8000 },
      { name: '泌尿道感染', baseCost: 10000 },
      { name: '烧伤', baseCost: 18000 },
      { name: '癫痫', baseCost: 15000 }
    ]
  }
  const multiplier = params.region && params.region !== 'all' ? 0.2 : 1
  const result = diseases.slice(0, 10).map(d => ({
    name: d.name,
    value: parseFloat((d.baseCost * (0.85 + Math.random() * 0.3) * multiplier).toFixed(2))
  })).sort((a, b) => b.value - a.value)

  return { code: 200, data: result }
}

export function getDeptCompareData(params = {}) {
  const multiplier = params.region && params.region !== 'all' ? 0.25 : 1
  const data = DEPARTMENTS.slice(0, 8).map(dept => ({
    name: dept,
    totalCharges: Math.round((5000000 + Math.random() * 8000000) * multiplier),
    avgStayDays: parseFloat((4 + Math.random() * 8).toFixed(1)),
    count: Math.round((1000 + Math.random() * 3000) * multiplier)
  }))
  return { code: 200, data }
}

// ========== AI Chat Mock ==========

const chatHistoryList = [
  { id: '1', title: '查询高血压费用', time: '2024-01-15 10:30' },
  { id: '2', title: '比较不同区域住院天数', time: '2024-01-14 15:20' },
  { id: '3', title: '糖尿病患者费用分析', time: '2024-01-13 09:45' },
  { id: '4', title: 'Bronx区急诊患者画像', time: '2024-01-12 14:10' },
  { id: '5', title: '按支付方式统计总费用', time: '2024-01-11 16:30' },
  { id: '6', title: '2023年度费用趋势分析', time: '2024-01-10 11:20' }
]

const suggestedQuestions = [
  { id: 'q1', text: '按支付方式统计总费用' },
  { id: 'q2', text: 'Bronx区急诊患者画像' },
  { id: 'q3', text: '2024年Q1费用趋势分析' },
  { id: 'q4', text: '各科室平均住院天数对比' },
  { id: 'q5', text: '70岁以上人群疾病分布' },
  { id: 'q6', text: '不同严重程度费用差异' }
]

export function getChatHistory() {
  return { code: 200, data: chatHistoryList }
}

export function getSuggestedQuestions() {
  return { code: 200, data: suggestedQuestions }
}

export function sendChatMessage(data) {
  const question = data.message || ''
  const responses = [
    {
      type: 'text',
      content: `根据数据分析，关于"${question}"的结果如下：\n\n根据${data.year || '2024'}年${data.region && data.region !== 'all' ? (REGIONS.find(r => r === data.region) || data.region) + '区域' : '全区域'}的住院数据统计：`
    },
    {
      type: 'chart',
      chartType: 'bar',
      option: {
        title: { text: '各区域总费用对比（单位：万元）', left: 'center', textStyle: { fontSize: 14 } },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: ['曼哈顿', '布鲁克林', '皇后区', '布朗克斯', '史泰登岛'] },
        yAxis: { type: 'value' },
        series: [{
          type: 'bar',
          data: [4850, 3620, 2980, 2150, 1080],
          itemStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: '#1890ff' },
                { offset: 1, color: '#096dd9' }
              ]
            }
          }
        }]
      }
    },
    {
      type: 'text',
      content: '主要发现：\n1. 曼哈顿区总费用最高，达4850万元\n2. 各区域费用差异显著，可能与医院等级和患者病情有关\n3. 建议重点关注费用较高的慢性病管理'
    }
  ]
  return { code: 200, data: responses }
}

// ========== Analytics Mock ==========

export function getFilterOptions() {
  return {
    code: 200,
    data: {
      facilities: FACILITIES.map(name => ({ label: name, value: name })),
      genders: GENDERS.map(g => ({ label: g, value: g })),
      severities: SEVERITIES.map(s => ({ label: s, value: s })),
      ageGroups: AGE_GROUPS.map(a => ({ label: a, value: a })),
      paymentTypes: PAYMENT_TYPES.map(p => ({ label: p, value: p })),
      departments: DEPARTMENTS.map(d => ({ label: d, value: d })),
      regions: REGIONS.map(r => ({ label: r, value: r }))
    }
  }
}

export function queryAnalyticsData(params = {}) {
  const total = 156
  const pageSize = params.pageSize || 20
  const page = params.page || 1
  const rows = []
  for (let i = 0; i < pageSize; i++) {
    const idx = (page - 1) * pageSize + i + 1
    if (idx > total) break
    const region = REGIONS[Math.floor(Math.random() * REGIONS.length)]
    const facility = FACILITIES[Math.floor(Math.random() * FACILITIES.length)]
    const dept = DEPARTMENTS[Math.floor(Math.random() * DEPARTMENTS.length)]
    const disease = DISEASES[Math.floor(Math.random() * DISEASES.length)]
    const gender = GENDERS[Math.floor(Math.random() * GENDERS.length)]
    const severity = SEVERITIES[Math.floor(Math.random() * SEVERITIES.length)]
    const ageGroup = AGE_GROUPS[Math.floor(Math.random() * AGE_GROUPS.length)]
    const count = 50 + Math.floor(Math.random() * 500)
    const avgCharges = disease.baseCost * (0.7 + Math.random() * 0.6)
    const avgCosts = avgCharges * (0.35 + Math.random() * 0.15)
    const avgStay = 3 + Math.random() * 10

    rows.push({
      id: idx,
      region,
      facility,
      department: dept,
      disease: disease.name,
      gender,
      severity,
      ageGroup,
      count,
      avgCharges: parseFloat(avgCharges.toFixed(2)),
      avgCosts: parseFloat(avgCosts.toFixed(2)),
      avgStay: parseFloat(avgStay.toFixed(1)),
      totalCharges: parseFloat((avgCharges * count).toFixed(2))
    })
  }
  return {
    code: 200,
    data: {
      list: rows,
      total,
      page,
      pageSize
    }
  }
}

// ========== Reports Mock（后端/Redis 未就绪时降级用）==========

const MOCK_TOPIC_PRESETS = {
  特定疾病分析: { cover: 'pathology', tags: ['病理', '病种分布'] },
  病种趋势对比: { cover: 'pathology', tags: ['病理', '病种分布'] },
  病情严重程度分析: { cover: 'pathology', tags: ['病理', '严重程度'] },
  死亡风险分层分析: { cover: 'pathology', tags: ['病理', '死亡风险'] },
  出院转归分析: { cover: 'pathology', tags: ['病理', '出院转归'] },
  急诊入院路径分析: { cover: 'pathology', tags: ['病理', '急诊入院'] },
  人群病理画像: { cover: 'pathology', tags: ['病理', '人群画像'] },
  '手术与内科路径对比': { cover: 'pathology', tags: ['病理', '手术路径'] },
  费用构成分析: { cover: 'finance', tags: ['财务', '费用构成'] },
  成本效益评估: { cover: 'finance', tags: ['财务', '成本效益'] },
  区域医疗评估: { cover: 'region', tags: ['区域分析', '资源管理'] },
  医院科室排名: { cover: 'region', tags: ['区域分析', '资源管理'] },
  季度综合报告: { cover: 'finance', tags: ['年度报告', '综合'] },
  年度综合总结: { cover: 'finance', tags: ['年度报告', '综合'] }
}

let reportList = [
  {
    id: 'r1',
    title: '2021年医疗费用构成分析报告',
    cover: 'finance',
    tags: ['财务', '费用构成'],
    createTime: '2024-04-05 14:30:00',
    description: '全面梳理支付方式与科室费用结构，指标来自真实聚合缓存。'
  },
  {
    id: 'r2',
    title: '2021年高费用病种特征分析',
    cover: 'pathology',
    tags: ['病理', '病种分布'],
    createTime: '2024-03-28 09:15:00',
    description: '基于诊断维度聚合，展示高费用病种人次与均费。'
  },
  {
    id: 'r3',
    title: '2021年病情严重程度分层报告',
    cover: 'pathology',
    tags: ['病理', '严重程度'],
    createTime: '2024-03-22 11:10:00',
    description: '按 APR 严重程度拆解人次、均费与住院日，识别高消耗分层。'
  },
  {
    id: 'r4',
    title: '2021年出院转归与结局分析',
    cover: 'pathology',
    tags: ['病理', '出院转归'],
    createTime: '2024-03-18 16:20:00',
    description: '覆盖回家、转护理院、院内死亡等转归，服务临床质量回顾。'
  },
  {
    id: 'r5',
    title: '2021年住院人群病理画像',
    cover: 'pathology',
    tags: ['病理', '人群画像', '老年医学'],
    createTime: '2024-03-12 09:40:00',
    description: '交叉年龄、性别与高发诊断，刻画住院病理人群结构。'
  },
  {
    id: 'r6',
    title: 'Bronx区域医疗资源利用率评估',
    cover: 'region',
    tags: ['区域分析', '资源管理'],
    createTime: '2024-03-20 16:45:00',
    description: '评估布朗克斯区各医院出院量、均费及科室负荷。'
  },
  {
    id: 'r7',
    title: '2021年度住院数据综合总结',
    cover: 'finance',
    tags: ['年度报告', '综合'],
    createTime: '2024-02-15 10:00:00',
    description: '汇总年度核心 KPI 与多维分布，作为洞察报告底稿。'
  }
]

export function getReportMeta() {
  return {
    code: 200,
    data: {
      tags: ['财务', '病理', '区域分析', '综合', '病种分布', '严重程度', '死亡风险', '急诊入院', '出院转归', '人群画像', '手术路径', '心血管', '肿瘤', '感染', '内分泌', '老年医学', '儿科', '费用构成', '成本效益', '资源管理', '年度报告'],
      topics: Object.keys(MOCK_TOPIC_PRESETS),
      topicGroups: [
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
      ],
      tagGroups: [
        { label: '报告类别', tags: ['财务', '病理', '区域分析', '综合'] },
        { label: '病理维度', tags: ['病种分布', '严重程度', '死亡风险', '急诊入院', '出院转归', '人群画像', '手术路径'] },
        { label: '病种方向', tags: ['心血管', '肿瘤', '感染', '内分泌', '老年医学', '儿科'] },
        { label: '管理维度', tags: ['费用构成', '成本效益', '资源管理', '年度报告'] }
      ],
      topicPresets: MOCK_TOPIC_PRESETS
    }
  }
}

export function getReportList() {
  return { code: 200, data: reportList }
}

export function generateReport(data) {
  const id = 'r' + Date.now()
  const preset = MOCK_TOPIC_PRESETS[data.topic] || { cover: 'finance', tags: ['综合'] }
  const tags = (data.tags && data.tags.length) ? data.tags : preset.tags
  const newReport = {
    id,
    title: data.title || `${data.year || ''}年${data.topic}报告`,
    cover: preset.cover,
    tags,
    createTime: new Date().toLocaleString('zh-CN'),
    description: `基于${data.year || '2021'}年${data.region && data.region !== 'all' ? data.region : '全区域'}数据生成的${data.topic || '综合'}分析报告。`,
    topic: data.topic,
    year: data.year,
    region: data.region
  }
  reportList = [newReport, ...reportList]
  return { code: 200, data: newReport, message: '报告生成成功' }
}

export function getReportDetail(id) {
  const report = reportList.find(r => r.id === id) || reportList[0]
  return {
    code: 200,
    data: {
      ...report,
      content: `# ${report.title}\n\n## 报告摘要\n\n本报告基于2024年纽约市住院患者数据，从多个维度对${report.tags.join('、')}进行深入分析。\n\n## 一、核心指标概览\n\n| 指标 | 数值 | 同比 |\n|------|------|------|\n| 出院人数 | 125,680 | +5.2% |\n| 平均住院总费用 | $45,680 | +3.8% |\n| 平均总成本 | $18,920 | +2.1% |\n| 平均住院天数 | 6.8天 | -0.3天 |\n\n## 二、详细分析\n\n### 2.1 费用构成分析\n\n总费用中，药品费占比最高（38%），其次是手术费（25%）、检查费（18%）、床位费（12%）及其他（7%）。\n\n### 2.2 病种分布\n\n排名前三的病种为：充血性心力衰竭、败血症、急性心肌梗死。\n\n## 三、图表分析\n\n### 各区域费用对比\n\n![区域对比图](chart-1)\n\n## 四、建议与结论\n\n1. 加强慢性病管理，降低再住院率\n2. 优化高值药品使用，控制药占比\n3. 推广日间手术，缩短平均住院日\n\n---\n*报告生成时间：${report.createTime}*`
    }
  }
}

export function updateReport(id, data) {
  const idx = reportList.findIndex(r => r.id === id)
  if (idx >= 0) {
    reportList[idx] = { ...reportList[idx], ...data }
    return { code: 200, data: reportList[idx] }
  }
  return { code: 404, message: '报告不存在' }
}

export function deleteReport(id) {
  reportList = reportList.filter(r => r.id !== id)
  return { code: 200, message: '删除成功' }
}

export function duplicateReport(id) {
  const src = reportList.find(r => r.id === id)
  if (!src) return { code: 404, message: '报告不存在' }
  const copy = {
    ...src,
    id: 'r' + Date.now(),
    title: `${src.title}（副本）`,
    createTime: new Date().toLocaleString('zh-CN')
  }
  reportList = [copy, ...reportList]
  return { code: 200, data: copy, message: '复制成功' }
}
