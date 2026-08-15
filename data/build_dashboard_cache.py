# -*- coding: utf-8 -*-
"""
智慧医疗分析平台 - Dashboard 数据预构建脚本
============================================
功能：
    读取 Hospital.xlsx，计算所有维度组合（年份×区域×年龄段）的 4 类聚合数据，
    一次性写入 Redis 缓存。后续 Flask 接口只需要命中 Redis，无需重复计算。

缓存 Key 设计（前缀 smartmed:dashboard:）：
    kpi:{year}:{region}                          KPI 4项指标
    agegroup:{year}:{region}                     5个年龄段分布
    topdiseases:{year}:{region}:{ageGroup}       Top10昂贵疾病（ageGroup=all 为全年龄）
    deptcompare:{year}:{region}                  科室对比 3 指标

运行方式：
    python data/build_dashboard_cache.py
"""

import os
import sys
import json
import math
import random
import numpy as np
import pandas as pd

try:
    import redis
except ImportError:
    print("[错误] 缺少 redis 依赖，请先安装: pip install redis pandas openpyxl")
    sys.exit(1)

# ============ 配置 ============
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# 数据文件路径（自动识别 .csv / .xlsx / .xls）
DATA_PATH = r'D:\project\Hwadee\bigdata_pro\cleaned_hospital_data.csv'

# 读取行数限制：设为 None 读全量，设为数字只读前 N 行（测试用）
MAX_ROWS = None  # 先用前10万条测试，验证没问题后改成 None 跑全量

REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
KEY_PREFIX = 'smartmed:dashboard:'

# 只读取需要的列（32列中只读8列，省75%内存）
USE_COLS = [
    'Hospital County',
    'Age Group',
    'Length of Stay',
    'Total Charges',
    'Total Costs',
    'APR MDC Description',
    'CCSR Diagnosis Description',
    'Discharge Year',
]
# 只指定数值列的 dtype（字符串列让 pyarrow 自动处理，避免兼容性问题）
DTYPE_MAP = {
    'Discharge Year': 'int16',
}

# 年份和地区不再写死：从 Excel 的 Discharge Year / Hospital County 列动态读取
# Hospital County -> 前端 region value 映射
COUNTY_TO_REGION = {
    'Bronx': 'Bronx',
    'Manhattan': 'Manhattan',
    'Kings': 'Brooklyn',       # Kings County = Brooklyn
    'Queens': 'Queens',
    'Richmond': 'Staten Island',  # Richmond County = Staten Island
}

AGE_GROUP_EN_TO_CN = {
    '0 to 17':      '0-17岁',
    '18 to 29':     '18-29岁',
    '30 to 49':     '30-49岁',
    '50 to 69':     '50-69岁',
    '70 or Older':  '70岁以上',
}
AGE_GROUP_ORDER = ['0-17岁', '18-29岁', '30-49岁', '50-69岁', '70岁以上']

# APR MDC -> 中文科室（只取前8大科室用于对比图）
MDC_TO_DEPT = {
    'DISEASES AND DISORDERS OF THE CIRCULATORY SYSTEM':     '心内科',
    'DISEASES AND DISORDERS OF THE RESPIRATORY SYSTEM':     '呼吸科',
    'DISEASES AND DISORDERS OF THE NERVOUS SYSTEM':         '神经科',
    'DISEASES AND DISORDERS OF THE DIGESTIVE SYSTEM':       '消化科',
    'PREGNANCY, CHILDBIRTH AND THE PUERPERIUM':             '妇产科',
    'NEWBORNS AND OTHER NEONATES WITH CONDITIONS ORIGINATING IN THE PERINATAL PERIOD': '新生儿科',
    'INFECTIOUS AND PARASITIC DISEASES (SYSTEMIC OR UNSPECIFIED SITES)': '感染科',
    'DISEASES AND DISORDERS OF THE MUSCULOSKELETAL SYSTEM AND CONNECTIVE TISSUE': '骨科',
    'ENDOCRINE, NUTRITIONAL AND METABOLIC DISEASES AND DISORDERS': '内分泌科',
    'ALCOHOL/DRUG USE AND ALCOHOL/DRUG INDUCED ORGANIC MENTAL DISORDERS': '精神科',
    'MYELOPROLIFERATIVE DISEASES AND DISORDERS, AND POORLY DIFFERENTIATED NEOPLASM': '肿瘤科',
    'DISEASES AND DISORDERS OF THE MALE REPRODUCTIVE SYSTEM': '泌尿科',
    'INJURIES, POISONINGS AND TOXIC EFFECTS OF DRUGS':      '急诊科',
    'HUMAN IMMUNODEFICIENCY VIRUS INFECTIONS':              '感染科',
}

