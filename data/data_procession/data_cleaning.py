import pandas as pd
import numpy as np
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')


def generate_cleaning_report(df_before, df_after, issues_found):
    """生成数据清洗报告"""
    print("\n" + "=" * 60)
    print("📊 数据清洗报告")
    print("=" * 60)
    print(f"清洗前数据量: {len(df_before):,} 条")
    print(f"清洗后数据量: {len(df_after):,} 条")
    print(f"删除数据量: {len(df_before) - len(df_after):,} 条")
    if len(df_before) > 0:
        print(f"删除比例: {(len(df_before) - len(df_after)) / len(df_before) * 100:.2f}%")

    print("\n--- 发现并修正的问题 ---")
    for issue, count in issues_found.items():
        print(f"  ✅ {issue}: {count:,} 条")
    print("=" * 60)


def clean_medical_data(file_path, sample_size=None):
    """医疗数据完整清洗函数"""
    print(f"📂 正在加载数据: {file_path} ...")

    # ============ 1. 数据加载 ============
    if file_path.endswith('.xlsx'):
        if sample_size:
            df = pd.read_excel(file_path, nrows=sample_size)
            print(f"📌 样本模式：仅读取前 {sample_size:,} 条数据")
        else:
            df = pd.read_excel(file_path)
    elif file_path.endswith('.csv'):
        if sample_size:
            df = pd.read_csv(file_path, encoding='utf-8', nrows=sample_size)
            print(f"📌 样本模式：仅读取前 {sample_size:,} 条数据")
        else:
            df = pd.read_csv(file_path, encoding='utf-8')
    else:
        raise ValueError("不支持的文件格式，请使用 .xlsx 或 .csv")

    original_count = len(df)
    print(f"实际加载数据量: {original_count:,} 条")

    issues_found = {}
    df_cleaned = df.copy()

    # ============ 2. 删除完全重复的行（去重） ============
    duplicates = df_cleaned.duplicated().sum()
    if duplicates > 0:
        df_cleaned = df_cleaned.drop_duplicates()
        issues_found['删除重复记录'] = duplicates
        print(f"  ✅ 删除了 {duplicates:,} 条重复记录")

    # ============ 3. 检查空行 ============
    empty_rows = df_cleaned.isna().all(axis=1).sum()
    if empty_rows > 0:
        df_cleaned = df_cleaned.dropna(how='all')
        issues_found['删除完全空行'] = empty_rows
        print(f"  ✅ 删除了 {empty_rows:,} 条完全空行")

    # ============ 4. 年龄分组验证 ============
    valid_age_groups = ['70 or Older', '50 to 69', '30 to 49', '18 to 29', '0 to 17']
    invalid_age = ~df_cleaned['Age Group'].isin(valid_age_groups)
    if invalid_age.sum() > 0:
        issues_found['年龄分组异常→设为Unknown'] = invalid_age.sum()
        df_cleaned.loc[invalid_age, 'Age Group'] = 'Unknown'
        print(f"  ✅ 修正了 {invalid_age.sum():,} 条年龄分组异常")

    # ============ 5. 性别标准化 ============
    gender_map = {'Male': 'M', 'Female': 'F', '男': 'M', '女': 'F'}
    df_cleaned['Gender'] = df_cleaned['Gender'].replace(gender_map)
    invalid_gender = ~df_cleaned['Gender'].isin(['M', 'F'])
    if invalid_gender.sum() > 0:
        issues_found['性别异常→设为空'] = invalid_gender.sum()
        df_cleaned.loc[invalid_gender, 'Gender'] = np.nan
        print(f"  ✅ 修正了 {invalid_gender.sum():,} 条性别异常")

    # ============ 6. 住院天数验证 ============
    df_cleaned['Length of Stay'] = pd.to_numeric(df_cleaned['Length of Stay'], errors='coerce')

    invalid_los = df_cleaned['Length of Stay'] < 0
    if invalid_los.sum() > 0:
        issues_found['住院天数为负→设为0'] = invalid_los.sum()
        df_cleaned.loc[invalid_los, 'Length of Stay'] = 0
        print(f"  ✅ 修正了 {invalid_los.sum():,} 条负住院天数")

    too_long = df_cleaned['Length of Stay'] > 365
    if too_long.sum() > 0:
        issues_found['⚠️ 住院超1年（已保留，需人工审核）'] = too_long.sum()
        print(f"  ⚠️ 发现 {too_long.sum():,} 条住院超过1年的记录（已保留）")

    # ============ 7. 入院类型验证 ============
    valid_admissions = ['Emergency', 'Urgent', 'Elective', 'Newborn', 'Trauma']
    invalid_admission = ~df_cleaned['Type of Admission'].isin(valid_admissions)
    if invalid_admission.sum() > 0:
        issues_found['入院类型异常→设为Unknown'] = invalid_admission.sum()
        df_cleaned.loc[invalid_admission, 'Type of Admission'] = 'Unknown'
        print(f"  ✅ 修正了 {invalid_admission.sum():,} 条入院类型异常")

    # ============ 8. 出生体重验证（关键修改） ============
    # 【要求1】非新生儿 Birth Weight 设为 "N/A"
    is_newborn = df_cleaned['Type of Admission'] == 'Newborn'

    # 先转为数值，便于验证
    df_cleaned['Birth Weight'] = pd.to_numeric(df_cleaned['Birth Weight'], errors='coerce')

    # 非新生儿 → "N/A"（字符串）
    df_cleaned.loc[~is_newborn, 'Birth Weight'] = 'N/A'

    # 新生儿体重异常验证（只对数值类型操作）
    newborn_mask = is_newborn & df_cleaned['Birth Weight'].notna()
    # 只对数值类型的行进行范围判断
    invalid_bw_mask = (
            is_newborn &
            df_cleaned['Birth Weight'].apply(lambda x: isinstance(x, (int, float)) and (x < 500 or x > 6000))
    )
    if invalid_bw_mask.sum() > 0:
        issues_found['新生儿体重异常→设为N/A'] = invalid_bw_mask.sum()
        df_cleaned.loc[invalid_bw_mask, 'Birth Weight'] = 'N/A'
        print(f"  ✅ 修正了 {invalid_bw_mask.sum():,} 条新生儿体重异常")

    # 新生儿中，如果是NaN也设为"N/A"
    df_cleaned.loc[is_newborn & df_cleaned['Birth Weight'].isna(), 'Birth Weight'] = 'N/A'

    # ============ 9. 费用字段处理（数据类型标准化） ============
    money_cols = ['Total Charges', 'Total Costs']
    for col in money_cols:
        # 【要求2】移除逗号并转换为浮点数
        if df_cleaned[col].dtype == 'object':
            df_cleaned[col] = df_cleaned[col].astype(str).str.replace(',', '', regex=False)
            df_cleaned[col] = df_cleaned[col].str.replace('$', '', regex=False)
        df_cleaned[col] = pd.to_numeric(df_cleaned[col], errors='coerce')

        negative_count = (df_cleaned[col] < 0).sum()
        if negative_count > 0:
            issues_found[f'{col}为负数→设为空'] = negative_count
            df_cleaned.loc[df_cleaned[col] < 0, col] = np.nan
            print(f"  ✅ 修正了 {negative_count:,} 条 {col} 负数")

        extreme = (df_cleaned[col] > 100000000) & df_cleaned[col].notna()
        if extreme.sum() > 0:
            issues_found[f'{col}异常高→设为空'] = extreme.sum()
            df_cleaned.loc[extreme, col] = np.nan
            print(f"  ✅ 修正了 {extreme.sum():,} 条 {col} 异常高值")

    # ============ 10. 费用逻辑验证 ============
    charges_less_cost = (df_cleaned['Total Charges'] < df_cleaned['Total Costs']) & \
                        df_cleaned['Total Charges'].notna() & \
                        df_cleaned['Total Costs'].notna()
    if charges_less_cost.sum() > 0:
        issues_found['⚠️ 收费低于成本（已保留，需人工审核）'] = charges_less_cost.sum()
        print(f"  ⚠️ 发现 {charges_less_cost.sum():,} 条收费低于成本的记录")

    # ============ 11. 种族验证 ============
    valid_races = ['White', 'Black/African American', 'Other Race', 'Asian',
                   'Native American', 'Unknown']
    invalid_race = ~df_cleaned['Race'].isin(valid_races)
    if invalid_race.sum() > 0:
        issues_found['种族异常→设为Unknown'] = invalid_race.sum()
        df_cleaned.loc[invalid_race, 'Race'] = 'Unknown'
        print(f"  ✅ 修正了 {invalid_race.sum():,} 条种族异常")

    # ============ 12. 民族验证 ============
    valid_ethnicity = ['Spanish/Hispanic', 'Not Span/Hispanic', 'Unknown']
    invalid_ethnicity = ~df_cleaned['Ethnicity'].isin(valid_ethnicity)
    if invalid_ethnicity.sum() > 0:
        issues_found['民族异常→设为Unknown'] = invalid_ethnicity.sum()
        df_cleaned.loc[invalid_ethnicity, 'Ethnicity'] = 'Unknown'
        print(f"  ✅ 修正了 {invalid_ethnicity.sum():,} 条民族异常")

    # ============ 13. 邮编处理（标准化格式） ============
    if 'Zip Code - 3 digits' in df_cleaned.columns:
        df_cleaned['Zip Code - 3 digits'] = df_cleaned['Zip Code - 3 digits'].astype(str)
        df_cleaned.loc[df_cleaned['Zip Code - 3 digits'] == 'nan', 'Zip Code - 3 digits'] = ''
        df_cleaned['Zip Code - 3 digits'] = df_cleaned['Zip Code - 3 digits'].str.extract(r'(\d{3})')
        df_cleaned.loc[df_cleaned['Zip Code - 3 digits'].isna(), 'Zip Code - 3 digits'] = 'Unknown'
        invalid_zip = df_cleaned['Zip Code - 3 digits'] == 'Unknown'
        if invalid_zip.sum() > 0:
            issues_found['邮编异常→设为Unknown'] = invalid_zip.sum()
            print(f"  ✅ 修正了 {invalid_zip.sum():,} 条邮编异常")

    # ============ 14. 缺失值填充（规范处理） ============
    df_cleaned['Payment Typology 2'] = df_cleaned['Payment Typology 2'].fillna('None')
    df_cleaned['Payment Typology 3'] = df_cleaned['Payment Typology 3'].fillna('None')
    df_cleaned['CCSR Procedure Code'] = df_cleaned['CCSR Procedure Code'].fillna('No Procedure')
    df_cleaned['CCSR Procedure Description'] = df_cleaned['CCSR Procedure Description'].fillna('No Procedure')
    df_cleaned['CCSR Diagnosis Code'] = df_cleaned['CCSR Diagnosis Code'].fillna('No Diagnosis')
    df_cleaned['CCSR Diagnosis Description'] = df_cleaned['CCSR Diagnosis Description'].fillna('No Diagnosis')
    df_cleaned['Patient Disposition'] = df_cleaned['Patient Disposition'].fillna('Unknown')
    df_cleaned['Emergency Department Indicator'] = df_cleaned['Emergency Department Indicator'].fillna('N')

    # ============ 15. 删除关键字段为空的行 ============
    critical_cols = ['Facility Name']
    before_drop = len(df_cleaned)
    df_cleaned = df_cleaned.dropna(subset=critical_cols, how='any')
    dropped = before_drop - len(df_cleaned)
    if dropped > 0:
        issues_found['删除机构名称为空的行'] = dropped
        print(f"  ✅ 删除了 {dropped:,} 条机构名称为空的记录")

    # ============ 16. 生成清洗报告 ============
    generate_cleaning_report(df, df_cleaned, issues_found)

    return df_cleaned


