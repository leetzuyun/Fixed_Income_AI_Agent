"""
pipelines/regulation_wiki/runner.py
手動觸發 LLM Wiki 匯入流程的入口。跟晨報不一樣，這個不進
infra/status_store.py 記錄——資料量小、是手動觸發、不需要排程監控，先
簡單一個函式就好，之後真的需要追蹤執行紀錄再比照晨報的做法加上去。

用法（從專案根目錄）：
    python -m pipelines.regulation_wiki.runner
"""
from pipelines.regulation_wiki.graph import regulation_wiki_graph


def run_pipeline() -> list:
    result = regulation_wiki_graph.invoke({})
    if result.get("skipped"):
        print("domains/regulation_kb/sources/ 底下沒有找到任何來源檔案。")
        return []
    pages = result.get("pages_written", [])
    print(f"\n完成，共寫入/更新 {len(pages)} 個頁面。")
    return pages


if __name__ == "__main__":
    run_pipeline()