random.seed(42)
np.random.seed(42)

# CCSR 诊断描述 英文 → 中文 映射表
# 说明：覆盖常见高频诊断；映射不到的保留英文原名（保证不丢数据）
DIAGNOSIS_CN_MAP = {
    # —— 心血管 / 循环系统 ——
    'HEART FAILURE': '心力衰竭',
    'CORONARY ATHEROSCLEROSIS': '冠状动脉粥样硬化',
    'ACUTE MYOCARDIAL INFARCTION': '急性心肌梗死',
    'CARDIAC ARRHYTHMIAS': '心律失常',
    'CARDIAC ARREST': '心脏骤停',
    'CEREBRAL INFARCTION': '脑梗死',
    'HYPERTENSION AND HYPERTENSIVE-RELATED CONDITIONS COMPLICATING PREGNANCY; CHILDBIRTH; AND THE PUERPERIUM': '妊娠相关高血压',
    'TRANSIENT CEREBRAL ISCHEMIA': '短暂性脑缺血发作',
    'PERIPHERAL AND VISCERAL ATHEROSCLEROSIS': '外周及内脏动脉粥样硬化',
    'CONDUCTION DISORDERS': '心脏传导障碍',
    # —— 呼吸系统 ——
    'PNEUMONIA': '肺炎',
    'CHRONIC OBSTRUCTIVE PULMONARY DISEASE AND BRONCHIECTASIS': '慢性阻塞性肺疾病',
    'ASTHMA': '哮喘',
    'ACUTE BRONCHITIS': '急性支气管炎',
    'RESPIRATORY FAILURE; INSUFFICIENCY; ARREST (ADULT)': '呼吸衰竭',
    'CORONAVIRUS DISEASE 2019 (COVID-19)': '新冠肺炎',
    'INFLUENZA': '流行性感冒',
    'PLEURAL EFFUSION AND PNEUMOTHORAX': '胸腔积液与气胸',
    # —— 感染 / 败血症 ——
    'SEPTICEMIA': '败血症',
    'URINARY TRACT INFECTIONS': '尿路感染',
    'GANGRENE': '坏疽',
    'CELLULITIS AND OTHER SKIN INFECTIONS': '蜂窝织炎与皮肤感染',
    'OTHER SPECIFIED AND UNSPECIFIED INFECTIONS': '其他感染',
    # —— 消化系统 ——
    'OTHER SPECIFIED AND UNSPECIFIED GASTROINTESTINAL DISORDERS': '其他胃肠道疾病',
    'GASTROINTESTINAL HEMORRHAGE': '消化道出血',
    'ACUTE PANCREATITIS': '急性胰腺炎',
    'CHOLELITHIASIS': '胆结石',
    'BILIARY TRACT DISEASE': '胆道疾病',
    'INTESTINAL OBSTRUCTION WITHOUT HERNIA': '肠梗阻',
    'APPENDICITIS': '阑尾炎',
    'ESOPHAGITIS': '食管炎',
    'GASTRITIS AND DUODENITIS': '胃炎与十二指肠炎',
    'NONINFECTIOUS GASTROENTERITIS': '非感染性胃肠炎',
    'LIVER DISEASES': '肝脏疾病',
    # —— 神经系统 ——
    'EPILEPSY; CONVULSIONS': '癫痫与惊厥',
    'OTHER SPECIFIED AND UNSPECIFIED CEREBROVASCULAR DISEASE': '其他脑血管疾病',
    'MULTIPLE SCLEROSIS, OTHER DEMYELINATING DISEASE': '多发性硬化',
    'PARKINSON\'S DISEASE': '帕金森病',
    'HEADACHE; INCLUDING MIGRAINE': '头痛（含偏头痛）',
    # —— 内分泌 / 代谢 ——
    'DIABETES MELLITUS WITH COMPLICATION': '糖尿病伴并发症',
    'DIABETES MELLITUS WITHOUT COMPLICATION': '糖尿病不伴并发症',
    'DISORDERS OF FLUID; ELECTROLYTE; AND ACID-BASE BALANCE': '水电解质酸碱平衡紊乱',
    'NUTRITIONAL; ENDOCRINE; AND METABOLIC DISORDERS': '营养内分泌代谢障碍',
    # —— 肾 / 泌尿 ——
    'ACUTE RENAL FAILURE': '急性肾功能衰竭',
    'CHRONIC KIDNEY DISEASE': '慢性肾脏疾病',
    'URINARY CALCULI': '泌尿系结石',
    'BENIGN PROSTATIC HYPERPLASIA': '前列腺良性增生',
    # —— 血液 / 肿瘤 ——
    'ANEMIA': '贫血',
    'ACUTE POSTHEMORRHAGIC ANEMIA': '急性失血性贫血',
    'ENCOUNTER FOR ANTINEOPLASTIC THERAPIES': '抗肿瘤治疗',
    'OTHER SCREENING AND EXAMINATION OF NEOPLASMS': '肿瘤筛查',
    # —— 肌骨系统 ——
    'FRACTURE OF TORSO, INITIAL ENCOUNTER': '躯干骨折',
    'PATHOLOGIC FRACTURES': '病理性骨折',
    'OSTEOARTHRITIS': '骨关节炎',
    'SPRAINS; STRAINS; AND DISLOCATIONS EXCEPT HEEL': '扭伤脱位',
    'PATHOLOGY OF BONES AND JOINTS': '骨关节病变',
    # —— 产科 / 新生儿 ——
    'LIVEBORN': '活产新生儿',
    'PREVIOUS C-SECTION': '剖宫产史',
    'COMPLICATIONS SPECIFIED DURING CHILDBIRTH': '分娩并发症',
    'POSTPARTUM HEMORRHAGE': '产后出血',
    'PRETERM LABOR': '早产临产',
    'HYPERTENSION AND HYPERTENSIVE-RELATED CONDITIONS COMPLICATING PREGNANCY; CHILDBIRTH; AND THE PUERPERIUM': '妊娠高血压',
    # —— 精神 / 行为 ——
    'ALCOHOL-RELATED DISORDERS': '酒精相关障碍',
    'SUBSTANCE-RELATED DISORDERS': '物质相关障碍',
    'SCHIZOPHRENIA SPECTRUM AND OTHER PSYCHOTIC DISORDERS': '精神分裂症谱系',
    'MOOD DISORDERS': '心境障碍',
    'ANXIETY; SOMATOFORM; DISSOCIATIVE; AND PERSONALITY DISORDERS': '焦虑等人格障碍',
    # —— 创伤 / 中毒 ——
    'INJURIES AND POISONINGS': '损伤与中毒',
    'POISONING BY NONOPIOID AND OTHER DRUGS': '非阿片类药物中毒',
    # —— 其他系统 ——
    'HIV INFECTION': 'HIV感染',
    'OTHER SPECIFIED AND UNSPECIFIED CIRCULATORY DISEASES': '其他循环系统疾病',
    'OTHER SPECIFIED AND UNSPECIFIED RESPIRATORY DISEASES': '其他呼吸系统疾病',
    'OTHER SPECIFIED AND UNSPECIFIED NERVOUS SYSTEM DISORDERS': '其他神经系统疾病',
    'OTHER SPECIFIED AND UNSPECIFIED GENITOURINARY DISORDERS': '其他泌尿生殖疾病',
}