if __name__ == "__main__":
    # 指定文件路径
    file_path = r'D:\project\Hwadee\009 医养项目数据\Hospital_Inpatient_Discharges__SPARCS_De-Identified___2021_20231012.csv\Hospital_Inpatient_Discharges__SPARCS_De-Identified___2021_20231012.csv'

    # 测试模式 - 只读前10000条
    print("\n" + "=" * 60)
    print("🔬 测试模式：读取前 10,000 条数据")
    print("=" * 60)
    cleaned_df = clean_medical_data(file_path)

    # 导出结果
    output_file = 'cleaned_hospital_data.csv'
    cleaned_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n✅ 清洗后的数据已保存至: {output_file}")

    # 数据概览
    print("\n--- 📈 数据概览 ---")
    print(f"总记录数: {len(cleaned_df):,}")
    print(f"总列数: {len(cleaned_df.columns)}")
    print(f"内存占用: {cleaned_df.memory_usage(deep=True).sum() / 1024 ** 2:.2f} MB")

    # 数值字段统计
    numeric_cols = ['Length of Stay', 'Total Charges', 'Total Costs']
    numeric_cols = [c for c in numeric_cols if c in cleaned_df.columns]
    if numeric_cols:
        print("\n--- 数值字段统计 ---")
        print(cleaned_df[numeric_cols].describe())

    # Birth Weight 分布（查看"N/A"占比）
    print("\n--- Birth Weight 分布 ---")
    if 'Birth Weight' in cleaned_df.columns:
        print(cleaned_df['Birth Weight'].value_counts().head(10))

    # 分类字段分布
    print("\n--- 关键字段分布 ---")
    for col in ['Age Group', 'Gender', 'Type of Admission', 'Race']:
        if col in cleaned_df.columns:
            print(f"\n{col}:")
            print(cleaned_df[col].value_counts().head(5))
