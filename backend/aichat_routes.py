# -*- coding: utf-8 -*-
"""
智慧医疗分析平台 - AI智能探索舱 后端路由 & LangChain 实现
==========================================================

路由（Blueprint 前缀 /api/aichat/*）：
    GET  /api/aichat/suggested           → 推荐问题（Redis 预构建缓存）
    GET  /api/aichat/history             → 会话历史列表（Redis conv:list）
    POST /api/aichat/chat/new            → 新建空会话，返回 chatId
    POST /api/aichat/chat                → 发送消息（LangChain 生成回答）

Redis Key 设计（前缀 smartmed:aichat:，独立命名空间，与 dashboard 不冲突）：
    suggested                 → List[{id,text}]       推荐问题（预构建）
    meta                      → Object                预构建元信息
    conv:list                 → Hash<chatId, JSON>    会话元数据列表
    conv:msgs:{chatId}        → List[JSON]            会话消息历史

LangChain 实现：
    - 从 backend/.env 读取 LLM 配置（OPENAI_API_KEY / DEEPSEEK_API_KEY 等）
    - 使用 ChatPromptTemplate 组装 system prompt（注入 Dashboard 真实数据作为上下文）
    - LangChain ChatModel（OpenAI 兼容接口）生成回答
    - 要求 LLM 输出严格 JSON 数组 [{type:'text'|'chart', ...}]
    - 多轮对话历史通过 Redis 维护，转换为 LangChain message 列表
"""

import os
import sys
import json
import time
import uuid
import re
from datetime import datetime

import redis
from flask import request, jsonify, Blueprint

# ---------- 加载 .env（python-dotenv 优先；未装则手动解析） ----------
_ENV_PATH = os.path.join(os.path.dirname(__file__), '.env')
try:
    from dotenv import load_dotenv
    if os.path.exists(_ENV_PATH):
        load_dotenv(_ENV_PATH)
except ImportError:
    if os.path.exists(_ENV_PATH):
        with open(_ENV_PATH, 'r', encoding='utf-8') as _f:
            for _line in _f:
                _line = _line.strip()
                if not _line or _line.startswith('#') or '=' not in _line:
                    continue
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# ---------- LangChain 必需依赖 ----------
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

# httpx 是 langchain_openai 的依赖，用于底层 HTTP 传输。
# 这里显式 import 是为了构造分阶段 Timeout，避免被"单一 timeout"过早掐断。
try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

# ---------- 配置 ----------
AICHAT_KEY_PREFIX = 'smartmed:aichat:'
DASHBOARD_KEY_PREFIX = 'smartmed:dashboard:'

REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

# ---------- LLM 配置（从 .env 读取，按 provider 自动选择） ----------
LLM_PROVIDER = (os.getenv('LLM_PROVIDER') or 'openai').lower()
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.3'))

# 超时（秒）：分阶段控制 connect / read / write，比单一 timeout 更可控
#   LLM_TIMEOUT       = 总超时（兜底，覆盖所有阶段之和，默认 300s）
#   LLM_CONNECT_TIMEOUT = 建连超时（默认 30s）
#   LLM_READ_TIMEOUT    = 读取响应超时（默认 300s，LLM 生成慢时主要卡在这里）
#   LLM_WRITE_TIMEOUT   = 上传请求超时（默认 30s）
LLM_TIMEOUT = int(os.getenv('LLM_TIMEOUT', '300'))
LLM_CONNECT_TIMEOUT = int(os.getenv('LLM_CONNECT_TIMEOUT', '30'))
LLM_READ_TIMEOUT = int(os.getenv('LLM_READ_TIMEOUT', '300'))
LLM_WRITE_TIMEOUT = int(os.getenv('LLM_WRITE_TIMEOUT', '30'))
LLM_MAX_RETRIES = int(os.getenv('LLM_MAX_RETRIES', '3'))

# 按 provider 读取对应的 API Key / Base / Model
_PROVIDER_KEY_MAP = {
    'openai':      ('OPENAI_API_KEY',      'OPENAI_API_BASE',      'OPENAI_MODEL',      'gpt-4o-mini'),
    'deepseek':    ('DEEPSEEK_API_KEY',    'DEEPSEEK_API_BASE',    'DEEPSEEK_MODEL',    'deepseek-chat'),
    'siliconflow': ('SILICONFLOW_API_KEY', 'SILICONFLOW_API_BASE', 'SILICONFLOW_MODEL', 'deepseek-ai/DeepSeek-V3.2'),
    'zhipu':       ('ZHIPUAI_API_KEY',     'ZHIPUAI_API_BASE',     'ZHIPUAI_MODEL',     'glm-4-flash'),
    'qwen':        ('DASHSCOPE_API_KEY',   'DASHSCOPE_API_BASE',   'DASHSCOPE_MODEL',   'qwen-plus'),
    'anthropic':   ('ANTHROPIC_API_KEY',   'ANTHROPIC_API_BASE',   'ANTHROPIC_MODEL',   'claude-3-5-sonnet-20240620'),
}
_key_env, _base_env, _model_env, _default_model = _PROVIDER_KEY_MAP.get(LLM_PROVIDER, _PROVIDER_KEY_MAP['openai'])
LLM_API_KEY = os.getenv(_key_env)
LLM_API_BASE = os.getenv(_base_env) or None
LLM_MODEL = os.getenv(_model_env) or _default_model


# ---------- Redis ----------
def get_redis():
    return redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
        password=REDIS_PASSWORD, decode_responses=True,
        socket_connect_timeout=2, socket_timeout=5,
    )

r = get_redis()

# ---------- Blueprint ----------
aichat_bp = Blueprint('aichat', __name__, url_prefix='/api/aichat')


# ==================== 通用工具 ====================
def ok(data):
    return jsonify({'code': 200, 'data': data})


def err(message, code=400):
    return jsonify({'code': code, 'message': message}), code


def _cache_get(full_key, fallback):
    try:
        raw = r.get(full_key)
        return json.loads(raw) if raw else fallback
    except Exception:
        return fallback


def _now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def _safe_get_dashboard_key(suffix):
    """读取 Dashboard 预构建数据（作为 LLM 上下文）"""
    return _cache_get(f'{DASHBOARD_KEY_PREFIX}{suffix}', None)


