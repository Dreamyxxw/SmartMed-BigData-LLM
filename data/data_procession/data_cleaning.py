import pandas as pd
import numpy as np
import os
"""
文件读取：加载指定的原始 CSV 医疗数据集。  
数据去重：自动识别并移除数据集中完全重复的住院记录。  
医疗业务规则应用：根据 Type of Admission（入院类型）字段，将所有非新生儿的 Birth Weight（出生体重）字段重置为空值（NaN）。  
财务字段标准化：清理 Total Charges 和 Total Costs 字段，移除其中的逗号等特殊符号，并强制转换为标准的浮点数类型。 
数值字段清洗：提取 Length of Stay（住院天数）字段中的纯数字部分，并转换为数值类型。  
分类字段格式化：自动去除性别、种族、民族等文本分类字段前后的冗余空格。  
缺失值统一：将各种非标准缺失标识（如 Unknown、N/A、None、空字符串等）统一映射为标准的 NaN（空值）。  
"""
def clean_medical_data(input_file, output_file):
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"未找到文件: {input_file}")
        
    df = pd.read_csv(input_file, low_memory=False)
    
    df = df.drop_duplicates(keep='first')

    if 'Type of Admission' in df.columns and 'Birth Weight' in df.columns:
        non_newborn = df['Type of Admission'].astype(str).str.strip().str.lower() != 'newborn'
        df.loc[non_newborn, 'Birth Weight'] = np.nan

    financial_cols = ['Total Charges', 'Total Costs']
    for col in financial_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r'[$,]', '', regex=True).str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'Length of Stay' in df.columns:
         df['Length of Stay'] = df['Length of Stay'].astype(str).str.replace(r'[^0-9.]', '', regex=True)
         df['Length of Stay'] = pd.to_numeric(df['Length of Stay'], errors='coerce')

    categorical_cols = ['Gender', 'Race', 'Ethnicity', 'Type of Admission', 'Patient Disposition']
    for col in categorical_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            
    replace_list = ['Unknown', 'Not Specified', 'nan', 'NaN', 'None', '', 'N/A']
    df.replace(replace_list, np.nan, inplace=True)

    df.to_csv(output_file, index=False, encoding='utf-8')
"""
旧文件 (清洗前) 行数: 2101588
新文件 (清洗后) 行数: 2094484
差值: 7104
"""
if __name__ == "__main__":
    # 配置文件输入输出
    input_csv = r"C:\Users\12794\Downloads\Hospital_Inpatient_Discharges__SPARCS_De-Identified___2021_20231012.csv\Hospital_Inpatient_Discharges__SPARCS_De-Identified___2021_20231012.csv"
    output_csv = r"./data/hospital_inpatient_discharges_cleaned.csv"
    clean_medical_data(input_csv, output_csv)