# -*- coding: utf-8 -*-
"""
智慧医疗分析平台 - AI智能探索舱 数据预构建脚本（重写版）
================================================
功能：
    1. 读取原始 CSV 数据 cleaned_hospital_data.csv
    2. 按多个维度聚合统计，构建 AI 问答用的数据缓存（Redis）
    3. 保留推荐问题 + 元信息缓存

缓存 Key 设计（前缀 smartmed:aichat:）：
    suggested                      6 个推荐问题（静态）
    meta                           构建元信息
    stats:summary                  全局汇总（总记录数、年份、区域范围等）
    stats:year:{year}              按年份汇总
    stats:year_region:{year}:{region}   按年份+区域汇总（最详细）
    stats:age_group                年龄段全局分布
    stats:diagnoses                全局 Top 疾病
    stats:payment                  支付方式分布

每个 stats 对象包含：
    - total_discharges, total_charges, total_costs, avg_charges, avg_costs, avg_stay_days
    - age_group_distribution: {age_group: count}
    - gender_distribution, race_distribution
    - top_diagnoses: [{code, desc, count, avg_charge}, ...] (Top 15)
    - top_procedures: [{code, desc, count, avg_charge}, ...] (Top 10)
    - payment_distribution: {payment: {count, total_charge}}
    - severity_distribution: {severity: {count, avg_charge}}
    - admission_type_distribution, disposition_distribution
    - emergency_department_ratio: {y, n}

运行方式：
    python data/build_aichat_cache.py
"""

import os
import sys
import json
import time
from collections import Counter, defaultdict

try:
    import redis
except ImportError:
    print("[错误] 缺少 redis 依赖，请先安装: pip install redis")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("[错误] 缺少 pandas 依赖，请先安装: pip install pandas")
    sys.exit(1)

# ============ 配置 ============
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
KEY_PREFIX = 'smartmed:aichat:'

# 原始 CSV 路径（上级目录）
CSV_PATH = os.path.abspath(os.path.join(PROJECT_ROOT, '..', 'cleaned_hospital_data.csv'))

# ============ 预置推荐问题（覆盖 CSV 各维度） ============
DEFAULT_SUGGESTED_QUESTIONS = [
    {'id': 'q1', 'text': '按支付方式统计总费用'},
    {'id': 'q2', 'text': 'Bronx区急诊患者画像'},
    {'id': 'q3', 'text': '各年龄段疾病分布对比'},
    {'id': 'q4', 'text': '不同严重程度的费用差异'},
    {'id': 'q5', 'text': '70岁以上人群的高发疾病'},
    {'id': 'q6', 'text': '手术类与内科类治疗费用对比'},
    {'id': 'q7', 'text': '住院天数最长的10种疾病'},
    {'id': 'q8', 'text': '不同种族的医疗费用差异'},
]


def write_cache(r, key, value):
    full_key = f"{KEY_PREFIX}{key}"
    payload = json.dumps(value, ensure_ascii=False)
    r.set(full_key, payload)
    return len(payload)


def safe_num(v):
    """转 float，失败返回 0"""
    try:
        f = float(v)
        if f != f:  # NaN
            return 0.0
        return f
    except Exception:
        return 0.0