# ==================== 会话管理（Redis 持久化） ====================
def get_conversation_list():
    """读取会话列表，按 updatedAt 倒序"""
    try:
        raw = r.hgetall(f'{AICHAT_KEY_PREFIX}conv:list')
        items = []
        for cid, payload in raw.items():
            try:
                items.append(json.loads(payload))
            except Exception:
                pass
        items.sort(key=lambda x: x.get('updatedAt', ''), reverse=True)
        return items
    except Exception:
        return []


def save_conversation_meta(chat_id, title, first_message=False):
    """新增或更新会话元信息"""
    key = f'{AICHAT_KEY_PREFIX}conv:list'
    existing_raw = r.hget(key, chat_id)
    now = _now_str()
    if existing_raw:
        try:
            meta = json.loads(existing_raw)
        except Exception:
            meta = {}
    else:
        meta = {'id': chat_id, 'createdAt': now, 'messageCount': 0}
    if title:
        meta['title'] = title
    meta['updatedAt'] = now
    if first_message:
        meta['messageCount'] = int(meta.get('messageCount', 0)) + 2  # 用户 + AI
    r.hset(key, chat_id, json.dumps(meta, ensure_ascii=False))
    return meta


def append_message(chat_id, role, content=None, parts=None):
    """向某会话追加一条消息"""
    msg = {'role': role, 'ts': int(time.time() * 1000)}
    if role == 'user':
        msg['content'] = content
    else:
        msg['parts'] = parts
    r.rpush(f'{AICHAT_KEY_PREFIX}conv:msgs:{chat_id}', json.dumps(msg, ensure_ascii=False))


def get_messages(chat_id, limit=20):
    """读取最近 N 条消息"""
    try:
        raw_list = r.lrange(f'{AICHAT_KEY_PREFIX}conv:msgs:{chat_id}', -limit, -1)
        return [json.loads(x) for x in raw_list]
    except Exception:
        return []


def history_to_langchain(history):
    """把 Redis 中的消息历史转成 LangChain message 列表（用于多轮对话）"""
    msgs = []
    for m in history:
        role = m.get('role')
        if role == 'user':
            msgs.append(HumanMessage(content=m.get('content', '')))
        elif role == 'assistant':
            parts = m.get('parts') or []
            texts = [p.get('content', '') for p in parts if p.get('type') == 'text']
            msgs.append(AIMessage(content='\n'.join(texts) if texts else '[图表回复]'))
    return msgs


# ==================== LangChain LLM 实例（懒加载单例） ====================
_llm_instance = None


def get_llm():
    """根据 .env 配置构造 LangChain ChatModel（OpenAI 兼容接口）。

    超时控制三层：
      1) ChatOpenAI(timeout=..)              → 传给 openai SDK 的总超时（兜底）
      2) ChatOpenAI(max_retries=..)          → SDK 内部对 429/5xx 的 tenacity 重试
      3) ChatOpenAI(http_client=httpx.Client(timeout=httpx.Timeout(..)))
         → httpx 分阶段超时（connect/read/write/pool），解决"生成较慢读超时"
    """
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    if not LLM_API_KEY:
        raise RuntimeError(
            f'未配置 LLM API Key。请在 backend/.env 中取消 LLM_PROVIDER={LLM_PROVIDER} 对应一组的注释，'
            f'并填入 {_key_env} 等环境变量。'
        )

    # 统一走 OpenAI 兼容协议（DeepSeek/智谱/通义/硅基流动都支持）
    kwargs = {
        'model': LLM_MODEL,
        'temperature': LLM_TEMPERATURE,
        'timeout': LLM_TIMEOUT,          # 层1：SDK 总超时兜底
        'max_retries': LLM_MAX_RETRIES,  # 层2：SDK 内部 429/5xx 重试
        'api_key': LLM_API_KEY,
    }
    if LLM_API_BASE:
        kwargs['base_url'] = LLM_API_BASE

    # 层3：httpx 分阶段超时（建连快、生成慢所以 read 放大）
    if httpx is not None:
        try:
            hx_timeout = httpx.Timeout(
                timeout=LLM_TIMEOUT,
                connect=LLM_CONNECT_TIMEOUT,
                read=LLM_READ_TIMEOUT,
                write=LLM_WRITE_TIMEOUT,
            )
            kwargs['http_client'] = httpx.Client(timeout=hx_timeout)
        except Exception as _e:
            print(f'[aichat] httpx 分阶段超时初始化失败，退回 SDK 默认 timeout: {_e}')

    _llm_instance = ChatOpenAI(**kwargs)
    return _llm_instance


