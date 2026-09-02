"""
pipelines/underwrite_info/state.py
LangGraph 的共享狀態定義。
"""
from typing import TypedDict, Optional


class UnderwriteInfoState(TypedDict, total=False):
    source_paths: list    # domains/underwriting_kb/sources/ 底下掃到的 PDF 路徑
    records: list          # 從每份 PDF 擷取出的完整紀錄
    saved_count: int
    excel_path: Optional[str]
    skipped: bool
