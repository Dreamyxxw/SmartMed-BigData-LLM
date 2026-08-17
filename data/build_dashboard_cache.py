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

# ============================================================
# Hospital County -> 前端 region value 映射（57 个县全部纳入，不再剔除非NYC数据）
# 说明：Kings County = Brooklyn，Richmond County = Staten Island 是 NYC 的别名
# ============================================================
COUNTY_TO_REGION = {
    # NYC 5 区（最知名）
    'Bronx': 'Bronx',
    'Manhattan': 'Manhattan',
    'Kings': 'Brooklyn',
    'Queens': 'Queens',
    'Richmond': 'Staten Island',
    # Long Island 长岛两郡
    'Nassau': 'Nassau',
    'Suffolk': 'Suffolk',
    # Hudson Valley 哈德逊谷
    'Westchester': 'Westchester',
    'Orange': 'Orange',
    'Dutchess': 'Dutchess',
    'Rockland': 'Rockland',
    'Putnam': 'Putnam',
    'Ulster': 'Ulster',
    'Columbia': 'Columbia',
    'Sullivan': 'Sullivan',
    # Western NY 西部
    'Erie': 'Erie',
    'Niagara': 'Niagara',
    'Chautauqua': 'Chautauqua',
    'Cattaraugus': 'Cattaraugus',
    'Allegany': 'Allegany',
    # Rochester 罗切斯特地区
    'Monroe': 'Monroe',
    'Genesee': 'Genesee',
    'Livingston': 'Livingston',
    'Wayne': 'Wayne',
    'Ontario': 'Ontario',
    'Wyoming': 'Wyoming',
    'Orleans': 'Orleans',
    'Yates': 'Yates',
    # Syracuse 锡拉丘兹地区
    'Onondaga': 'Onondaga',
    'Oswego': 'Oswego',
    'Madison': 'Madison',
    'Cayuga': 'Cayuga',
    'Cortland': 'Cortland',
    'Tompkins': 'Tompkins',
    # Capital Region 首府地区
    'Albany': 'Albany',
    'Schenectady': 'Schenectady',
    'Rensselaer': 'Rensselaer',
    'Saratoga': 'Saratoga',
    'Warren': 'Warren',
    'Washington': 'Washington',
    'Essex': 'Essex',
    'Clinton': 'Clinton',
    'Franklin': 'Franklin',
    'St Lawrence': 'St Lawrence',
    'Jefferson': 'Jefferson',
    'Lewis': 'Lewis',
    'Herkimer': 'Herkimer',
    'Fulton': 'Fulton',
    'Montgomery': 'Montgomery',
    'Schoharie': 'Schoharie',
    'Otsego': 'Otsego',
    'Delaware': 'Delaware',
    'Greene': 'Greene',
    'Chenango': 'Chenango',
    # Southern Tier 南部
    'Broome': 'Broome',
    'Chemung': 'Chemung',
    'Steuben': 'Steuben',
    'Tioga': 'Tioga',
    'Oneida': 'Oneida',
    'Schuyler': 'Schuyler',
    'Seneca': 'Seneca',
}