# ==================== Prompt 模板 ====================
SYSTEM_PROMPT_TEMPLATE = """你是 SmartMed 智慧医疗大数据分析平台的 AI 助手。
基于用户的医疗数据分析问题和下方真实的住院数据上下文，生成专业、结构化、含图表的回答。

【真实数据上下文（来自原始 CSV 聚合统计）】
- 当前筛选：年份={year}，区域={region_cn}（{region}）
- 全局汇总（跨年/跨区域）: {summary_json}
- 当前年份+区域明细: {stats_json}
- 按年龄段汇总（全局）: {age_group_stats_json}

【数据字段说明（纽约州住院数据）】
- Age Group: 0-17 / 18-29 / 30-49 / 50-69 / 70 or Older
- Gender: M / F / U
- Race: White / Black/African American / Other Race / Unknown
- Ethnicity: Spanish/Hispanic / Not Span/Hispanic / Unknown
- Type of Admission: Emergency / Elective / Newborn / Transfer / Unknown
- Patient Disposition: Home / Home w/ Home Health Services / Expired / Transfer 等
- APR Severity of Illness: Minor / Moderate / Major / Extreme
- APR Risk of Mortality: Minor / Moderate / Major / Extreme
- APR Medical Surgical Description: Medical / Surgical
- Payment Typology 1/2/3: Medicare / Medicaid / Private Health Insurance / Blue Cross 等
- Emergency Department Indicator: Y/N（是否经急诊入院）
- CCSR Diagnosis/Procedure Description: 疾病/手术名称（已按临床分类）
- Total Charges / Total Costs: 总费用 / 总成本
- Length of Stay: 住院天数

【输出格式 — 严格 JSON 语法（最重要，违反则不可解析）】
你必须返回一个 JSON 数组，且"只返回 JSON 数组本身"：
  - 文本片段: {{"type": "text", "content": "回答文本（支持 \\n 换行，建议 emoji 增强可读性）"}}
  - 图表片段: {{"type": "chart", "chartType": "bar|pie|line", "option": {{"...": "ECharts 5.x 完整配置对象，必须是纯 JSON，不允许任何 JS 语法"}} }}

【回答结构规范】
1. 回答必须包含 2~4 个片段，通常结构：文本(分析) → 图表(可视化) → 文本(建议)
2. 图表 option 必须完整、合法、能直接 echarts.init(el).setOption(option) 渲染
3. 图表数据必须基于上方真实数据上下文，不要凭空编造
4. 文本要专业、有条理，使用 emoji 分段（如 📊 💡 🎯 🏥 💰 🧓 🔍 等）
5. 所有文字使用简体中文
6. 涉及具体数字时务必引用上下文中的真实统计值（如费用、人数、占比）
7. 用户问"哪种疾病最多"时，参考 top_diagnoses；问"支付方式"参考 payment_distribution；
   问"严重程度"参考 severity_distribution；问"急诊"参考 emergency_department_ratio

【严格 JSON 禁令 —— 任何一条都会导致 JSON 解析失败！不要犯！】
❌ 绝对禁止用 ```json``` 或 `````` 这类 Markdown 代码块包裹 JSON
❌ 绝对禁止在 JSON 前后附加任何解释性文字（例如"好的，以下是分析："或"希望对你有帮助"）
❌ 绝对禁止使用 JS 语法：
   - 不要尾逗号（如 [1,2,3,] 中最后那个逗号必须去掉）
   - 不要 // 行注释 或 /* */ 块注释
   - 不要 undefined / NaN / Infinity（一律改用 null 或数字）
   - 不要单引号，所有字符串/对象的 key 都必须用双引号 "..."
   - 不要 Python 的 True/False/None，必须用 JSON 的 true/false/null
❌ 字符串里的反斜杠必须转义：换行写 \\n，引号写 \\"，制表写 \\t
❌ 图表 option 中禁止出现 function() {{ ... }} 等 JS 代码，颜色用固定字符串数组即可

【正确的输出示例（仅 JSON，无任何前后缀）】
[
  {{"type": "text", "content": "📊 分析结果：\\n\\n根据 {year} 年 {region_cn} 的数据..."}},
  {{"type": "chart", "chartType": "bar", "option": {{"title": {{"text": "示例", "left": "center"}}, "tooltip": {{"trigger": "axis"}}, "xAxis": {{"type": "category", "data": ["心内科","神经科"]}}, "yAxis": {{"type": "value"}}, "series": [{{"type": "bar", "data": [100, 80]}}]}}}},
  {{"type": "text", "content": "💡 建议：\\n1. ...\\n2. ..."}}
]

【错误示例 —— 千万别这样输出】
✗ ```json
[ {{"type": "text", ...}} ]
```
✗ 好的，这里是分析结果：[ {{"type": "text", ...}} ]
✗ [ {{"type": "text", "content": "ok", }} ]   ← 尾逗号
✗ [ {{'type': 'text', 'content': 'ok'}} ]     ← 单引号
✗ [ {{"type": "text", "content": undefined}} ] ← undefined
✗ [ {{"type": "chart", "option": {{...}}}}, ] ← 尾逗号
✗ "color": function(params) {{ ... }}         ← JS 函数
"""


# ==================== 数据目录（Catalog）构建 ====================
def _build_catalog():
    """构建数据目录，供 LLM 规划阶段检索。返回紧凑的 JSON 字符串。"""
    meta = _cache_get(f'{AICHAT_KEY_PREFIX}meta', {})
    catalog = {
        'description': '纽约州住院数据统计，可按年份、区域、县、年龄段筛选',
        'dimensions': {
            'year': meta.get('years', []),
            'region': meta.get('regions', []),
            'county': meta.get('counties', []),
            'age_group': meta.get('age_groups', []),
        },
        'available_data_keys': [
            {
                'key': 'stats:summary',
                'desc': '全局汇总（所有年份区域合计）',
                'fields': ['total_discharges', 'total_charges', 'avg_charges', 'avg_costs',
                           'avg_stay_days', 'top_diagnoses', 'top_procedures',
                           'payment_distribution', 'severity_distribution', 'gender_distribution',
                           'race_distribution', 'age_group_distribution', 'emergency_department_ratio',
                           'medical_surgical_distribution']
            },
            {
                'key_pattern': 'stats:year:{year}',
                'desc': '按年份汇总',
                'example': 'stats:year:2021',
                'fields': '同 stats:summary'
            },
            {
                'key_pattern': 'stats:year_region:{year}:{region}',
                'desc': '按年份+服务区域汇总（最详细）',
                'example': 'stats:year_region:2021:Bronx',
                'fields': '同 stats:summary'
            },
            {
                'key_pattern': 'stats:year_county:{year}:{county}',
                'desc': '按年份+县汇总',
                'example': 'stats:year_county:2021:Bronx',
                'fields': '同 stats:summary'
            },
            {
                'key_pattern': 'stats:age_group:{age_group}',
                'desc': '按年龄段全局汇总（跨年）',
                'example': 'stats:age_group:70_or_Older',
                'fields': '同 stats:summary'
            },
        ],
        'field_guide': {
            'total_discharges': '出院人数',
            'total_charges': '总费用',
            'avg_charges': '平均费用',
            'top_diagnoses': 'Top15疾病（含count/avg_charge/avg_stay）',
            'top_procedures': 'Top10手术（含count/avg_charge）',
            'payment_distribution': '支付方式分布（count/total_charge）',
            'severity_distribution': '严重程度分布（Minor/Moderate/Major/Extreme）',
            'risk_distribution': '死亡风险分布',
            'gender_distribution': '性别分布',
            'race_distribution': '种族分布',
            'ethnicity_distribution': '民族分布',
            'age_group_distribution': '年龄段分布',
            'emergency_department_ratio': '急诊入院比例（Y/N）',
            'medical_surgical_distribution': '内科/外科分布',
            'admission_type_distribution': '入院方式分布（Emergency/Elective等）',
            'disposition_distribution': '出院去向分布',
        }
    }
    return catalog


