import calendar
import csv
import io
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
import warnings
import requests
import urllib3
from bs4 import BeautifulSoup

try:
    import openpyxl
    _OPENPYXL_AVAILABLE = True
except ImportError:
    _OPENPYXL_AVAILABLE = False

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("scrapers")


ELI_LOGIN_URL = "https://app.everydayloanindia.co.in/admin/loginindex"
ELI_DATA_URL = "https://app.everydayloanindia.co.in/admin/dateWiseDisbursed"
ELI_EXPORT_URL = "https://app.everydayloanindia.co.in/admin/disbursedDataExport"
ELI_EXPORT_REFERER = "https://app.everydayloanindia.co.in/admin/disbursedData"

ELI_USERNAME = os.getenv("ELI_USERNAME", "")
ELI_PASSWORD = os.getenv("ELI_PASSWORD", "")

NBL_ADMIN_URL = "https://app.nextbigloan.co.in/admin"
NBL_DATA_URL = "https://app.nextbigloan.co.in/admin/dateWiseDisbursed"
NBL_EXPORT_URL = "https://app.nextbigloan.co.in/admin/disbursedDataExport"
NBL_EXPORT_REFERER = "https://app.nextbigloan.co.in/admin/disbursedData"

NBL_USERNAME = os.getenv("NBL_USERNAME", "")
NBL_PASSWORD = os.getenv("NBL_PASSWORD", "")

CP_LOGIN_URL = "https://app.creditpey.in/"
CP_DATA_URL = "https://app.creditpey.in/reporting/filter/disbursed"

CP_USERNAME = os.getenv("CP_USERNAME", "")
CP_PASSWORD = os.getenv("CP_PASSWORD", "")

LR_LOGIN_URL = "https://app.lendingrupee.in/"
LR_DATA_URL = "https://app.lendingrupee.in/reporting/filter/disbursed"

LR_USERNAME = os.getenv("LR_USERNAME", "")
LR_PASSWORD = os.getenv("LR_PASSWORD", "")


