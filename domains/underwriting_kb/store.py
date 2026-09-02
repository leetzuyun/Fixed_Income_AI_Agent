"""
domains/underwriting_kb/store.py
承銷公告資料的 SQLite 儲存與查詢層。跟 infra/status_store.py 是同樣的
設計哲學（stdlib sqlite3，不用另外裝套件），但這裡存的是實際業務資料
（承銷公告、債券、承銷商、承銷金額），不是執行紀錄。

四張表對應原本 bond_scraper.py 的 star schema 設計（維度表 + 事實表）：
  - announcements：每筆公告
  - bonds：每支債券
  - underwriters：每家承銷商
  - underwriting_facts：承銷商對債券的承銷紀錄（FK 對應前三張表）

用 announcement_no 當唯一鍵：同一份公告重複匯入（例如重跑同一個年度）
會更新既有紀錄，不會重複累積——這點跟原本 bond_scraper.py 每次都重新產
生一份全新 Excel 不一樣，這裡是持續累積的資料庫，設計上要處理重跑。

為什麼用「特定查詢函式」而不是開放 agent 自己下 SQL：LLM 生成的 SQL 不
夠穩定可預期（打錯欄位名稱、忘記 JOIN 條件都很常見），這裡改成寫死幾個
明確、涵蓋常見問題的查詢函式，agent 只需要選對函式、給對參數，不用自己
組 SQL。
"""
import os
import re
import sqlite3
import contextlib

from infra.paths import PROJECT_ROOT

DB_PATH = os.path.join(PROJECT_ROOT, "domains", "underwriting_kb", "underwriting.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS announcements (
    announcement_no TEXT PRIMARY KEY,
    published_date TEXT,
    year TEXT,
    month TEXT,
    quarter TEXT,
    lead_underwriter TEXT,
    case_name TEXT,
    method TEXT,
    issue_nature TEXT,
    issue_type TEXT
);

CREATE TABLE IF NOT EXISTS bonds (
    bond_name TEXT PRIMARY KEY,
    issuer_name TEXT,
    bond_type TEXT,
    maturity_date TEXT
);

CREATE TABLE IF NOT EXISTS underwriters (
    underwriter_name TEXT PRIMARY KEY,
    underwriter_type TEXT
);