# ==================== 规划阶段 Prompt ====================
PLANNER_PROMPT_TEMPLATE = """你是一个医疗数据检索规划器。根据用户的问题和下方数据目录，决定需要检索哪些数据 key 来回答用户的问题。

【数据目录】
{catalog_json}

【规则】
1. 只返回一个 JSON 数组，包含需要的数据 key 字符串
2. key 必须使用目录中列出的格式（含占位符的要替换为实际值）
3. year 和 region 从用户筛选条件获取
4. 尽量精简：通常 2~4 个 key 足够，不要请求不必要的数据
5. 如果问题是全局性质（不涉及具体年份/区域），只用 stats:summary
6. 常见问题对应：
   - 费用/支付方式 → 需要 payment_distribution + 对应的 year/region 统计
   - 疾病分布 → 需要 top_diagnoses + age_group_distribution
   - 年龄段 → 需要 age_group 统计
   - 严重程度 → 需要 severity_distribution
   - 急诊/入院 → 需要 emergency_department_ratio + admission_type_distribution
   - 手术 → 需要 top_procedures

【用户筛选条件】
- 年份: {year}
- 区域: {region}

【用户问题】
{question}

【输出格式（仅 JSON 数组，无其他文字）】
["stats:year:2021", "stats:year_region:2021:Bronx"]
"""


def planner_llm_call(question, year, region):
    """规划阶段：让 LLM 决定需要检索哪些数据 key。"""
    catalog = _build_catalog()
    catalog_json = json.dumps(catalog, ensure_ascii=False)

    prompt = PLANNER_PROMPT_TEMPLATE.format(
        catalog_json=catalog_json[:3000],  # 限制 catalog 长度
        year=year,
        region=region,
        question=question,
    )

    llm = get_llm()
    try:
        response = llm.invoke(prompt)
        raw = getattr(response, 'content', str(response)).strip()
        # 尝试解析为 JSON 数组
        keys = json.loads(raw)
        if isinstance(keys, list):
            # 清理和验证 key
            valid_keys = []
            for k in keys:
                k = k.strip()
                if k.startswith(AICHAT_KEY_PREFIX):
                    valid_keys.append(k)
                elif k.startswith('stats:'):
                    valid_keys.append(f'{AICHAT_KEY_PREFIX}{k}')
            return valid_keys
    except Exception as e:
        print(f"[aichat] 规划阶段解析失败: {e}, raw: {raw[:200]}")

    # Fallback：返回默认的 year + summary
    return [
        f'{AICHAT_KEY_PREFIX}stats:summary',
        f'{AICHAT_KEY_PREFIX}stats:year:{year}',
    ]


def fetch_data_for_keys(keys):
    """根据 key 列表获取 Redis 数据，返回 {key: data} 字典。"""
    result = {}
    for key in keys:
        data = _cache_get(key, None)
        if data is not None:
            result[key] = data
    return result


def build_prompt_context(year, region, data_keys=None):
    """从 Redis 读取按需获取的统计数据作为 LLM 上下文。
    如果提供 data_keys，则只获取这些 key 的数据；否则使用默认策略。"""
    year_s = str(year)
    region_key = region.replace(' ', '_') if region != 'all' else 'all'
    region_cn_map = {
        'all': '全区域', 'New York City': '纽约市区', 'Finger Lakes': '手指湖区',
        'Southern Tier': '南部地区', 'Long Island': '长岛',
        'Capital/Adirondack': '首府/阿迪朗达克', 'Western NY': '西纽约',
        'Central NY': '中纽约', 'Hudson Valley': '哈德逊河谷',
        'New York City-Long Island': '纽约市-长岛',
    }

    if data_keys:
        # 按需获取模式
        fetched = fetch_data_for_keys(data_keys)
        # 构建上下文：把所有获取到的数据合并成一个紧凑的 JSON
        data_sections = {}
        for key, data in fetched.items():
            # 从 key 中提取可读名称
            short_key = key.replace(AICHAT_KEY_PREFIX, '')
            data_sections[short_key] = data

        summary = data_sections.get('stats:summary', {})
        stats = {}
        for k, v in data_sections.items():
            if k != 'stats:summary' and isinstance(v, dict):
                # 合并非 summary 的数据
                for field in ['top_diagnoses', 'top_procedures', 'payment_distribution',
                             'severity_distribution', 'gender_distribution', 'race_distribution',
                             'age_group_distribution', 'emergency_department_ratio',
                             'medical_surgical_distribution', 'admission_type_distribution',
                             'disposition_distribution']:
                    if field in v and field not in stats:
                        stats[field] = v[field]
                if 'total_discharges' in v and 'total_discharges' not in stats:
                    stats['total_discharges'] = v['total_discharges']
                if 'total_charges' in v and 'total_charges' not in stats:
                    stats['total_charges'] = v['total_charges']
                if 'avg_charges' in v and 'avg_charges' not in stats:
                    stats['avg_charges'] = v['avg_charges']
                if 'avg_stay_days' in v and 'avg_stay_days' not in stats:
                    stats['avg_stay_days'] = v['avg_stay_days']

        # 各年龄段汇总
        age_group_stats = {}
        if 'stats:summary' in data_sections:
            meta = _cache_get(f'{AICHAT_KEY_PREFIX}meta', {})
            for ag in meta.get('age_groups', []):
                ag_key = ag.replace(' ', '_').replace('/', '_')
                ag_data = _cache_get(f'{AICHAT_KEY_PREFIX}stats:age_group:{ag_key}', None)
                if ag_data:
                    age_group_stats[ag] = {
                        'total': ag_data.get('total_discharges', 0),
                        'avg_charge': ag_data.get('avg_charges', 0),
                        'top_diseases': [d['desc'] for d in ag_data.get('top_diagnoses', [])[:5]],
                    }
    else:
        # 默认模式（向后兼容）
        summary = _cache_get(f'{AICHAT_KEY_PREFIX}stats:summary', {})
        if region == 'all':
            stats = _cache_get(f'{AICHAT_KEY_PREFIX}stats:year:{year_s}', {})
        else:
            stats = _cache_get(f'{AICHAT_KEY_PREFIX}stats:year_region:{year_s}:{region_key}', {})
        age_group_stats = {}
        meta = _cache_get(f'{AICHAT_KEY_PREFIX}meta', {})
        for ag in meta.get('age_groups', []):
            ag_key = ag.replace(' ', '_').replace('/', '_')
            ag_data = _cache_get(f'{AICHAT_KEY_PREFIX}stats:age_group:{ag_key}', None)
            if ag_data:
                age_group_stats[ag] = {
                    'total': ag_data.get('total_discharges', 0),
                    'avg_charge': ag_data.get('avg_charges', 0),
                    'top_diseases': [d['desc'] for d in ag_data.get('top_diagnoses', [])[:5]],
                }

    return {
        'year': year_s,
        'region': region,
        'region_cn': region_cn_map.get(region, region),
        'summary_json': json.dumps(summary, ensure_ascii=False)[:4000],
        'stats_json': json.dumps(stats, ensure_ascii=False)[:6000],
        'age_group_stats_json': json.dumps(age_group_stats, ensure_ascii=False)[:3000],
    }