def translate_diagnosis(en_name):
    """英文病名 → 中文；映射不到则按关键词模糊匹配，仍匹配不到则归为'其他疾病'"""
    if not en_name:
        return en_name
    name = str(en_name).strip()
    # 1. 精确匹配
    if name in DIAGNOSIS_CN_MAP:
        return DIAGNOSIS_CN_MAP[name]
    # 2. 关键词模糊匹配（包含即命中）
    name_upper = name.upper()
    for keyword, cn in DIAGNOSIS_KEYWORD_MAP.items():
        if keyword in name_upper:
            return cn
    # 3. 兜底：归为"其他疾病"，保证不会出现英文
    return '其他疾病'


# 关键词模糊映射表（当精确匹配不到时，按包含关键词翻译）
DIAGNOSIS_KEYWORD_MAP = {
    'HEART FAILURE': '心力衰竭',
    'MYOCARDIAL INFARCTION': '急性心肌梗死',
    'ATHEROSCLEROSIS': '动脉粥样硬化',
    'ARRHYTHMIA': '心律失常',
    'CARDIAC': '心脏疾病',
    'CORONARY': '冠状动脉疾病',
    'CEREBRAL': '脑血管疾病',
    'STROKE': '脑卒中',
    'PNEUMONIA': '肺炎',
    'BRONCHITIS': '支气管炎',
    'ASTHMA': '哮喘',
    'COPD': '慢性阻塞性肺疾病',
    'RESPIRATORY': '呼吸系统疾病',
    'PULMONARY': '肺部疾病',
    'COVID': '新冠肺炎',
    'INFLUENZA': '流行性感冒',
    'SEPTICEMIA': '败血症',
    'SEPSIS': '败血症',
    'INFECTION': '感染',
    'URINARY TRACT': '尿路感染',
    'GANGRENE': '坏疽',
    'CELLULITIS': '蜂窝织炎',
    'GASTROINTESTINAL': '胃肠道疾病',
    'GASTROENT': '胃肠炎',
    'GASTRITIS': '胃炎',
    'DUODENITIS': '十二指肠炎',
    'PANCREATITIS': '胰腺炎',
    'CHOLELITHIASIS': '胆结石',
    'BILIARY': '胆道疾病',
    'INTESTINAL': '肠道疾病',
    'OBSTRUCTION': '梗阻',
    'APPENDICITIS': '阑尾炎',
    'ESOPHAG': '食管疾病',
    'LIVER': '肝脏疾病',
    'HEPATITIS': '肝炎',
    'CIRRHOSIS': '肝硬化',
    'HEMORRHAGE': '出血',
    'BLEEDING': '出血',
    'EPILEPSY': '癫痫',
    'CONVULSION': '惊厥',
    'SEIZURE': '癫痫发作',
    'MULTIPLE SCLEROSIS': '多发性硬化',
    'PARKINSON': '帕金森病',
    'ALZHEIMER': '阿尔茨海默病',
    'DEMENTIA': '痴呆',
    'HEADACHE': '头痛',
    'MIGRAINE': '偏头痛',
    'DIABETES': '糖尿病',
    'THYROID': '甲状腺疾病',
    'ELECTROLYTE': '电解质紊乱',
    'METABOLIC': '代谢障碍',
    'NUTRITIONAL': '营养障碍',
    'RENAL FAILURE': '肾功能衰竭',
    'KIDNEY': '肾脏疾病',
    'NEPHRITIS': '肾炎',
    'DIALYSIS': '透析',
    'CALCULI': '结石',
    'PROSTATIC': '前列腺疾病',
    'ANEMIA': '贫血',
    'LEUKEMIA': '白血病',
    'LYMPHOMA': '淋巴瘤',
    'NEOPLASM': '肿瘤',
    'CANCER': '恶性肿瘤',
    'TUMOR': '肿瘤',
    'MALIGNANT': '恶性疾病',
    'BENIGN': '良性疾病',
    'ANTINEOPLASTIC': '抗肿瘤治疗',
    'CHEMOTHERAPY': '化疗',
    'FRACTURE': '骨折',
    'OSTEOARTHRITIS': '骨关节炎',
    'ARTHROPATHY': '关节病变',
    'ARTHROPLASTY': '关节置换',
    'SPINE': '脊柱疾病',
    'SPINAL': '脊柱疾病',
    'DISLOCATION': '脱位',
    'SPRAIN': '扭伤',
    'STRAIN': '拉伤',
    'BONE': '骨骼疾病',
    'JOINT': '关节疾病',
    'LIVEBORN': '活产新生儿',
    'NEWBORN': '新生儿',
    'C-SECTION': '剖宫产',
    'CESAREAN': '剖宫产',
    'CHILDBIRTH': '分娩',
    'DELIVERY': '分娩',
    'PREGNANCY': '妊娠',
    'POSTPARTUM': '产后',
    'PRETERM': '早产',
    'ABORTION': '流产',
    'ECTOPIC': '异位妊娠',
    'ALCOHOL': '酒精相关障碍',
    'SUBSTANCE': '物质相关障碍',
    'DRUG': '药物相关障碍',
    'OPIOID': '阿片类相关',
    'SCHIZOPHRENIA': '精神分裂症',
    'PSYCHOTIC': '精神障碍',
    'MOOD': '心境障碍',
    'DEPRESSION': '抑郁',
    'DEPRESSIVE': '抑郁',
    'ANXIETY': '焦虑',
    'PERSONALITY': '人格障碍',
    'SUICIDE': '自杀/自伤',
    'POISONING': '中毒',
    'TOXIC': '中毒',
    'BURN': '烧伤',
    'TRAUMA': '创伤',
    'INJURY': '损伤',
    'WOUND': '伤口',
    'HIV': 'HIV感染',
    'IMMUNE': '免疫疾病',
    'AUTOIMMUNE': '自身免疫病',
    'CIRCULATORY': '循环系统疾病',
    'VASCULAR': '血管疾病',
    'VENOUS': '静脉疾病',
    'ARTERIAL': '动脉疾病',
    'BLOOD': '血液疾病',
    'COAGULATION': '凝血障碍',
    'THROMBOSIS': '血栓',
    'EMBOLISM': '栓塞',
    'HYPERTENSION': '高血压',
    'HYPOTENSION': '低血压',
    'SHOCK': '休克',
    'FLUID': '体液紊乱',
    'DEHYDRATION': '脱水',
    'FEVER': '发热',
    'PAIN': '疼痛',
    'SYNCOPE': '晕厥',
    'DIZZINESS': '眩晕',
    'FALL': '跌倒',
    'AGING': '老年相关',
    'SCREENING': '筛查',
    'EXAMINATION': '检查',
    'OBSERVATION': '观察',
    'REHABILITATION': '康复治疗',
    'PALLIATIVE': '姑息治疗',
    'HOSPICE': '临终关怀',
    'DIALYSIS': '透析',
    'TRANSPLANT': '移植',
    'AMPUTATION': '截肢',
    'SURGERY': '手术',
    'POSTOPERATIVE': '术后',
    'COMPLICATION': '并发症',
}


