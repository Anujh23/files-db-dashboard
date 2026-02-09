import calendar


def month_name(year: int, month: int) -> str:
    return f"{calendar.month_name[month]} {year}"


def top3(rows: list[dict], source: str) -> list[dict]:
    src_rows = [r for r in rows if r.get("source") == source]
    if not src_rows:
        return []

    totals: dict[str, float] = {}
    for r in src_rows:
        cm = str(r.get("credit_by") or "").strip()
        amt = r.get("loan_amount")
        if amt is None:
            continue
        totals[cm] = totals.get(cm, 0.0) + float(amt)

    top = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:3]
    return [{"CM_Name": k, "Achievement": float(v)} for k, v in top]


def top_state(rows: list[dict], source: str) -> dict:
    src_rows = [r for r in rows if r.get("source") == source]
    if not src_rows:
        return {"state": None, "total": 0}

    totals: dict[str, float] = {}
    for r in src_rows:
        st = str(r.get("state") or "").strip()
        amt = r.get("loan_amount")
        if amt is None:
            continue
        totals[st] = totals.get(st, 0.0) + float(amt)

    if not totals:
        return {"state": None, "total": 0}

    state, total = max(totals.items(), key=lambda x: x[1])
    return {"state": state, "total": float(total)}


def daily_totals(rows: list[dict], source: str, year: int, month: int):
    days_in_month = calendar.monthrange(year, month)[1]
    days = list(range(1, days_in_month + 1))

    src_rows = [r for r in rows if r.get("source") == source]
    if not src_rows:
        return days, [0] * len(days)

    totals_by_day: dict[int, float] = {}
    for r in src_rows:
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
