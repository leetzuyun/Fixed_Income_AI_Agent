"""
pipelines/regulation_wiki/nodes/update_index.py
掃描 wiki/regulations/ 底下所有頁面的 frontmatter，重新產生
regulations/index.md 的清單，對應 INSTRUCTIONS.md 裡的「index.md 維護
規則」：每次新增或更新頁面後，這份清單都要保持同步。

frontmatter 解析邏輯共用 domains/regulation_kb/wiki_reader.py 那一份，
不在這裡重寫一次。
"""
import os

from langchain_core.runnables import chain

from domains.regulation_kb.wiki_reader import list_pages, REGULATIONS_DIR

REGULATIONS_INDEX_PATH = os.path.join(REGULATIONS_DIR, "index.md")


@chain
def update_index(state: dict) -> dict:
    if not os.path.isdir(REGULATIONS_DIR):
        return state

    pages = list_pages()

    lines = ["---", "type: Index", "title: 法規列表", "---", "", "# 法規列表", ""]
    if not pages:
        lines.append("（尚未匯入任何法規）")
    for page in pages:
        entry = f"- [[{page['filename']}|{page['title']}]]"
        if page["description"]:
            entry += f" — {page['description']}"
        lines.append(entry)

    with open(REGULATIONS_INDEX_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return state
