import{a9 as c}from"./index-DFfLC3oa.js";const g=["Manhattan","Brooklyn","Queens","Bronx","Staten Island"],d=["内科","外科","妇产科","儿科","心内科","骨科","神经科","急诊科","肿瘤科","泌尿科"],r=[{name:"充血性心力衰竭",baseCost:25e3},{name:"败血症",baseCost:32e3},{name:"急性心肌梗死",baseCost:45e3},{name:"慢性阻塞性肺疾病",baseCost:18e3},{name:"脑卒中",baseCost:38e3},{name:"糖尿病伴并发症",baseCost:22e3},{name:"肾功能衰竭",baseCost:4e4},{name:"肺炎",baseCost:15e3},{name:"消化道出血",baseCost:28e3},{name:"髋关节置换术",baseCost:52e3},{name:"膝关节置换术",baseCost:48e3},{name:"冠状动脉搭桥",baseCost:65e3},{name:"结肠癌切除术",baseCost:42e3},{name:"胆囊切除术",baseCost:16e3},{name:"子宫切除术",baseCost:2e4}];function m(e={}){const t=e.region&&e.region!=="all"?.25:1;return{code:200,data:{totalDischarges:Math.round(125680*t),avgTotalCharges:parseFloat((45680.52*t).toFixed(2)),avgTotalCosts:parseFloat((18920.35*t).toFixed(2)),avgStayDays:parseFloat((6.8*t).toFixed(1))}}}function p(e={}){const t=[{name:"0-17岁",value:8520},{name:"18-29岁",value:15340},{name:"30-49岁",value:32680},{name:"50-69岁",value:41250},{name:"70岁以上",value:27890}];return e.region&&e.region!=="all"&&t.forEach(n=>n.value=Math.round(n.value*.25)),{code:200,data:t}}function f(e={}){const t=e.ageGroup;let n=[...r];t==="70岁以上"?n=r.filter(o=>["充血性心力衰竭","脑卒中","慢性阻塞性肺疾病","肾功能衰竭","髋关节置换术","膝关节置换术","糖尿病伴并发症","肺炎","结肠癌切除术","急性心肌梗死"].includes(o.name)):t==="50-69岁"?n=r.filter(o=>["糖尿病伴并发症","急性心肌梗死","膝关节置换术","慢性阻塞性肺疾病","结肠癌切除术","胆囊切除术","充血性心力衰竭","肺炎","子宫切除术","冠状动脉搭桥"].includes(o.name)):t==="0-17岁"&&(n=[{name:"肺炎",baseCost:12e3},{name:"急性阑尾炎",baseCost:14e3},{name:"哮喘",baseCost:9e3},{name:"病毒性脑炎",baseCost:22e3},{name:"骨折",baseCost:16e3},{name:"先天性心脏病",baseCost:45e3},{name:"急性肠胃炎",baseCost:8e3},{name:"泌尿道感染",baseCost:1e4},{name:"烧伤",baseCost:18e3},{name:"癫痫",baseCost:15e3}]);const a=e.region&&e.region!=="all"?.2:1;return{code:200,data:n.slice(0,10).map(o=>({name:o.name,value:parseFloat((o.baseCost*(.85+Math.random()*.3)*a).toFixed(2))})).sort((o,l)=>l.value-o.value)}}function y(e={}){const t=e.region&&e.region!=="all"?.25:1;return{code:200,data:d.slice(0,8).map(a=>({name:a,totalCharges:Math.round((5e6+Math.random()*8e6)*t),avgStayDays:parseFloat((4+Math.random()*8).toFixed(1)),count:Math.round((1e3+Math.random()*3e3)*t)}))}}const C=[{id:"1",title:"查询高血压费用",time:"2024-01-15 10:30"},{id:"2",title:"比较不同区域住院天数",time:"2024-01-14 15:20"},{id:"3",title:"糖尿病患者费用分析",time:"2024-01-13 09:45"},{id:"4",title:"Bronx区急诊患者画像",time:"2024-01-12 14:10"},{id:"5",title:"按支付方式统计总费用",time:"2024-01-11 16:30"},{id:"6",title:"2023年度费用趋势分析",time:"2024-01-10 11:20"}],b=[{id:"q1",text:"按支付方式统计总费用"},{id:"q2",text:"Bronx区急诊患者画像"},{id:"q3",text:"2024年Q1费用趋势分析"},{id:"q4",text:"各科室平均住院天数对比"},{id:"q5",text:"70岁以上人群疾病分布"},{id:"q6",text:"不同严重程度费用差异"}];function h(){return{code:200,data:C}}function x(){return{code:200,data:b}}function v(e){return{code:200,data:[{type:"text",content:`根据数据分析，关于"${e.message||""}"的结果如下：

根据${e.year||"2024"}年${e.region&&e.region!=="all"?(g.find(a=>a===e.region)||e.region)+"区域":"全区域"}的住院数据统计：`},{type:"chart",chartType:"bar",option:{title:{text:"各区域总费用对比（单位：万元）",left:"center",textStyle:{fontSize:14}},tooltip:{trigger:"axis"},xAxis:{type:"category",data:["曼哈顿","布鲁克林","皇后区","布朗克斯","史泰登岛"]},yAxis:{type:"value"},series:[{type:"bar",data:[4850,3620,2980,2150,1080],itemStyle:{color:{type:"linear",x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:"#1890ff"},{offset:1,color:"#096dd9"}]}}}]}},{type:"text",content:`主要发现：
1. 曼哈顿区总费用最高，达4850万元
2. 各区域费用差异显著，可能与医院等级和患者病情有关
3. 建议重点关注费用较高的慢性病管理`}]}}let s=[{id:"r1",title:"2024年Q1医疗费用综合分析报告",cover:"finance",tags:["财务","季度报告"],createTime:"2024-04-05 14:30:00",description:"全面分析第一季度各科室费用结构、支付方式占比及成本控制情况。"},{id:"r2",title:"老年慢性病患者住院特征分析",cover:"pathology",tags:["病理","老年医学"],createTime:"2024-03-28 09:15:00",description:"针对65岁以上慢性病患者的住院天数、费用分布和再住院率进行深入分析。"},{id:"r3",title:"Bronx区域医疗资源利用率评估",cover:"region",tags:["区域分析","资源管理"],createTime:"2024-03-20 16:45:00",description:"评估布朗克斯区各医院床位利用率、急诊科负荷及手术量分布。"},{id:"r4",title:"心血管疾病诊疗成本效益分析",cover:"pathology",tags:["病理","心血管"],createTime:"2024-03-10 11:20:00",description:"对比不同心血管疾病治疗方案的成本与疗效，为临床决策提供数据支撑。"},{id:"r5",title:"2023年度住院数据年度总结",cover:"finance",tags:["年度报告","综合"],createTime:"2024-02-15 10:00:00",description:"汇总2023全年出院患者数据，包含KPI趋势、科室排名、区域对比等核心指标。"},{id:"r6",title:"糖尿病并发症预防干预效果报告",cover:"pathology",tags:["病理","内分泌"],createTime:"2024-02-08 15:30:00",description:"分析糖尿病管理项目对降低并发症发生率和住院费用的实际效果。"}];function D(){return{code:200,data:s}}function T(e){const n={id:"r"+Date.now(),title:e.title||`${e.topic}分析报告`,cover:e.topic==="特定疾病分析"?"pathology":e.topic==="区域医疗评估"?"region":"finance",tags:[e.topic||"综合分析",...e.tags||[]],createTime:new Date().toLocaleString("zh-CN"),description:`基于${e.year||"2024"}年${e.region&&e.region!=="all"?e.region:"全区域"}数据生成的${e.topic||"综合"}分析报告。`};return s=[n,...s],{code:200,data:n,message:"报告生成成功"}}function $(e){const t=s.find(n=>n.id===e)||s[0];return{code:200,data:{...t,content:`# ${t.title}

## 报告摘要

本报告基于2024年纽约市住院患者数据，从多个维度对${t.tags.join("、")}进行深入分析。

## 一、核心指标概览

| 指标 | 数值 | 同比 |
|------|------|------|
| 出院人数 | 125,680 | +5.2% |
| 平均住院总费用 | $45,680 | +3.8% |
| 平均总成本 | $18,920 | +2.1% |
| 平均住院天数 | 6.8天 | -0.3天 |

## 二、详细分析

### 2.1 费用构成分析

总费用中，药品费占比最高（38%），其次是手术费（25%）、检查费（18%）、床位费（12%）及其他（7%）。

### 2.2 病种分布

排名前三的病种为：充血性心力衰竭、败血症、急性心肌梗死。

## 三、图表分析

### 各区域费用对比

![区域对比图](chart-1)

## 四、建议与结论

1. 加强慢性病管理，降低再住院率
2. 优化高值药品使用，控制药占比
3. 推广日间手术，缩短平均住院日

---
*报告生成时间：${t.createTime}*`}}}async function i(e,t,n,a){try{return await c.get(e,{params:t})}catch{return new Promise(o=>{setTimeout(()=>o(n(a)),100)})}}function M(e={}){return i("/dashboard/kpi",e,m,e)}function q(e={}){return i("/dashboard/age-group",e,p,e)}function F(e={}){const t={...e};return t.ageGroup||(t.ageGroup="all"),i("/dashboard/top-diseases",t,f,t)}function w(e={}){return i("/dashboard/dept-compare",e,y,e)}function P(){return new Promise(e=>{setTimeout(()=>e(h()),200)})}function R(e){return new Promise(t=>{setTimeout(()=>t(v(e)),1e3)})}function A(){return new Promise(e=>{setTimeout(()=>e(x()),200)})}function E(){return c.get("/analytics/filters")}function G(e={}){return c.get("/analytics/query",{params:e})}function Q(){return new Promise(e=>{setTimeout(()=>e(D()),300)})}function B(e){return new Promise(t=>{setTimeout(()=>t(T(e)),2e3)})}function L(e){return new Promise(t=>{setTimeout(()=>t($(e)),300)})}export{q as a,F as b,w as c,P as d,A as e,E as f,M as g,Q as h,B as i,L as j,G as q,R as s};
