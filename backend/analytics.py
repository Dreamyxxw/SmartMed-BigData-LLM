# -*- coding: utf-8 -*-
"""Redis-backed APIs for the real multi-dimensional analytics page."""
import json
from math import ceil

from flask import request

ANALYTICS_PREFIX = "smartmed:analytics:"
ROWS_KEY = f"{ANALYTICS_PREFIX}rows"
META_KEY = f"{ANALYTICS_PREFIX}meta"
FILTERS_KEY = f"{ANALYTICS_PREFIX}filters"


def register_analytics_routes(app, redis_client, ok, err):
    rows_cache = None

    def cache_json(key, fallback=None):
        try:
            raw = redis_client.get(key)
            return json.loads(raw) if raw else fallback
        except Exception as exc:
            app.logger.error("[analytics-cache-error] %s: %s", key, exc)
            return fallback

    def load_rows():
        nonlocal rows_cache
        if rows_cache is not None:
            return rows_cache
        try:
            rows_cache = [json.loads(raw) for raw in redis_client.hgetall(ROWS_KEY).values()]
            return rows_cache
        except Exception as exc:
            app.logger.error("[analytics-cache-error] rows: %s", exc)
            return []

    def match(row, params):
        for field in ("year", "region", "facility", "department", "gender", "ageGroup", "severity", "paymentType"):
            value = params.get(field, "").strip()
            if value and row.get(field) != value:
                return False
        return True

    @app.route("/api/analytics/meta", methods=["GET"])
    def analytics_meta():
        meta = cache_json(META_KEY)
        if not meta:
            return err("未找到 Analytics 缓存，请先运行 data/build_analytics_cache.py。", 503)
        return ok(meta)

    @app.route("/api/analytics/filters", methods=["GET"])
    def analytics_filters():
        filters = cache_json(FILTERS_KEY)
        if not filters:
            return err("未找到 Analytics 缓存，请先运行 data/build_analytics_cache.py。", 503)
        return ok(filters)

    @app.route("/api/analytics/query", methods=["GET"])
    def analytics_query():
        try:
            page = max(int(request.args.get("page", 1)), 1)
            page_size = min(max(int(request.args.get("pageSize", 20)), 1), 200)
        except ValueError:
            return err("page 和 pageSize 必须是整数。")

        params = {name: (request.args.get(name) or "").strip() for name in (
            "year", "region", "facility", "department", "gender", "ageGroup", "severity", "paymentType",
        )}
        matched = [row for row in load_rows() if match(row, params)]
        matched.sort(key=lambda row: row["totalCharges"], reverse=True)

        total_patients = sum(row["count"] for row in matched)
        total_charges = round(sum(row["totalCharges"] for row in matched), 2)
        total_costs = round(sum(row["totalCosts"] for row in matched), 2)
        total_stay_days = sum(row["totalStayDays"] for row in matched)
        summary = {
            "recordCount": len(matched),
            "totalPatients": total_patients,
            "totalCharges": total_charges,
            "totalCosts": total_costs,
            "avgStay": round(total_stay_days / total_patients, 1) if total_patients else 0,
            "avgCharges": round(total_charges / total_patients, 2) if total_patients else 0,
        }

        start = (page - 1) * page_size
        response_rows = [{
            **row,
            "avgStay": round(row["totalStayDays"] / row["count"], 1),
            "avgCharges": round(row["totalCharges"] / row["count"], 2),
            "avgCosts": round(row["totalCosts"] / row["count"], 2),
        } for row in matched[start:start + page_size]]

        return ok({
            "list": response_rows, "total": len(matched), "page": page,
            "pageSize": page_size, "pages": ceil(len(matched) / page_size) if matched else 0,
            "summary": summary,
        })