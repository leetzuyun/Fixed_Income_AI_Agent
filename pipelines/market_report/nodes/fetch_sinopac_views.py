"""
pipelines/market_report/nodes/fetch_sinopac_views.py
Graph node（LangChain Runnable）：讀取「永豐投顧」資料夾底下的 PDF 附件
（財富管理日報、台灣指標評析、國際經濟評論、永豐總經與產業週報）。跟
fetch_bbg_news.py 是同一種包法，只是叫用 get_outlook_email.py 裡不同的
函式、寫進 state 的 key 不同（sinopac_views 而不是 bbg_news）。

單獨測試：
    from pipelines.market_report.nodes.fetch_sinopac_views import fetch_sinopac_views
    result = fetch_sinopac_views.invoke({"today_date": date.today()})
    print(len(result["sinopac_views"]))
"""
from langchain_core.runnables import chain

from pipelines.market_report import get_outlook_email as ingest


@chain
def fetch_sinopac_views(state: dict) -> dict:
    sinopac_views = ingest.load_sinopac_views_from_outlook(target_date=state["today_date"])
    return {**state, "sinopac_views": sinopac_views}
