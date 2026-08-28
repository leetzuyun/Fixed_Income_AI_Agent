"""
domains/regulation_kb/wiki_reader.py
讀取 wiki/regulations/ 底下頁面、以及對應原始來源檔案的共用工具，給
orchestrator 的查詢工具（orchestrator/tools.py）跟
pipelines/regulation_wiki 的 update_index node 共用，frontmatter 解析
邏輯只寫這一份。

wiki 頁面是刻意精簡過的摘要，快速定位用；如果摘要不足以精確回答（例如
需要引用確切條文文字、數字門檻），read_source() 讓 agent 可以回頭讀
sources/ 底下對應的原始檔案全文——摘要負責快、原文負責準，兩層都留著。

這裡的 frontmatter 解析是刻意簡化過的正規表示式，只吃單行純量欄位
（type / title / description / tags / source_file / effective_date），
不是完整的 YAML parser——INSTRUCTIONS.md 裡也明確要求 LLM 只能寫純量欄
位，兩邊要對得起來。如果之後 frontmatter 需要巢狀結構（例如 tags 要是
真正的 YAML 陣列而不是逗號分隔字串），再換成 pyyaml 或
python-frontmatter 這種正式的套件解析，這支檔案只有 read_frontmatter()
這一個函式需要換掉，呼叫端不用改。
"""
import os
import re

from infra.paths import PROJECT_ROOT
from infra.pdf_text import extract_text

WIKI_DIR = os.path.join(PROJECT_ROOT, "domains", "regulation_kb", "wiki")
REGULATIONS_DIR = os.path.join(WIKI_DIR, "regulations")
SOURCES_DIR = os.path.join(PROJECT_ROOT, "domains", "regulation_kb", "sources")

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_FIELD_RE = re.compile(r'^(\w+):\s*(.+)$', re.MULTILINE)


def read_frontmatter(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}
    fields = {}
    for key, value in _FIELD_RE.findall(match.group(1)):
        fields[key] = value.strip().strip('"')
    return fields


def list_pages() -> list:
    """回傳所有法規頁面的摘要清單：
    [{"filename", "title", "description", "tags"}, ...]
    這是給 agent 判斷「使用者的問題可能對應到哪一頁」用的第一步，通常
    要接著呼叫 read_page() 讀完整內容才能實際回答問題。
    """
    if not os.path.isdir(REGULATIONS_DIR):
        return []
    pages = []
    for name in sorted(os.listdir(REGULATIONS_DIR)):
        if not name.endswith(".md") or name == "index.md":
            continue
        meta = read_frontmatter(os.path.join(REGULATIONS_DIR, name))
        pages.append({
            "filename": name[:-3],
            "title": meta.get("title", name[:-3]),
            "description": meta.get("description", ""),
            "tags": meta.get("tags", ""),
        })
    return pages


def read_page(filename: str) -> str:
    """讀一頁的完整內容（含 frontmatter）。filename 不用加 .md 副檔名，
    直接用 list_pages() 回傳的 filename 欄位。找不到回傳 None。

    回傳內容裡本來就含有 frontmatter 的 source_file 欄位，agent 讀完這
    頁如果發現摘要不夠精確，可以直接拿這個欄位的值去呼叫 read_source()
    讀原始全文，不需要另外查表。
    """
    path = os.path.join(REGULATIONS_DIR, f"{filename}.md")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_source(source_filename: str) -> str:
    """讀取 sources/ 底下指定原始來源檔案的完整未摘要內容（用 wiki 頁面
    frontmatter 裡的 source_file 欄位當 source_filename）。支援
    .pdf / .txt / .md。找不到回傳 None。

    這是摘要不夠精確時的第二層——例如需要引用確切條文文字、數字門檻，
    或摘要沒有涵蓋到的細節，不應該每次查詢都先讀這個，只有必要時才用。
    """
    path = os.path.join(SOURCES_DIR, source_filename)
    if not os.path.exists(path):
        return None
    if path.lower().endswith(".pdf"):
        return extract_text(path)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