# ==================== LangChain 调用核心 ====================
def _build_chain_and_inputs(message, year, region, chat_id, data_keys=None):
    """构造 Prompt 模板 + chain + 输入变量（同步/流式共用）。
    data_keys: 如果提供，使用按需获取的数据；否则使用默认模式。"""
    llm = get_llm()
    ctx = build_prompt_context(year, region, data_keys=data_keys)
    prompt = ChatPromptTemplate.from_messages([
        ('system', SYSTEM_PROMPT_TEMPLATE),
        MessagesPlaceholder(variable_name='history', optional=True),
        ('human', '{question}'),
    ])
    history_msgs = history_to_langchain(get_messages(chat_id, limit=20)[:-1])
    chain = prompt | llm
    inputs = {
        'year': ctx['year'],
        'region': ctx['region'],
        'region_cn': ctx['region_cn'],
        'summary_json': ctx['summary_json'],
        'stats_json': ctx['stats_json'],
        'age_group_stats_json': ctx['age_group_stats_json'],
        'history': history_msgs,
        'question': message,
    }
    return chain, inputs


def llm_generate(message, year, region, chat_id, data_keys=None):
    """
    使用 LangChain 同步生成医疗分析回答。
    返回 parts 列表: [{type:'text', content}, {type:'chart', chartType, option}, ...]
    """
    chain, inputs = _build_chain_and_inputs(message, year, region, chat_id, data_keys=data_keys)
    response = chain.invoke(inputs)
    raw_text = getattr(response, 'content', str(response))
    return parse_llm_output(raw_text)


def llm_stream_generate(message, year, region, chat_id, data_keys=None):
    """
    LangChain 流式生成，生成器每次 yield 增量 token 字符串（delta）。
    """
    chain, inputs = _build_chain_and_inputs(message, year, region, chat_id, data_keys=data_keys)
    for chunk in chain.stream(inputs):
        delta = getattr(chunk, 'content', '') or ''
        if delta:
            yield delta


