-- 数据库创建与使用
USE `smartmed-bigdata-llm`;

-- =========================================================
-- 第一部分：创建分表（维度表 + 事实表）
-- =========================================================

-- 1. 医院机构维度表
CREATE TABLE IF NOT EXISTS dim_facility (
    facility_id VARCHAR(50) PRIMARY KEY COMMENT '医疗机构永久ID',
    operating_cert_num VARCHAR(50) COMMENT '医院运营证书编号',
    facility_name VARCHAR(255) COMMENT '医疗机构名称',
    hospital_service_area VARCHAR(100) COMMENT '医院服务区域',
    hospital_county VARCHAR(100) COMMENT '医院所在县',
    INDEX idx_county (hospital_county)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. CCSR 诊断维度表
CREATE TABLE IF NOT EXISTS dim_ccsr_diagnosis (
    diagnosis_code VARCHAR(20) PRIMARY KEY COMMENT '诊断代码',
    diagnosis_description TEXT COMMENT '诊断描述'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. CCSR 手术操作维度表
CREATE TABLE IF NOT EXISTS dim_ccsr_procedure (
    procedure_code VARCHAR(20) PRIMARY KEY COMMENT '操作代码',
    procedure_description TEXT COMMENT '操作描述'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. APR DRG 维度表
CREATE TABLE IF NOT EXISTS dim_apr_drg (
    drg_code VARCHAR(20) PRIMARY KEY COMMENT '疾病诊断相关组代码',
    drg_description TEXT COMMENT 'DRG描述'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. APR MDC 维度表
CREATE TABLE IF NOT EXISTS dim_apr_mdc (
    mdc_code VARCHAR(20) PRIMARY KEY COMMENT '主要诊断类别代码',
    mdc_description TEXT COMMENT '主要诊断类别描述'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. 住院记录事实表 (核心业务表)
CREATE TABLE IF NOT EXISTS fact_inpatient_discharges (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    facility_id VARCHAR(50),
    ccsr_diagnosis_code VARCHAR(20),
    ccsr_procedure_code VARCHAR(20),
    apr_drg_code VARCHAR(20),
    apr_mdc_code VARCHAR(20),
    age_group VARCHAR(50),
    zip_code_3 VARCHAR(10),
    gender VARCHAR(10),
    race VARCHAR(50),
    ethnicity VARCHAR(50),
    discharge_year INT,
    type_of_admission VARCHAR(50),
    patient_disposition VARCHAR(100),
    length_of_stay INT,
    emergency_dept_indicator TINYINT(1),
    birth_weight DECIMAL(8,2),
    apr_severity_code INT,
    apr_severity_desc VARCHAR(50),
    apr_risk_of_mortality INT,
    apr_medical_surgical_desc VARCHAR(50),
    payment_typology_1 VARCHAR(100),
    payment_typology_2 VARCHAR(100),
    payment_typology_3 VARCHAR(100),
    total_charges DECIMAL(12,2),
    total_costs DECIMAL(12,2),

    INDEX idx_discharge_year (discharge_year),
    INDEX idx_facility_id (facility_id),
    INDEX idx_diagnosis_code (ccsr_diagnosis_code),
    INDEX idx_drg_code (apr_drg_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- =========================================================
-- 第二部分：数据清洗与分发插入 (ETL过程)
-- 假设您的宽表名为 `raw_inpatient_data` (您通过DataGrip直接导入CSV的表)
-- =========================================================

-- 1. 从宽表抽取唯一数据写入【医院维度表】
INSERT IGNORE INTO dim_facility (facility_id, operating_cert_num, facility_name, hospital_service_area, hospital_county)
SELECT
    `Permanent Facility Id`,
    MAX(`Operating Certificate Number`),
    MAX(`Facility Name`),
    MAX(`Hospital Service Area`),
    MAX(`Hospital County`)
FROM cleaned_hospital_data
WHERE `Permanent Facility Id` IS NOT NULL AND `Permanent Facility Id` != ''
GROUP BY `Permanent Facility Id`;

-- 2. 从宽表抽取唯一数据写入【CCSR诊断维度表】
INSERT IGNORE INTO dim_ccsr_diagnosis (diagnosis_code, diagnosis_description)
SELECT DISTINCT
    `CCSR Diagnosis Code`,
    `CCSR Diagnosis Description`
FROM cleaned_hospital_data
WHERE `CCSR Diagnosis Code` IS NOT NULL AND `CCSR Diagnosis Code` != '';

-- 3. 从宽表抽取唯一数据写入【CCSR手术维度表】
INSERT IGNORE INTO dim_ccsr_procedure (procedure_code, procedure_description)
SELECT
    `CCSR Procedure Code`,
    MAX(`CCSR Procedure Description`)
FROM cleaned_hospital_data
WHERE `CCSR Procedure Code` IS NOT NULL AND `CCSR Procedure Code` != ''
GROUP BY `CCSR Procedure Code`;

-- 4. 从宽表抽取唯一数据写入【DRG维度表】
INSERT IGNORE INTO dim_apr_drg (drg_code, drg_description)
SELECT
    `APR DRG Code`,
    MAX(`APR DRG Description`)
FROM cleaned_hospital_data
WHERE `APR DRG Code` IS NOT NULL AND `APR DRG Code` != ''
GROUP BY `APR DRG Code`;

-- 5. 从宽表抽取唯一数据写入【MDC维度表】
INSERT IGNORE INTO dim_apr_mdc (mdc_code, mdc_description)
SELECT
    `APR MDC Code`,
    MAX(`APR MDC Description`)
FROM cleaned_hospital_data
WHERE `APR MDC Code` IS NOT NULL AND `APR MDC Code` != ''
GROUP BY `APR MDC Code`;

-- 6. 将宽表核心业务数据与代码写入【事实表】
-- 6. 将宽表数据安全转换为数值并写入【事实表】
INSERT INTO fact_inpatient_discharges (
    facility_id, ccsr_diagnosis_code, ccsr_procedure_code, apr_drg_code, apr_mdc_code,
    age_group, zip_code_3, gender, race, ethnicity,
    discharge_year, type_of_admission, patient_disposition, length_of_stay,
    emergency_dept_indicator, birth_weight,
    apr_severity_code, apr_severity_desc, apr_risk_of_mortality, apr_medical_surgical_desc,
    payment_typology_1, payment_typology_2, payment_typology_3, total_charges, total_costs
)
SELECT
    `Permanent Facility Id`,
    `CCSR Diagnosis Code`,
    `CCSR Procedure Code`,
    `APR DRG Code`,
    `APR MDC Code`,
    `Age Group`,
    `Zip Code - 3 digits`,
    `Gender`,
    `Race`,
    `Ethnicity`,

    -- 出院年份
    CASE WHEN `Discharge Year` REGEXP '^[0-9]+$' THEN CAST(`Discharge Year` AS UNSIGNED) ELSE NULL END,
    `Type of Admission`,
    `Patient Disposition`,

    -- 住院天数：过滤 '120 +' 或 'N/A' 等非纯数字
    CASE WHEN `Length of Stay` REGEXP '^[0-9]+$' THEN CAST(`Length of Stay` AS UNSIGNED) ELSE NULL END,

    -- 是否急诊
    CASE WHEN `Emergency Department Indicator` IN ('Y', 'y', '1', 'True') THEN 1 ELSE 0 END,

    -- 出生体重：过滤 'N/A'、'Unknown'，仅当为有效数字时才转换为 DECIMAL，否则设为 NULL
    CASE WHEN `Birth Weight` REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(`Birth Weight` AS DECIMAL(8,2)) ELSE NULL END,

    -- 疾病严重程度代码与风险代码
    CASE WHEN `APR Severity of Illness Code` REGEXP '^[0-9]+$' THEN CAST(`APR Severity of Illness Code` AS UNSIGNED) ELSE NULL END,
    `APR Severity of Illness Description`,
    CASE WHEN `APR Risk of Mortality` REGEXP '^[0-9]+$' THEN CAST(`APR Risk of Mortality` AS UNSIGNED) ELSE NULL END,
    `APR Medical Surgical Description`,

    `Payment Typology 1`,
    `Payment Typology 2`,
    `Payment Typology 3`,

    -- 总费用：自动去除可能残余的逗号，仅保留合法浮点数
    CASE WHEN REPLACE(REPLACE(`Total Charges`, ',', ''), '$', '') REGEXP '^[0-9]+(\\.[0-9]+)?$'
         THEN CAST(REPLACE(REPLACE(`Total Charges`, ',', ''), '$', '') AS DECIMAL(12,2)) ELSE NULL END,

    -- 总成本：自动去除可能残余的逗号，仅保留合法浮点数
    CASE WHEN REPLACE(REPLACE(`Total Costs`, ',', ''), '$', '') REGEXP '^[0-9]+(\\.[0-9]+)?$'
         THEN CAST(REPLACE(REPLACE(`Total Costs`, ',', ''), '$', '') AS DECIMAL(12,2)) ELSE NULL END

FROM cleaned_hospital_data;