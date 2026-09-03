"""
chainlit_app.py

刻意不用 LangGraph 的即時串流（.stream() / astream_events()）：這類即
時串流在 Chainlit 裡目前還有已知的效能與相容性問題（社群回報某些串流
實作方式會讓回應明顯變慢，尤其是 LangGraph 這種多節點的圖）。改成等
agent.invoke() 完整跑完後，再把回傳的 messages 列表裡「這一輪新增的」
部分攤開顯示成 Step，一樣能看到完整的工具呼叫過程，只是不是「一邊跑一
邊即時顯示」，換取穩定性。之後如果真的需要逐字即時輸出，再回頭處理這
個已知的摩擦點。

執行方式（從專案根目錄）：
    pip install chainlit
    chainlit run chainlit_app.py

預設只能在這台電腦上用瀏覽器開 http://localhost:8000。
如果想讓同一區網內的同事也能連，加 --host 128.110.135.25：
    chainlit run chainlit_app.py --host 128.110.135.25 --port 8000
然後同事瀏覽器輸入「這台電腦的區網 IP:8000」（IP 可用 ipconfig 查）。
Windows 防火牆可能會跳出詢問是否允許，記得允許。

如果想加密碼保護（同事以外的人在同網段也連得到，不想讓所有人都能
用），Chainlit 支援內建的密碼／OAuth 驗證，需要另外設定
CHAINLIT_AUTH_SECRET 環境變數跟一個 @cl.password_auth_callback，這支
檔案先不加，之後真的需要再處理，不影響現在的邏輯。
"""
import chainlit as cl
from orchestrator.langchain_agent import build_agent
from orchestrator.message_utils import extract_answer_text

TOOL_NAME_LABELS = {
    "get_latest_report_status": "查詢晨報狀態",
    "get_report_history": "查詢晨報歷史紀錄",
    "trigger_daily_report": "觸發晨報產製",
    "search_knowledge_base": "檢索個人知識庫",
    "list_regulation_pages": "列出法規頁面",
    "read_regulation_page": "讀取法規頁面摘要",
    "read_regulation_source": "讀取法規原始全文",
    "list_underwriters_market_share": "查詢承銷商市占率",
    "search_underwriting_bonds": "搜尋承銷公告",
    "get_underwriting_announcement": "讀取承銷公告細節",
}


@cl.on_chat_start
async def on_chat_start():
    agent = build_agent()
    cl.user_session.set("agent", agent)
    cl.user_session.set("history", [])
    await cl.Message(
        content=(
            "🤖 金交處助理已啟動。可以問晨報狀態、觸發今天的報告，"
            "問法規／知識庫裡的內容，或問搜尋網路資訊。"
        )
    ).send()


async def _show_tool_steps(result_messages: list, already_shown: int):
    """把 agent.invoke() 回傳的完整 messages 裡，這一輪新增的部分挑出
    工具呼叫，用可展開的 Step 顯示呼叫參數跟結果。already_shown 是這一
    輪呼叫前 history 的長度，用來只挑出這一輪新增的訊息，不重複顯示之
    前輪次的工具呼叫。

    兩種工具呼叫要分開處理：
      1. 我們自己寫的 @tool 函式（orchestrator/tools.py 那 10 個）：
         LangChain 會產生獨立的 ToolMessage，直接挑出來顯示。
      2. openai 的 web_search：這是 OpenAI 伺服器端執行的內建工具，不
         會產生 ToolMessage，而是嵌在 AIMessage.content 的內容區塊列
         表裡（見 message_utils.py 的說明），要另外從那裡挑出
         "web_search_call" 類型的區塊顯示。
    """
    new_messages = result_messages[already_shown:]

    # 先建立 tool_call_id -> 呼叫參數 的對照，等一下要跟結果配對
    pending_calls = {}
    for msg in new_messages:
        for call in getattr(msg, "tool_calls", None) or []:
            pending_calls[call["id"]] = call

    for msg in new_messages:
        if getattr(msg, "type", None) == "tool":
            call = pending_calls.get(getattr(msg, "tool_call_id", None), {})
            tool_name = call.get("name") or getattr(msg, "name", "unknown_tool")
            label = TOOL_NAME_LABELS.get(tool_name, tool_name)
            async with cl.Step(name=label, type="tool") as step:
                step.input = call.get("args", {})
                step.output = str(msg.content)
            continue

        content = getattr(msg, "content", None)
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "web_search_call":
                continue
            action = block.get("action") or {}
            queries = action.get("queries") or [action.get("query", "")]
            async with cl.Step(name="網路搜尋", type="tool") as step:
                step.output = "、".join(q for q in queries if q) or "（無查詢字串）"


@cl.on_message
async def on_message(message: cl.Message):
    agent = cl.user_session.get("agent")
    history = cl.user_session.get("history")

    history.append({"role": "user", "content": message.content})
    messages_before = len(history)

    result = await cl.make_async(agent.invoke)({"messages": history})
    result_messages = result["messages"]

    await _show_tool_steps(result_messages, already_shown=messages_before)

    answer = extract_answer_text(result_messages[-1])
    history.append({"role": "assistant", "content": answer})
    cl.user_session.set("history", history)

    await cl.Message(content=answer).send()