def _extract_json_body(text, open_char='[', close_char=']'):
    """从任意文本中用"括号配对法"抽取最外层 JSON 主体（数组或对象）。
    优先查找 open_char（默认 '[' 数组）；若没找到则回退到 '{' 对象。
    返回 (substr_or_None, did_fallback_to_object)。"""
    if not text:
        return None, False
    # 先按数组找
    first = text.find(open_char)
    if first < 0:
        if open_char == '[':
            return _extract_json_body(text, '{', '}')
        return None, False
    depth = 0
    in_str = False
    esc = False
    in_sq_str = False  # ECharts/JS 风格的单引号字符串
    end = -1
    for i in range(first, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if in_sq_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == "'":
                in_sq_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "'" and open_char == '{':
            # 仅在对象搜索时容忍单引号字符串（JS 对象 key/value）
            in_sq_str = True
        elif ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0:
        # 数组没配对，尝试对象
        if open_char == '[':
            return _extract_json_body(text, '{', '}')
        return None, False
    return text[first:end + 1], (open_char == '{')


def _strip_js_comments(s):
    """移除 JSON 候选串中的 JS 风格 // 行注释 与 /* */ 块注释（字符串内豁免）。"""
    if not s:
        return s
    out = []
    i = 0
    n = len(s)
    in_str = False
    str_ch = ''
    esc = False
    while i < n:
        ch = s[i]
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == str_ch:
                in_str = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = True
            str_ch = ch
            out.append(ch)
            i += 1
            continue
        # 行注释
        if ch == '/' and i + 1 < n and s[i + 1] == '/':
            j = s.find('\n', i + 2)
            if j < 0:
                break  # 注释到结尾，全丢
            i = j
            continue
        # 块注释
        if ch == '/' and i + 1 < n and s[i + 1] == '*':
            j = s.find('*/', i + 2)
            if j < 0:
                break
            i = j + 2
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _remove_trailing_commas(s):
    """移除最后一个 ], } 之前多余的逗号（JS 对象里合法，JSON 里非法）。"""
    if not s:
        return s
    out = []
    i = 0
    n = len(s)
    in_str = False
    str_ch = ''
    esc = False
    while i < n:
        ch = s[i]
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == str_ch:
                in_str = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = True
            str_ch = ch
            out.append(ch)
            i += 1
            continue
        if ch == ',':
            # 向后扫描（跳过空白/注释字符）看是否紧跟 ] 或 }
            k = i + 1
            while k < n and s[k] in ' \t\r\n':
                k += 1
            if k < n and s[k] in (']', '}'):
                # 跳过这个逗号
                i += 1
                continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _normalize_js_literals(s):
    """把 undefined / NaN / Infinity 这类 JS 字面量替换成 JSON 合法值。
    注意：必须在字符串外匹配。"""
    if not s:
        return s
    out = []
    i = 0
    n = len(s)
    in_str = False
    str_ch = ''
    esc = False
    # 匹配整词：前面不能是 [A-Za-z0-9_$]，后面不能是 [A-Za-z0-9_$]
    word_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$')
    literals = {
        'undefined': 'null',
        'NaN': 'null',
        'Infinity': '1e999',
        '-Infinity': '-1e999',
        '+Infinity': '1e999',
        'True': 'true',
        'False': 'false',
        'None': 'null',
    }
    while i < n:
        ch = s[i]
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == str_ch:
                in_str = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = True
            str_ch = ch
            out.append(ch)
            i += 1
            continue
        # 尝试匹配字面量
        matched = None
        for lit in sorted(literals.keys(), key=len, reverse=True):
            if s.startswith(lit, i):
                prev_ok = (i == 0) or (s[i - 1] not in word_chars)
                end = i + len(lit)
                next_ok = (end == n) or (s[end] not in word_chars)
                if prev_ok and next_ok:
                    matched = lit
                    break
        if matched:
            out.append(literals[matched])
            i += len(matched)
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _single_quote_to_double(s):
    """把 JS 风格的单引号 JSON 转成标准双引号（仅当整体看上去是单引号 JSON 时）。
    实现：非字符串内的单引号字符串边界 → 换双引号；字符串内的双引号自动加转义。"""
    if not s:
        return s
    out = []
    i = 0
    n = len(s)
    in_str = False
    str_ch = ''
    esc = False
    while i < n:
        ch = s[i]
        if in_str:
            if esc:
                out.append(ch)
                esc = False
                i += 1
                continue
            if ch == '\\':
                out.append(ch)
                esc = True
                i += 1
                continue
            if ch == str_ch:
                # 结束字符串
                out.append('"' if str_ch == "'" else '"')
                in_str = False
                i += 1
                continue
            if str_ch == "'" and ch == '"':
                # 单引号串里有双引号 → 转义
                out.append('\\"')
                i += 1
                continue
            out.append(ch)
            i += 1
            continue
        if ch == "'":
            in_str = True
            str_ch = "'"
            out.append('"')
            i += 1
            continue
        if ch == '"':
            in_str = True
            str_ch = '"'
            out.append('"')
            i += 1
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _strip_js_functions(s):
    """把 JSON 字符串里的 function(params) { ... } 替换成占位符 "__FUNC_N__"。
    返回 (修复后的字符串, {占位符: 原始函数源码})。
    ECharts 的 itemStyle.color / label.formatter 等字段常用 JS 函数，json.loads 无法解析。"""
    if not s:
        return s, {}
    out = []
    i = 0
    n = len(s)
    placeholders = {}
    func_idx = 0
    while i < n:
        ch = s[i]
        # 跳过字符串内内容
        if ch in ('"', "'"):
            quote = ch
            out.append(ch)
            i += 1
            while i < n:
                c = s[i]
                out.append(c)
                if c == '\\' and i + 1 < n:
                    out.append(s[i + 1])
                    i += 2
                    continue
                if c == quote:
                    i += 1
                    break
                i += 1
            continue
        # 检测 function 关键字
        if s.startswith('function', i):
            # 检查前面是否是冒号或逗号或空白（即这是 JSON 值的位置）
            before = s[max(0, i - 5):i]
            if re.search(r'[:,\s]\s*$', before) or i == 0:
                # 找到 function(...) { 的 {
                j = i + 8  # len('function')
                while j < n and s[j] != '{':
                    j += 1
                if j < n:
                    # 从 { 开始找配对的 }
                    depth = 0
                    k = j
                    in_str = False
                    str_ch = ''
                    esc = False
                    while k < n:
                        c = s[k]
                        if in_str:
                            if esc:
                                esc = False
                            elif c == '\\':
                                esc = True
                            elif c == str_ch:
                                in_str = False
                            k += 1
                            continue
                        if c in ('"', "'"):
                            in_str = True
                            str_ch = c
                            k += 1
                            continue
                        if c == '{':
                            depth += 1
                        elif c == '}':
                            depth -= 1
                            if depth == 0:
                                k += 1
                                break
                        k += 1
                    func_code = s[i:k]
                    placeholder = f'__FUNC_{func_idx}__'
                    placeholders[placeholder] = func_code
                    out.append(f'"{placeholder}"')
                    func_idx += 1
                    i = k
                    continue
        out.append(ch)
        i += 1
    return ''.join(out), placeholders


def _repair_json_candidate(candidate):
    """对提取出的"疑似 JSON 字符串"做常见 JS→JSON 兼容修复，返回 (修复后字符串, 函数占位映射)。"""
    if not candidate:
        return candidate, {}
    s = candidate
    # 先剥离 JS 函数（在注释和字符串修复之前）
    s, func_map = _strip_js_functions(s)
    s = _strip_js_comments(s)
    # 若整体单引号多（对象/数组的 key/value），先转双引号
    if s.count("'") > s.count('"') // 2 and s.count("'") > 0:
        s = _single_quote_to_double(s)
    s = _remove_trailing_commas(s)
    s = _normalize_js_literals(s)
    return s, func_map


def parse_llm_output(text):
    """解析 LLM 输出为 parts 列表（双通道：严格 → lenient 修复）。"""
    if not text:
        return [{'type': 'text', 'content': '抱歉，AI 未返回有效内容，请重试。'}]

    # 阶段 A：直接按 Markdown ```json 围栏提取
    json_str = None
    for fence_re in (
        r'```\s*json\s*\n?([\s\S]*?)\n?\s*```',  # ```json ... ```
        r'```\s*JSON\s*\n?([\s\S]*?)\n?\s*```',
        r'```\s*\n?([\s\S]*?)\n?\s*```',           # ``` ... ``` （无语言标记）
    ):
        m = re.search(fence_re, text)
        if m:
            json_str = m.group(1).strip()
            break

    # 阶段 B：括号配对找主体（兼容 [ ... ] 数组；数组找不着再回退 { ... }）
    if json_str is None:
        extracted, is_obj = _extract_json_body(text)
        if extracted:
            json_str = extracted
        else:
            # 连括号都没配成对，那肯定不是合法 JSON，直接走文本兜底
            safe = text.strip()
            if safe:
                return [{'type': 'text', 'content': safe}]
            return [{'type': 'text', 'content': 'AI 返回内容解析失败，请重试。'}]

    # 阶段 1：严格 json.loads
    cleaned, func_map = _try_parse_as_parts(json_str)
    if cleaned is not None:
        return cleaned

    # 阶段 2：对候选串做 JSON 兼容性修复后再解析
    repaired, func_map = _repair_json_candidate(json_str)
    cleaned, func_map2 = _try_parse_as_parts(repaired, func_map)
    if cleaned is not None:
        return cleaned

    # 阶段 3：修复失败，对原文括号配对主体 + 修复再试
    alt, _ = _extract_json_body(text)
    if alt and alt != json_str:
        repaired2, func_map3 = _repair_json_candidate(alt)
        cleaned, func_map4 = _try_parse_as_parts(repaired2, func_map3)
        if cleaned is not None:
            return cleaned

    # 阶段 4：仍然失败 —— 把原文当文本回答，附加友好的解析失败原因
    ctx = json_str if len(json_str) <= 500 else json_str[:250] + '\n...(省略中间)...\n' + json_str[-250:]
    print(f"[aichat] LLM 输出 JSON 解析最终失败，片段如下：\n{ctx}\n")
    fallback_parts = [
        {'type': 'text', 'content': text.strip() if text.strip() else 'AI 返回内容解析失败，请重试。'}
    ]
    return fallback_parts


def _try_parse_as_parts(json_str, func_map=None):
    """尝试把 json_str 解析为 parts 列表。成功返回 (cleaned parts, func_map)；失败返回 (None, func_map)。
    func_map: {占位符: 原始函数源码}，用于把 JSON 中的 __FUNC_N__ 占位符还原为函数源码。
    兼容两种 LLM 输出形态：
      (a) 顶层是数组（如 [{type:'text'..}, {type:'chart'..}]）—— 直接用
      (b) 顶层是对象（如 {parts:[..]} 或 {answer:[..]} 或单一个 {type:'chart'..}）—— 提取数组/包成单元素"""
    if func_map is None:
        func_map = {}
    if not json_str:
        return None, func_map
    try:
        data = json.loads(json_str)
    except Exception as e:
        # 再尝试 JSONDecoder.raw_decode 从任意位置解
        try:
            data, _ = json.JSONDecoder().raw_decode(json_str.lstrip())
        except Exception:
            print(f"[aichat] JSON 解析（严格）失败: {e}")
            return None, func_map

    items = None
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        # 常见外壳键：parts / answer / data / result / messages / output
        for k in ('parts', 'answer', 'data', 'result', 'messages', 'output', 'segments', 'content'):
            v = data.get(k)
            if isinstance(v, list):
                items = v
                break
        if items is None:
            # 单一个对象片段（如直接返回了一个 type:'chart'），包成 [obj]
            if data.get('type') in ('text', 'chart'):
                items = [data]
    if items is None:
        print(f"[aichat] JSON 解析成功但结构不是 parts 列表，顶层类型={type(data).__name__}")
        return None, func_map

    def _restore_funcs(obj):
        """递归遍历 dict/list，把 __FUNC_N__ 字符串替换为带 __func__ 标记的 dict。"""
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if isinstance(v, str) and v in func_map:
                    # 替换为特殊标记，前端识别 __func__ 转为真实 JS 函数
                    result[k] = {'__func__': func_map[v]}
                else:
                    result[k] = _restore_funcs(v)
            return result
        elif isinstance(obj, list):
            return [_restore_funcs(item) for item in obj]
        return obj

    cleaned = []
    for p in items:
        if not isinstance(p, dict):
            continue
        if p.get('type') == 'text' and isinstance(p.get('content'), str):
            cleaned.append({'type': 'text', 'content': p['content']})
        elif p.get('type') == 'chart' and isinstance(p.get('option'), dict):
            # 还原函数占位符
            option = _restore_funcs(p['option'])
            cleaned.append({
                'type': 'chart',
                'chartType': p.get('chartType') or p.get('chart_type') or 'bar',
                'option': option,
            })
    if cleaned:
        return cleaned, func_map
    return None, func_map


# ==================== 路由 ====================
@aichat_bp.route('/suggested', methods=['GET'])
def api_suggested():
    """推荐问题（Redis 预构建缓存）"""
    data = _cache_get(f'{AICHAT_KEY_PREFIX}suggested', [
        {'id': 'q1', 'text': '按支付方式统计总费用'},
        {'id': 'q2', 'text': 'Bronx区急诊患者画像'},
        {'id': 'q3', 'text': '各年度KPI费用趋势分析'},
        {'id': 'q4', 'text': '各科室平均住院天数对比'},
        {'id': 'q5', 'text': '70岁以上人群疾病分布'},
        {'id': 'q6', 'text': '不同区域住院费用对比'},
    ])
    return ok(data)


@aichat_bp.route('/history', methods=['GET'])
def api_history():
    """历史对话列表"""
    convs = get_conversation_list()
    result = [
        {
            'id': c.get('id'),
            'title': c.get('title', '新对话'),
            'time': c.get('updatedAt', ''),
        } for c in convs
    ]
    return ok(result)


@aichat_bp.route('/messages/<chat_id>', methods=['GET'])
def api_messages(chat_id):
    """拉取指定会话的全部消息（用于历史会话切换时恢复聊天记录）"""
    msgs = get_messages(chat_id, limit=200)
    # 转成前端 messages 数组格式
    result = []
    for m in msgs:
        if m.get('role') == 'user':
            result.append({'role': 'user', 'content': m.get('content', '')})
        elif m.get('role') == 'assistant':
            parts = m.get('parts') or []
            result.append({'role': 'assistant', 'parts': parts})
    return ok(result)


@aichat_bp.route('/chat/<chat_id>', methods=['DELETE'])
def api_delete_chat(chat_id):
    """删除指定会话（元数据 + 消息历史）"""
    try:
        r.hdel(f'{AICHAT_KEY_PREFIX}conv:list', chat_id)
        r.delete(f'{AICHAT_KEY_PREFIX}conv:msgs:{chat_id}')
    except Exception as e:
        print(f"[aichat] 删除会话失败 {chat_id}: {e}")
        return err(f'删除失败: {e}')
    return ok({'chatId': chat_id, 'deleted': True})


@aichat_bp.route('/chat/<chat_id>/rename', methods=['POST'])
def api_rename_chat(chat_id):
    """重命名会话标题"""
    body = request.get_json(silent=True) or {}
    new_title = (body.get('title') or '').strip()
    if not new_title:
        return err('标题不能为空')
    meta = save_conversation_meta(chat_id, new_title, first_message=False)
    return ok({'chatId': chat_id, 'title': meta.get('title', new_title)})


@aichat_bp.route('/chat/new', methods=['POST'])
def api_new_chat():
    """新建空会话，返回 chatId"""
    chat_id = 'c_' + uuid.uuid4().hex[:10]
    title = (request.get_json(silent=True) or {}).get('title') or '新对话'
    save_conversation_meta(chat_id, title, first_message=False)
    return ok({'chatId': chat_id, 'title': title})


@aichat_bp.route('/chat', methods=['POST'])
def api_chat():
    """
    发送消息（LangChain 生成）
    Body: { message, year, region, chatId }
    响应: {code:200, data:[ {type:'text', content}, {type:'chart', chartType, option}, ... ]}
    """
    body = request.get_json(silent=True) or {}
    message = (body.get('message') or '').strip()
    year = body.get('year') or '2021'
    region = body.get('region') or 'all'
    chat_id = body.get('chatId') or ('c_' + uuid.uuid4().hex[:10])

    if not message:
        return err('消息不能为空')

    # 1. 用户消息写入会话
    append_message(chat_id, 'user', content=message)

    # 2. 生成标题（首条消息截取前 20 字）
    convs = get_conversation_list()
    existing_ids = {c.get('id') for c in convs}
    is_first = chat_id not in existing_ids
    title = (message[:20] + ('…' if len(message) > 20 else '')) if is_first else None
    save_conversation_meta(chat_id, title, first_message=True)

    # 3. 调用 LangChain 生成
    try:
        parts = llm_generate(message, year, region, chat_id)
    except Exception as e:
        print(f"[aichat] LangChain 调用失败: {e}")
        parts = _build_llm_error_parts(e)

    # 4. AI 回复写入会话
    append_message(chat_id, 'assistant', parts=parts)
    return ok(parts)


# ---------- SSE 流式对话（delta 增量 + 最终 done 返回完整 parts） ----------
def _sse_event(event, **payload):
    """构造 SSE 单行事件文本：data: <json>\n\n"""
    payload['event'] = event
    try:
        body = json.dumps(payload, ensure_ascii=False)
    except Exception:
        body = json.dumps({'event': event, 'message': 'json encode error'}, ensure_ascii=False)
    return f'data: {body}\n\n'


def _build_llm_error_parts(exc):
    # 安全的 Key 脱敏：只显示前 6 位 + 长度，避免 Key 短时切片崩
    if LLM_API_KEY:
        key_disp = f'{LLM_API_KEY[:6]}...(len={len(LLM_API_KEY)})'
    else:
        key_disp = '(未设置)'
    return [{
        'type': 'text',
        'content': (
            f'⚠️ AI 服务调用失败：{str(exc)}\n\n'
            '【排查建议】\n'
            f'1. backend/.env 中 LLM_PROVIDER={LLM_PROVIDER} 对应一组是否取消注释并填入了 API Key\n'
            f'2. 当前：{_key_env}={key_disp}\n'
            f'3. 已装依赖：pip install langchain langchain-core langchain-openai python-dotenv\n'
            f'4. 网络：{LLM_API_BASE or "(默认 OpenAI 官方)"}'
        ),
    }]


@aichat_bp.route('/chat/stream', methods=['POST'])
def api_chat_stream():
    """
    SSE 流式发送消息（两阶段智能数据检索 + LangChain 流式生成）。

    阶段 1（规划）：LLM 根据用户问题决定需要哪些数据 key → 只获取这些数据
    阶段 2（分析）：用获取到的数据作为上下文，流式生成回答

    事件流协议：
      event=delta  { text: "<增量token>" }          → 前端打字机效果
      event=planning_done  { keys: [...] }          → 规划完成（调试用）
      event=done   { parts: [...] , chatId: "..." } → 最终 parts
      event=error  { message: "..." }
    """
    body = request.get_json(silent=True) or {}
    message = (body.get('message') or '').strip()
    year = body.get('year') or '2021'
    region = body.get('region') or 'all'
    chat_id = body.get('chatId') or ('c_' + uuid.uuid4().hex[:10])

    def generate():
        if not message:
            yield _sse_event('error', message='消息不能为空')
            return

        # 1. 用户消息落库 + 会话标题
        append_message(chat_id, 'user', content=message)
        convs = get_conversation_list()
        existing_ids = {c.get('id') for c in convs}
        is_first = chat_id not in existing_ids
        title = (message[:20] + ('…' if len(message) > 20 else '')) if is_first else None
        save_conversation_meta(chat_id, title, first_message=True)

        # 2. 阶段 1：智能数据检索规划
        data_keys = None
        try:
            print(f"[aichat] 规划阶段：year={year}, region={region}, question={message[:50]}")
            data_keys = planner_llm_call(message, year, region)
            print(f"[aichat] 规划完成，需要 {len(data_keys)} 个数据 key: {data_keys}")
            yield _sse_event('planning_done', keys=data_keys)
        except Exception as e:
            print(f"[aichat] 规划阶段失败（降级到默认数据）: {e}")
            data_keys = None

        # 3. 阶段 2：流式生成回答
        full_buf = []
        parts = None
        try:
            for delta in llm_stream_generate(message, year, region, chat_id, data_keys=data_keys):
                full_buf.append(delta)
                yield _sse_event('delta', text=delta)
            full_text = ''.join(full_buf)
            parts = parse_llm_output(full_text)
        except Exception as e:
            print(f"[aichat] 流式 LangChain 调用失败: {e}")
            parts = _build_llm_error_parts(e)

        # 4. AI 回复落库
        try:
            append_message(chat_id, 'assistant', parts=parts)
        except Exception as e:
            print(f"[aichat] 流式结果写入 Redis 失败: {e}")

        # 5. 发送最终 done 事件
        yield _sse_event('done', parts=parts, chatId=chat_id)

    # Flask Response
    from flask import Response
    resp = Response(generate(), mimetype='text/event-stream; charset=utf-8')
    resp.headers['Cache-Control'] = 'no-cache, no-transform'
    resp.headers['X-Accel-Buffering'] = 'no'
    resp.headers['Connection'] = 'keep-alive'
    return resp


# ==================== 注册到 Flask app ====================
def register_routes(app):
    """供 app.py 在末尾调用，挂载 aichat Blueprint"""
    try:
        r.ping()
        meta = _cache_get(f'{AICHAT_KEY_PREFIX}meta', None)
        if meta:
            print(f"[🤖] AI智能探索舱 路由已注册，Redis 预构建存在：{meta}")
        else:
            print("[⚠️] AI智能探索舱 路由已注册，但未找到预构建缓存。建议先运行：")
            print("     python ../data/build_aichat_cache.py")
        # LLM 配置状态检查
        if LLM_API_KEY:
            print(f"[✅] LangChain LLM 已配置：provider={LLM_PROVIDER}, model={LLM_MODEL}")
            if LLM_API_BASE:
                print(f"     api_base={LLM_API_BASE}")
        else:
            print(f"[⚠️] LangChain LLM 未配置 API Key（provider={LLM_PROVIDER}）")
            print(f"     请在 backend/.env 中取消 {_key_env} 对应一组的注释并填入 API Key")
    except Exception as e:
        print(f"[⚠️] AI智能探索舱 Redis 连接异常：{e}")
    app.register_blueprint(aichat_bp)