def _month_date_range(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    start_d = date(year, month, 1)
    end_d = date(year, month, last_day)
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
    s = s.replace("\u00a0", " ")
    
    # Normalize am/pm to uppercase for parsing
    s_normalized = s.replace(" am", " AM").replace(" pm", " PM")
    
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
        "%d-%m-%Y %I:%M:%S %p",  # 12-hour format with seconds: 07-02-2026 05:24:07 PM
        "%d-%m-%Y %I:%M %p",     # 12-hour format without seconds
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(s_normalized, fmt).date()
        except Exception:
            pass
    
    # Log parsing failure for debugging
    logger.warning("_parse_date_any: failed to parse date %r", s)
    
    # last resort: try split date portion
    for sep in [" ", "T"]:
        if sep in s:
            head = s.split(sep, 1)[0]
            if head != s:
                d = _parse_date_any(head)
                if d:
                    return d
    return None

def _get_field(d: dict, *keys):
    """Return the first non-empty value found under any of the given keys."""
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
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

    for attempt in range(3):
        try:
            r = session.get(ELI_LOGIN_URL, timeout=60)
            r.raise_for_status()
            break
        except requests.exceptions.Timeout:
            logger.warning("ELI: login page attempt %s timed out", attempt + 1)
            if attempt == 2:
                raise
            time.sleep(3)

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


def fetch_eli_loans(year: int, month: int) -> list[dict]:
    start_d, end_d = _month_date_range(year, month)

    logger.info("ELI: fetching disbursed data for %04d-%02d (%s..%s)", year, month, start_d, end_d)

    session = requests.Session()
    _eli_login(session)

    logger.info("ELI: HTML scrape via %s", ELI_DATA_URL)
    session.get(ELI_DATA_URL, timeout=60)
    html_payload = {
        "startDate": start_d.strftime("%d-%m-%Y"),
        "endDate": end_d.strftime("%d-%m-%Y"),
        "submit": "Search",
    }
    html_headers = {
        "Referer": ELI_DATA_URL,
        "Origin": "https://app.everydayloanindia.co.in",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    records: list[dict] = []
    max_retries = 3
    for attempt in range(max_retries):
        try:
            r = session.post(ELI_DATA_URL, data=html_payload, headers=html_headers, timeout=90)
            r.raise_for_status()
            break
        except requests.exceptions.Timeout:
            logger.warning("ELI: HTML attempt %s timed out", attempt + 1)
            if attempt == max_retries - 1:
                raise
            time.sleep(3)

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", {"id": "example2"}) or soup.find("table")
    if not table:
        logger.warning("ELI: table not found on response")
        return []
    thead = table.find("thead")
    header_tr = thead.find("tr") if thead else table.find("tr")
    headers_row = [th.get_text(" ", strip=True) for th in header_tr.find_all("th")] if header_tr else []
    tbody = table.find("tbody")
    trs = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
    for tr in trs:
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        if not cells:
            continue
        if headers_row and len(cells) >= len(headers_row):
            records.append(dict(zip(headers_row, cells[: len(headers_row)])))
        else:
            records.append({f"col_{i+1}": v for i, v in enumerate(cells)})

    if not records:
        logger.warning("ELI: fetched 0 rows")
        return []

    logger.info("ELI: raw rows=%s, first row keys: %s", len(records), list(records[0].keys()))

    normalized: list[dict] = []
    parse_fail = 0
    date_mismatch = 0
    for rec in records:
        disbursal_date = _parse_date_any(
            _get_field(rec, "Disbursal Date", "disbursal_date", "Disbursed Date", "Date")
        )
        if not disbursal_date:
            parse_fail += 1
            continue
        if disbursal_date.year != year or disbursal_date.month != month:
            date_mismatch += 1
            continue

        normalized.append(
            {
                "source": "ELI",
                "disbursal_date": disbursal_date,
                "credit_by": str(_get_field(rec, "Credit By", "credit_by") or "").strip(),
                "loan_amount": _clean_amount(_get_field(rec, "Loan Amount", "loan_amount")),
                "branch": str(_get_field(rec, "Branch", "branch") or "").strip(),
                "state": str(_get_field(rec, "State", "state") or "").strip(),
                "loan_no": str(_get_field(rec, "Loan No", "loan_no") or "").strip(),
                "lead_id": str(_get_field(rec, "LeadID", "lead_id", "Lead Id") or "").strip(),
            }
        )

    logger.info("ELI: normalized rows=%s (parse_fail=%s, date_mismatch=%s)", len(normalized), parse_fail, date_mismatch)
    return normalized


def fetch_nbl_loans(year: int, month: int) -> list[dict]:
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

    # NBL export endpoint returns ALL historical data (ignores date range), so use HTML scrape instead
    logger.info("NBL: HTML scrape via %s (startDate=%s, endDate=%s)", NBL_DATA_URL, start_d.strftime("%d-%m-%Y"), end_d.strftime("%d-%m-%Y"))
    session.get(NBL_DATA_URL, timeout=90)
    html_headers = {
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
    raw_rows: list[dict] = []
    max_retries = 3
    for attempt in range(max_retries):
        try:
            r = session.post(NBL_DATA_URL, data=payload, headers=html_headers, timeout=90)
            r.raise_for_status()
            break
        except requests.exceptions.Timeout:
            logger.warning("NBL: attempt %s timed out", attempt + 1)
            if attempt == max_retries - 1:
                raise
            time.sleep(3)
    raw_rows = _parse_html_table(r.text)

    if not raw_rows:
        logger.warning("NBL: fetched 0 rows")
        return []

    logger.info("NBL: raw rows=%s, first row keys: %s", len(raw_rows), list(raw_rows[0].keys()))

    normalized: list[dict] = []
    parse_fail = 0
    date_mismatch = 0
    for rec in raw_rows:
        disb = _get_field(rec, "disbursal_date", "Disbursal Date", "disbursed_date", "Disbursed Date", "Date")
        disb_date = _parse_date_any(disb)
        if not disb_date:
            parse_fail += 1
            if parse_fail <= 3:
                logger.info("NBL: parse_fail for date=%r", disb)
            continue
        if disb_date.year != year or disb_date.month != month:
            date_mismatch += 1
            continue

        normalized.append(
            {
                "source": "NBL",
                "disbursal_date": disb_date,
                "credit_by": str(_get_field(rec, "credit_by", "Credit By") or "").strip(),
                "loan_amount": _clean_amount(_get_field(rec, "loan_amount", "Loan Amount", "amount")),
                "branch": str(_get_field(rec, "branch", "Branch") or "").strip(),
                "state": str(_get_field(rec, "state", "State", "Branch", "branch") or "").strip(),
                "loan_no": str(_get_field(rec, "loan_no", "Loan No", "Loan No.") or "").strip(),
                "lead_id": str(_get_field(rec, "lead_id", "LeadID", "Lead Id") or "").strip(),
            }
        )

    logger.info("NBL: normalized rows=%s (parse_fail=%s, date_mismatch=%s)", len(normalized), parse_fail, date_mismatch)
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


def _parse_export_file(response: requests.Response, label: str) -> list[dict]:
    """Parse an export file response (xlsx or csv) into a list of dicts."""
    content_type = (response.headers.get("Content-Type") or "").lower()
    content = response.content

    # Try Excel first (xlsx)
    is_xlsx = (
        "spreadsheet" in content_type
        or "excel" in content_type
        or "openxmlformats" in content_type
        or content[:4] == b"PK\x03\x04"  # ZIP magic bytes for xlsx
    )
    if is_xlsx and _OPENPYXL_AVAILABLE:
        try:
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            wb.close()
            if not rows:
                logger.warning("%s: export xlsx has no rows", label)
                return []
            headers = [str(h).strip() if h is not None else f"col_{i+1}" for i, h in enumerate(rows[0])]
            result = []
            for row in rows[1:]:
                if all(v is None or str(v).strip() == "" for v in row):
                    continue
                result.append({headers[i]: (row[i] if i < len(row) else None) for i in range(len(headers))})
            logger.info("%s: export xlsx parsed %s rows (headers=%s)", label, len(result), headers[:5])
            return result
        except Exception as e:
            logger.warning("%s: xlsx parse failed (%s), trying csv", label, e)

    # Try CSV
    try:
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        result = [row for row in reader]
        if result:
            logger.info("%s: export csv parsed %s rows", label, len(result))
            return result
    except Exception as e:
        logger.warning("%s: csv parse failed (%s)", label, e)

    logger.warning("%s: export response not xlsx or csv (content_type=%s, bytes=%s)", label, content_type, len(content))
    return []


def _parse_html_table(html_text: str):
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


def _fetch_crm_loans(
    year: int, month: int, *,
    label: str, login_url: str, data_url: str, username: str, password: str
) -> list[dict]:
    """Shared fetcher for CRM portals (CP and LR) that support exportByDate."""
    if not username or not password:
        raise RuntimeError(f"Missing {label} credentials.")

    logger.info("%s: fetching disbursed data for %04d-%02d", label, year, month)

    session = requests.Session()
    _crm_login(session, label=label, login_url=login_url, username=username, password=password)

    start_d, end_d = _month_date_range(year, month)
    date_range_str = f"{start_d.strftime('%m/%d/%Y')} - {end_d.strftime('%m/%d/%Y')}"

    # Try export endpoint first (single request, exact data)
    r = session.get(
        data_url,
        params={"filter": "exportByDate", "exportRange": date_range_str},
        headers={"Referer": data_url},
        timeout=120,
        verify=False,
    )
    r.raise_for_status()
    logger.info("%s: export response status=%s content_type=%s bytes=%s",
                label, r.status_code, r.headers.get("Content-Type"), len(r.content))

    all_rows = _parse_export_file(r, label)

    # Fallback: paginate via sortByDate if export returned nothing
    if not all_rows:
        logger.warning("%s: export returned 0 rows, falling back to sortByDate pagination", label)
        page = 1
        while page <= 1000:
            r2 = session.get(
                data_url,
                params={"filter": "sortByDate", "searchRange": date_range_str, "page": page},
                headers={"Referer": data_url},
                timeout=90,
                verify=False,
            )
            r2.raise_for_status()
            rows = _parse_html_table(r2.text)
            if not rows or len(rows) <= 1:
                break
            logger.info("%s: fallback page %s → %s rows", label, page, len(rows))
            all_rows.extend(rows)
            if len(rows) < 10:
                break
            page += 1
        # Dedup by loan_no to handle cross-page overlaps
        seen_ln: set[str] = set()
        deduped: list[dict] = []
        for row in all_rows:
            ln = str(row.get("Loan No", row.get("Loan No.", "")) or "").strip()
            if ln and ln in seen_ln:
                continue
            if ln:
                seen_ln.add(ln)
            deduped.append(row)
        all_rows = deduped

    if not all_rows:
        logger.warning("%s: fetched 0 rows after all attempts", label)
        return []

    logger.info("%s: first row keys: %s", label, list(all_rows[0].keys()))

    normalized: list[dict] = []
    parse_fail = 0
    date_mismatch = 0
    for rec in all_rows:
        disb = _get_field(rec, "Disbursal Date", "Disbursed Date", "disbursal_date", "disbursed_date", "Date")
        disb_date = _parse_date_any(disb)
        if not disb_date:
            parse_fail += 1
            if parse_fail <= 3:
                logger.info("%s: parse_fail for date=%r", label, disb)
            continue
        if disb_date.year != year or disb_date.month != month:
            date_mismatch += 1
            logger.info("%s: DATE_MISMATCH date=%s", label, disb_date)
            continue

        normalized.append({
            "source": label,
            "disbursal_date": disb_date,
            "credit_by": str(_get_field(rec, "Credit By", "credit_by", "CM", "Sales", "Sanction By") or "").strip(),
            "loan_amount": _clean_amount(
                _get_field(rec, "Loan Amount", "loan_amount", "Amount", "Disbursed Amount", "disbursed_amount")
            ),
            "branch": str(_get_field(rec, "Branch", "branch") or "").strip(),
            "state": str(_get_field(rec, "State", "state", "Location", "location", "Region", "region",
                                  "City", "city", "Area", "area", "Branch", "branch") or "").strip(),
            "loan_no": str(_get_field(rec, "Loan No", "Loan No.", "loan_no", "Loan Number") or "").strip(),
            "lead_id": str(_get_field(rec, "LeadID", "Lead Id", "lead_id", "Lead ID") or "").strip(),
        })

    total = sum(float(r.get("loan_amount") or 0) for r in normalized)
    logger.info("%s: normalized rows=%s (parse_fail=%s, date_mismatch=%s) total=%.2f",
                label, len(normalized), parse_fail, date_mismatch, total)
    return normalized


def fetch_cp_loans(year: int, month: int) -> list[dict]:
    return _fetch_crm_loans(
        year, month,
        label="CP", login_url=CP_LOGIN_URL, data_url=CP_DATA_URL,
        username=CP_USERNAME, password=CP_PASSWORD,
    )


def fetch_lr_loans(year: int, month: int) -> list[dict]:
    return _fetch_crm_loans(
        year, month,
        label="LR", login_url=LR_LOGIN_URL, data_url=LR_DATA_URL,
        username=LR_USERNAME, password=LR_PASSWORD,
    )


def fetch_all_loans(year: int, month: int) -> list[dict]:
    sources = [
        ("ELI", fetch_eli_loans),
        ("NBL", fetch_nbl_loans),
        ("CP", fetch_cp_loans),
        ("LR", fetch_lr_loans),
    ]
    results = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        future_to_label = {pool.submit(fn, year, month): label for label, fn in sources}
        for future in as_completed(future_to_label):
            label = future_to_label[future]
            try:
                results[label] = future.result()
            except Exception as exc:
                logger.error("%s: fetch failed - %s", label, exc)
                results[label] = []

    eli, nbl, cp, lr = results["ELI"], results["NBL"], results["CP"], results["LR"]
    combined = eli + nbl + cp + lr
    combined = [r for r in combined if r.get("disbursal_date") and r.get("loan_amount") is not None]
    for r in combined:
        r["credit_by"] = str(r.get("credit_by") or "").strip()

    logger.info("COMBINED: ELI=%s NBL=%s CP=%s LR=%s TOTAL=%s", len(eli), len(nbl), len(cp), len(lr), len(combined))
    return combined