# ============ 工具函数 ============
def round2(x):
    return float(f"{x:.2f}")


def round1(x):
    return float(f"{x:.1f}")


def load_and_clean_data():
    """加载并清洗数据（自动识别 CSV/Excel），返回 (df, years, regions) 真实维度"""
    print(f"[1/5] 加载数据: {DATA_PATH}")
    if MAX_ROWS:
        print(f"      ⚙️ 测试模式：只读前 {MAX_ROWS:,} 行（MAX_ROWS={MAX_ROWS}）")

    ext = os.path.splitext(DATA_PATH)[1].lower()

    if ext == '.csv':
        # CSV 大文件加速策略：
        # - 全量模式（MAX_ROWS=None）：用 pyarrow 引擎（快 3-5 倍）
        # - 测试模式（MAX_ROWS=数字）：pyarrow 不支持 nrows，用默认 C 引擎
        if MAX_ROWS:
            df = pd.read_csv(DATA_PATH, usecols=USE_COLS, dtype=DTYPE_MAP, nrows=MAX_ROWS)
            print(f"      [默认引擎 + nrows] 读取完成（测试模式）")
        else:
            try:
                df = pd.read_csv(DATA_PATH, usecols=USE_COLS, dtype=DTYPE_MAP, engine='pyarrow')
                print(f"      [pyarrow 引擎] 读取完成（全量加速）")
            except Exception:
                df = pd.read_csv(DATA_PATH, usecols=USE_COLS, dtype=DTYPE_MAP)
                print(f"      [默认引擎] 读取完成（建议 pip install pyarrow 加速）")
    elif ext in ('.xlsx', '.xls'):
        df = pd.read_excel(DATA_PATH, usecols=USE_COLS, dtype=DTYPE_MAP, nrows=MAX_ROWS)
        print(f"      [Excel 引擎] 读取完成")
    else:
        print(f"[错误] 不支持的文件格式: {ext}")
        sys.exit(1)

    print(f"      原始记录数: {len(df):,} 条")

    # 1. 标准化区域（只保留 Excel 里真实存在的 County）
    df['region'] = df['Hospital County'].map(COUNTY_TO_REGION)
    # 未匹配到的 County 丢弃，不编造
    unmapped = df[df['region'].isna()]
    if len(unmapped) > 0:
        print(f"      ⚠️ {len(unmapped)} 条记录的 County 未匹配，已剔除: {unmapped['Hospital County'].unique().tolist()}")

    # 2. 标准化年龄段
    df['age_cn'] = df['Age Group'].map(AGE_GROUP_EN_TO_CN).fillna('30-49岁')

    # 3. 数值字段转换（安全）
    for col in ['Length of Stay', 'Total Charges', 'Total Costs']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 4. 科室映射
    df['dept'] = df['APR MDC Description'].map(MDC_TO_DEPT).fillna('其他')

    # 5. 丢弃关键字段空值
    before = len(df)
    df = df.dropna(subset=['Total Charges', 'Length of Stay', 'region'])
    print(f"      清洗后记录数: {len(df):,} 条 (剔除 {before - len(df)} 条空值)")

    # 6. 动态读取真实年份和地区
    years = sorted(df['Discharge Year'].astype(int).astype(str).unique().tolist())
    regions_raw = sorted(df['region'].unique().tolist())
    regions = ['all'] + regions_raw

    print(f"      真实年份: {years}")
    print(f"      真实地区: {regions}")
    return df, years, regions


