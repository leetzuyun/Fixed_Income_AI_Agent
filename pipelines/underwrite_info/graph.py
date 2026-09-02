"""
pipelines/underwrite_info/graph.py
本機 PDF 解析流程：掃描 sources/ -> LLM 擷取欄位 -> 寫入 SQLite +
Excel。不再包含爬蟲/下載步驟——scraper.py 還留著沒有刪，如果之後想切回
自動抓取最新公告，把 fetch_listing / download_pdfs 兩個 node 重新接回
來即可（邏輯都在 scraper.py 裡），這裡先移除，換成直接讀本機 PDF。
"""
from langgraph.graph import StateGraph, START, END

from pipelines.underwrite_info.state import UnderwriteInfoState
from pipelines.underwrite_info.nodes.load_sources import load_sources
from pipelines.underwrite_info.nodes.extract_fields import extract_fields
from pipelines.underwrite_info.nodes.persist import persist

_graph = StateGraph(UnderwriteInfoState)
_graph.add_node("load_sources", load_sources)
_graph.add_node("extract_fields", extract_fields)
_graph.add_node("persist", persist)

_graph.add_edge(START, "load_sources")
_graph.add_edge("load_sources", "extract_fields")
_graph.add_edge("extract_fields", "persist")
_graph.add_edge("persist", END)

underwrite_info_graph = _graph.compile()
