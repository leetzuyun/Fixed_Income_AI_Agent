"""
pipelines/regulation_wiki/nodes/load_sources.py
掃描 domains/regulation_kb/sources/ 底下的法規來源檔案（支援
.pdf / .txt / .md）。

第一版沒有做「有沒有變更」的判斷，每次執行都會把 sources/ 底下全部檔案
重新處理一次——資料量小、又是手動觸發，先求簡單。之後如果來源檔案變
多、重新處理全部檔案的 LLM 成本變得有感，再比照
infra/status_store.py 的模式加一個時間戳記錄，只處理有變動的檔案。
"""
import os

from langchain_core.runnables import chain

from infra.paths import PROJECT_ROOT

SOURCES_DIR = os.path.join(PROJECT_ROOT, "domains", "regulation_kb", "sources")
SUPPORTED_EXTENSIONS = (".pdf", ".txt", ".md")


@chain
def load_sources(state: dict) -> dict:
    if not os.path.isdir(SOURCES_DIR):
        return {**state, "source_paths": [], "skipped": True}

    paths = [
        os.path.join(SOURCES_DIR, name)
        for name in sorted(os.listdir(SOURCES_DIR))
        if name.lower().endswith(SUPPORTED_EXTENSIONS)
    ]
    return {**state, "source_paths": paths, "skipped": not paths}
