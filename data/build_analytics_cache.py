# -*- coding: utf-8 -*-
"""Build Redis aggregates for the real multi-dimensional analytics page."""
import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_PATH =  r'C:\Users\86186\Desktop\SmartMed-BigData-LLM\cleaned_hospital_data.csv'
KEY_PREFIX = "smartmed:analytics:"
ROWS_KEY = f"{KEY_PREFIX}rows"
META_KEY = f"{KEY_PREFIX}meta"
FILTERS_KEY = f"{KEY_PREFIX}filters"
SOURCE_COLUMNS = [
    "Hospital County", "Facility Name", "Age Group", "Gender",
    "APR MDC Description", "CCSR Diagnosis Description",
    "APR Severity of Illness Description", "Payment Typology 1",
    "Discharge Year", "Length of Stay", "Total Charges", "Total Costs",
]
GROUP_COLUMNS = ["year", "region", "facility", "department", "disease", "gender", "ageGroup", "severity", "paymentType"]
AGE_GROUPS = {"0 to 17": "0-17岁", "18 to 29": "18-29岁", "30 to 49": "30-49岁", "50 to 69": "50-69岁", "70 or Older": "70岁以上"}
GENDER = {"M": "男", "F": "女"}
SEVERITY = {"Minor": "轻微", "Moderate": "中度", "Major": "严重", "Extreme": "极重"}
REGION_NAMES = {"Kings": "Brooklyn", "Richmond": "Staten Island"}
DEPARTMENTS = {
    "DISEASES AND DISORDERS OF THE CIRCULATORY SYSTEM": "心内科",
    "DISEASES AND DISORDERS OF THE RESPIRATORY SYSTEM": "呼吸科",
    "DISEASES AND DISORDERS OF THE NERVOUS SYSTEM": "神经科",
    "DISEASES AND DISORDERS OF THE DIGESTIVE SYSTEM": "消化科",
    "PREGNANCY, CHILDBIRTH AND THE PUERPERIUM": "妇产科",
    "NEWBORNS AND OTHER NEONATES WITH CONDITIONS ORIGINATING IN THE PERINATAL PERIOD": "新生儿科",
    "INFECTIOUS AND PARASITIC DISEASES (SYSTEMIC OR UNSPECIFIED SITES)": "感染科",
    "DISEASES AND DISORDERS OF THE MUSCULOSKELETAL SYSTEM AND CONNECTIVE TISSUE": "骨科",
    "ENDOCRINE, NUTRITIONAL AND METABOLIC DISEASES AND DISORDERS": "内分泌科",
    "ALCOHOL/DRUG USE AND ALCOHOL/DRUG INDUCED ORGANIC MENTAL DISORDERS": "精神科",
    "MYELOPROLIFERATIVE DISEASES AND DISORDERS, AND POORLY DIFFERENTIATED NEOPLASM": "肿瘤科",
    "DISEASES AND DISORDERS OF THE MALE REPRODUCTIVE SYSTEM": "泌尿科",
    "INJURIES, POISONINGS AND TOXIC EFFECTS OF DRUGS": "急诊科",
}


def normalized(chunk):
    data = chunk.copy()
    data["year"] = data["Discharge Year"].astype(str)
    data["region"] = data["Hospital County"].replace(REGION_NAMES).fillna("未提供")
    data["facility"] = data["Facility Name"].replace("", "未提供").fillna("未提供")
    data["department"] = data["APR MDC Description"].map(DEPARTMENTS).fillna("其他科室")
    data["disease"] = data["CCSR Diagnosis Description"].replace("", "未提供").fillna("未提供")
    data["gender"] = data["Gender"].map(GENDER).fillna("未知")
    data["ageGroup"] = data["Age Group"].map(AGE_GROUPS).fillna("未知")
    data["severity"] = data["APR Severity of Illness Description"].map(SEVERITY).fillna("未知")
    data["paymentType"] = data["Payment Typology 1"].replace("", "未提供").fillna("未提供")
    for source, target in (("Length of Stay", "totalStayDays"), ("Total Charges", "totalCharges"), ("Total Costs", "totalCosts")):
        data[target] = pd.to_numeric(data[source], errors="coerce")
    return data.dropna(subset=["totalStayDays", "totalCharges", "totalCosts"])


