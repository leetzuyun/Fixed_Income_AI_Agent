"""
pipelines/underwrite_info/scraper.py
爬 TWSA 承銷公告列表（http://web2.twsa.org.tw/Bond/Home/Index）跟下載每
筆公告對應的 PDF 檔案。邏輯搬自你原本的 bond_scraper.py，這支只負責
「抓資料」，不做 LLM 欄位擷取（見 extractor.py）也不做儲存（見
domains/underwriting_kb/store.py）——三件事分開，之後要各自測試或替換
其中一段都不會牽動其他部分。
"""
import re

import requests
from bs4 import BeautifulSoup

BASE_URL = "http://web2.twsa.org.tw"
LIST_URL = f"{BASE_URL}/Bond/Home/Index"
DOWNLOAD_URL = f"{BASE_URL}/Bond/Home/Download"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": LIST_URL,
}


def fetch_listing(year: str, session: requests.Session = None) -> list:
    session = session or requests.Session()
    params = {"year": year}
    resp = session.get(LIST_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        print(f"[WARN] No table found on listing page (year={year})")
        return []

    rows = []
    for tr in table.find("tbody").find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 11:
            continue
        fn_tag = tds[10].find("a")
        fn = ""
        if fn_tag and fn_tag.get("href"):
            m = re.search(r"fn=([^\"&\s]+)", fn_tag["href"])
            if m:
                fn = m.group(1)
        rows.append({
            "序號": tds[0].get_text(strip=True),
            "申報日期": tds[1].get_text(strip=True),
            "主辦承銷商": tds[2].get_text(strip=True),
            "案件名稱": tds[3].get_text(strip=True),
            "方式": tds[4].get_text(strip=True),
            "發行性質": tds[5].get_text(strip=True),
            "發行種類": tds[6].get_text(strip=True),
            "公告檔_fn": fn,
        })
    return rows


def download_pdf(fn: str, session: requests.Session = None):
    session = session or requests.Session()
    try:
        resp = session.get(DOWNLOAD_URL, params={"fn": fn}, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        if resp.content[:4] == b"%PDF" or b"%PDF" in resp.content[:10]:
            return resp.content
        print(f"  [WARN] fn={fn} response not PDF (Content-Type: {resp.headers.get('Content-Type')})")
        return None
    except Exception as e:
        print(f"  [ERROR] download fn={fn}: {e}")
        return None
