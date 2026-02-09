import calendar
import logging
import os
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


logger = logging.getLogger("scrapers")


ELI_LOGIN_URL = "https://app.everydayloanindia.co.in/admin/loginindex"
ELI_DATA_URL = "https://app.everydayloanindia.co.in/admin/dateWiseDisbursed"

ELI_USERNAME = os.getenv("ELI_USERNAME", "")
ELI_PASSWORD = os.getenv("ELI_PASSWORD", "")

NBL_ADMIN_URL = "https://app.nextbigloan.co.in/admin"
NBL_DATA_URL = "https://app.nextbigloan.co.in/admin/dateWiseDisbursed"

NBL_USERNAME = os.getenv("NBL_USERNAME", "")
NBL_PASSWORD = os.getenv("NBL_PASSWORD", "")

CP_LOGIN_URL = "https://app.creditpey.in/"
CP_DATA_URL = "https://app.creditpey.in/reporting/list/disbursed"

CP_USERNAME = os.getenv("CP_USERNAME", "")
CP_PASSWORD = os.getenv("CP_PASSWORD", "")

LR_LOGIN_URL = "https://app.lendingrupee.in/"
LR_DATA_URL = "https://app.lendingrupee.in/reporting/list/disbursed"

LR_USERNAME = os.getenv("LR_USERNAME", "")
LR_PASSWORD = os.getenv("LR_PASSWORD", "")


def _nbl_login(session: requests.Session) -> requests.Session:
    """Login to NBL admin and return the session."""
    if not NBL_USERNAME or not NBL_PASSWORD:
        raise RuntimeError("Missing NBL credentials. Set NBL_USERNAME and NBL_PASSWORD environment variables.")

    # First, get the login page to obtain CSRF token and session cookies
    logger.info("NBL: fetching login page %s", NBL_ADMIN_URL)
    login_page = session.get(NBL_ADMIN_URL, timeout=60)
    login_page.raise_for_status()
    
    soup = BeautifulSoup(login_page.text, "html.parser")
    
    # Find the login form
    form = soup.find("form", {"action": "/admin/login/doLogin"})
    if not form:
        raise RuntimeError("NBL login form not found")

    # Get the CSRF token
    csrf_token = form.find("input", {"name": "csrf_token"})
    if not csrf_token or not csrf_token.get("value"):
        raise RuntimeError("CSRF token not found in login form")

    # Prepare login data
    login_data = {
        "csrf_token": csrf_token["value"],
        "username": NBL_USERNAME,
        "password": NBL_PASSWORD,
        "remember": "on"  
    }

    headers = {
        "Referer": NBL_ADMIN_URL,
        "Origin": "https://app.nextbigloan.co.in",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }

    # Submit login form
    login_url = "https://app.nextbigloan.co.in/admin/login/doLogin"
    logger.info("NBL: POST login %s", login_url)
    login_resp = session.post(
        login_url,
        data=login_data,
        headers=headers,
        allow_redirects=True,
        timeout=60
    )
    login_resp.raise_for_status()

    # Check if login was successful
    if "login=incorrect" in login_resp.url:
        error_msg = "Login failed - invalid username or password"
        logger.error("NBL: %s", error_msg)
        raise RuntimeError(error_msg)

    logger.info("NBL: login successful")
    return session