def build_aggregates(data_path, chunk_size):
    aggregates = defaultdict(lambda: [0, 0.0, 0.0, 0.0])
    source_rows = 0
    for index, chunk in enumerate(pd.read_csv(data_path, usecols=SOURCE_COLUMNS, chunksize=chunk_size, keep_default_na=False, low_memory=False), start=1):
        source_rows += len(chunk)
        data = normalized(chunk)
        grouped = data.groupby(GROUP_COLUMNS, dropna=False, observed=True).agg(
            count=("facility", "size"), totalStayDays=("totalStayDays", "sum"),
            totalCharges=("totalCharges", "sum"), totalCosts=("totalCosts", "sum"),
        ).reset_index()
        for values in grouped.itertuples(index=False, name=None):
            key, metrics = values[:len(GROUP_COLUMNS)], values[len(GROUP_COLUMNS):]
            target = aggregates[key]
            target[0] += int(metrics[0]); target[1] += float(metrics[1]); target[2] += float(metrics[2]); target[3] += float(metrics[3])
        print(f"[{index}] 已读取 {source_rows:,} 行，当前聚合 {len(aggregates):,} 条")
    return aggregates, source_rows


def rows_from(aggregates):
    rows = []
    for index, (key, metrics) in enumerate(aggregates.items(), start=1):
        row = dict(zip(GROUP_COLUMNS, key))
        row.update({"id": index, "count": metrics[0], "totalStayDays": round(metrics[1], 2), "totalCharges": round(metrics[2], 2), "totalCosts": round(metrics[3], 2)})
        rows.append(row)
    return rows


def filter_options(rows):
    fields = {"regions": "region", "facilities": "facility", "departments": "department", "genders": "gender", "ageGroups": "ageGroup", "severities": "severity", "paymentTypes": "paymentType"}
    return {name: [{"label": value, "value": value} for value in sorted({row[field] for row in rows})] for name, field in fields.items()}


def clear_prefix(client):
    pipeline, count = client.pipeline(transaction=False), 0
    for key in client.scan_iter(match=f"{KEY_PREFIX}*"):
        pipeline.delete(key); count += 1
        if count % 1000 == 0:
            pipeline.execute()
    pipeline.execute()
    return count


def write_cache(client, rows, source_rows):
    removed = clear_prefix(client)
    pipeline, mapping = client.pipeline(transaction=False), {}
    for row in rows:
        mapping[str(row["id"])] = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        if len(mapping) == 1000:
            pipeline.hset(ROWS_KEY, mapping=mapping); pipeline.execute(); mapping.clear()
    if mapping:
        pipeline.hset(ROWS_KEY, mapping=mapping); pipeline.execute()
    filters = filter_options(rows)
    meta = {"source": "cleaned_hospital_data.csv", "source_rows": source_rows, "aggregate_rows": len(rows), "years": sorted({row["year"] for row in rows}), "regions": [item["value"] for item in filters["regions"]], "build_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"), "key_prefix": KEY_PREFIX, "replaced_keys": removed}
    client.set(FILTERS_KEY, json.dumps(filters, ensure_ascii=False))
    client.set(META_KEY, json.dumps(meta, ensure_ascii=False))
    return meta


def main():
    parser = argparse.ArgumentParser(description="构建 Analytics Redis 聚合缓存")
    parser.add_argument("--data-path", default=os.getenv("SMARTMED_CLEAN_DATA_PATH", str(DEFAULT_DATA_PATH)))
    parser.add_argument("--chunk-size", type=int, default=100_000)
    parser.add_argument("--dry-run", action="store_true", help="只计算聚合，不连接 Redis")
    args = parser.parse_args()
    data_path = Path(args.data_path)
    if not data_path.is_file():
        raise SystemExit(f"找不到清洗数据文件: {data_path}")
    print(f"读取: {data_path}")
    aggregates, source_rows = build_aggregates(data_path, args.chunk_size)
    rows = rows_from(aggregates)
    print(f"完成聚合：{source_rows:,} 行 → {len(rows):,} 条 Analytics 记录")
    if args.dry_run:
        return
    try:
        import redis
    except ImportError:
        raise SystemExit("缺少 redis 依赖。请在 backend 环境执行: pip install -r requirements.txt")
    client = redis.Redis(host=os.getenv("REDIS_HOST", "127.0.0.1"), port=int(os.getenv("REDIS_PORT", "6379")), db=int(os.getenv("REDIS_DB", "0")), password=os.getenv("REDIS_PASSWORD"), decode_responses=True)
    client.ping()
    print("Redis 写入完成：", json.dumps(write_cache(client, rows, source_rows), ensure_ascii=False))


if __name__ == "__main__":
    main()