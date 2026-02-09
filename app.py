import calendar
import logging
import os
import threading
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

from scrapers import fetch_combined_disbursed_df


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


_CACHE_TTL_SECONDS = 60
_cache: dict[tuple[int, int], dict] = {}
_locks: dict[tuple[int, int], threading.Lock] = {}


def _refresh_cache(key: tuple[int, int], year: int, month: int) -> None:
    started = time.time()
    try:
        logger.info("Background refresh start for %s", key)
        try:
            rows = fetch_combined_disbursed_df(year, month)
            err = None
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            rows = []
            logger.exception("Background refresh failed for %s", key)

        elapsed = round(time.time() - started, 2)
        logger.info("Background refresh finished for %s in %ss. Rows=%s Error=%s", key, elapsed, len(rows), err)

        _cache[key] = {"ts": time.time(), "df": rows, "error": err, "refreshing": False}
    finally:
        # Ensure we always clear the refreshing flag even if something goes wrong
        hit = _cache.get(key)
        if hit:
            hit["refreshing"] = False


def _kickoff_refresh(year: int, month: int) -> None:
    key = (year, month)
    lock = _get_lock(key)

    # Only one refresh thread per key
    with lock:
        hit = _cache.get(key)
        if hit and hit.get("refreshing"):
            return
        if hit is None:
            _cache[key] = {"ts": 0.0, "df": [], "error": "warming_up", "refreshing": True}
        else:
            hit["refreshing"] = True

    t = threading.Thread(target=_refresh_cache, args=(key, year, month), daemon=True)
    t.start()


def _get_lock(key: tuple[int, int]) -> threading.Lock:
    lock = _locks.get(key)
    if lock is None:
        lock = threading.Lock()
        _locks[key] = lock
    return lock


def _get_cached_df(year: int, month: int):
    key = (year, month)
    now = time.time()
    hit = _cache.get(key)
    if hit and (now - hit["ts"]) < _CACHE_TTL_SECONDS:
        if hit.get("error"):
            logger.warning("Cache hit with previous error for %s: %s", key, hit.get("error"))
        return hit["df"], hit.get("error")

    # Cache is missing or stale: return immediately and refresh in background.
    if hit:
        if not hit.get("refreshing"):
            _kickoff_refresh(year, month)
        return hit.get("df", []), hit.get("error") or "stale"

    _kickoff_refresh(year, month)
    return [], "warming_up"


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


def _month_name(year: int, month: int) -> str:
    return f"{calendar.month_name[month]} {year}"


def _top3(df, source: str):
    rows = [r for r in df if r.get("source") == source]
    if not rows:
        return []

    totals: dict[str, float] = {}
    for r in rows:
        cm = str(r.get("credit_by") or "").strip()
        amt = r.get("loan_amount")
        if amt is None:
            continue
        totals[cm] = totals.get(cm, 0.0) + float(amt)

    top = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:3]
    return [{"CM_Name": k, "Achievement": float(v)} for k, v in top]


def _top_state(df, source: str):
    rows = [r for r in df if r.get("source") == source]
    if not rows:
        return {"state": None, "total": 0}

    totals: dict[str, float] = {}
    for r in rows:
        st = str(r.get("state") or "").strip()
        amt = r.get("loan_amount")
        if amt is None:
            continue
        totals[st] = totals.get(st, 0.0) + float(amt)

    if not totals:
        return {"state": None, "total": 0}

    state, total = max(totals.items(), key=lambda x: x[1])
    return {"state": state, "total": float(total)}


def _daily_totals(df, source: str, year: int, month: int):
    days_in_month = calendar.monthrange(year, month)[1]
    days = list(range(1, days_in_month + 1))

    rows = [r for r in df if r.get("source") == source]
    if not rows:
        return days, [0] * len(days)

    totals_by_day: dict[int, float] = {}
    for r in rows:
        d = r.get("disbursal_date")
        amt = r.get("loan_amount")
        if d is None or amt is None:
            continue
        day = int(getattr(d, "day", 0) or 0)
        if day <= 0:
            continue
        totals_by_day[day] = totals_by_day.get(day, 0.0) + float(amt)

    totals = [float(totals_by_day.get(day, 0.0)) for day in days]
    return days, totals


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/health")
def api_health():
    return jsonify({"ok": True})


@app.post("/api/refresh")
def api_refresh():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    _kickoff_refresh(year, month)

    key = (year, month)
    hit = _cache.get(key) or {}
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
    rows, err = _get_cached_df(year, month)

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
def api_eli_top3():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_cached_df(year, month)
    return jsonify({"top3": _top3(rows, "ELI"), "error": err})


@app.get("/api/nbl-top3")
def api_nbl_top3():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_cached_df(year, month)
    return jsonify({"top3": _top3(rows, "NBL"), "error": err})


