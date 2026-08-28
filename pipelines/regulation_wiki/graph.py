"""
pipelines/regulation_wiki/graph.py
LLM Wiki 的匯入流程：讀來源 -> 寫/更新頁面 -> 重新產生 index。跟
pipelines/market_report/graph.py 是同一套模式（每個 node 都是
langchain_core 的 Runnable），只是這裡沒有平行分支，單純三步驟循序執
行，資料量小、也沒有像 Outlook COM 那種需要考慮並行風險的操作。
"""
from langgraph.graph import StateGraph, START, END

from pipelines.regulation_wiki.state import RegulationWikiState
from pipelines.regulation_wiki.nodes.load_sources import load_sources
from pipelines.regulation_wiki.nodes.write_wiki_pages import write_wiki_pages
from pipelines.regulation_wiki.nodes.update_index import update_index

_graph = StateGraph(RegulationWikiState)
_graph.add_node("load_sources", load_sources)
_graph.add_node("write_wiki_pages", write_wiki_pages)
_graph.add_node("update_index", update_index)

_graph.add_edge(START, "load_sources")
_graph.add_edge("load_sources", "write_wiki_pages")
_graph.add_edge("write_wiki_pages", "update_index")
_graph.add_edge("update_index", END)

regulation_wiki_graph = _graph.compile()
