"""
pipelines/underwrite_info/nodes/persist.py
把解析後的 records 寫進 SQLite（給查詢工具用），同時輸出一份 Excel
（人工瀏覽用）。Excel 檔名改用執行當下的日期，不再用「年度」命名——因為
sources/ 底下可能混著不同年度的公告，不是像爬蟲版本一樣一次只抓一個年
度。
"""
import datetime
import os

from langchain_core.runnables import chain

from infra.paths import PROJECT_ROOT
from domains.underwriting_kb import store
from pipelines.underwrite_info.excel_export import write_excel

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "domains", "underwriting_kb", "exports")


@chain
def persist(state: dict) -> dict:
    if state.get("skipped"):
        return state

    records = state.get("records", [])
    saved_count = store.save_records(records)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.date.today().isoformat()
    excel_path = os.path.join(OUTPUT_DIR, f"underwriting_{date_str}.xlsx")
    write_excel(records, excel_path)

    print(f"  -> 寫入 SQLite {saved_count} 筆，Excel 輸出至 {excel_path}")
    return {**state, "saved_count": saved_count, "excel_path": excel_path}