@app.get("/api/eli-top-state")
def api_eli_top_state():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_cached_df(year, month)
    out = _top_state(rows, "ELI")
    out["error"] = err
    return jsonify(out)


@app.get("/api/nbl-top-state")
def api_nbl_top_state():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_cached_df(year, month)
    out = _top_state(rows, "NBL")
    out["error"] = err
    return jsonify(out)


@app.get("/api/dashboard-stats")
def api_dashboard_stats():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_cached_df(year, month)

    eli_total = sum(float(r.get("loan_amount") or 0.0) for r in rows if r.get("source") == "ELI")
    nbl_total = sum(float(r.get("loan_amount") or 0.0) for r in rows if r.get("source") == "NBL")
    combined_total = eli_total + nbl_total

    eli_target = 42500000.0  # ₹4.25 Cr
    nbl_target = 50000000.0  # ₹5 Cr
    combined_target = 92500000.0  # ₹9.25 Cr

    eli_progress_pct = round(min(100.0, (eli_total / eli_target) * 100.0), 2) if eli_target else 0.0
    nbl_progress_pct = round(min(100.0, (nbl_total / nbl_target) * 100.0), 2) if nbl_target else 0.0
    leader_progress_pct = round(min(100.0, (combined_total / combined_target) * 100.0), 2) if combined_target else 0.0

    # Score mirrors progress pct
    eli_score = eli_progress_pct
    nbl_score = nbl_progress_pct

    return jsonify(
        {
            "month": month,
            "year": year,
            "error": err,
            "eli_total": eli_total,
            "nbl_total": nbl_total,
            "combined_total": combined_total,
            "eli_progress_pct": eli_progress_pct,
            "nbl_progress_pct": nbl_progress_pct,
            "leader_progress_pct": leader_progress_pct,
            "eli_score": eli_score,
            "nbl_score": nbl_score,
        }
    )


@app.get("/api/daily-performance")
def api_daily_performance():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_cached_df(year, month)

    days, eli_totals = _daily_totals(rows, "ELI", year, month)
    _, nbl_totals = _daily_totals(rows, "NBL", year, month)

    return jsonify(
        {
            "current_month": _month_name(year, month),
            "error": err,
            "days": days,
            "eli_daily_totals": eli_totals,
            "nbl_daily_totals": nbl_totals,
        }
    )


@app.get("/api/cp-top3")
def api_cp_top3():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_cached_df(year, month)
    return jsonify({"top3": _top3(rows, "CP"), "error": err})


@app.get("/api/lr-top3")
def api_lr_top3():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_cached_df(year, month)
    return jsonify({"top3": _top3(rows, "LR"), "error": err})


@app.get("/api/cp-top-state")
def api_cp_top_state():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_cached_df(year, month)
    out = _top_state(rows, "CP")
    out["error"] = err
    return jsonify(out)


@app.get("/api/lr-top-state")
def api_lr_top_state():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_cached_df(year, month)
    out = _top_state(rows, "LR")
    out["error"] = err
    return jsonify(out)


@app.get("/api/cp-lr-stats")
def api_cp_lr_stats():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_cached_df(year, month)

    cp_total = sum(float(r.get("loan_amount") or 0.0) for r in rows if r.get("source") == "CP")
    lr_total = sum(float(r.get("loan_amount") or 0.0) for r in rows if r.get("source") == "LR")
    combined_total = cp_total + lr_total

    cp_target = 50000000.0  # ₹5 Cr
    lr_target = 50000000.0  # ₹5 Cr
    combined_target = 100000000.0  # ₹10 Cr

    cp_progress_pct = round(min(100.0, (cp_total / cp_target) * 100.0), 2) if cp_target else 0.0
    lr_progress_pct = round(min(100.0, (lr_total / lr_target) * 100.0), 2) if lr_target else 0.0
    combined_progress_pct = round(min(100.0, (combined_total / combined_target) * 100.0), 2) if combined_target else 0.0

    cp_score = cp_progress_pct
    lr_score = lr_progress_pct

    return jsonify(
        {
            "month": month,
            "year": year,
            "error": err,
            "cp_total": cp_total,
            "lr_total": lr_total,
            "combined_total": combined_total,
            "cp_progress_pct": cp_progress_pct,
            "lr_progress_pct": lr_progress_pct,
            "combined_progress_pct": combined_progress_pct,
            "cp_score": cp_score,
            "lr_score": lr_score,
        }
    )


@app.get("/api/cp-lr-daily")
def api_cp_lr_daily():
    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))
    rows, err = _get_cached_df(year, month)

    days, cp_totals = _daily_totals(rows, "CP", year, month)
    _, lr_totals = _daily_totals(rows, "LR", year, month)

    return jsonify(
        {
            "current_month": _month_name(year, month),
            "error": err,
            "days": days,
            "cp_daily_totals": cp_totals,
            "lr_daily_totals": lr_totals,
        }
    )


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
