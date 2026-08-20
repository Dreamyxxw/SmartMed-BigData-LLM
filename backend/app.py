# -*- coding: utf-8 -*-
"""
智慧医疗分析平台 - Flask 后端

Dashboard：
    GET /api/dashboard/kpi|age-group|top-diseases|dept-compare|meta

Reports：
    GET  /api/reports/meta
    GET  /api/reports/stats
    GET  /api/reports/list
    GET  /api/reports/detail/<id>
    POST /api/reports/generate
    PUT  /api/reports/<id>
    DELETE /api/reports/<id>
    POST /api/reports/<id>/duplicate

运行：
    cd backend
    pip install -r requirements.txt
    python app.py
"""
import json
import sys
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


# ============ Reports 洞察报告接口 ============
# Redis 前缀：smartmed:reports:（见 data/build_reports_cache.py）

@app.route('/api/reports/meta', methods=['GET'])
def api_reports_meta():
    """报告元信息：年份/区域/主题/标签"""
    import reports_service as rs
    return ok(rs.get_meta(r))


@app.route('/api/reports/stats', methods=['GET'])
def api_reports_stats():
    """获取某年份×区域的聚合指标包（供调试 / 后续 LLM）"""
    import reports_service as rs
    meta = rs.get_meta(r)
    years = meta.get('years') or [config.DEFAULT_YEAR]
    regions = meta.get('regions') or ['all']
    year = request.args.get('year') or (years[0] if years else config.DEFAULT_YEAR)
    region = request.args.get('region') or 'all'
    if year not in years:
        year = years[0]
    if region not in regions:
        region = 'all' if 'all' in regions else (regions[0] if regions else 'all')
    data = rs.get_stats(r, str(year), str(region))
    if data is None:
        return err('未找到统计缓存，请先运行 python data/build_reports_cache.py', 404)
    return ok(data)


@app.route('/api/reports/list', methods=['GET'])
def api_reports_list():
    """报告列表"""
    import reports_service as rs
    return ok(rs.list_reports(r))


@app.route('/api/reports/detail/<report_id>', methods=['GET'])
def api_reports_detail(report_id):
    """报告详情（含 Markdown content）"""
    import reports_service as rs
    data = rs.get_detail(r, report_id)
    if not data:
        return err('报告不存在', 404)
    return ok(data)


@app.route('/api/reports/generate', methods=['POST'])
def api_reports_generate():
    """
    生成报告：读取 Redis stats + 模板渲染；
    LLM 调用在 reports_service.call_llm_for_report 中留空。
    """
    import reports_service as rs
    body = request.get_json(silent=True) or {}
    try:
        summary = rs.generate_report(r, body)
        return jsonify({'code': 200, 'data': summary, 'message': '报告生成成功'})
    except ValueError as e:
        return err(str(e), 400)
    except RuntimeError as e:
        return jsonify({'code': 500, 'message': str(e)})
    except Exception as e:
        app.logger.exception('generate report failed')
        return jsonify({'code': 500, 'message': f'生成失败: {e}'})


@app.route('/api/reports/<report_id>', methods=['PUT'])
def api_reports_update(report_id):
    """更新报告元信息（标题/描述/标签）"""
    import reports_service as rs
    body = request.get_json(silent=True) or {}
    try:
        data = rs.update_report_meta(r, report_id, body)
        return ok(data)
    except ValueError as e:
        return err(str(e), 404)


@app.route('/api/reports/<report_id>', methods=['DELETE'])
def api_reports_delete(report_id):
    """删除报告"""
    import reports_service as rs
    detail = rs.get_detail(r, report_id)
    if not detail:
        return err('报告不存在', 404)
    rs.delete_report(r, report_id)
    return jsonify({'code': 200, 'message': '删除成功'})


@app.route('/api/reports/<report_id>/duplicate', methods=['POST'])
def api_reports_duplicate(report_id):
    """复制报告"""
    import reports_service as rs
    try:
        data = rs.duplicate_report(r, report_id)
        return jsonify({'code': 200, 'data': data, 'message': '复制成功'})
    except ValueError as e:
        return err(str(e), 404)


# ============ 追加：AI智能探索舱 路由注册 (smartmed:aichat:*) ============
# 必须在 app.run() 之前注册，否则路由不会被挂载（app.run 阻塞）
import aichat_routes as _aichat_routes
_aichat_routes.register_routes(app)


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
