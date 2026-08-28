"""
pipelines/market_report/state.py
LangGraph 的共享狀態定義。每個 node（都是 langchain_core 的 Runnable）
收到完整的 state、回傳更新過的完整 state，LangGraph 會自動合併不同 key
的寫入——fetch_bbg_news 只寫 bbg_news、fetch_sinopac_views 只寫
sinopac_views，兩個 key 不會互相覆蓋，所以之後不管兩個 fetch node 是循序
還是平行執行，state 的合併邏輯都不用改。
"""
from typing import TypedDict, Optional
import datetime


class MarketReportState(TypedDict, total=False):
    run_id: Optional[int]
    today_date: datetime.date
    skipped: bool  # 由 summarize 節點判斷：兩區資料都是空的就設 True，
                   # 後面的 make_chart / assemble_report 看到就直接跳過

    bbg_news: list
    sinopac_views: list

    other_summaries: dict
    sinopac_summaries: dict
    section1_body: str
    section2_body: str

    chart_paths: list
    output_path: Optional[str]