CREATE TABLE IF NOT EXISTS underwriting_facts (
    announcement_no TEXT PRIMARY KEY,
    bond_name TEXT,
    underwriter_name TEXT,
    amount_raw TEXT,
    amount_numeric REAL,
    currency TEXT,
    quantity_raw TEXT,
    FOREIGN KEY (announcement_no) REFERENCES announcements(announcement_no),
    FOREIGN KEY (bond_name) REFERENCES bonds(bond_name),
    FOREIGN KEY (underwriter_name) REFERENCES underwriters(underwriter_name)
);
"""


@contextlib.contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn.executescript(_SCHEMA)  # _SCHEMA 有 4 個 CREATE TABLE 陳述式，
        # execute() 一次只能跑一句，這裡要用 executescript()
        yield conn
        conn.commit()
    finally:
        conn.close()


_AMOUNT_CLEAN_RE = re.compile(r"[,\s元]")


def parse_amount(raw):
    """把「總承銷/洽商銷售金額」的原始字串轉成數字，轉不出來（空白、
    "—"、非數字文字）回傳 None。

    這只是去除逗號/空白/「元」之後轉 float，沒有處理匯率換算——所以
    list_underwriters() 的市占率彙總，只在同幣別（多半是 TWD）之間比較
    才有意義，混著不同幣別直接加總會失真，見 list_underwriters() 的
    docstring。
    """
    if raw is None or raw == "—":
        return None
    cleaned = _AMOUNT_CLEAN_RE.sub("", str(raw))
    try:
        return float(cleaned)
    except ValueError:
        return None


def save_records(records: list) -> int:
    """把一批 records（listing 資料 + Gemini 擷取欄位合併後的 dict）寫進
    SQLite，用 announcement_no 當鍵，重複匯入會更新既有紀錄，不會重複累
    積。回傳實際寫入（含更新）的筆數。"""
    count = 0
    with _connect() as conn:
        for rec in records:
            ann_no = rec.get("序號", "")
            if not ann_no:
                continue

            date_str = rec.get("申報日期", "")
            parts = date_str.split("/") if "/" in date_str else []
            year = parts[0] if len(parts) > 0 else ""
            month = parts[1] if len(parts) > 1 else ""
            quarter = f"Q{((int(month) - 1) // 3) + 1}" if month.isdigit() else ""

            conn.execute(
                """INSERT INTO announcements
                   (announcement_no, published_date, year, month, quarter,
                    lead_underwriter, case_name, method, issue_nature, issue_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(announcement_no) DO UPDATE SET
                     published_date=excluded.published_date, year=excluded.year,
                     month=excluded.month, quarter=excluded.quarter,
                     lead_underwriter=excluded.lead_underwriter,
                     case_name=excluded.case_name, method=excluded.method,
                     issue_nature=excluded.issue_nature, issue_type=excluded.issue_type""",
                (ann_no, date_str, year, month, quarter,
                 rec.get("主辦承銷商", ""), rec.get("案件名稱", ""),
                 rec.get("方式", ""), rec.get("發行性質", ""), rec.get("發行種類", "")),
            )

            bond_name = rec.get("債券名稱") or rec.get("案件名稱", "—")
            conn.execute(
                """INSERT INTO bonds (bond_name, issuer_name, bond_type, maturity_date)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(bond_name) DO UPDATE SET
                     issuer_name=excluded.issuer_name, bond_type=excluded.bond_type,
                     maturity_date=excluded.maturity_date""",
                (bond_name, rec.get("發行人", "—"), rec.get("發行種類", "—"),
                 rec.get("到期日", "—")),
            )

            uw_name = rec.get("承銷商名稱", "—")
            conn.execute(
                """INSERT INTO underwriters (underwriter_name, underwriter_type)
                   VALUES (?, ?)
                   ON CONFLICT(underwriter_name) DO UPDATE SET
                     underwriter_type=excluded.underwriter_type""",
                (uw_name, "—"),
            )

            amount_raw = rec.get("總承銷/洽商銷售金額", "—")
            conn.execute(
                """INSERT INTO underwriting_facts
                   (announcement_no, bond_name, underwriter_name, amount_raw,
                    amount_numeric, currency, quantity_raw)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(announcement_no) DO UPDATE SET
                     bond_name=excluded.bond_name, underwriter_name=excluded.underwriter_name,
                     amount_raw=excluded.amount_raw, amount_numeric=excluded.amount_numeric,
                     currency=excluded.currency, quantity_raw=excluded.quantity_raw""",
                (ann_no, bond_name, uw_name, amount_raw, parse_amount(amount_raw),
                 rec.get("幣別", "TWD"), rec.get("總承銷/洽商銷售數量", "—")),
            )
            count += 1
    return count


def list_underwriters(year: str = None) -> list:
    """列出承銷商在指定年度（year=None 代表全部年度）的案件數、TWD 計價
    案件的金額總計、市占率。

    市占率只計算幣別為 TWD 且金額可解析為數字的案件；非 TWD 計價、或金
    額欄位無法解析成數字的案件，不納入市占率分母（沒有匯率換算資料，
    直接加總會失真），改用 excluded_count 標示這家承銷商有幾筆案件被排
    除在市占率計算外。
    """
    with _connect() as conn:
        where = "WHERE a.year = ?" if year else ""
        params = (year,) if year else ()
        rows = conn.execute(
            f"""SELECT f.underwriter_name, f.currency, f.amount_numeric
                FROM underwriting_facts f
                JOIN announcements a ON a.announcement_no = f.announcement_no
                {where}""",
            params,
        ).fetchall()

    totals = {}
    counts = {}
    excluded_counts = {}
    for row in rows:
        name = row["underwriter_name"]
        counts[name] = counts.get(name, 0) + 1
        if row["currency"] == "TWD" and row["amount_numeric"] is not None:
            totals[name] = totals.get(name, 0.0) + row["amount_numeric"]
        else:
            excluded_counts[name] = excluded_counts.get(name, 0) + 1

    grand_total = sum(totals.values())
    result = []
    for name in sorted(counts):
        twd_total = totals.get(name, 0.0)
        result.append({
            "underwriter_name": name,
            "deal_count": counts[name],
            "twd_total_amount": twd_total,
            "market_share_pct": round(twd_total / grand_total * 100, 2) if grand_total else None,
            "excluded_non_twd_count": excluded_counts.get(name, 0),
        })
    result.sort(key=lambda r: r["twd_total_amount"], reverse=True)
    return result


def search_bonds(keyword: str) -> list:
    """依債券名稱或發行人關鍵字搜尋，回傳符合的公告摘要清單（公告序
    號、申報日期、案件名稱、承銷商、金額原始字串、幣別）。"""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT a.announcement_no, a.published_date, a.case_name,
                      f.bond_name, f.underwriter_name, f.amount_raw, f.currency
               FROM underwriting_facts f
               JOIN announcements a ON a.announcement_no = f.announcement_no
               JOIN bonds b ON b.bond_name = f.bond_name
               WHERE b.bond_name LIKE ? OR b.issuer_name LIKE ?
               ORDER BY a.published_date DESC""",
            (f"%{keyword}%", f"%{keyword}%"),
        ).fetchall()
        return [dict(r) for r in rows]


def get_announcement(announcement_no: str):
    """讀取單一公告的完整細節（公告資訊 + 債券資訊 + 承銷資訊）。找不到
    回傳 None。"""
    with _connect() as conn:
        row = conn.execute(
            """SELECT a.*, b.issuer_name, b.bond_type, b.maturity_date,
                      f.underwriter_name, f.amount_raw, f.currency, f.quantity_raw
               FROM announcements a
               LEFT JOIN underwriting_facts f ON f.announcement_no = a.announcement_no
               LEFT JOIN bonds b ON b.bond_name = f.bond_name
               WHERE a.announcement_no = ?""",
            (announcement_no,),
        ).fetchone()
        return dict(row) if row else None


def count_records() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM underwriting_facts").fetchone()
        return row["c"]