# ============================================================
# Region value → 中文 Label 映射
# 知名城市用 "城市名(郡名)"，其余用 "XX郡"
# ============================================================
REGION_CN_NAMES = {
    'all': '全部区域',
    # NYC 5 区
    'Manhattan': '曼哈顿',
    'Brooklyn': '布鲁克林',
    'Queens': '皇后区',
    'Bronx': '布朗克斯',
    'Staten Island': '斯塔滕岛',
    # 长岛
    'Nassau': '拿骚郡(长岛)',
    'Suffolk': '萨福克郡(长岛)',
    # 哈德逊谷
    'Westchester': '威彻斯特郡',
    'Orange': '奥兰治郡',
    'Dutchess': '达奇斯郡',
    'Rockland': '罗克兰郡',
    'Putnam': '帕特南郡',
    'Ulster': '阿尔斯特郡',
    'Columbia': '哥伦比亚郡',
    'Sullivan': '沙利文郡',
    # 大城市：布法罗(伊利郡)
    'Erie': '布法罗市(伊利郡)',
    'Niagara': '尼亚加拉郡',
    'Chautauqua': '肖托夸郡',
    'Cattaraugus': '卡塔拉格斯郡',
    'Allegany': '阿利根尼郡',
    # 大城市：罗切斯特(门罗郡)
    'Monroe': '罗切斯特市(门罗郡)',
    'Genesee': '杰纳西郡',
    'Livingston': '利文斯顿郡',
    'Wayne': '韦恩郡',
    'Ontario': '安大略郡',
    'Wyoming': '怀俄明郡',
    'Orleans': '奥尔良郡',
    'Yates': '耶茨郡',
    # 大城市：锡拉丘兹(奥农达加郡)
    'Onondaga': '锡拉丘兹市(奥农达加郡)',
    'Oswego': '奥斯威戈郡',
    'Madison': '麦迪逊郡',
    'Cayuga': '卡尤加郡',
    'Cortland': '科特兰郡',
    'Tompkins': '汤普金斯郡(伊萨卡)',
    # 大城市：奥尔巴尼(州府)
    'Albany': '奥尔巴尼市(州府)',
    'Schenectady': '斯克内克塔迪郡',
    'Rensselaer': '伦斯勒郡',
    'Saratoga': '萨拉托加郡',
    'Warren': '沃伦郡',
    'Washington': '华盛顿郡',
    'Essex': '埃塞克斯郡',
    'Clinton': '克林顿郡',
    'Franklin': '富兰克林郡',
    'St Lawrence': '圣劳伦斯郡',
    'Jefferson': '杰斐逊郡',
    'Lewis': '刘易斯郡',
    'Herkimer': '赫基默郡',
    'Fulton': '富尔顿郡',
    'Montgomery': '蒙哥马利郡',
    'Schoharie': '斯科哈里郡',
    'Otsego': '奥特西戈郡',
    'Delaware': '特拉华郡',
    'Greene': '格林郡',
    'Chenango': '希南戈郡',
    # 南部
    'Broome': '布鲁姆郡(宾厄姆顿)',
    'Chemung': '希芒郡(埃尔迈拉)',
    'Steuben': '斯托本郡',
    'Tioga': '泰奥加郡',
    'Oneida': '奥奈达郡',
    'Schuyler': '斯凯勒郡',
    'Seneca': '塞内卡郡',
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
# 说明：覆盖数据集中所有高频诊断；映射不到则保留英文原名（保证不丢数据、避免不同病名翻译成相同中文导致重复）
DIAGNOSIS_CN_MAP = {
    # —— 心血管 / 循环系统 ——
    'HEART FAILURE': '心力衰竭',
    'CORONARY ATHEROSCLEROSIS': '冠状动脉粥样硬化',
    'CORONARY ATHEROSCLEROSIS AND OTHER HEART DISEASE': '冠状动脉粥样硬化性心脏病',
    'ACUTE MYOCARDIAL INFARCTION': '急性心肌梗死',
    'CARDIAC ARRHYTHMIAS': '心律失常',
    'CARDIAC DYSRHYTHMIAS': '心律失常',
    'CARDIAC ARREST': '心脏骤停',
    'CEREBRAL INFARCTION': '脑梗死',
    'HYPERTENSION AND HYPERTENSIVE-RELATED CONDITIONS COMPLICATING PREGNANCY; CHILDBIRTH; AND THE PUERPERIUM': '妊娠高血压',
    'TRANSIENT CEREBRAL ISCHEMIA': '短暂性脑缺血发作',
    'PERIPHERAL AND VISCERAL ATHEROSCLEROSIS': '外周及内脏动脉粥样硬化',
    'CONDUCTION DISORDERS': '心脏传导障碍',
    'NONRHEUMATIC AND UNSPECIFIED VALVE DISORDERS': '非风湿性心脏瓣膜病',
    'MYOCARDITIS AND CARDIOMYOPATHY': '心肌炎与心肌病',
    'CHRONIC RHEUMATIC HEART DISEASE': '慢性风湿性心脏病',
    'ACUTE RHEUMATIC HEART DISEASE': '急性风湿性心脏病',
    'AORTIC; PERIPHERAL; AND VISCERAL ARTERY ANEURYSMS': '主动脉及外周动脉瘤',
    'PERICARDITIS AND PERICARDIAL DISEASE': '心包炎与心包疾病',
    'ENDOCARDITIS AND ENDOCARDIAL DISEASE': '心内膜炎与心内膜疾病',
    'OTHER AND ILL-DEFINED HEART DISEASE': '其他心脏病',
    'COMPLICATION OF CARDIOVASCULAR DEVICE, IMPLANT OR GRAFT, INITIAL ENCOUNTER': '心血管器械并发症',
    # —— 呼吸系统 ——
    'PNEUMONIA': '肺炎',
    'CHRONIC OBSTRUCTIVE PULMONARY DISEASE AND BRONCHIECTASIS': '慢性阻塞性肺疾病',
    'ASTHMA': '哮喘',
    'ACUTE BRONCHITIS': '急性支气管炎',
    'RESPIRATORY FAILURE; INSUFFICIENCY; ARREST (ADULT)': '呼吸衰竭',
    'RESPIRATORY FAILURE; INSUFFICIENCY; ARREST': '呼吸衰竭',
    'CORONAVIRUS DISEASE 2019 (COVID-19)': '新冠肺炎',
    'INFLUENZA': '流行性感冒',
    'PLEURAL EFFUSION AND PNEUMOTHORAX': '胸腔积液与气胸',
    'PNEUMOTHORAX': '气胸',
    'LUNG DISEASE DUE TO EXTERNAL AGENTS': '外源性肺病',
    'ASPIRATION PNEUMONITIS': '吸入性肺炎',
    # —— 感染 / 败血症 ——
    'SEPTICEMIA': '败血症',
    'URINARY TRACT INFECTIONS': '尿路感染',
    'GANGRENE': '坏疽',
    'CELLULITIS AND OTHER SKIN INFECTIONS': '蜂窝织炎与皮肤感染',
    'OTHER SPECIFIED AND UNSPECIFIED INFECTIONS': '其他感染',
    'TUBERCULOSIS': '结核病',
    'ENCEPHALITIS': '脑炎',
    'MENINGITIS': '脑膜炎',
    'CNS ABSCESS': '中枢神经系统脓肿',
    'OSTEOMYELITIS': '骨髓炎',
    'INFECTIVE ARTHRITIS': '感染性关节炎',
    'MUSCULOSKELETAL ABSCESS': '肌骨系统脓肿',
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
    'HEPATIC FAILURE': '肝衰竭',
    'DIVERTICULOSIS AND DIVERTICULITIS': '憩室病与憩室炎',
    'ABDOMINAL HERNIA': '腹疝',
    'PERITONITIS AND INTRA-ABDOMINAL ABSCESS': '腹膜炎与腹腔脓肿',
    'GASTRODUODENAL ULCER': '胃十二指肠溃疡',
    'REGIONAL ENTERITIS AND ULCERATIVE COLITIS': '克罗恩病与溃疡性结肠炎',
    'ANAL AND RECTAL CONDITIONS': '肛直肠疾病',
    'OTHER SPECIFIED AND UNSPECIFIED DISORDERS OF STOMACH AND DUODENUM': '胃与十二指肠疾病',
    'DIGESTIVE CONGENITAL ANOMALIES': '消化系统先天性异常',
    'NEONATAL DIGESTIVE AND FEEDING DISORDERS': '新生儿消化与喂养障碍',
    'DYSPHAGIA': '吞咽困难',
    'NAUSEA AND VOMITING': '恶心与呕吐',
    'CLEFT LIP OR PALATE': '唇裂或腭裂',
    'DISORDERS OF TEETH AND GINGIVA': '牙齿与牙龈疾病',
    'DISEASES OF MOUTH; EXCLUDING DENTAL': '口腔疾病',
    'DISORDERS OF JAW': '颌骨疾病',
    # —— 神经系统 ——
    'EPILEPSY; CONVULSIONS': '癫痫与惊厥',
    'OTHER SPECIFIED AND UNSPECIFIED CEREBROVASCULAR DISEASE': '其他脑血管疾病',
    'MULTIPLE SCLEROSIS, OTHER DEMYELINATING DISEASE': '多发性硬化',
    'PARKINSON\'S DISEASE': '帕金森病',
    'HEADACHE; INCLUDING MIGRAINE': '头痛（含偏头痛）',
    'SPONDYLOPATHIES/SPONDYLOARTHROPATHY (INCLUDING INFECTIVE)': '脊柱关节病',
    'NEUROCOGNITIVE DISORDERS': '神经认知障碍',
    'NERVOUS SYSTEM SIGNS AND SYMPTOMS': '神经系统体征与症状',
    'POLYNEUROPATHIES': '多发性神经病',
    'COMA; STUPOR; AND BRAIN DAMAGE': '昏迷与脑损伤',
    'NERVOUS SYSTEM CONGENITAL ANOMALIES': '神经系统先天性异常',
    'OTHER SPECIFIED HEREDITARY AND DEGENERATIVE NERVOUS SYSTEM CONDITIONS': '遗传性与退行性神经系统疾病',
    'NERVE AND NERVE ROOT DISORDERS': '神经与神经根疾病',
    'OTHER SPECIFIED NERVOUS SYSTEM DISORDERS': '其他神经系统疾病(特指)',
    'SEQUELA OF SPECIFIED NERVOUS SYSTEM CONDITIONS': '神经系统疾病后遗症',
    'NEURODEVELOPMENTAL DISORDERS': '神经发育障碍',
    # —— 内分泌 / 代谢 ——
    'DIABETES MELLITUS WITH COMPLICATION': '糖尿病伴并发症',
    'DIABETES MELLITUS WITHOUT COMPLICATION': '糖尿病不伴并发症',
    'DISORDERS OF FLUID; ELECTROLYTE; AND ACID-BASE BALANCE': '水电解质酸碱平衡紊乱',
    'NUTRITIONAL; ENDOCRINE; AND METABOLIC DISORDERS': '营养内分泌代谢障碍',
    'OBESITY': '肥胖症',
    'PITUITARY DISORDERS': '垂体疾病',
    'MALNUTRITION': '营养不良',
    'DISORDERS OF LIPID METABOLISM': '脂质代谢障碍',
    'OTHER SPECIFIED AND UNSPECIFIED ENDOCRINE DISORDERS': '其他内分泌疾病',
    # —— 肾 / 泌尿 ——
    'ACUTE RENAL FAILURE': '急性肾功能衰竭',
    'CHRONIC KIDNEY DISEASE': '慢性肾脏疾病',
    'URINARY CALCULI': '泌尿系结石',
    'BENIGN PROSTATIC HYPERPLASIA': '前列腺良性增生',
    'HYPERPLASIA OF PROSTATE': '前列腺增生',
    'URINARY INCONTINENCE': '尿失禁',
    'HEMATURIA': '血尿',
    'PROTEINURIA': '蛋白尿',
    'OTHER SPECIFIED AND UNSPECIFIED DISEASES OF BLADDER AND URETHRA': '膀胱与尿道疾病',
    'VESICOURETERAL REFLUX': '膀胱输尿管反流',
    'GENITOURINARY SIGNS AND SYMPTOMS': '泌尿生殖系统体征与症状',
    'GENITOURINARY CONGENITAL ANOMALIES': '泌尿生殖系统先天性异常',
    # —— 血液 / 肿瘤 ——
    'ANEMIA': '贫血',
    'ACUTE POSTHEMORRHAGIC ANEMIA': '急性失血性贫血',
    'ENCOUNTER FOR ANTINEOPLASTIC THERAPIES': '抗肿瘤治疗',
    'OTHER SCREENING AND EXAMINATION OF NEOPLASMS': '肿瘤筛查',
    'BENIGN NEOPLASMS': '良性肿瘤',
    'MYELODYSPLASTIC SYNDROME (MDS)': '骨髓增生异常综合征',
    'OTHER SPECIFIED AND UNSPECIFIED HEMATOLOGIC CONDITIONS': '其他血液疾病',
    'IMMUNITY DISORDERS': '免疫障碍',
    # —— 白血病（必须区分6种类型）——
    'LEUKEMIA - ACUTE MYELOID LEUKEMIA (AML)': '急性髓系白血病',
    'LEUKEMIA - ACUTE LYMPHOBLASTIC LEUKEMIA (ALL)': '急性淋巴细胞白血病',
    'LEUKEMIA - CHRONIC MYELOID LEUKEMIA (CML)': '慢性髓系白血病',
    'LEUKEMIA - CHRONIC LYMPHOCYTIC LEUKEMIA (CLL)': '慢性淋巴细胞白血病',
    'LEUKEMIA - HAIRY CELL': '毛细胞白血病',
    'LEUKEMIA - ALL OTHER TYPES': '其他类型白血病',
    # —— 癌症（按部位区分）——
    'BREAST CANCER - ALL OTHER TYPES': '乳腺癌',
    'BREAST CANCER - DUCTAL CARCINOMA IN SITU (DCIS)': '乳腺导管原位癌',
    'MALE REPRODUCTIVE SYSTEM CANCERS - PROSTATE': '前列腺癌',
    'MALE REPRODUCTIVE SYSTEM CANCERS - TESTIS': '睾丸癌',
    'MALE REPRODUCTIVE SYSTEM CANCERS - PENIS': '阴茎癌',
    'MALE REPRODUCTIVE SYSTEM CANCERS - ALL OTHER TYPES': '其他男性生殖系统癌',
    'FEMALE REPRODUCTIVE SYSTEM CANCERS - CERVIX': '宫颈癌',
    'FEMALE REPRODUCTIVE SYSTEM CANCERS - ENDOMETRIUM': '子宫内膜癌',
    'FEMALE REPRODUCTIVE SYSTEM CANCERS - UTERUS': '子宫癌',
    'FEMALE REPRODUCTIVE SYSTEM CANCERS - OVARY': '卵巢癌',
    'FEMALE REPRODUCTIVE SYSTEM CANCERS - VULVA': '外阴癌',
    'FEMALE REPRODUCTIVE SYSTEM CANCERS - VAGINA': '阴道癌',
    'FEMALE REPRODUCTIVE SYSTEM CANCERS - FALLOPIAN TUBE': '输卵管癌',
    'FEMALE REPRODUCTIVE SYSTEM CANCERS - ALL OTHER TYPES': '其他女性生殖系统癌',
    'URINARY SYSTEM CANCERS - BLADDER': '膀胱癌',
    'URINARY SYSTEM CANCERS - URETER AND RENAL PELVIS': '输尿管肾盂癌',
    'URINARY SYSTEM CANCERS - URETHRA': '尿道癌',
    'URINARY SYSTEM CANCERS - ALL OTHER TYPES': '其他泌尿系统癌',
    'ENDOCRINE SYSTEM CANCERS - PANCREAS': '胰腺癌',
    'ENDOCRINE SYSTEM CANCERS - THYMUS': '胸腺癌',
    'ENDOCRINE SYSTEM CANCERS - ADRENOCORTICAL': '肾上腺皮质癌',
    'ENDOCRINE SYSTEM CANCERS - PITUITARY GLAND': '垂体癌',
    'ENDOCRINE SYSTEM CANCERS - ALL OTHER TYPES': '其他内分泌系统癌',
    'NERVOUS SYSTEM CANCERS - BRAIN': '脑癌',
    'NERVOUS SYSTEM CANCERS - ALL OTHER TYPES': '其他神经系统癌',
    'HEAD AND NECK CANCERS - LIP AND ORAL CAVITY': '口腔癌',
    'HEAD AND NECK CANCERS - THROAT': '咽喉癌',
    'HEAD AND NECK CANCERS - LARYNGEAL': '喉癌',
    'HEAD AND NECK CANCERS - TONSILS': '扁桃体癌',
    'HEAD AND NECK CANCERS - SALIVARY GLAND': '涎腺癌',
    'HEAD AND NECK CANCERS - NASOPHARYNGEAL': '鼻咽癌',
    'HEAD AND NECK CANCERS - PHARYNGEAL': '咽癌',
    'HEAD AND NECK CANCERS - HYPOPHARYNGEAL': '下咽癌',
    'HEAD AND NECK CANCERS - EYE': '眼癌',
    'HEAD AND NECK CANCERS - ALL OTHER TYPES': '其他头颈部癌',
    'SKIN CANCERS - MELANOMA': '黑色素瘤',
    'SKIN CANCERS - SQUAMOUS CELL CARCINOMA': '皮肤鳞状细胞癌',
    'SKIN CANCERS - BASAL CELL CARCINOMA': '皮肤基底细胞癌',
    'SKIN CANCERS - ALL OTHER TYPES': '其他皮肤癌',
    'BONE CANCER': '骨癌',
    'CANCER OF OTHER SITES': '其他部位癌',
    'SECONDARY MALIGNANCIES': '继发恶性肿瘤',
    'MULTIPLE MYELOMA': '多发性骨髓瘤',
    'SARCOMA': '肉瘤',
    'MESOTHELIOMA': '间皮瘤',
    # —— 肌骨系统 ——
    'FRACTURE OF TORSO, INITIAL ENCOUNTER': '躯干骨折',
    'PATHOLOGIC FRACTURES': '病理性骨折',
    'OSTEOARTHRITIS': '骨关节炎',
    'SPRAINS; STRAINS; AND DISLOCATIONS EXCEPT HEEL': '扭伤脱位',
    'PATHOLOGY OF BONES AND JOINTS': '骨关节病变',
    'SCOLIOSIS AND OTHER POSTURAL DORSOPATHIC DEFORMITIES': '脊柱侧弯',
    'TENDON AND SYNOVIAL DISORDERS': '肌腱与滑膜疾病',
    'MUSCULOSKELETAL CONGENITAL CONDITIONS': '肌骨系统先天性异常',
    'ACQUIRED DEFORMITIES (EXCLUDING FOOT)': '获得性畸形',
    'MUSCLE DISORDERS': '肌肉疾病',
    'BIOMECHANICAL LESIONS': '生物力学损伤',
    'OSTEOPOROSIS': '骨质疏松',
    'ACQUIRED FOOT DEFORMITIES': '获得性足部畸形',
    'ASEPTIC NECROSIS AND OSTEONECROSIS': '无菌性坏死与骨坏死',
    'MYOPATHIES': '肌病',
    'JUVENILE ARTHRITIS': '幼年型关节炎',
    'RHEUMATOID ARTHRITIS AND RELATED DISEASE': '类风湿关节炎',
    'CRYSTAL ARTHROPATHIES (EXCLUDING GOUT)': '晶体性关节病(非痛风)',
    'GOUT': '痛风',
    'AUTOINFLAMMATORY SYNDROMES': '自身炎症综合征',
    'SYSTEMIC LUPUS ERYTHEMATOSUS AND CONNECTIVE TISSUE DISORDERS': '系统性红斑狼疮与结缔组织病',
    'OTHER SPECIFIED CONNECTIVE TISSUE DISEASE': '其他结缔组织病',
    # —— 产科 / 新生儿 ——
    'LIVEBORN': '活产新生儿',
    'PREVIOUS C-SECTION': '剖宫产史',
    'COMPLICATIONS SPECIFIED DURING CHILDBIRTH': '分娩并发症',
    'POSTPARTUM HEMORRHAGE': '产后出血',
    'PRETERM LABOR': '早产临产',
    'EARLY OR THREATENED LABOR': '早产/先兆临产',
    'MATERNAL CARE RELATED TO FETAL CONDITIONS': '胎儿相关产科护理',
    'MATERNAL CARE RELATED TO DISORDERS OF THE PLACENTA AND PLACENTAL IMPLANTATION': '胎盘相关产科护理',
    'MATERNAL CARE FOR ABNORMALITY OF PELVIC ORGANS': '盆腔器官异常产科护理',
    'POLYHYDRAMNIOS AND OTHER PROBLEMS OF AMNIOTIC CAVITY': '羊膜腔问题',
    'MULTIPLE GESTATION': '多胎妊娠',
    'OTHER SPECIFIED AND UNSPECIFIED PERINATAL CONDITIONS': '围产期疾病',
    'HEMOLYTIC JAUNDICE AND PERINATAL JAUNDICE': '溶血性与围产期黄疸',
    'SHORT GESTATION; LOW BIRTH WEIGHT; AND FETAL GROWTH RETARDATION': '短孕期/低出生体重',
    'NEONATAL ACIDEMIA AND HYPOXIA': '新生儿酸血症与缺氧',
    'NEONATAL ABSTINENCE SYNDROME': '新生儿戒断综合征',
    'CONTRACEPTIVE AND PROCREATIVE MANAGEMENT': '避孕与生育管理',
    'FEMALE INFERTILITY': '女性不孕症',
    # —— 女性生殖系统 ——
    'INFLAMMATORY DISEASES OF FEMALE PELVIC ORGANS': '女性盆腔器官炎症',
    'PROLAPSE OF FEMALE GENITAL ORGANS': '女性生殖器官脱垂',
    'ENDOMETRIOSIS': '子宫内膜异位症',
    'OTHER SPECIFIED FEMALE GENITAL DISORDERS': '其他女性生殖系统疾病',
    'MENSTRUAL DISORDERS': '月经障碍',
    'MENOPAUSAL DISORDERS': '更年期障碍',
    # —— 男性生殖系统 ——
    'INFLAMMATORY CONDITIONS OF MALE GENITAL ORGANS': '男性生殖器官炎症',
    'ERECTILE DYSFUNCTION': '勃起功能障碍',
    'OTHER SPECIFIED MALE GENITAL DISORDERS': '其他男性生殖系统疾病',
    # —— 精神 / 行为 ——
    'ALCOHOL-RELATED DISORDERS': '酒精相关障碍',
    'SUBSTANCE-RELATED DISORDERS': '物质相关障碍',
    'SCHIZOPHRENIA SPECTRUM AND OTHER PSYCHOTIC DISORDERS': '精神分裂症谱系',
    'MOOD DISORDERS': '心境障碍',
    'ANXIETY; SOMATOFORM; DISSOCIATIVE; AND PERSONALITY DISORDERS': '焦虑等人格障碍',
    'BIPOLAR AND RELATED DISORDERS': '双相情感障碍',
    'SUICIDAL IDEATION/ATTEMPT/INTENTIONAL SELF-HARM': '自杀意念/自伤',
    'MISCELLANEOUS MENTAL AND BEHAVIORAL DISORDERS/CONDITIONS': '其他精神行为障碍',
    'SLEEP WAKE DISORDERS': '睡眠障碍',
    'CANNABIS-RELATED DISORDERS': '大麻相关障碍',
    'SEDATIVE-RELATED DISORDERS': '镇静剂相关障碍',
    'STIMULANT-RELATED DISORDERS': '兴奋剂相关障碍',
    'OBSESSIVE-COMPULSIVE AND RELATED DISORDERS': '强迫症与相关障碍',
    'DISRUPTIVE, IMPULSE-CONTROL AND CONDUCT DISORDERS': '破坏性冲动控制障碍',
    'FEEDING AND EATING DISORDERS': '进食障碍',
    'SOMATIC DISORDERS': '躯体化障碍',
    'ENCOUNTER FOR MENTAL HEALTH CONDITIONS': '心理健康就诊',
    # —— 创伤 / 中毒 ——
    'INJURIES AND POISONINGS': '损伤与中毒',
    'POISONING BY NONOPIOID AND OTHER DRUGS': '非阿片类药物中毒',
    'COMPLICATION OF OTHER SURGICAL OR MEDICAL CARE, INJURY, INITIAL ENCOUNTER': '手术/医疗并发症',
    'EFFECT OF FOREIGN BODY ENTERING OPENING, INITIAL ENCOUNTER': '异物进入(初次)',
    'EFFECT OF FOREIGN BODY ENTERING OPENING, SUBSEQUENT ENCOUNTER': '异物进入(后续)',
    'EFFECT OF OTHER EXTERNAL CAUSES, INITIAL ENCOUNTER': '其他外因伤害(初次)',
    'EFFECT OF OTHER EXTERNAL CAUSES, SUBSEQUENT ENCOUNTER': '其他外因伤害(后续)',
    'ALLERGIC REACTIONS': '过敏反应',
    'ALLERGIC REACTIONS, SUBSEQUENT ENCOUNTER': '过敏反应(后续)',
    'ACQUIRED ABSENCE OF LIMB OR ORGAN': '获得性肢体/器官缺失',
    'MALTREATMENT/ABUSE': '虐待',
    # —— 眼 / 耳 / 鼻 ——
    'BLINDNESS AND VISION DEFECTS': '失明与视力缺陷',
    'CONGENITAL MALFORMATIONS OF EYE, EAR, FACE, NECK': '眼耳面颈部先天性畸形',
    'RETINAL AND VITREOUS CONDITIONS': '视网膜与玻璃体疾病',
    'UVEITIS AND OCULAR INFLAMMATION': '葡萄膜炎与眼部炎症',
    'GLAUCOMA': '青光眼',
    'CORNEA AND EXTERNAL DISEASE': '角膜与外部眼病',
    'OTHER SPECIFIED EYE DISORDERS': '其他眼部疾病',
    'OCULOFACIAL PLASTICS AND ORBITAL CONDITIONS': '眼面部整形与眶部疾病',
    'CATARACT AND OTHER LENS DISORDERS': '白内障与晶状体疾病',
    'REFRACTIVE ERROR': '屈光不正',
    'STRABISMUS': '斜视',
    'HEARING LOSS': '听力损失',
    'DISEASES OF INNER EAR AND RELATED CONDITIONS': '内耳疾病',
    'OTHER SPECIFIED AND UNSPECIFIED DISORDERS OF THE EAR': '耳部疾病',
    'DISEASES OF MIDDLE EAR AND MASTOID (EXCEPT OTITIS MEDIA)': '中耳与乳突疾病',
    'OTITIS MEDIA': '中耳炎',
    'SINUSITIS': '鼻窦炎',
    'ACUTE AND CHRONIC TONSILLITIS': '急慢性扁桃体炎',
    # —— 皮肤 ——
    'NON-PRESSURE ULCER OF SKIN': '非压迫性皮肤溃疡',
    'PRESSURE ULCER OF SKIN': '压迫性皮肤溃疡',
    'OTHER SPECIFIED INFLAMMATORY CONDITION OF SKIN': '其他皮肤炎症',
    'CONTACT DERMATITIS': '接触性皮炎',
    'OTHER SPECIFIED AND UNSPECIFIED SKIN DISORDERS': '其他皮肤疾病',
    'SKIN/SUBCUTANEOUS SIGNS AND SYMPTOMS': '皮肤体征与症状',
    # —— 其他系统 / 体征 / 就诊 ——
    'HIV INFECTION': 'HIV感染',
    'OTHER SPECIFIED AND UNSPECIFIED CIRCULATORY DISEASES': '其他循环系统疾病',
    'OTHER SPECIFIED AND UNSPECIFIED RESPIRATORY DISEASES': '其他呼吸系统疾病',
    'OTHER SPECIFIED AND UNSPECIFIED NERVOUS SYSTEM DISORDERS': '其他神经系统疾病',
    'OTHER SPECIFIED AND UNSPECIFIED GENITOURINARY DISORDERS': '其他泌尿生殖疾病',
    'MALAISE AND FATIGUE': '不适与疲劳',
    'OTHER GENERAL SIGNS AND SYMPTOMS': '其他一般体征与症状',
    'GENERAL SENSATION/PERCEPTION SIGNS AND SYMPTOMS': '感觉与知觉体征',
    'ABNORMAL FINDINGS WITHOUT DIAGNOSIS': '异常发现(无诊断)',
    'OTHER AFTERCARE ENCOUNTER': '随访复查',
    'IMPLANT, DEVICE OR GRAFT RELATED ENCOUNTER': '植入物/器械相关就诊',
    'ENCOUNTER FOR PROPHYLACTIC OR OTHER PROCEDURES': '预防性操作',
    'OTHER SPECIFIED ENCOUNTERS AND COUNSELING': '其他就诊与咨询',
    'OTHER SPECIFIED STATUS': '其他特定状态',
    'MEDIASTINAL DISORDERS': '纵隔疾病',
    'VARICOSE VEINS OF LOWER EXTREMITY': '下肢静脉曲张',
    'OTHER SPECIFIED DISEASES OF VEINS AND LYMPHATICS': '静脉与淋巴管疾病',
    'CYSTIC FIBROSIS': '囊性纤维化',
    'CHROMOSOMAL ABNORMALITIES': '染色体异常',
    'OTHER SPECIFIED AND UNSPECIFIED CONGENITAL ANOMALIES': '其他先天性异常',
    'No Diagnosis': '无诊断',
    'SEQUELA OF SPECIFIED INFECTIOUS DISEASE CONDITIONS': '传染病后遗症',
    # —— 补充映射（覆盖数据集中所有高频病名，避免英文名超16字被截断导致重复）——
    'SKIN AND SUBCUTANEOUS TISSUE INFECTIONS': '皮肤与皮下组织感染',
    'PROLONGED PREGNANCY': '过期妊娠',
    'MALPOSITION, DISPROPORTION OR OTHER LABOR COMPLICATIONS': '胎位异常/头盆不称/产程并发症',
    'ACUTE AND UNSPECIFIED RENAL FAILURE': '急性和未特指肾功能衰竭',
    'UNCOMPLICATED PREGNANCY, DELIVERY OR PUERPERIUM': '无并发症妊娠/分娩/产褥',
    'FLUID AND ELECTROLYTE DISORDERS': '体液与电解质紊乱',
    'PNEUMONIA (EXCEPT THAT CAUSED BY TUBERCULOSIS)': '肺炎(非结核性)',
    'NONSPECIFIC CHEST PAIN': '非特异性胸痛',
    'DEPRESSIVE DISORDERS': '抑郁障碍',
    'APPENDICITIS AND OTHER APPENDICEAL CONDITIONS': '阑尾炎与阑尾疾病',
    'SYNCOPE': '晕厥',
    'PANCREATIC DISORDERS (EXCLUDING DIABETES)': '胰腺疾病(非糖尿病)',
    'INTESTINAL OBSTRUCTION AND ILEUS': '肠梗阻与肠麻痹',
    'HYPERTENSION WITH COMPLICATIONS AND SECONDARY HYPERTENSION': '高血压并发症与继发性高血压',
    'OB-RELATED TRAUMA TO PERINEUM AND VULVA': '产科相关会阴外阴创伤',
    'DIABETES OR ABNORMAL GLUCOSE TOLERANCE COMPLICATING PREGNANCY; CHILDBIRTH; OR THE PUERPERIUM': '妊娠期糖尿病/糖耐量异常',
    'FRACTURE OF THE LOWER LIMB (EXCEPT HIP), INITIAL ENCOUNTER': '下肢骨折(初次,不含髋)',
    'POISONING BY DRUGS, INITIAL ENCOUNTER': '药物中毒(初次)',
    'OTHER SPECIFIED COMPLICATIONS IN PREGNANCY': '其他特指妊娠并发症',
    'SICKLE CELL TRAIT/ANEMIA': '镰状细胞特征/贫血',
    'FRACTURE OF THE NECK OF THE FEMUR (HIP), INITIAL ENCOUNTER': '股骨颈骨折(初次)',
    'TRAUMATIC BRAIN INJURY (TBI); CONCUSSION, INITIAL ENCOUNTER': '创伤性脑损伤/脑震荡(初次)',
    'RESPIRATORY CANCERS': '呼吸系统癌症',
    'ACUTE PULMONARY EMBOLISM': '急性肺栓塞',
    'OTHER SPECIFIED AND UNSPECIFIED LIVER DISEASE': '其他肝脏疾病(未特指)',
    'GASTROINTESTINAL CANCERS - COLORECTAL': '结直肠癌',
    'INTESTINAL INFECTION': '肠道感染',
    'POSTPROCEDURAL OR POSTOPERATIVE DIGESTIVE SYSTEM COMPLICATION': '术后消化系统并发症',
    'ESOPHAGEAL DISORDERS': '食管疾病',
    'COMPLICATION OF INTERNAL ORTHOPEDIC DEVICE OR IMPLANT, INITIAL ENCOUNTER': '骨科内置器械并发症(初次)',
    'COMPLICATION OF GENITOURINARY DEVICE, IMPLANT OR GRAFT, INITIAL ENCOUNTER': '泌尿生殖器械并发症(初次)',
    'OTHER SPECIFIED AND UNSPECIFIED DISEASES OF KIDNEY AND URETERS': '肾与输尿管疾病(未特指)',
    'ACUTE HEMORRHAGIC CEREBROVASCULAR DISEASE': '急性出血性脑血管病',
    'NUTRITIONAL ANEMIA': '营养性贫血',
    'FRACTURE OF THE UPPER LIMB, INITIAL ENCOUNTER': '上肢骨折(初次)',
    'HYPOTENSION': '低血压',
    'SEQUELA OF CEREBRAL INFARCTION AND OTHER CEREBROVASCULAR DISEASE': '脑梗死及脑血管病后遗症',
    'ACUTE PHLEBITIS; THROMBOPHLEBITIS AND THROMBOEMBOLISM': '急性静脉炎/血栓栓塞',
    'COMPLICATION OF TRANSPLANTED ORGANS OR TISSUE, INITIAL ENCOUNTER': '移植器官并发症(初次)',
    'ABDOMINAL PAIN AND OTHER DIGESTIVE/ABDOMEN SIGNS AND SYMPTOMS': '腹痛与消化/腹部体征',
    'OPIOID-RELATED DISORDERS': '阿片类相关障碍',
    'CARDIAC AND CIRCULATORY CONGENITAL ANOMALIES': '心脏与循环系统先天性异常',
    'PERIPHERAL AND VISCERAL VASCULAR DISEASE': '外周与内脏血管疾病',
    'NON-HODGKIN LYMPHOMA': '非霍奇金淋巴瘤',
    'FRACTURE OF THE SPINE AND BACK, INITIAL ENCOUNTER': '脊柱与背部骨折(初次)',
    'CIRCULATORY SIGNS AND SYMPTOMS': '循环系统体征与症状',
    'OTHER SPECIFIED AND UNSPECIFIED LOWER RESPIRATORY DISEASE': '下呼吸道疾病(未特指)',
    'OTHER SPECIFIED AND UNSPECIFIED NUTRITIONAL AND METABOLIC DISORDERS': '营养与代谢疾病(未特指)',
    'FRACTURE OF HEAD AND NECK, INITIAL ENCOUNTER': '头颈部骨折(初次)',
    'CONDITIONS DUE TO NEOPLASM OR THE TREATMENT OF NEOPLASM': '肿瘤或其治疗所致疾病',
    'INTERNAL ORGAN INJURY, INITIAL ENCOUNTER': '内脏损伤(初次)',
    'VIRAL INFECTION': '病毒感染',
    'COAGULATION AND HEMORRHAGIC DISORDERS': '凝血与出血性疾病',
    'GASTROINTESTINAL CANCERS - STOMACH': '胃癌',
    'RESPIRATORY SIGNS AND SYMPTOMS': '呼吸系统体征与症状',
    'DRUG INDUCED OR TOXIC RELATED CONDITION': '药物诱发/毒性相关疾病',
    'APLASTIC ANEMIA': '再生障碍性贫血',
    'URINARY SYSTEM CANCERS - KIDNEY': '肾癌',
    'TRAUMA- AND STRESSOR-RELATED DISORDERS': '创伤与应激相关障碍',
    'PLEURISY, PLEURAL EFFUSION AND PULMONARY COLLAPSE': '胸膜炎/胸腔积液/肺萎陷',
    'OCCLUSION OR STENOSIS OF PRECEREBRAL OR CEREBRAL ARTERIES WITHOUT INFARCTION': '脑血管闭塞或狭窄(无梗死)',
    'OTHER SPECIFIED UPPER RESPIRATORY INFECTIONS': '其他特指上呼吸道感染',
    'THYROID DISORDERS': '甲状腺疾病',
    'OTHER SPECIFIED AND UNSPECIFIED MOOD DISORDERS': '其他心境障碍(未特指)',
    'POSTPROCEDURAL OR POSTOPERATIVE RESPIRATORY SYSTEM COMPLICATION': '术后呼吸系统并发症',
    'CALCULUS OF URINARY TRACT': '尿路结石',
    'PARKINSON`S DISEASE': '帕金森病',
    'OTHER SPECIFIED SUBSTANCE-RELATED DISORDERS': '其他特指物质相关障碍',
    'DISEASES OF WHITE BLOOD CELLS': '白细胞疾病',
    'MUSCULOSKELETAL PAIN, NOT LOW BACK PAIN': '肌骨疼痛(非腰背)',
    'OTHER AND ILL-DEFINED CEREBROVASCULAR DISEASE': '其他不明确脑血管病',
    'FEVER': '发热',
    'NEOPLASMS OF UNSPECIFIED NATURE OR UNCERTAIN BEHAVIOR': '未特指性质/行为不定的肿瘤',
    'SUPERFICIAL INJURY; CONTUSION, INITIAL ENCOUNTER': '表浅损伤/挫伤(初次)',
    'HEMORRHOIDS': '痔疮',
    'OPEN WOUNDS OF HEAD AND NECK, INITIAL ENCOUNTER': '头颈部开放伤口(初次)',
    'PATHOLOGICAL FRACTURE, INITIAL ENCOUNTER': '病理性骨折(初次)',
    'BURN AND CORROSION, INITIAL ENCOUNTER': '烧伤与腐蚀(初次)',
    'NERVOUS SYSTEM PAIN AND PAIN SYNDROMES': '神经系统疼痛与疼痛综合征',
    'GASTROINTESTINAL CANCERS - LIVER': '肝癌',
    'HEPATITIS': '肝炎',
    'OPEN WOUNDS TO LIMBS, INITIAL ENCOUNTER': '肢体开放伤口(初次)',
    'ANXIETY AND FEAR-RELATED DISORDERS': '焦虑与恐惧相关障碍',
    'POSTPROCEDURAL OR POSTOPERATIVE GENITOURINARY SYSTEM COMPLICATION': '术后泌尿生殖系统并发症',
    'MALIGNANT NEUROENDOCRINE TUMORS': '恶性神经内分泌肿瘤',
    'POSTTHROMBOTIC SYNDROME AND VENOUS INSUFFICIENCY/HYPERTENSION': '血栓后综合征/静脉功能不全',
    'ENDOCRINE SYSTEM CANCERS - THYROID': '甲状腺癌',
    'MULTIPLE SCLEROSIS': '多发性硬化症',
    'OTHER SPECIFIED AND UNSPECIFIED UPPER RESPIRATORY DISEASE': '上呼吸道疾病(未特指)',
    'OTHER SPECIFIED BONE DISEASE AND MUSCULOSKELETAL DEFORMITIES': '其他骨病与肌骨畸形',
    'POSTPROCEDURAL OR POSTOPERATIVE MUSCULOSKELETAL SYSTEM COMPLICATION': '术后肌骨系统并发症',
    'OTHER SPECIFIED INJURY': '其他特指损伤',
    'SPRAINS AND STRAINS, INITIAL ENCOUNTER': '扭伤与拉伤(初次)',
    'PERSONALITY DISORDERS': '人格障碍',
    'ARTERIAL DISSECTIONS': '动脉夹层',
    'ESSENTIAL HYPERTENSION': '原发性高血压',
    'PULMONARY HEART DISEASE': '肺源性心脏病',
    'NONMALIGNANT BREAST CONDITIONS': '非恶性乳腺疾病',
    'CARDIAC ARREST AND VENTRICULAR FIBRILLATION': '心脏骤停与心室颤动',
    'STRESS FRACTURE, INITIAL ENCOUNTER': '应力性骨折(初次)',
    'DISLOCATIONS, INITIAL ENCOUNTER': '关节脱位(初次)',
    'PARALYSIS (OTHER THAN CEREBRAL PALSY)': '瘫痪(非脑瘫)',
    'TOXIC EFFECTS, INITIAL ENCOUNTER': '毒性反应(初次)',
    'BENIGN OVARIAN CYST': '良性卵巢囊肿',
    'OTHER SPECIFIED JOINT DISORDERS': '其他关节疾病',
    'OPEN WOUNDS OF TRUNK, INITIAL ENCOUNTER': '躯干开放伤口(初次)',
    'POSTPROCEDURAL OR POSTOPERATIVE SKIN COMPLICATION': '术后皮肤并发症',
    'GASTROINTESTINAL CANCERS - ESOPHAGUS': '食管癌',
    'SEQUELA OF HEMORRHAGIC CEREBROVASCULAR DISEASE': '出血性脑血管病后遗症',
    'POSTPROCEDURAL OR POSTOPERATIVE CIRCULATORY SYSTEM COMPLICATION': '术后循环系统并发症',
    'GASTROINTESTINAL CANCERS - BILE DUCT': '胆管癌',
    'MATERNAL INTRAUTERINE INFECTION': '母体宫内感染',
    'FRACTURE OF THE NECK OF THE FEMUR (HIP), SUBSEQUENT ENCOUNTER': '股骨颈骨折(后续)',
    'GASTROINTESTINAL CANCERS - ALL OTHER TYPES': '其他胃肠道癌',
    'FRACTURE OF LOWER LIMB (EXCEPT HIP), SUBSEQUENT ENCOUNTER': '下肢骨折(后续,不含髋)',
    'SEXUALLY TRANSMITTED INFECTIONS (EXCLUDING HIV AND HEPATITIS)': '性传播感染(不含HIV/肝炎)',
    'NEURO-OPHTHALMOLOGY': '神经眼科学',
    'PERINATAL INFECTIONS': '围产期感染',
    'PARASITIC, OTHER SPECIFIED AND UNSPECIFIED INFECTIONS': '寄生虫及其他感染',
    'LOW BACK PAIN': '腰背痛',
    'TRAUMATIC BRAIN INJURY (TBI); CONCUSSION, SUBSEQUENT ENCOUNTER': '创伤性脑损伤/脑震荡(后续)',
    'NEPHRITIS; NEPHROSIS; RENAL SCLEROSIS': '肾炎/肾病变/肾硬化',
    'HEMOLYTIC ANEMIA': '溶血性贫血',
    'OTHER SPECIFIED AND UNSPECIFIED CIRCULATORY DISEASE': '其他循环系统疾病(未特指)',
    'AORTIC AND PERIPHERAL ARTERIAL EMBOLISM OR THROMBOSIS': '主动脉及外周动脉栓塞或血栓',
    'NONINFECTIOUS HEPATITIS': '非感染性肝炎',
    'INJURY TO BLOOD VESSELS, INITIAL ENCOUNTER': '血管损伤(初次)',
    'NUTRITIONAL DEFICIENCIES': '营养缺乏症',
    'HEMORRHAGE AFTER FIRST TRIMESTER': '孕早期后出血',
    'GASTROINTESTINAL CANCERS - SMALL INTESTINE': '小肠癌',
    'OTHER UNSPECIFIED INJURY': '其他未特指损伤',
    'COMPLICATIONS SPECIFIED DURING THE PUERPERIUM': '产褥期并发症',
    'RESPIRATORY CONGENITAL MALFORMATIONS': '呼吸系统先天性畸形',
    'SPINAL CORD INJURY (SCI), INITIAL ENCOUNTER': '脊髓损伤(初次)',
    'GASTROINTESTINAL CANCERS - ANUS': '肛门癌',
    'POSTPROCEDURAL OR POSTOPERATIVE NERVOUS SYSTEM COMPLICATION': '术后神经系统并发症',
    'GASTROINTESTINAL CANCERS - GALLBLADDER': '胆囊癌',
    'ENCOUNTER FOR OBSERVATION AND EXAMINATION FOR CONDITIONS RULED OUT (EXCLUDES INFECTIOUS DISEASE, NEOPLASM, MENTAL DISORDERS)': '排除性观察/检查就诊',
    'GASTROINTESTINAL AND BILIARY PERFORATION': '胃肠道与胆道穿孔',
    'HODGKIN LYMPHOMA': '霍奇金淋巴瘤',
    'RESPIRATORY PERINATAL CONDITION': '围产期呼吸系统疾病',
    'FRACTURE OF THE UPPER LIMB, SUBSEQUENT ENCOUNTER': '上肢骨折(后续)',
    'INJURY TO NERVES, MUSCLES AND TENDONS, INITIAL ENCOUNTER': '神经肌肉肌腱损伤(初次)',
    'FOODBORNE INTOXICATIONS': '食物中毒',
    'FRACTURE OF TORSO, SUBSEQUENT ENCOUNTER': '躯干骨折(后续)',
    'SYMPTOMS OF MENTAL AND SUBSTANCE USE CONDITIONS': '精神与物质使用症状',
    'FRACTURE OF THE SPINE AND BACK, SUBSEQUENT ENCOUNTER': '脊柱与背部骨折(后续)',
    'NEOPLASM-RELATED ENCOUNTERS': '肿瘤相关就诊',
    'MALIGNANT NEOPLASM, UNSPECIFIED': '未特指恶性肿瘤',
    'SHOCK': '休克',
    'FUNGAL INFECTIONS': '真菌感染',
    'BACTERIAL INFECTIONS': '细菌感染',
    'AMPUTATION OF A LIMB, INITIAL ENCOUNTER': '肢体截肢(初次)',
    'CHRONIC PHLEBITIS; THROMBOPHLEBITIS AND THROMBOEMBOLISM': '慢性静脉炎/血栓栓塞',
    'POSTPROCEDURAL OR POSTOPERATIVE ENDOCRINE OR METABOLIC COMPLICATION': '术后内分泌/代谢并发症',
    'GASTROINTESTINAL CANCERS - PERITONEUM': '腹膜癌',
    'HALLUCINOGEN-RELATED DISORDERS': '致幻剂相关障碍',
    'CARDIAC CANCERS': '心脏癌',
    'MOLAR PREGNANCY AND OTHER ABNORMAL PRODUCTS OF CONCEPTION': '葡萄胎/异常妊娠产物',
    'PATHOLOGICAL FRACTURE, SUBSEQUENT ENCOUNTER': '病理性骨折(后续)',
    'INJURY, SEQUELA': '损伤后遗症',
    'CEREBRAL PALSY': '脑性瘫痪',
    'RESPIRATORY DISTRESS SYNDROME': '呼吸窘迫综合征',
    'NEONATAL CEREBRAL DISORDERS': '新生儿脑部疾病',
    'MENTAL AND SUBSTANCE USE DISORDERS IN REMISSION': '缓解期精神与物质使用障碍',
    'CRUSHING INJURY, INITIAL ENCOUNTER': '挤压伤(初次)',
    'SPINAL CORD INJURY (SCI), SUBSEQUENT ENCOUNTER': '脊髓损伤(后续)',
    'OTHER SPECIFIED CNS INFECTION AND POLIOMYELITIS': '其他中枢神经系统感染/脊髓灰质炎',
    'COMPLICATION OF INTERNAL ORTHOPEDIC DEVICE OR IMPLANT, SUBSEQUENT ENCOUNTER': '骨科内置器械并发症(后续)',
    'BURNS AND CORROSION, SUBSEQUENT ENCOUNTER': '烧伤与腐蚀(后续)',
    'OBSTETRIC HISTORY AFFECTING CARE IN PREGNANCY': '产科史影响妊娠护理',
    'EARLY, FIRST OR UNSPECIFIED TRIMESTER HEMORRHAGE': '早孕期出血',
    'COMPLICATION OF OTHER SURGICAL OR MEDICAL CARE, INJURY, SUBSEQUENT ENCOUNTER': '手术/医疗并发症(后续)',
    'TRAUMATIC ARTHROPATHY': '创伤性关节病',
    'FRACTURE OF HEAD AND NECK, SUBSEQUENT ENCOUNTER': '头颈部骨折(后续)',
    'HEMORRHAGIC AND HEMATOLOGIC DISORDERS OF NEWBORN': '新生儿出血与血液疾病',
    'STRESS FRACTURE, SUBSEQUENT ENCOUNTER': '应力性骨折(后续)',
    'MEDICAL EXAMINATION/EVALUATION': '医学检查/评估',
    'COMPLICATIONS OF ACUTE MYOCARDIAL INFARCTION': '急性心肌梗死并发症',
    'IMMUNE-MEDIATED/REACTIVE ARTHROPATHIES': '免疫介导/反应性关节病',
    'BIRTH TRAUMA': '产伤',
    'COMPLICATION OF CARDIOVASCULAR DEVICE, IMPLANT OR GRAFT, SUBSEQUENT ENCOUNTER': '心血管器械并发症(后续)',
    'OPEN WOUNDS TO LIMBS, SUBSEQUENT ENCOUNTER': '肢体开放伤口(后续)',
    'SUPERFICIAL INJURY; CONTUSION, SUBSEQUENT ENCOUNTER': '表浅损伤/挫伤(后续)',
    'INTERNAL ORGAN INJURY, SUBSEQUENT ENCOUNTER': '内脏损伤(后续)',
    'DISLOCATIONS, SUBSEQUENT ENCOUNTER': '关节脱位(后续)',
    'POSTPROCEDURAL OR POSTOPERATIVE EYE COMPLICATION': '术后眼部并发症',
    'EXPOSURE, ENCOUNTERS, SCREENING OR CONTACT WITH INFECTIOUS DISEASE': '传染病暴露/筛查/接触就诊',
    'COMPLICATION, SEQUELA': '并发症后遗症',
    'ATYPICAL FRACTURE, INITIAL ENCOUNTER': '非典型骨折(初次)',
    'SPRAINS AND STRAINS, SUBSEQUENT ENCOUNTER': '扭伤与拉伤(后续)',
    'NEUROGENIC/NEUROPATHIC ARTHROPATHY': '神经性关节病',
    'POSTPROCEDURAL OR POSTOPERATIVE EAR AND/OR MASTOID PROCESS COMPLICATION': '术后耳/乳突并发症',
    'OTHER SPECIFIED INJURY, SUBSEQUENT ENCOUNTER': '其他特指损伤(后续)',
    'INJURY TO NERVES, MUSCLES AND TENDONS, SUBSEQUENT ENCOUNTER': '神经肌肉肌腱损伤(后续)',
    'TOXIC EFFECTS, SUBSEQUENT ENCOUNTER': '毒性反应(后续)',
    'OPEN WOUNDS OF TRUNK, SUBSEQUENT ENCOUNTER': '躯干开放伤口(后续)',
    'COMPLICATION OF GENITOURINARY DEVICE, IMPLANT OR GRAFT, SUBSEQUENT ENCOUNTER': '泌尿生殖器械并发症(后续)',
    'NEWBORN AFFECTED BY MATERNAL CONDITIONS OR COMPLICATIONS OF LABOR/DELIVERY': '新生儿受母体/产程并发症影响',
    'AMPUTATION OF OTHER BODY PARTS, INITIAL ENCOUNTER': '其他身体部位截肢(初次)',
    'POSTPROCEDURAL OR POSTOPERATIVE COMPLICATIONS OF THE SPLEEN': '术后脾脏并发症',
    'PATHOLOGICAL, STRESS AND ATYPICAL FRACTURES, SEQUELA': '病理性/应力/非典型骨折后遗症',
    'ADVERSE EFFECTS OF DRUGS AND MEDICAMENTS, INITIAL ENCOUNTER': '药物不良反应(初次)',
    'OTHER SPECIFIED CHRONIC ARTHROPATHY': '其他特指慢性关节病',
    'OPEN WOUNDS OF HEAD AND NECK, SUBSEQUENT ENCOUNTER': '头颈部开放伤口(后续)',
    'CRUSHING INJURY, SUBSEQUENT ENCOUNTER': '挤压伤(后续)',
    'ANESTHESIA COMPLICATIONS DURING PREGNANCY': '妊娠期麻醉并发症',
    'ENDOCRINE SYSTEM CANCERS - PARATHYROID': '甲状旁腺癌',
    'INJURY TO BLOOD VESSELS, SUBSEQUENT ENCOUNTER': '血管损伤(后续)',
    'ATYPICAL FRACTURE, SUBSEQUENT ENCOUNTER': '非典型骨折(后续)',
}


def translate_diagnosis(en_name):
    """英文病名 → 中文；精确匹配映射表，映射不到则保留英文原名（保证不重复）"""
    if not en_name:
        return en_name
    name = str(en_name).strip()
    if name in DIAGNOSIS_CN_MAP:
        return DIAGNOSIS_CN_MAP[name]
    return name  # 映射不到则保留英文原名，避免不同病名翻译成相同中文


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

    # 1. 标准化区域（所有 County 都纳入，不再剔除非NYC数据）
    df['region'] = df['Hospital County'].map(COUNTY_TO_REGION)
    # 未匹配到的 County 丢弃（COUNTY_TO_REGION 已经覆盖所有 57 个可能值，正常不会到这里）
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
    print(f"      清洗后记录数: {len(df):,} 条 (剔除 {before - len(df)} 条空值/无效County)")

    # 6. 动态读取真实年份（升序）
    years = sorted(df['Discharge Year'].astype(int).astype(str).unique().tolist())

    # 7. 地区按记录数**降序**排序（病例多的大市放前面），'all' 永远放第一个
    region_counts = df['region'].value_counts().sort_values(ascending=False)
    regions_sorted_by_count = region_counts.index.tolist()
    regions = ['all'] + regions_sorted_by_count

    # 同时构造中文 label 映射（按同样顺序）
    region_labels = {}
    for r in regions:
        region_labels[r] = REGION_CN_NAMES.get(r, r)

    # 打印信息：展示病例数 Top10 地区
    print(f"      真实年份: {years}")
    print(f"      真实地区数: {len(regions_sorted_by_count)} 个 (Top10按病例数降序):")
    for i, (r, cnt) in enumerate(region_counts.head(10).items()):
        cn = REGION_CN_NAMES.get(r, r)
        print(f"        {i+1:>2}. {cn:18s} ({r:13s}) → {cnt:>7,} 条")
    if len(region_counts) > 10:
        print(f"        ... 其余 {len(region_counts) - 10} 个地区")

    return df, years, regions, region_labels


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

    # 2. 加载数据（动态读取真实年份和地区，按病例数降序排序）
    df_raw, years, regions, region_labels = load_and_clean_data()

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

    # 4. 写入 meta key（包含真实维度+中文label，前端据此动态加载筛选器）
    meta = {
        'build_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
        'years': years,
        'regions': regions,
        'regionLabels': region_labels,
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
