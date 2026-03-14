import calendar
import logging
import os
import time
from datetime import date

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.exceptions import HTTPException

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # .env loading is optional; production typically uses real environment variables
    pass

from dashboard.analytics.aggregations import daily_totals, month_name, top3, top_branch
from dashboard.web.cache import RefreshCache
from scrapers import fetch_all_loans


app = Flask(__name__, template_folder="templates", static_folder="static")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("dashboard")


@app.before_request
def _log_request():
    try:
        logger.info("HTTP %s %s args=%s", request.method, request.path, dict(request.args))
    except Exception:
        # never break request handling due to logging
        pass


_CACHE_TTL_SECONDS = 120
_refresh_cache = RefreshCache(ttl_seconds=_CACHE_TTL_SECONDS)


def _get_loans(year: int, month: int):
    key = (year, month)

    def _fetch():
        return fetch_all_loans(year, month)

    return _refresh_cache.get_cached(key, _fetch)


@app.errorhandler(Exception)
def _handle_unexpected_error(e):
    # Avoid treating normal HTTP errors (like 404) as "Unhandled error"
    if isinstance(e, HTTPException):
        if request.path.startswith("/api/"):
            return jsonify({"error": f"{e.code} {e.name}"}), e.code
        return e

    logger.exception("Unhandled error")
    if request.path.startswith("/api/"):
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500
    return ("Internal Server Error", 500)


def _top3_response(source: str):
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_loans(year, month)
    return jsonify({"top3": top3(rows, source), "error": err})


def _top_state_response(source: str):
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_loans(year, month)
    out = top_branch(rows, source)
    out["error"] = err
    return jsonify(out)


@app.get("/")
def home():
    return render_template("eli_nbl.html")


@app.get("/api/health")
def api_health():
    return jsonify({"ok": True})


@app.route("/api/clear-cache", methods=["GET", "POST"])
def api_clear_cache():
    """Clear all cached data to force fresh fetch."""
    _refresh_cache.clear()
    logger.info("Cache cleared")
    return jsonify({"cleared": True, "message": "Cache cleared successfully"})


@app.route("/api/refresh", methods=["GET", "POST"])
def api_refresh():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    key = (year, month)

    def _fetch():
        return fetch_all_loans(year, month)

    _refresh_cache.kickoff_refresh(key, _fetch)
    hit = _refresh_cache.get_entry(key) or {}
    return jsonify(
        {
            "month": month,
            "year": year,
            "cache_ttl_seconds": _CACHE_TTL_SECONDS,
            "refreshing": bool(hit.get("refreshing")),
            "last_ts": hit.get("ts"),
            "rows_total": len(hit.get("df", []) or []),
            "last_error": hit.get("error"),
        }
    )


@app.get("/api/debug")
def api_debug():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_loans(year, month)

    sample = rows[:2]
    counts = {"ELI": 0, "NBL": 0}
    for r in rows:
        src = r.get("source")
        if src in counts:
            counts[src] += 1

    return jsonify(
        {
            "month": month,
            "year": year,
            "cache_ttl_seconds": _CACHE_TTL_SECONDS,
            "rows_total": len(rows),
            "rows_by_source": counts,
            "last_error": err,
            "sample": sample,
        }
    )
@app.get("/api/eli-top3")
def api_eli_top3(): return _top3_response("ELI")

@app.get("/api/nbl-top3")
def api_nbl_top3(): return _top3_response("NBL")

@app.get("/api/eli-top-state")
def api_eli_top_state(): return _top_state_response("ELI")

@app.get("/api/nbl-top-state")
def api_nbl_top_state(): return _top_state_response("NBL")


# Load targets from environment variables with defaults
ELI_TARGET = float(os.getenv("ELI_TARGET", "45000000"))  # ₹4.50 Cr default
NBL_TARGET = float(os.getenv("NBL_TARGET", "52500000"))  # ₹5.25 Cr default
CP_TARGET = float(os.getenv("CP_TARGET", "23500000"))  # ₹2.35 Cr default
LR_TARGET = float(os.getenv("LR_TARGET", "24000000"))  # ₹2.40 Cr default


