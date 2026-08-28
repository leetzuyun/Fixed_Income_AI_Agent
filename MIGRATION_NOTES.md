# 遷移筆記

## 這裡有什麼

照 LangChain / LangGraph 為主架構重新組織好的完整程式碼。

```
daily_report_agent/
├── main.py                          Task Scheduler 排程入口（大幅簡化）
├── orchestrator/
│   ├── langchain_agent.py            agent 組裝（模型 + system prompt + 工具清單）
│   ├── tools.py                       四個 @tool：晨報操作 x3、知識庫問答 x1
│   └── streamlit_app.py                聊天 UI
├── pipelines/market_report/
│   ├── graph.py                        LangGraph StateGraph 組裝
│   ├── runner.py                        包 status_store 的 start/finish
│   ├── state.py                          共享狀態定義
│   ├── get_outlook_email.py               函式庫：Outlook MAPI 抓信
│   ├── report1.py                          函式庫：PDF 組裝
│   ├── analyze.py                          函式庫：表格轉 tidy data（尚未接上）
│   ├── chart.py                             函式庫：畫圖表（尚未接上）
│   └── nodes/                                每個都是 @chain 包出來的 LangChain Runnable
│       ├── fetch_bbg_news.py
│       ├── fetch_sinopac_views.py
│       ├── summarize.py
│       ├── make_chart.py
│       └── assemble_report.py
├── domains/_shared/
│   ├── rag_store.py                     知識庫向量檢索（Chroma）
│   └── ingest_documents.py               把資料夾內容索引進知識庫
└── infra/
    ├── paths.py                          PROJECT_ROOT，全專案唯一的路徑基準
    ├── llm.py                             LLM provider 切換
    └── status_store.py                    run_history.db 讀寫
```

## 你還要自己做的事

1. **搬 `config.py` 進 `infra/config.py`**：我沒有這支檔案的內容，不敢
   幫你捏造。搬過去後**務必檢查裡面有沒有用
   `os.path.dirname(os.path.abspath(__file__))` 算 `OUTPUT_DIR` 之類的
   路徑**——如果有，那個邏輯原本假設 config.py 在專案根目錄，搬進
   `infra/` 後同樣算法會偏移一層，跟 `report1.py` / `status_store.py`
   之前遇到的問題一樣。改成 `from infra.paths import PROJECT_ROOT` 再
   拼路徑最保險。

2. **把 `fonts/`、`sample_data/`、`output/` 三個資料夾原封不動留在專案
   根目錄**，不用搬進 `pipelines/market_report/` 裡——`report1.py` /
   `chart.py` 都是透過 `PROJECT_ROOT` 指回根目錄找它們的。

3. **`requirements.txt` 加兩行**：
   ```
   langgraph
   langchain-core
   ```
   （`langchain`、`langchain-text-splitters`、`pymupdf`、`pdfplumber`
   你應該已經裝過了。）

4. **執行方式改變，用 `python -m`**：
   - 排程／CLI：`python main.py`（不變）
   - 對話版 CLI：`python -m orchestrator.langchain_agent`
     （不能直接 `python orchestrator/langchain_agent.py`，那樣會把
     `orchestrator/` 當成 `sys.path[0]`，找不到 `infra`、`pipelines`
     這些其他套件）
   - 聊天網頁：`streamlit run orchestrator/streamlit_app.py`，一定要
     從**專案根目錄**執行這行指令
   - 索引知識庫：`python -m domains._shared.ingest_documents --path "..."`

5. **Windows Task Scheduler**：確認動作設定裡的「起始位置 (Start in)」
   是專案根目錄，不是 `scheduling/` 或別的路徑，理由跟第 4 點一樣。

## 已經幫你決定 / 修正的地方

- **`get_outlook_email.py` 拆成兩個 node**（`fetch_bbg_news` /
  `fetch_sinopac_views`），因為 BBG News 跟永豐投顧是兩個互不依賴的資料
  來源，理應是兩個獨立步驟；但 `get_outlook_email.py` 本身維持一支純函
  式庫，不拆進 `nodes/`——node 是「LangChain Runnable 轉接層」，函式庫
  邏輯（Outlook COM、日期比對）應該能脫離 graph 單獨測試。

- **兩個 fetch node 目前是循序執行**（先 BBG 再永豐），不是平行——兩邊
  各自開一個新的 Outlook MAPI 連線，多執行緒同時存取 Outlook COM 容易
  不穩定。`graph.py` 裡有註解說明怎麼改成平行（LangGraph 原生支援
  fan-out/fan-in），如果你想試可以自己切換。

- **`skipped` 短路判斷**移到 `summarize` node（兩個 fetch 的匯合點）
  做，不是在 fetch 階段各自判斷——這樣只需要判斷一次。

- **`analyze.py` / `chart.py`** 照現況搬過去（`main.py` 原本就沒有真的
  呼叫它們，`config.ENABLE_CHARTS` 開了也只是印訊息），`make_chart.py`
  裡留了 TODO 註解，等你決定好圖表資料來源再接上，其他 node 不用改。

## 我怎麼確認這批程式碼真的接得起來

不是只有語法檢查，有實際 mock 掉 Outlook COM 跑過完整 import 鏈路 +
graph 執行：
- `infra.paths.PROJECT_ROOT` 算出來的路徑正確
- `infra.status_store.DB_PATH` 指向專案根目錄的 `run_history.db`
- `orchestrator.tools` 四個工具正確載入
- 模擬「今天沒有任何信件」→ `skipped=True`，正確短路
- 模擬「有 BBG + 永豐資料」→ 完整跑過 fetch → summarize → make_chart →
  assemble_report，`output_path` 跟 `report1.build_pdf()` 收到的
  sections 內容都正確

`win32com` / `pythoncom` / `pywintypes` 這三個是 Windows-only 套件，沙
盒是 Linux 環境裝不了，測試時用最小 stub 模組頂替（只是讓 import 不報
錯，沒有真的模擬 Outlook 行為）——所以這份驗證證明的是「架構接線正
確」，不是「在你的 Windows 機器上、接到真的 Outlook 資料，一定完全正
常」，實機第一次跑完還是要看一下輸出的 PDF 內容跟以前是否一致。
