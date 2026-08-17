# -*- coding: utf-8 -*-
"""
Redis & Flask 配置
"""
import os

# ---------- Redis ----------
REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

# 缓存 key 前缀（必须和 build_dashboard_cache.py 一致）
KEY_PREFIX = 'smartmed:dashboard:'

# ---------- Flask ----------
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
FLASK_DEBUG = os.getenv('FLASK_DEBUG', '1') == '1'

# ---------- 合法参数白名单 ----------
# 不再写死：从 Redis meta 动态读取真实年份/地区
# 以下仅为 fallback（Redis meta 不存在时用）
VALID_YEARS = ['2021']
VALID_REGIONS = ['all', 'Bronx', 'Manhattan', 'Brooklyn']
VALID_AGE_GROUPS = ['all', '0-17岁', '18-29岁', '30-49岁', '50-69岁', '70岁以上']

# 默认值（从 meta 动态覆盖）
DEFAULT_YEAR = '2021'
DEFAULT_REGION = 'all'
