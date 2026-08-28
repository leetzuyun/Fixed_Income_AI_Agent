"""
pipelines/regulation_wiki/nodes/write_wiki_pages.py
LLM Wiki 的核心步驟：把每份法規來源讀進來，請 LLM 依照
domains/regulation_kb/wiki/INSTRUCTIONS.md 訂的規則，寫成（或更新）一頁
Markdown wiki 頁面。

這是跟傳統 RAG 最大的不同：這個成本只在「匯入資料的當下」付一次，不是
每次使用者提問都重新組裝一次答案。之後查詢時，orchestrator/tools.py 的
read_regulation_page 直接讀這頁 Markdown 就好，不用再叫一次 LLM 去組
答案。

檔名規則：直接用來源檔名（去掉副檔名）當作頁面檔名，例如
`銀行法.pdf` -> `regulations/銀行法.md`。如果同名頁面已存在，就把舊內容
一起放進 prompt，讓 LLM 用「更新」的方式重寫，不是每次從零生成。
"""
import os

from langchain_core.runnables import chain

from infra.llm import chat
from infra.pdf_text import extract_text
from domains.regulation_kb.wiki_reader import WIKI_DIR, REGULATIONS_DIR

INSTRUCTIONS_PATH = os.path.join(WIKI_DIR, "INSTRUCTIONS.md")


def _read_source_text(path: str) -> str:
    if path.lower().endswith(".pdf"):
        return extract_text(path)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _page_path_for_source(source_path: str) -> str:
    base = os.path.splitext(os.path.basename(source_path))[0]
    return os.path.join(REGULATIONS_DIR, f"{base}.md")


def _build_prompt(instructions: str, source_filename: str, source_text: str,
                   existing_page: str = None) -> str:
    existing_block = (
        f"\n\n這是目前已經存在的舊版頁面內容，請在保留正確資訊的前提下，"
        f"依照新的來源內容更新它（不要無中生有地刪掉舊頁面裡跟新來源無"
        f"關、但仍然正確的內容）：\n---現有頁面---\n{existing_page}\n"
        if existing_page else ""
    )
    return (
        f"你是負責維護一份法規知識庫 Wiki 的助理。請依照以下規則撰寫一頁"
        f"完整的 Markdown 頁面（包含 YAML frontmatter），只回傳這份"
        f"Markdown 內容本身，不要有任何其他說明文字。\n\n"
        f"---撰寫規則---\n{instructions}\n"
        f"{existing_block}\n"
        f"---來源檔名---\n{source_filename}\n\n"
        f"---來源內容---\n{source_text[:15000]}"
    )


@chain
def write_wiki_pages(state: dict) -> dict:
    if state.get("skipped"):
        return state

    with open(INSTRUCTIONS_PATH, "r", encoding="utf-8") as f:
        instructions = f.read()

    os.makedirs(REGULATIONS_DIR, exist_ok=True)
    pages_written = []

    for source_path in state.get("source_paths", []):
        source_text = _read_source_text(source_path)
        if not source_text.strip():
            print(f"  [warn] {os.path.basename(source_path)} 讀不到任何文字內容，跳過。")
            continue

        page_path = _page_path_for_source(source_path)
        existing_page = None
        if os.path.exists(page_path):
            with open(page_path, "r", encoding="utf-8") as f:
                existing_page = f.read()

        prompt = _build_prompt(
            instructions, os.path.basename(source_path), source_text, existing_page,
        )
        page_content = chat(prompt)

        with open(page_path, "w", encoding="utf-8") as f:
            f.write(page_content.strip() + "\n")
        pages_written.append(page_path)
        action = "更新" if existing_page else "新增"
        print(f"  -> {action} {os.path.relpath(page_path, WIKI_DIR)}")

    return {**state, "pages_written": pages_written}
