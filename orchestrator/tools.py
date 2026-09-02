"""
orchestrator/tools.py
Orchestrator agent 用的所有 @tool 函式。晨報操作三個工具包住
pipelines/market_report/runner.py 跟 infra/status_store.py；知識庫問答
工具包住 domains/_shared/rag_store.py。

原本這四個 @tool 都寫在 langchain_agent.py 裡，這裡只是搬過來、把
`import main as pipeline` 改成 `from pipelines.market_report.runner import
run_pipeline`，工具本身的說明文字（docstring，也就是模型拿來判斷該不該
呼叫這個工具的依據）完全沒動。
"""
import threading

from langchain_core.tools import tool

import infra.status_store as status
from pipelines.market_report.runner import run_pipeline
import domains._shared.rag_store as rag_store
import domains.regulation_kb.wiki_reader as regulation_wiki
import domains.underwriting_kb.store as underwriting_store


@tool
def get_latest_report_status() -> dict:
    """查詢「晨報」最近一次產製的狀態：是否成功、開始/結束時間、輸出路徑、
    錯誤訊息等。只用於晨報流程，跟知識庫問答無關。"""
    result = status.latest_status()
    return result or {"message": "尚無任何執行紀錄。"}


@tool
def get_report_history(limit: int = 5) -> list:
    """查詢「晨報」最近 N 次產製的歷史紀錄，預設 5 筆。只用於晨報流程。"""
    return status.history(limit=limit)


@tool
def trigger_daily_report() -> str:
    """手動觸發今日「晨報」的產製流程（抓信→摘要→產 PDF）。會在背景
    執行，不會卡住對話；如果已有流程正在執行中，不會重複啟動。"""
    if status.is_run_in_progress():
        return "已有一個報告產製流程正在執行中，請稍後再查詢狀態，這次不會重複啟動。"

    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()
    return "已在背景啟動報告產製流程，可以稍後說『查一下報告狀態』來確認進度。"


@tool
def search_knowledge_base(query: str) -> str:
    """在「個人知識庫」中做語意檢索，回傳最相關的幾段內容與其來源。
    用於一般性的知識問答問題（例如查詢筆記裡的內容），不是查詢晨報狀態
    或觸發晨報——這是另一組獨立的資料庫，跟晨報無關。"""
    results = rag_store.search(query, k=5)
    if not results:
        return "知識庫目前是空的，還沒有任何文件被索引進去。"
    formatted = []
    for r in results:
        source = r["metadata"].get("source", "未知來源")
        formatted.append(f"【來源：{source}】\n{r['content']}")
    return "\n\n---\n\n".join(formatted)


@tool
def list_regulation_pages() -> list:
    """列出「法規知識庫」Wiki 目前有哪些頁面，每筆包含 filename、標題、
    一句話說明、標籤。這是查法規問題的第一步——用來判斷使用者的問題可能
    對應到哪一頁或哪幾頁，通常要接著呼叫 read_regulation_page 讀完整內
    容才能實際回答。跟 search_knowledge_base 不一樣：這裡是逐頁瀏覽，
    不是語意向量檢索。"""
    pages = regulation_wiki.list_pages()
    if not pages:
        return [{"message": "法規知識庫目前是空的，還沒有任何頁面。"}]
    return pages


@tool
def read_regulation_page(filename: str) -> str:
    """讀取「法規知識庫」Wiki 裡指定頁面的完整內容（含 frontmatter 與正
    文）。filename 用 list_regulation_pages() 回傳結果裡的 filename 欄
    位，不用加 .md。這是精簡過的摘要，不是條文全文。"""
    content = regulation_wiki.read_page(filename)
    return content or f"找不到頁面：{filename}"


@tool
def read_regulation_source(source_filename: str) -> str:
    """讀取法規的原始來源檔案全文（未經摘要），用 read_regulation_page
    回傳內容裡 frontmatter 的 source_file 欄位當作 source_filename。只
    有在 wiki 頁面的摘要不足以精確回答問題時才用這個——例如需要引用確切
    條文文字、數字門檻，或摘要沒有涵蓋到的細節，不要每次查詢都先讀這
    個。"""
    content = regulation_wiki.read_source(source_filename)
    return content or f"找不到來源檔案：{source_filename}"


@tool
def list_underwriters_market_share(year: str = None) -> list:
    """列出承銷商在指定年度的承銷案件數、台幣計價金額總計、市占率。year
    用民國年字串（例如 "115"），不填則統計資料庫裡的全部年度。市占率只
    計算幣別為 TWD 的案件，非台幣計價的案件不納入分母（沒有匯率換算資
    料，直接加總會失真），用 excluded_non_twd_count 標示這家承銷商有幾
    筆案件被排除在市占率計算外，回答時如果有排除筆數應該提醒使用者。"""
    return underwriting_store.list_underwriters(year=year)


@tool
def search_underwriting_bonds(keyword: str) -> list:
    """依債券名稱或發行人關鍵字搜尋承銷公告資料庫，回傳符合的案件清單
    （公告序號、申報日期、案件名稱、承銷商、金額、幣別）。"""
    return underwriting_store.search_bonds(keyword)


@tool
def get_underwriting_announcement(announcement_no: str) -> dict:
    """讀取指定序號的承銷公告完整細節（公告資訊、債券資訊、承銷金額
    等）。序號從 search_underwriting_bonds 的結果取得。"""
    result = underwriting_store.get_announcement(announcement_no)
    return result or {"message": f"找不到序號 {announcement_no} 的公告"}


TOOLS = [
    get_latest_report_status,
    get_report_history,
    trigger_daily_report,
    search_knowledge_base,
    list_regulation_pages,
    read_regulation_page,
    read_regulation_source,
    list_underwriters_market_share,
    search_underwriting_bonds,
    get_underwriting_announcement,
]
