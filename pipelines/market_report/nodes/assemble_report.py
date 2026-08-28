"""
pipelines/market_report/nodes/assemble_report.py
Graph node（LangChain Runnable）：組裝最終 PDF。包住
pipelines/market_report/report1.py 的 build_pdf()，邏輯不變。
"""
import os

from langchain_core.runnables import chain

import infra.config as config
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

    return {**state, "output_path": output_path}