def build_stats_block(df_sub):
    """对一个数据子集（DataFrame）构建统计块。返回 dict。"""
    n = len(df_sub)
    if n == 0:
        return {'total_discharges': 0}

    # 基础聚合
    total_charges = safe_num(df_sub['Total Charges'].sum())
    total_costs = safe_num(df_sub['Total Costs'].sum())
    avg_charges = total_charges / n
    avg_costs = total_costs / n
    avg_stay = safe_num(df_sub['Length of Stay'].mean())

    # 年龄段分布
    age_dist = df_sub['Age Group'].value_counts().to_dict()

    # 性别分布
    gender_dist = df_sub['Gender'].value_counts().to_dict()

    # 种族分布
    race_dist = df_sub['Race'].value_counts().to_dict()

    # 民族分布
    ethnicity_dist = df_sub['Ethnicity'].value_counts().to_dict()

    # Top 15 疾病（按 CCSR Diagnosis Description）
    diag_stats = df_sub.groupby('CCSR Diagnosis Description').agg(
        count=('Total Charges', 'count'),
        avg_charge=('Total Charges', 'mean'),
        avg_stay=('Length of Stay', 'mean'),
    ).sort_values('count', ascending=False).head(15).reset_index()
    top_diagnoses = [
        {
            'desc': row['CCSR Diagnosis Description'],
            'count': int(row['count']),
            'avg_charge': round(safe_num(row['avg_charge']), 2),
            'avg_stay': round(safe_num(row['avg_stay']), 1),
        }
        for _, row in diag_stats.iterrows()
    ]

    # Top 10 手术（按 CCSR Procedure Description）
    # 过滤掉 "No Procedure"
    proc_df = df_sub[df_sub['CCSR Procedure Description'] != 'No Procedure']
    if len(proc_df) > 0:
        proc_stats = proc_df.groupby('CCSR Procedure Description').agg(
            count=('Total Charges', 'count'),
            avg_charge=('Total Charges', 'mean'),
        ).sort_values('count', ascending=False).head(10).reset_index()
        top_procedures = [
            {
                'desc': row['CCSR Procedure Description'],
                'count': int(row['count']),
                'avg_charge': round(safe_num(row['avg_charge']), 2),
            }
            for _, row in proc_stats.iterrows()
        ]
    else:
        top_procedures = []

    # 支付方式分布（3 列合并）
    payment_counter = Counter()
    payment_charge = defaultdict(float)
    for col in ['Payment Typology 1', 'Payment Typology 2', 'Payment Typology 3']:
        for pay, charge in zip(df_sub[col], df_sub['Total Charges']):
            if pd.notna(pay) and pay:
                payment_counter[pay] += 1
                payment_charge[pay] += safe_num(charge)
    payment_distribution = {
        k: {'count': v, 'total_charge': round(payment_charge[k], 2)}
        for k, v in payment_counter.most_common(15)
    }

    # 严重程度分布
    severity_stats = df_sub.groupby('APR Severity of Illness Description').agg(
        count=('Total Charges', 'count'),
        avg_charge=('Total Charges', 'mean'),
    ).reset_index()
    severity_distribution = {
        row['APR Severity of Illness Description']: {
            'count': int(row['count']),
            'avg_charge': round(safe_num(row['avg_charge']), 2),
        }
        for _, row in severity_stats.iterrows()
    }

    # 死亡风险分布
    risk_stats = df_sub.groupby('APR Risk of Mortality').agg(
        count=('Total Charges', 'count'),
        avg_charge=('Total Charges', 'mean'),
    ).reset_index()
    risk_distribution = {
        row['APR Risk of Mortality']: {
            'count': int(row['count']),
            'avg_charge': round(safe_num(row['avg_charge']), 2),
        }
        for _, row in risk_stats.iterrows()
    }

    # 入院方式分布
    admission_dist = df_sub['Type of Admission'].value_counts().to_dict()

    # 出院去向分布
    disposition_dist = df_sub['Patient Disposition'].value_counts().head(10).to_dict()

    # 急诊比例
    ed_series = df_sub['Emergency Department Indicator'].value_counts()
    emergency_department_ratio = {
        'y': int(ed_series.get('Y', 0)),
        'n': int(ed_series.get('N', 0)),
    }

    # 内科/外科分布
    med_surg_dist = df_sub['APR Medical Surgical Description'].value_counts().to_dict()

    # 医院数
    facility_count = int(df_sub['Facility Name'].nunique())

    return {
        'total_discharges': int(n),
        'total_charges': round(total_charges, 2),
        'total_costs': round(total_costs, 2),
        'avg_charges': round(avg_charges, 2),
        'avg_costs': round(avg_costs, 2),
        'avg_stay_days': round(avg_stay, 1),
        'facility_count': facility_count,
        'age_group_distribution': {k: int(v) for k, v in age_dist.items()},
        'gender_distribution': {k: int(v) for k, v in gender_dist.items()},
        'race_distribution': {k: int(v) for k, v in race_dist.items()},
        'ethnicity_distribution': {k: int(v) for k, v in ethnicity_dist.items()},
        'top_diagnoses': top_diagnoses,
        'top_procedures': top_procedures,
        'payment_distribution': payment_distribution,
        'severity_distribution': severity_distribution,
        'risk_distribution': risk_distribution,
        'admission_type_distribution': {k: int(v) for k, v in admission_dist.items()},
        'disposition_distribution': {k: int(v) for k, v in disposition_dist.items()},
        'emergency_department_ratio': emergency_department_ratio,
        'medical_surgical_distribution': {k: int(v) for k, v in med_surg_dist.items()},
    }


