"""
pipelines/market_report/nodes/summarize.py
Graph node（LangChain Runnable）：把 fetch_bbg_news / fetch_sinopac_views
兩個 node 抓回來的信件分別丟給 LLM 摘要，再各自整合成一段/一份條列。

這是兩條 fetch 分支的匯合點，所以「今天完全沒抓到任何資料」的判斷放在
這裡做一次就好（state["skipped"]），後面的 make_chart / assemble_report
看到 skipped=True 就直接原樣通過，不用每個 node 各自重新判斷一次「有
沒有資料」。

safe_summarize 是原本 main.py 裡帶重試機制的包裝，邏輯完全不變，只是
run_id 改成從 state 讀，重試次數一樣寫回 infra/status_store.py。
"""
import time

from langchain_core.runnables import chain

import infra.status_store as status
from infra.llm import summarize_file, summarize_section

SECTION_1_TITLE = "重點債市新聞與數據評析"
SECTION_1_FOCUS = "這些是市場上其他來源（非永豐投顧）的債市新聞與數據分析。"
SECTION_1_FORMAT = "從所有來源中擷取最重要的資訊，整合成「一段」精簡的文字（不要條列、不要分點）"
SECTION_2_TITLE = "永豐觀點"
SECTION_2_FOCUS = "這些全部來自永豐投顧，呈現我們自己的觀點與分析。"
SECTION_2_FORMAT = "將重點內容以「列點（Bullet points）」方式整理，條理分明，不要包含任何多餘的對話或問答文字。"


def _safe_summarize(label: str, text: str, run_id=None) -> str:
    max_retries = 5
    for attempt in range(max_retries):
        try:
            result = summarize_file(label, text)
            time.sleep(4)  # 成功後固定休息 4 秒，保護後續請求
            return result
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                wait_time = 35
                print(f"      [warn] 觸發 API 限制！自動掛機 {wait_time} 秒後重試... ({attempt+1}/{max_retries})")
                if run_id is not None:
                    status.bump_retry(run_id)
                time.sleep(wait_time)
            else:
                raise e
    raise RuntimeError(f"已達最大重試次數，無法完成摘要：{label}")


@chain
def summarize(state: dict) -> dict:
    bbg_news = state.get("bbg_news", [])
    sinopac_views = state.get("sinopac_views", [])

    if not bbg_news and not sinopac_views:
        return {**state, "skipped": True}

    run_id = state.get("run_id")
    date_str = state["today_date"].isoformat()

    other_summaries = {}
    for item in bbg_news:
        label = item.get("subject", "Unknown News")
        other_summaries[label] = _safe_summarize(label, item.get("text", ""), run_id=run_id)

    sinopac_summaries = {}
    for item in sinopac_views:
        label = item.get("pdf_name") or item.get("subject", "Unknown Sinopac Report")
        sinopac_summaries[label] = _safe_summarize(label, item.get("text", ""), run_id=run_id)

    section1_body = summarize_section(
        date_str, SECTION_1_TITLE, SECTION_1_FOCUS, other_summaries,
        format_instruction=SECTION_1_FORMAT,
    ) if other_summaries else "今日無重點債市新聞與數據評析更新。"

    section2_body = summarize_section(
        date_str, SECTION_2_TITLE, SECTION_2_FOCUS, sinopac_summaries,
        format_instruction=SECTION_2_FORMAT,
    ) if sinopac_summaries else "今日無永豐觀點報告更新。"

    return {
        **state,
        "skipped": False,
        "other_summaries": other_summaries,
        "sinopac_summaries": sinopac_summaries,
        "section1_body": section1_body,
        "section2_body": section2_body,
    }
