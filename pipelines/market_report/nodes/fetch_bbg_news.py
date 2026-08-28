"""
pipelines/market_report/nodes/fetch_bbg_news.py
Graph node（LangChain Runnable）：讀取「BBG News」+「金融市場短觀」兩個
Outlook 資料夾的信件。

實際的 Outlook MAPI / 日期比對邏輯都留在 get_outlook_email.py 裡（那支
檔案本身不 import 任何 langchain 相關套件，純粹是「讀信件」的函式庫，
可以脫離 graph 單獨測試）。這裡只是把它包成一個吃 state、回傳 state 的
Runnable，讓 graph.py 可以直接掛進去，也可以自己單獨呼叫測試：

    from pipelines.market_report.nodes.fetch_bbg_news import fetch_bbg_news
    result = fetch_bbg_news.invoke({"today_date": date.today()})
    print(len(result["bbg_news"]))

用 @chain 裝飾器把一般函式變成 langchain_core 的 Runnable，好處：
  - 跟其他 Runnable 一樣支援 .invoke() / .batch() / | 串接
  - LangSmith 有開的話，這個 node 會單獨出現在 trace 裡，方便除錯
  - 之後要幫這個 node 加重試（.with_retry()）或 fallback
    （.with_fallbacks()）可以直接在這個 Runnable 上加，不用自己再寫一層
"""
from langchain_core.runnables import chain

from pipelines.market_report import get_outlook_email as ingest


@chain
def fetch_bbg_news(state: dict) -> dict:
    bbg_news = ingest.load_bbg_news_from_outlook(today_date=state["today_date"])
    return {**state, "bbg_news": bbg_news}