def main():
    print("=" * 60)
    print("🤖 智慧医疗分析平台 - AI智能探索舱 数据预构建（重写版）")
    print("=" * 60)

    # 1. 检查 CSV 文件
    print(f"\n[1/6] 读取原始 CSV 数据")
    print(f"      路径: {CSV_PATH}")
    if not os.path.exists(CSV_PATH):
        print(f"[错误] CSV 文件不存在: {CSV_PATH}")
        sys.exit(1)

    print("      正在加载 CSV（pandas）...")
    try:
        df = pd.read_csv(CSV_PATH, low_memory=False)
        print(f"      ✅ 加载完成: {len(df)} 行, {len(df.columns)} 列")
    except Exception as e:
        print(f"[错误] CSV 读取失败: {e}")
        sys.exit(1)

    # 2. 连接 Redis
    print(f"\n[2/6] 连接 Redis {REDIS_HOST}:{REDIS_PORT} (db={REDIS_DB})")
    try:
        r = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
            password=REDIS_PASSWORD, decode_responses=True
        )
        r.ping()
        print("      ✅ Redis 连接成功")
    except Exception as e:
        print(f"[错误] Redis 连接失败: {e}")
        sys.exit(1)

    # 3. 清除旧缓存（保留会话历史）
    old_keys = [k for k in r.keys(f'{KEY_PREFIX}*') if not k.startswith(f'{KEY_PREFIX}conv:')]
    if old_keys:
        r.delete(*old_keys)
        print(f"      🧹 已清除旧缓存 {len(old_keys)} 个 Key（保留会话历史）")

    # 4. 数据预处理
    print(f"\n[3/6] 数据预处理")
    # 取年份列表
    years = sorted(df['Discharge Year'].dropna().unique().tolist())
    years = [int(y) for y in years]
    print(f"      年份: {years}")

    # 取区域列表（Hospital Service Area）
    regions = sorted(df['Hospital Service Area'].dropna().unique().tolist())
    print(f"      服务区域: {regions}")

    # 取 county 列表
    counties = sorted(df['Hospital County'].dropna().unique().tolist())
    print(f"      医院县: {counties}")

    # 5. 构建统计缓存
    print(f"\n[4/6] 构建统计缓存（可能需要 30~60 秒）")

    # 5.1 全局汇总
    print(f"      构建 stats:summary ...")
    summary_stats = build_stats_block(df)
    summary_stats['years'] = years
    summary_stats['regions'] = regions
    summary_stats['counties'] = counties
    b = write_cache(r, 'stats:summary', summary_stats)
    print(f"      ✅ stats:summary ({b} bytes) - {summary_stats['total_discharges']} 条记录")

    # 5.2 按年份汇总
    for year in years:
        df_year = df[df['Discharge Year'] == year]
        key = f'stats:year:{year}'
        stats = build_stats_block(df_year)
        b = write_cache(r, key, stats)
        print(f"      ✅ {key} ({b} bytes) - {stats['total_discharges']} 条")

    # 5.3 按年份+区域汇总
    for year in years:
        for region in regions:
            df_sub = df[(df['Discharge Year'] == year) & (df['Hospital Service Area'] == region)]
            if len(df_sub) == 0:
                continue
            # region 转为安全 key（空格 → _）
            region_key = region.replace(' ', '_')
            key = f'stats:year_region:{year}:{region_key}'
            stats = build_stats_block(df_sub)
            b = write_cache(r, key, stats)

    print(f"      ✅ 按年份+区域汇总完成（{len(years) * len(regions)} 个组合）")

    # 5.4 按 county 汇总（更细粒度）
    for year in years:
        for county in counties:
            df_sub = df[(df['Discharge Year'] == year) & (df['Hospital County'] == county)]
            if len(df_sub) == 0:
                continue
            county_key = county.replace(' ', '_').replace('/', '_')
            key = f'stats:year_county:{year}:{county_key}'
            stats = build_stats_block(df_sub)
            write_cache(r, key, stats)
    print(f"      ✅ 按年份+县汇总完成")

    # 5.5 按年龄段全局汇总（跨年份）
    print(f"      构建按年龄段汇总 ...")
    age_groups = df['Age Group'].dropna().unique().tolist()
    for ag in age_groups:
        df_sub = df[df['Age Group'] == ag]
        ag_key = ag.replace(' ', '_').replace('/', '_')
        key = f'stats:age_group:{ag_key}'
        stats = build_stats_block(df_sub)
        write_cache(r, key, stats)
    print(f"      ✅ 按年龄段汇总完成（{len(age_groups)} 组）")

    # 6. 写入推荐问题和 meta
    print(f"\n[5/6] 写入推荐问题缓存...")
    suggested = DEFAULT_SUGGESTED_QUESTIONS
    b = write_cache(r, 'suggested', suggested)
    print(f"      → {len(suggested)} 个推荐问题, {b} bytes")

    print(f"\n[6/6] 写入 meta...")
    meta = {
        'build_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'csv_path': CSV_PATH,
        'csv_rows': len(df),
        'csv_cols': len(df.columns),
        'years': years,
        'regions': regions,
        'counties': counties,
        'age_groups': age_groups,
        'suggested_count': len(suggested),
        'key_prefix': KEY_PREFIX,
        'cache_keys': [
            'stats:summary',
            'stats:year:{year}',
            'stats:year_region:{year}:{region}',
            'stats:year_county:{year}:{county}',
            'stats:age_group:{age_group}',
        ],
    }
    b = write_cache(r, 'meta', meta)
    print(f"      → meta {b} bytes")

    # 7. 抽样验证
    print(f"\n[验证] 抽样读取...")
    s = json.loads(r.get(f'{KEY_PREFIX}suggested') or '[]')
    print(f"      suggested 数量: {len(s)}")
    m = json.loads(r.get(f'{KEY_PREFIX}meta') or '{}')
    print(f"      meta.build_at: {m.get('build_at')}")
    print(f"      meta.csv_rows: {m.get('csv_rows')}")
    summary = json.loads(r.get(f'{KEY_PREFIX}stats:summary') or '{}')
    print(f"      summary.total_discharges: {summary.get('total_discharges')}")
    print(f"      summary.top_diagnoses[0]: {summary.get('top_diagnoses', [{}])[0] if summary.get('top_diagnoses') else 'N/A'}")

    print(f"\n完成 🎉")
    print("=" * 60)
    print(f"  Key 前缀:    {KEY_PREFIX}*")
    print(f"  缓存 Key 类型:")
    print(f"    suggested                   推荐问题")
    print(f"    meta                        元信息")
    print(f"    stats:summary               全局汇总")
    print(f"    stats:year:{{year}}          按年份汇总")
    print(f"    stats:year_region:{{y}}:{{r}}   按年份+区域汇总")
    print(f"    stats:year_county:{{y}}:{{c}}   按年份+县汇总")
    print(f"    stats:age_group:{{ag}}       按年龄段汇总")
    print(f"  会话历史键:  {KEY_PREFIX}conv:* (动态写入)")
    print("=" * 60)


if __name__ == '__main__':
    main()