def _month_date_range(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    start_d = date(year, month, 1)
    end_d = date(year, month, last_day)

    today = date.today()
    if year == today.year and month == today.month:
        # For current month, fetch only up to today so we always get the latest range
        end_d = today

    return start_d, end_d


def _clean_amount(v) -> float | None:
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _parse_date_any(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    s = str(v).strip()
    if not s:
        return None
    # handle strings like '2025-02-01', '01-02-2025', '01/02/2025', and with time
    s = s.replace("\\u00a0", " ")
    candidates = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    # last resort: try split date portion
    for sep in [" ", "T"]:
        if sep in s:
            head = s.split(sep, 1)[0]
            if head != s:
                d = _parse_date_any(head)
                if d:
                    return d
    return None


def _eli_login(session: requests.Session) -> None:
    if not ELI_USERNAME or not ELI_PASSWORD:
        raise RuntimeError("Missing ELI credentials. Set ELI_USERNAME and ELI_PASSWORD environment variables.")

    logger.info("ELI: fetching login page %s", ELI_LOGIN_URL)
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
    )

    r = session.get(ELI_LOGIN_URL, timeout=60)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    form = soup.find("form")
    if not form:
        raise RuntimeError("ELI login form not found")

    logger.info("ELI: found login form action=%s", form.get("action"))

    form_data: dict[str, str] = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        form_data[name] = inp.get("value", "")

    form_data.update({"userName": ELI_USERNAME, "password": ELI_PASSWORD})

    form_action = form.get("action", "")
    form_url = form_action if form_action.startswith("http") else "https://app.everydayloanindia.co.in" + form_action

    headers = {
        "Referer": ELI_LOGIN_URL,
        "Origin": "https://app.everydayloanindia.co.in",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    r2 = session.post(form_url, data=form_data, headers=headers, allow_redirects=True, timeout=60)
    r2.raise_for_status()
    if "dashboard" not in r2.url.lower():
        raise RuntimeError("ELI login failed")

    logger.info("ELI: login OK -> %s", r2.url)


def fetch_eli_disbursed_df(year: int, month: int) -> list[dict]:
    start_d, end_d = _month_date_range(year, month)

    logger.info("ELI: fetching disbursed data for %04d-%02d (%s..%s)", year, month, start_d, end_d)

    session = requests.Session()
    _eli_login(session)

    # visit page once
    session.get(ELI_DATA_URL, timeout=60)

    payload = {
        "startDate": start_d.strftime("%d-%m-%Y"),
        "endDate": end_d.strftime("%d-%m-%Y"),
        "submit": "Search",
    }
    headers = {
        "Referer": ELI_DATA_URL,
        "Origin": "https://app.everydayloanindia.co.in",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    logger.info("ELI: POST %s payload(startDate=%s,endDate=%s)", ELI_DATA_URL, payload.get("startDate"), payload.get("endDate"))
    r = session.post(ELI_DATA_URL, data=payload, headers=headers, timeout=90)
    r.raise_for_status()
    logger.info("ELI: response %s bytes=%s", r.status_code, len(r.text))
    soup = BeautifulSoup(r.text, "html.parser")

    table = soup.find("table", {"id": "example2"}) or soup.find("table")
    if not table:
        logger.warning("ELI: table not found on response")
        return []

    thead = table.find("thead")
    header_tr = thead.find("tr") if thead else table.find("tr")
    headers_row = [th.get_text(" ", strip=True) for th in header_tr.find_all("th")] if header_tr else []
    logger.info("ELI: header columns=%s", len(headers_row))

    tbody = table.find("tbody")
    trs = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

    records: list[dict] = []
    for tr in trs:
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        if not cells:
            continue
        if headers_row and len(cells) >= len(headers_row):
            records.append(dict(zip(headers_row, cells[: len(headers_row)])))
        else:
            records.append({f"col_{i+1}": v for i, v in enumerate(cells)})

    if not records:
        logger.warning("ELI: parsed 0 table rows")
        return []

    logger.info("ELI: parsed table rows=%s", len(records))

    normalized: list[dict] = []
    for rec in records:
        disbursal_date = _parse_date_any(rec.get("Disbursal Date"))
        if not disbursal_date:
            continue
        if disbursal_date.year != year or disbursal_date.month != month:
            continue

        normalized.append(
            {
                "source": "ELI",
                "disbursal_date": disbursal_date,
                "credit_by": str(rec.get("Credit By") or "").strip(),
                "loan_amount": _clean_amount(rec.get("Loan Amount")),
                "branch": str(rec.get("Branch") or "").strip(),
                "state": str(rec.get("State") or "").strip(),
                "loan_no": str(rec.get("Loan No") or "").strip(),
                "lead_id": str(rec.get("LeadID") or "").strip(),
            }
        )

    logger.info("ELI: normalized rows=%s", len(normalized))
    return normalized


def fetch_nbl_disbursed_df(year: int, month: int) -> list[dict]:
    if not NBL_USERNAME or not NBL_PASSWORD:
        raise RuntimeError("Missing NBL credentials. Set NBL_USERNAME and NBL_PASSWORD environment variables.")

    start_d, end_d = _month_date_range(year, month)

    logger.info("NBL: fetching disbursed data for %04d-%02d (%s..%s)", year, month, start_d, end_d)

    session = requests.Session()

    # Save login page HTML for debugging
    logger.info("NBL: fetching login page %s", NBL_ADMIN_URL)
    login_page = session.get(NBL_ADMIN_URL, timeout=60)
    login_page.raise_for_status()
    
    soup = BeautifulSoup(login_page.text, "html.parser")
    form = soup.find("form")
    if not form:
        logger.error("NBL: no login form found! Page title: %s", soup.title.text if soup.title else 'No title')
        raise RuntimeError("NBL login form not found")

    form_action = form.get("action") or NBL_ADMIN_URL
    logger.info("NBL: found login form action=%s", form_action)

    # Log all form inputs for debugging
    form_inputs = [(inp.get('name', 'unnamed'), inp.get('type', 'text')) 
                  for inp in form.find_all('input')]
    logger.info("NBL: form inputs: %s", form_inputs)

    login_data: dict[str, str] = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        login_data[name] = inp.get("value", "")

    # Try to find the actual field names from the form
    username_field = None
    password_field = None
    
    for inp in form.find_all('input'):
        name = inp.get('name', '').lower()
        if 'user' in name:
            username_field = inp.get('name')
        elif 'pass' in name:
            password_field = inp.get('name')
    
    # Fallback to common field names if not found
    if not username_field:
        if 'username' in login_data:
            username_field = 'username'
        elif 'userName' in login_data:
            username_field = 'userName'
        else:
            text_inp = form.find("input", {"type": "text"})
            if text_inp and text_inp.get("name"):
                username_field = text_inp["name"]
    
    if not password_field:
        if 'password' in login_data:
            password_field = 'password'
        else:
            pass_inp = form.find("input", {"type": "password"})
            if pass_inp and pass_inp.get("name"):
                password_field = pass_inp["name"]
    
    if not username_field or not password_field:
        raise RuntimeError(f"Could not determine username/password fields. Found username_field={username_field}, password_field={password_field}")
    
    logger.info("NBL: using username field='%s', password field='%s'", username_field, password_field)
    
    # Update login data with credentials
    login_data[username_field] = NBL_USERNAME
    login_data[password_field] = NBL_PASSWORD

    headers = {
        "Referer": NBL_ADMIN_URL,
        "Origin": "https://app.nextbigloan.co.in",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    logger.info("NBL: POST login %s with data: %s", form_action, 
               {k: '***' if k == password_field else v for k, v in login_data.items()})
    
    login_resp = session.post(
        form_action, 
        data=login_data, 
        headers=headers, 
        allow_redirects=True, 
        timeout=60
    )
    login_resp.raise_for_status()
    
    # Check for login failure
    if 'login=incorrect' in login_resp.url or 'login' in login_resp.url.lower():
        error_msg = "Login failed - check credentials"
        logger.error("NBL: %s", error_msg)
        raise RuntimeError(error_msg)
        
    logger.info("NBL: login OK (final url=%s, status=%d, content_length=%d)", 
        login_resp.url, login_resp.status_code, len(login_resp.text))

    # NBL sometimes does not support DataTables JSON pagination reliably.
    # Use ELI-style: visit page and POST the search form once.
    session.get(NBL_DATA_URL, timeout=60)

    headers = {
        "Referer": NBL_DATA_URL,
        "Origin": "https://app.nextbigloan.co.in",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }
    payload = {
        "startDate": start_d.strftime("%d-%m-%Y"),
        "endDate": end_d.strftime("%d-%m-%Y"),
        "submit": "Search",
    }

    logger.info(
        "NBL: POST %s payload(startDate=%s,endDate=%s)",
        NBL_DATA_URL,
        payload.get("startDate"),
        payload.get("endDate"),
    )
    r = session.post(NBL_DATA_URL, data=payload, headers=headers, timeout=90)
    r.raise_for_status()
    logger.info("NBL: response %s bytes=%s", r.status_code, len(r.text))

    def _rows_from_html_table(html_text: str):
        html_soup = BeautifulSoup(html_text, "html.parser")
        table = html_soup.find("table")
        if not table:
            return []

        headers_row = []
        thead = table.find("thead")
        if thead:
            headers_row = [th.get_text(" ", strip=True) for th in thead.find_all("th")]

        if headers_row:
            logger.info("NBL: HTML header columns=%s", len(headers_row))

        rows_local = []
        tbody = table.find("tbody") or table
        for tr in tbody.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if not cells:
                continue
            if headers_row and len(headers_row) == len(cells):
                rows_local.append(dict(zip(headers_row, cells)))
            else:
                rows_local.append({f"col_{i+1}": v for i, v in enumerate(cells)})
        return rows_local

    raw_rows: list[dict] = _rows_from_html_table(r.text)

    if not raw_rows:
        logger.warning("NBL: fetched 0 rows")
        return []

    logger.info("NBL: raw rows=%s", len(raw_rows))

    def _get_any(d: dict, *keys):
        for k in keys:
            if k in d and d[k] not in (None, ""):
                return d[k]
        return None

    normalized: list[dict] = []
    for rec in raw_rows:
        disb = _get_any(rec, "disbursal_date", "Disbursal Date", "disbursed_date", "Disbursed Date")
        disb_date = _parse_date_any(disb)
        if not disb_date:
            continue
        if disb_date.year != year or disb_date.month != month:
            continue

        normalized.append(
            {
                "source": "NBL",
                "disbursal_date": disb_date,
                "credit_by": str(_get_any(rec, "credit_by", "Credit By") or "").strip(),
                "loan_amount": _clean_amount(_get_any(rec, "loan_amount", "Loan Amount", "amount")),
                "branch": str(_get_any(rec, "branch", "Branch") or "").strip(),
                "state": str(_get_any(rec, "state", "State") or "").strip(),
                "loan_no": str(_get_any(rec, "loan_no", "Loan No", "Loan No.") or "").strip(),
                "lead_id": str(_get_any(rec, "lead_id", "LeadID", "Lead Id") or "").strip(),
            }
        )

    return normalized


def _crm_login(session: requests.Session, *, label: str, login_url: str, username: str, password: str) -> None:
    if not username or not password:
        raise RuntimeError(f"Missing {label} credentials. Set {label}_USERNAME and {label}_PASSWORD environment variables.")

    logger.info("%s: fetching login page %s", label, login_url)
    r = session.get(login_url, timeout=60, verify=False)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    form = soup.find("form")
    if not form:
        raise RuntimeError(f"{label} login form not found")

    form_action = form.get("action") or login_url
    if not form_action.startswith("http"):
        base = login_url.rstrip("/")
        if form_action.startswith("/"):
            form_action = base + form_action
        else:
            form_action = base + "/" + form_action

    inputs = []
    form_data: dict[str, str] = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        itype = (inp.get("type") or "").lower()
        inputs.append((name, itype))
        form_data[name] = inp.get("value", "")

    logger.info("%s: found login form action=%s", label, form_action)
    logger.info("%s: form inputs: %s", label, inputs)

    username_field = None
    password_field = None
    for name, itype in inputs:
        n = name.lower()
        if itype == "password" or "pass" in n:
            if not password_field:
                password_field = name
        if any(x in n for x in ["user", "email", "login", "employee", "userid", "username", "employeeid"]):
            if not username_field and itype != "password":
                username_field = name

    if not username_field:
        text_inp = form.find("input", {"type": "text"})
        if text_inp and text_inp.get("name"):
            username_field = text_inp["name"]

    if not password_field:
        pass_inp = form.find("input", {"type": "password"})
        if pass_inp and pass_inp.get("name"):
            password_field = pass_inp["name"]

    if not username_field or not password_field:
        raise RuntimeError(
            f"{label} could not determine username/password fields. Found username_field={username_field}, password_field={password_field}"
        )

    form_data[username_field] = username
    form_data[password_field] = password

    headers = {
        "Referer": login_url,
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    logger.info(
        "%s: POST login %s with data: %s",
        label,
        form_action,
        {k: "***" if k == password_field else v for k, v in form_data.items()},
    )
    r2 = session.post(form_action, data=form_data, headers=headers, allow_redirects=True, timeout=60, verify=False)
    r2.raise_for_status()
    logger.info("%s: login response final url=%s status=%s bytes=%s", label, r2.url, r2.status_code, len(r2.text))

    if "login" in (r2.url or "").lower() and "dashboard" not in (r2.url or "").lower():
        raise RuntimeError(f"{label} login failed (final url={r2.url})")


def _rows_from_any_html_table(html_text: str) -> list[dict]:
    html_soup = BeautifulSoup(html_text, "html.parser")
    table = html_soup.find("table")
    if not table:
        return []

    headers_row: list[str] = []
    thead = table.find("thead")
    if thead:
        headers_row = [th.get_text(" ", strip=True) for th in thead.find_all("th")]

    rows_local: list[dict] = []
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        if not cells:
            continue
        if headers_row and len(headers_row) == len(cells):
            rows_local.append(dict(zip(headers_row, cells)))
        else:
            rows_local.append({f"col_{i+1}": v for i, v in enumerate(cells)})

    return rows_local


def _normalize_disbursed_rows(rows: list[dict], *, source: str, year: int, month: int) -> list[dict]:
    def _get_any(d: dict, *keys):
        for k in keys:
            if k in d and d[k] not in (None, ""):
                return d[k]
        return None

    normalized: list[dict] = []
    for rec in rows:
        disb = _get_any(
            rec,
            "Disbursal Date",
            "Disbursed Date",
            "disbursal_date",
            "disbursed_date",
            "Date",
        )
        disb_date = _parse_date_any(disb)
        if not disb_date:
            continue
        if disb_date.year != year or disb_date.month != month:
            continue

        normalized.append(
            {
                "source": source,
                "disbursal_date": disb_date,
                "credit_by": str(_get_any(rec, "Credit By", "credit_by", "CM", "Sales") or "").strip(),
                "loan_amount": _clean_amount(_get_any(rec, "Loan Amount", "loan_amount", "Amount", "Disbursed Amount", "disbursed_amount")),
                "branch": str(_get_any(rec, "Branch", "branch") or "").strip(),
                "state": str(_get_any(rec, "State", "state") or "").strip(),
                "loan_no": str(_get_any(rec, "Loan No", "Loan No.", "loan_no", "Loan Number") or "").strip(),
                "lead_id": str(_get_any(rec, "LeadID", "Lead Id", "lead_id", "Lead ID") or "").strip(),
            }
        )

    return normalized


def fetch_cp_disbursed_df(year: int, month: int) -> list[dict]:
    if not CP_USERNAME or not CP_PASSWORD:
        raise RuntimeError("Missing CP credentials. Set CP_USERNAME and CP_PASSWORD environment variables.")

    start_d, end_d = _month_date_range(year, month)
    logger.info("CP: fetching disbursed data for %04d-%02d (%s..%s)", year, month, start_d, end_d)

    session = requests.Session()
    _crm_login(session, label="CP", login_url=CP_LOGIN_URL, username=CP_USERNAME, password=CP_PASSWORD)

    logger.info("CP: GET %s", CP_DATA_URL)
    r = session.get(CP_DATA_URL, timeout=90, allow_redirects=True, verify=False)
    r.raise_for_status()
    logger.info("CP: response %s bytes=%s final_url=%s", r.status_code, len(r.text), r.url)

    rows = _rows_from_any_html_table(r.text)
    if not rows:
        logger.warning("CP: fetched 0 rows")
        return []

    out = _normalize_disbursed_rows(rows, source="CP", year=year, month=month)
    logger.info("CP: normalized rows=%s", len(out))
    return out


def fetch_lr_disbursed_df(year: int, month: int) -> list[dict]:
    if not LR_USERNAME or not LR_PASSWORD:
        raise RuntimeError("Missing LR credentials. Set LR_USERNAME and LR_PASSWORD environment variables.")

    start_d, end_d = _month_date_range(year, month)
    logger.info("LR: fetching disbursed data for %04d-%02d (%s..%s)", year, month, start_d, end_d)

    session = requests.Session()
    _crm_login(session, label="LR", login_url=LR_LOGIN_URL, username=LR_USERNAME, password=LR_PASSWORD)

    logger.info("LR: GET %s", LR_DATA_URL)
    r = session.get(LR_DATA_URL, timeout=90, allow_redirects=True, verify=False)
    r.raise_for_status()
    logger.info("LR: response %s bytes=%s final_url=%s", r.status_code, len(r.text), r.url)

    rows = _rows_from_any_html_table(r.text)
    if not rows:
        logger.warning("LR: fetched 0 rows")
        return []

    out = _normalize_disbursed_rows(rows, source="LR", year=year, month=month)
    logger.info("LR: normalized rows=%s", len(out))
    return out


def fetch_combined_disbursed_df(year: int, month: int) -> list[dict]:
    eli = fetch_eli_disbursed_df(year, month)
    nbl = fetch_nbl_disbursed_df(year, month)
    cp = fetch_cp_disbursed_df(year, month)
    lr = fetch_lr_disbursed_df(year, month)
    logger.info("NBL: fetched %s rows", len(nbl))

    combined = list(eli) + list(nbl) + list(cp) + list(lr)
    combined = [r for r in combined if r.get("disbursal_date") and r.get("loan_amount") is not None]
    for r in combined:
        r["credit_by"] = str(r.get("credit_by") or "").strip()

    logger.info("COMBINED: ELI=%s NBL=%s CP=%s LR=%s TOTAL=%s", len(eli), len(nbl), len(cp), len(lr), len(combined))
    return combined