def filter_region(df_raw, region):
    """根据 region 获取对应数据集（纯真实数据，不合成）"""
    if region == 'all':
        return df_raw
    return df_raw[df_raw['region'] == region].copy()


# ============ 4 类聚合计算 ============
def calc_kpi(df_subset):
    """KPI: 总出院人数 / 平均住院总费用 / 平均总成本 / 平均住院天数（纯真实数据）"""
    n = len(df_subset)
    if n == 0:
        return {
            'totalDischarges': 0,
            'avgTotalCharges': 0.0,
            'avgTotalCosts': 0.0,
            'avgStayDays': 0.0,
        }
    return {
        'totalDischarges': n,
        'avgTotalCharges': round2(float(df_subset['Total Charges'].mean())),
        'avgTotalCosts': round2(float(df_subset['Total Costs'].mean())),
        'avgStayDays': round1(float(df_subset['Length of Stay'].mean())),
    }


def calc_age_group(df_subset):
    """5个年龄段人数分布（纯真实计数）"""
    counts = df_subset['age_cn'].value_counts().to_dict()
    result = []
    for age in AGE_GROUP_ORDER:
        c = counts.get(age, 0)
        result.append({'name': age, 'value': int(c)})
    return result


def calc_top_diseases(df_subset, age_filter=None):
    """按疾病名称聚合平均费用，取 Top10（纯真实数据）"""
    df = df_subset.copy()
    if age_filter and age_filter != 'all':
        df = df[df['age_cn'] == age_filter]
    if len(df) == 0:
        return []

    grouped = (
        df.groupby('CCSR Diagnosis Description')
          .agg(avg_charge=('Total Charges', 'mean'), cnt=('Total Charges', 'count'))
          .reset_index()
    )
    grouped = grouped[grouped['cnt'] >= 1]
    grouped = grouped.sort_values('avg_charge', ascending=False).head(10)

    result = []
    for _, row in grouped.iterrows():
        en_name = str(row['CCSR Diagnosis Description'])
        name = translate_diagnosis(en_name)  # 英文 → 中文
        if len(name) > 16:
            name = name[:15] + '…'
        result.append({
            'name': name,
            'value': round2(float(row['avg_charge'])),
        })
    return result


