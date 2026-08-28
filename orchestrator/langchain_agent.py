"""
orchestrator/langchain_agent.py
建立 orchestrator agent 本身：選模型、掛 system prompt、掛
orchestrator/tools.py 裡的工具清單。實際工具邏輯都不在這支檔案裡，這是
跟原本版本相比唯一的結構性改動——內容（_build_llm、SYSTEM_PROMPT、CLI
迴圈）完全不變，只把四個 @tool 抽到 tools.py 去。

執行方式（從專案根目錄）：
    python -m orchestrator.langchain_agent

注意：因為現在是套件內的模組（orchestrator.langchain_agent），不能直接
`python orchestrator/langchain_agent.py` 執行——那樣跑的話 Python 會把
orchestrator/ 當成 sys.path[0]，找不到 infra.config、
pipelines.market_report 這些其他套件，會噴 ModuleNotFoundError。一定要
用 `python -m` 從專案根目錄啟動，或透過 streamlit_app.py 間接載入。
"""
import infra.config as config
from langchain.agents import create_agent
from orchestrator.tools import TOOLS


def _build_llm():
    """
    沿用你原本 llm.py 已經設定好的 provider。要注意：create_agent 需要
    模型真的支援 function calling —— OpenAI / Gemini 的對話模型大多沒
    問題；本機 Ollama 的話，請挑支援 tool calling 的模型（例如
    qwen2.5、llama3.1 這類），太舊或太小的模型常常選不準工具。
    """
    if config.LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=config.OPENAI_MODEL,
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
        )
    if config.LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=config.GEMINI_MODEL,
            google_api_key=config.GEMINI_API_KEY,
        )
    from langchain_ollama import ChatOllama
    return ChatOllama(model=config.OLLAMA_MODEL, base_url=config.OLLAMA_HOST)


SYSTEM_PROMPT = (
    "你是一個具備三種能力的助理：\n"
    "1. 晨報操作——查詢晨報執行狀態、查看歷史紀錄、手動觸發今日晨報產製。\n"
    "2. 法規知識庫問答——用 list_regulation_pages 先看有哪些頁面，判斷"
    "跟問題相關的頁面後，用 read_regulation_page 讀該頁摘要。這個摘要是"
    "精簡過的，不是條文全文——如果問題需要引用確切條文文字、確切數字門"
    "檻，或摘要明顯沒有涵蓋到問題需要的細節，改用該頁 frontmatter 裡的"
    "source_file 欄位呼叫 read_regulation_source 讀原始全文再回答，不要"
    "在摘要不足時直接用猜的或用摘要內容硬答。\n"
    "3. 一般知識庫問答——在另一組獨立的個人知識庫中做語意檢索並回答問"
    "題，這組資料跟晨報、法規都無關，只在使用者的問題明顯不是法規、也不"
    "是晨報時才用。\n"
    "請根據使用者問題的性質，判斷該呼叫哪一種工具。"
    "回答時使用繁體中文，簡潔明確，不要多餘的客套話。"
    "如果是引用知識庫或法規頁面的內容，請註明來源（頁面標題或知識庫來源"
    "欄位）。"
)


def build_agent():
    """
    回傳一個 LangGraph 編譯出來的 agent。呼叫方式：
        result = agent.invoke({"messages": [{"role": "user", "content": "..."}]})
        answer = result["messages"][-1].content
    """
    llm = _build_llm()
    return create_agent(model=llm, tools=TOOLS, system_prompt=SYSTEM_PROMPT)


if __name__ == "__main__":
    agent = build_agent()
    print("助理已啟動（輸入 exit 離開）\n")
    history = []
    while True:
        query = input("你: ").strip()
        if query.lower() in ("exit", "quit"):
            break
        history.append({"role": "user", "content": query})
        result = agent.invoke({"messages": history})
        answer = result["messages"][-1].content
        history.append({"role": "assistant", "content": answer})
        print(f"助理: {answer}\n")
