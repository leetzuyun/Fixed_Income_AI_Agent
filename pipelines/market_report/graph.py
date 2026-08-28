"""
pipelines/market_report/graph.py
把 main.py 原本的線性流程改寫成 LangGraph 的 StateGraph，每個 node 都是
langchain_core 的 Runnable（見 nodes/ 底下各檔案的 @chain 裝飾器），
LangGraph 的 add_node() 原生就接受 Runnable，不用額外轉換。

--- 為什麼兩個 fetch node 預設是「循序」而不是「平行」---
fetch_bbg_news 和 fetch_sinopac_views 彼此沒有資料依賴，理論上可以平行
跑，LangGraph 也原生支援 fan-out/fan-in（見下方註解）。但這兩個函式各自
呼叫 pythoncom.CoInitialize() 去開一個新的 Outlook MAPI 連線——分別在
不同 thread 裡同時對同一個 Outlook 行程做 COM 呼叫，雖然理論上因為各自
是獨立的 apartment 應該可行，但 Outlook COM 對多執行緒同時存取本來就容
易有間歇性的不穩定（尤其是公司電腦有防毒/DLP 軟體攔截 MAPI 呼叫的環
境）。抓信這幾秒鐘的時間差影響不大，先求穩定，預設循序執行。

如果之後想試平行版本，把下面這兩行：
    _graph.add_edge("fetch_bbg_news", "fetch_sinopac_views")
    _graph.add_edge("fetch_sinopac_views", "summarize")
換成：
    _graph.add_edge(START, "fetch_sinopac_views")
    _graph.add_edge("fetch_bbg_news", "summarize")
    _graph.add_edge("fetch_sinopac_views", "summarize")
（保留原本 `_graph.add_edge(START, "fetch_bbg_news")` 那一行）
LangGraph 看到 summarize 有兩條進來的邊，會自動等兩個 fetch node 都跑完
才執行 summarize（fan-out / fan-in），state 合併不會衝突，因為兩個 fetch
node 各自只寫自己的 key（bbg_news / sinopac_views）。
"""
from langgraph.graph import StateGraph, START, END

from pipelines.market_report.state import MarketReportState
from pipelines.market_report.nodes.fetch_bbg_news import fetch_bbg_news
from pipelines.market_report.nodes.fetch_sinopac_views import fetch_sinopac_views
from pipelines.market_report.nodes.summarize import summarize
from pipelines.market_report.nodes.make_chart import make_chart
from pipelines.market_report.nodes.assemble_report import assemble_report

_graph = StateGraph(MarketReportState)
_graph.add_node("fetch_bbg_news", fetch_bbg_news)
_graph.add_node("fetch_sinopac_views", fetch_sinopac_views)
_graph.add_node("summarize", summarize)
_graph.add_node("make_chart", make_chart)
_graph.add_node("assemble_report", assemble_report)

_graph.add_edge(START, "fetch_bbg_news")
_graph.add_edge("fetch_bbg_news", "fetch_sinopac_views")
_graph.add_edge("fetch_sinopac_views", "summarize")
_graph.add_edge("summarize", "make_chart")
_graph.add_edge("make_chart", "assemble_report")
_graph.add_edge("assemble_report", END)

market_report_graph = _graph.compile()
