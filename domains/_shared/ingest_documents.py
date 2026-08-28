"""
domains/_shared/ingest_documents.py
把一個資料夾底下的文件讀進來，切塊後加進 rag_store.py 管理的知識庫。
跟晨報的 Outlook 抓信流程完全無關，是獨立的另一條路。

搬家後唯一改動：`import rag_store` -> `import domains._shared.rag_store as rag_store`。

用法（從專案根目錄執行）：
    python -m domains._shared.ingest_documents --path "C:\\path\\to\\your\\folder"

之後你把 Obsidian vault（或任何資料夾）路徑準備好，指向它跑一次就能
全部索引進去；之後有新文件，同一個指令重跑一次即可。

目前只支援 .md / .txt。如果你要連 PDF 也一起索引，說一聲，我們可以
接你專案裡已經有的 pdfplumber 邏輯（get_outlook_email.py 的
extract_pdf_content）進來，不用重寫。

目前沒有去重機制——同一份文件重複執行會被當成新的一份再加一次。如果
之後會常態性重跑同一批文件，之後再補上依檔案路徑/修改時間判斷是否
需要重新索引的邏輯。
"""
import argparse
import os

import domains._shared.rag_store as rag_store

SUPPORTED_EXTENSIONS = (".md", ".txt")


def find_files(root: str) -> list:
    matches = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(SUPPORTED_EXTENSIONS):
                matches.append(os.path.join(dirpath, name))
    return matches


def main():
    parser = argparse.ArgumentParser(description="把資料夾裡的文件索引進 RAG 知識庫")
    parser.add_argument("--path", required=True, help="要索引的資料夾路徑")
    args = parser.parse_args()

    files = find_files(args.path)
    if not files:
        print(f"在 {args.path} 底下找不到任何 .md / .txt 檔案。")
        return

    print(f"找到 {len(files)} 份文件，開始索引...")
    total_chunks = 0
    for path in files:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        if not text.strip():
            continue
        relative = os.path.relpath(path, args.path)
        chunk_count = rag_store.add_document(
            text, metadata={"source": relative, "filename": os.path.basename(path)}
        )
        total_chunks += chunk_count
        print(f"  -> {relative}（{chunk_count} 個片段）")

    print(f"\n完成，總共索引了 {total_chunks} 個片段。")
    print(f"目前知識庫累計片段數：{rag_store.count_documents()}")


if __name__ == "__main__":
    main()