@app.get("/api/dashboard-stats")
def api_dashboard_stats():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_loans(year, month)

    eli_rows = [r for r in rows if r.get("source") == "ELI"]
    nbl_rows = [r for r in rows if r.get("source") == "NBL"]
    eli_total = sum(float(r.get("loan_amount") or 0.0) for r in eli_rows)
    nbl_total = sum(float(r.get("loan_amount") or 0.0) for r in nbl_rows)
    combined_total = eli_total + nbl_total

    eli_target = ELI_TARGET
    nbl_target = NBL_TARGET
    combined_target = ELI_TARGET + NBL_TARGET

    eli_progress_pct = round(min(100.0, (eli_total / eli_target) * 100.0), 2) if eli_target else 0.0
    nbl_progress_pct = round(min(100.0, (nbl_total / nbl_target) * 100.0), 2) if nbl_target else 0.0
    leader_progress_pct = round(min(100.0, (combined_total / combined_target) * 100.0), 2) if combined_target else 0.0

    # Days-in-month for run-rate calculation (frontend uses this)
    days_in_month = calendar.monthrange(year, month)[1]

    return jsonify(
        {
            "month": month,
            "year": year,
            "error": err,
            "eli_total": eli_total,
            "nbl_total": nbl_total,
            "combined_total": combined_total,
            "eli_target": eli_target,
            "nbl_target": nbl_target,
            "combined_target": combined_target,
            "eli_count": len(eli_rows),
            "nbl_count": len(nbl_rows),
            "eli_progress_pct": eli_progress_pct,
            "nbl_progress_pct": nbl_progress_pct,
            "leader_progress_pct": leader_progress_pct,
            "eli_score": eli_progress_pct,
            "nbl_score": nbl_progress_pct,
            "days_in_month": days_in_month,
        }
    )


@app.get("/api/daily-performance")
def api_daily_performance():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_loans(year, month)

    days, eli_totals = daily_totals(rows, "ELI", year, month)
    _, nbl_totals = daily_totals(rows, "NBL", year, month)

    return jsonify(
        {
            "current_month": month_name(year, month),
            "error": err,
            "days": days,
            "eli_daily_totals": eli_totals,
            "nbl_daily_totals": nbl_totals,
        }
    )


@app.get("/api/cp-top3")
def api_cp_top3(): return _top3_response("CP")

@app.get("/api/lr-top3")
def api_lr_top3(): return _top3_response("LR")

@app.get("/api/cp-top-state")
def api_cp_top_state(): return _top_state_response("CP")

@app.get("/api/lr-top-state")
def api_lr_top_state(): return _top_state_response("LR")
    
@app.get("/api/cp-lr-stats")
def api_cp_lr_stats():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_loans(year, month)

    cp_rows = [r for r in rows if r.get("source") == "CP"]
    lr_rows = [r for r in rows if r.get("source") == "LR"]
    cp_total = sum(float(r.get("loan_amount") or 0.0) for r in cp_rows)
    lr_total = sum(float(r.get("loan_amount") or 0.0) for r in lr_rows)
    combined_total = cp_total + lr_total
    days_in_month = calendar.monthrange(year, month)[1]

    cp_target = CP_TARGET
    lr_target = LR_TARGET
    combined_target = CP_TARGET + LR_TARGET

    cp_progress_pct = round(min(100.0, (cp_total / cp_target) * 100.0), 2) if cp_target else 0.0
    lr_progress_pct = round(min(100.0, (lr_total / lr_target) * 100.0), 2) if lr_target else 0.0
    combined_progress_pct = (
        round(min(100.0, (combined_total / combined_target) * 100.0), 2) if combined_target else 0.0
    )

    return jsonify(
        {
            "month": month,
            "year": year,
            "error": err,
            "cp_total": cp_total,
            "lr_total": lr_total,
            "combined_total": combined_total,
            "cp_target": cp_target,
            "lr_target": lr_target,
            "combined_target": combined_target,
            "cp_count": len(cp_rows),
            "lr_count": len(lr_rows),
            "cp_progress_pct": cp_progress_pct,
            "lr_progress_pct": lr_progress_pct,
            "combined_progress_pct": combined_progress_pct,
            "cp_score": cp_progress_pct,
            "lr_score": lr_progress_pct,
            "days_in_month": days_in_month,
        }
    )


@app.get("/api/cp-lr-daily")
def api_cp_lr_daily():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_loans(year, month)

    days, cp_totals = daily_totals(rows, "CP", year, month)
    _, lr_totals = daily_totals(rows, "LR", year, month)

    return jsonify(
        {
            "current_month": month_name(year, month),
            "error": err,
            "days": days,
            "cp_daily_totals": cp_totals,
            "lr_daily_totals": lr_totals,
        }
    )


@app.get("/api/recent-highlights")
def api_recent_highlights():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_loans(year, month)

    highlights = [
        {
            "loan_no": r.get("loan_no", ""),
            "credit_by": r.get("credit_by", ""),
            "loan_amount": r.get("loan_amount", 0),
            "source": r.get("source", ""),
            "disbursal_date": str(r.get("disbursal_date", "")),
        }
        for r in rows
        if float(r.get("loan_amount") or 0) >= 100000
    ]
    highlights.sort(key=lambda x: x["disbursal_date"], reverse=True)
    return jsonify({"highlights": highlights, "error": err})



@app.get("/cp-lr")
def cp_lr_page():
    return render_template("cp_lr.html")


@app.route('/favicon.ico')
def favicon():
    static_dir = os.path.join(app.root_path, 'static')
    favicon_path = os.path.join(static_dir, 'favicon.ico')
    if not os.path.exists(favicon_path):
        return ("", 204)
    return send_from_directory(
        static_dir,
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon',
    )


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") in {"1", "true", "True", "yes", "YES"}
    app.run(host=host, port=port, debug=debug)