def calc_dept_compare(df_subset):
    """科室维度对比：总费用 / 平均住院天数 / 出院人数（取前8，纯真实数据）"""
    df = df_subset.copy()
    df = df[df['dept'] != '其他']
    if len(df) == 0:
        return []

    grouped = (
        df.groupby('dept')
          .agg(
              total_charges=('Total Charges', 'sum'),
              avg_stay=('Length of Stay', 'mean'),
              count=('dept', 'count'),
          )
          .reset_index()
    )
    grouped = grouped.sort_values('count', ascending=False).head(8)

    result = []
    for _, row in grouped.iterrows():
        result.append({
            'name': row['dept'],
            'totalCharges': round2(float(row['total_charges'])),
            'avgStayDays': round1(float(row['avg_stay'])),
            'count': int(row['count']),
        })
    return result


# ============ 缓存写入 ============
def write_cache(r, key, value):
    full_key = f"{KEY_PREFIX}{key}"
    payload = json.dumps(value, ensure_ascii=False)
    r.set(full_key, payload)
    # 不设过期时间（静态数据永不过期，如需重建手动 flushdb）
    return len(payload)


def main():
    print("=" * 60)
    print("🏥 智慧医疗分析平台 - Dashboard 数据预构建")
    print("=" * 60)

    if not os.path.exists(DATA_PATH):
        print(f"[错误] 找不到数据文件: {DATA_PATH}")
        sys.exit(1)

    # 1. 连接 Redis
    print(f"\n[连接] Redis {REDIS_HOST}:{REDIS_PORT} (db={REDIS_DB})")
    try:
        r = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
            password=REDIS_PASSWORD, decode_responses=True
        )
        r.ping()
        print("      ✅ Redis 连接成功")
    except Exception as e:
        print(f"[错误] Redis 连接失败: {e}")
        print("      请先启动 Redis: redis-server")
        sys.exit(1)

    # 2. 加载数据（动态读取真实年份和地区）
    df_raw, years, regions = load_and_clean_data()

    # 2.5 清除旧缓存（防止伪造的 2022/2023/2024 数据残留）
    old_keys = r.keys(f'{KEY_PREFIX}*')
    if old_keys:
        r.delete(*old_keys)
        print(f"      🧹 已清除旧缓存 {len(old_keys)} 个 Key")

    # 3. 遍历所有维度组合并写入缓存（只用真实年份和地区）
    print("\n[3/5] 计算聚合数据并写入 Redis...")
    total_keys = 0
    total_bytes = 0

    age_groups_for_top = ['all'] + AGE_GROUP_ORDER

    for year in years:
        for region in regions:
            df_sub = filter_region(df_raw, region)
            if len(df_sub) == 0:
                continue  # 该地区无数据，跳过不写缓存

            # 3.1 KPI
            kpi = calc_kpi(df_sub)
            b = write_cache(r, f"kpi:{year}:{region}", kpi)
            total_keys += 1; total_bytes += b

            # 3.2 Age Group 分布
            age_data = calc_age_group(df_sub)
            b = write_cache(r, f"agegroup:{year}:{region}", age_data)
            total_keys += 1; total_bytes += b

            # 3.3 Top Diseases (all + 5 年龄段)
            for age in age_groups_for_top:
                top = calc_top_diseases(df_sub, age_filter=age)
                b = write_cache(r, f"topdiseases:{year}:{region}:{age}", top)
                total_keys += 1; total_bytes += b

            # 3.4 Dept Compare
            dept = calc_dept_compare(df_sub)
            b = write_cache(r, f"deptcompare:{year}:{region}", dept)
            total_keys += 1; total_bytes += b

            print(f"      year={year} region={region:13s} rows={len(df_sub):>4} → 8 keys written")

    # 4. 写入 meta key（包含真实维度，前端据此动态加载筛选器）
    meta = {
        'build_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
        'years': years,
        'regions': regions,
        'age_groups': AGE_GROUP_ORDER,
        'total_raw_rows': len(df_raw),
        'keys_written': total_keys,
    }
    b = write_cache(r, 'meta', meta)
    total_keys += 1; total_bytes += b

    # 5. 验证抽样（用真实年份，不再写死 2024）
    print(f"\n[4/5] 抽样验证缓存...")
    sample_year = years[0]
    sample_key = f"{KEY_PREFIX}kpi:{sample_year}:all"
    sample = json.loads(r.get(sample_key) or '{}')
    print(f"      {sample_key}")
    print(f"      → {json.dumps(sample, ensure_ascii=False)}")

    sample_key2 = f"{KEY_PREFIX}topdiseases:{sample_year}:all:70岁以上"
    sample2 = json.loads(r.get(sample_key2) or '[]')
    print(f"      {sample_key2}")
    print(f"      → Top {len(sample2)} diseases, first: {sample2[0] if sample2 else None}")

    print(f"\n[5/5] 完成 🎉")
    print("=" * 60)
    print(f"  写入总 Key 数: {total_keys}")
    print(f"  写入总字节数: {total_bytes/1024:.2f} KB")
    print(f"  Key 前缀:     {KEY_PREFIX}*")
    print(f"  Meta Key:     {KEY_PREFIX}meta")
    print("=" * 60)


if __name__ == '__main__':
    main()
