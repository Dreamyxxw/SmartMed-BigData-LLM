# -*- coding: utf-8 -*-
"""
智慧医疗分析平台 - Flask 后端（第一阶段：Dashboard 接口）

已实现接口（对应前端 api/index.js）：
    GET /api/dashboard/kpi              → getKpiData
    GET /api/dashboard/age-group        → getAgeGroupData
    GET /api/dashboard/top-diseases     → getTopDiseasesData
    GET /api/dashboard/dept-compare     → getDeptCompareData
    GET /api/dashboard/meta             → 预构建元信息（调试用）

所有接口直接读取 Redis 预构建缓存，响应时间通常 < 1ms。

运行：
    cd backend
    pip install -r requirements.txt
    python app.py
"""
import json
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
import redis

import config
from analytics import register_analytics_routes

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)


# ============ Redis 连接 ============
def get_redis():
    return redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB,
        password=config.REDIS_PASSWORD,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


r = get_redis()


# ============ 从 Redis meta 动态加载真实维度 ============
def _load_meta_dimensions():
    """启动时从 Redis meta key 读取真实的 years/regions，覆盖 config 白名单"""
    try:
        raw = r.get(f"{config.KEY_PREFIX}meta")
        if raw:
            meta = json.loads(raw)
            years = meta.get('years', [])
            regions = meta.get('regions', [])
            if years:
                config.VALID_YEARS = years
                config.DEFAULT_YEAR = years[0]
            if regions:
                config.VALID_REGIONS = regions
                config.DEFAULT_REGION = 'all' if 'all' in regions else regions[0]
            return meta
    except Exception as e:
        app.logger.warning(f"加载 meta 失败，使用 fallback: {e}")
    return None

_meta = _load_meta_dimensions()


# ============ 通用工具 ============
def ok(data):
    """统一成功响应格式（与前端 mock 保持一致：{code, data}）"""
    return jsonify({'code': 200, 'data': data})


def err(message, code=400):
    return jsonify({'code': code, 'message': message}), 400


register_analytics_routes(app, r, ok, err)


def safe_param(val, whitelist, default):
    if val is None:
        return default
    val = str(val).strip()
    return val if val in whitelist else default


def cache_get(key_suffix, fallback):
    """
    读取 Redis 缓存。失败时返回 fallback（确保前端在 Redis 挂掉时也不会完全空白）
    """
    try:
        raw = r.get(f"{config.KEY_PREFIX}{key_suffix}")
        if raw is None:
            app.logger.warning(f"[cache-miss] {key_suffix}")
            return fallback
        return json.loads(raw)
    except Exception as e:
        app.logger.error(f"[cache-error] {key_suffix}: {e}")
        return fallback


@app.before_request
def _start_timer():
    request._start_ts = time.perf_counter()


@app.after_request
def _log_time(resp):
    if hasattr(request, '_start_ts'):
        ms = (time.perf_counter() - request._start_ts) * 1000
        resp.headers['X-Response-Time'] = f"{ms:.2f}ms"
    return resp


# ============ 4 个 Dashboard 接口 ============

@app.route('/api/dashboard/kpi', methods=['GET'])
def api_kpi():
    """
    KPI 4 项指标
    Params: year, region
    """
    year = safe_param(request.args.get('year'),   config.VALID_YEARS,   config.DEFAULT_YEAR)
    region = safe_param(request.args.get('region'), config.VALID_REGIONS, config.DEFAULT_REGION)
    data = cache_get(f"kpi:{year}:{region}", {
        'totalDischarges': 0,
        'avgTotalCharges': 0.0,
        'avgTotalCosts': 0.0,
        'avgStayDays': 0.0,
    })
    return ok(data)


@app.route('/api/dashboard/age-group', methods=['GET'])
def api_age_group():
    """
    5 年龄段分布
    Params: year, region
    """
    year = safe_param(request.args.get('year'),   config.VALID_YEARS,   config.DEFAULT_YEAR)
    region = safe_param(request.args.get('region'), config.VALID_REGIONS, config.DEFAULT_REGION)
    data = cache_get(f"agegroup:{year}:{region}", [])
    return ok(data)


@app.route('/api/dashboard/top-diseases', methods=['GET'])
def api_top_diseases():
    """
    Top10 昂贵疾病（支持年龄段联动）
    Params: year, region, ageGroup ('all' 或 5 个中文年龄段)
    """
    year = safe_param(request.args.get('year'),   config.VALID_YEARS,   config.DEFAULT_YEAR)
    region = safe_param(request.args.get('region'), config.VALID_REGIONS, config.DEFAULT_REGION)
    age_group = safe_param(request.args.get('ageGroup'), config.VALID_AGE_GROUPS, 'all')
    data = cache_get(f"topdiseases:{year}:{region}:{age_group}", [])
    return ok(data)


@app.route('/api/dashboard/dept-compare', methods=['GET'])
def api_dept_compare():
    """
    科室对比（费用/天数/人数）
    Params: year, region
    """
    year = safe_param(request.args.get('year'),   config.VALID_YEARS,   config.DEFAULT_YEAR)
    region = safe_param(request.args.get('region'), config.VALID_REGIONS, config.DEFAULT_REGION)
    data = cache_get(f"deptcompare:{year}:{region}", [])
    return ok(data)


# ============ 辅助接口 ============

@app.route('/api/dashboard/meta', methods=['GET'])
def api_meta():
    """预构建元信息（构建时间、可用维度、key数量等）"""
    data = cache_get('meta', {})
    return ok(data)


@app.route('/api/health', methods=['GET'])
def api_health():
    """健康检查"""
    try:
        r.ping()
        redis_ok = True
    except Exception as e:
        redis_ok = False
    return jsonify({
        'code': 200,
        'flask': 'ok',
        'redis': 'ok' if redis_ok else 'fail',
        'ts': int(time.time()),
    })


# ============ 启动 ============
if __name__ == '__main__':
    # 启动时做一次 Redis 连通性检查
    try:
        r.ping()
        meta = cache_get('meta', None)
        if meta:
            print(f"[✅] Redis 已连通，预构建数据存在：{meta}")
        else:
            print("[⚠️] Redis 已连通，但未找到预构建数据。请先运行：")
            print("     python ../data/build_dashboard_cache.py")
    except Exception as e:
        print(f"[❌] Redis 连接失败：{e}")
        print("     请启动 Redis 服务，或通过 REDIS_HOST/REDIS_PORT 环境变量指定")

    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
    )
