"""
pipelines/underwrite_info/nodes/load_sources.py
掃描 domains/underwriting_kb/sources/ 底下的承銷公告 PDF 檔案。跟
regulation_wiki 的 load_sources.py 是同一個模式：資料是本機檔案、不是
爬蟲抓的，每次執行都重新掃描整個資料夾，沒有做「有沒有變更」的判斷——
資料量大起來、或需要頻繁重跑時，再比照 infra/status_store.py 的模式加
時間戳記錄只處理新檔案。
"""
import os

from langchain_core.runnables import chain

from infra.paths import PROJECT_ROOT

SOURCES_DIR = os.path.join(PROJECT_ROOT, "domains", "underwriting_kb", "sources")


@chain
def load_sources(state: dict) -> dict:
    if not os.path.isdir(SOURCES_DIR):
        return {**state, "source_paths": [], "skipped": True}

    paths = [
        os.path.join(SOURCES_DIR, name)
        for name in sorted(os.listdir(SOURCES_DIR))
        if name.lower().endswith(".pdf")
    ]
    return {**state, "source_paths": paths, "skipped": not paths}
