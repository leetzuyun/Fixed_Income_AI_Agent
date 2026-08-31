"""
pipelines/market_report/nodes/assemble_report.py
Graph node（LangChain Runnable）：組裝最終 PDF。包住
pipelines/market_report/report1.py 的 build_pdf()，邏輯不變，多加一
步：PDF 產出後額外複製一份到「執行這支程式的使用者」的下載資料夾。

之所以是「複製一份」而不是「改成只存下載資料夾」：config.OUTPUT_DIR
（專案裡的 output/）是 pipeline 自己讀寫歷史報告用的固定路徑，
status_store.py、之後如果要做「查看歷史報告」這類功能都會依賴這個路徑
穩定；下載資料夾則是給執行者自己方便的副本，路徑會隨著誰在哪台機器上
執行而不同，兩者用途不一樣，都留著。

複製到下載資料夾失敗（例如找不到資料夾、權限問題）不會讓整個晨報流程
失敗——這時 config.OUTPUT_DIR 那份已經產出成功，下載資料夾這份只是加
分項，用 try/except 包起來，失敗只印警告訊息。
"""
import os
import shutil

from langchain_core.runnables import chain

import infra.config as config
from infra.downloads import get_downloads_folder
from pipelines.market_report import report1


@chain
def assemble_report(state: dict) -> dict:
    if state.get("skipped"):
        return state

    date_str = state["today_date"].isoformat()
    sections = [
        {
            "title": "重點債市新聞與數據評析",
            "body": state["section1_body"],
            "sources": list(state["other_summaries"].keys()),
        },
        {
            "title": "永豐觀點",
            "body": state["section2_body"],
            "sources": list(state["sinopac_summaries"].keys()),
        },
    ]

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(config.OUTPUT_DIR, f"daily_report_{date_str}.pdf")
    report1.build_pdf(date_str, sections, output_path, chart_paths=state.get("chart_paths") or None)

    downloads_path = None
    try:
        downloads_dir = get_downloads_folder()
        os.makedirs(downloads_dir, exist_ok=True)
        downloads_path = os.path.join(downloads_dir, os.path.basename(output_path))
        shutil.copy2(output_path, downloads_path)
    except OSError as e:
        print(f"      [warn] 複製報告到下載資料夾失敗：{e}")
        downloads_path = None

    return {**state, "output_path": output_path, "downloads_path": downloads_path}

