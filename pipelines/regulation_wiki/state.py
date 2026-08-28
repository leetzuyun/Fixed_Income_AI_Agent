"""
pipelines/regulation_wiki/state.py
LangGraph 的共享狀態定義，結構比 market_report 簡單很多——這個流程沒有
平行分支，三個 node 循序執行就好。
"""
from typing import TypedDict


class RegulationWikiState(TypedDict, total=False):
    source_paths: list    # 這次要處理的來源檔案路徑
    pages_written: list   # 這次寫入/更新的頁面路徑
    skipped: bool
