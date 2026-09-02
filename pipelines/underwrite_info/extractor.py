"""
pipelines/underwrite_info/extractor.py
從承銷公告 PDF 的純文字內容擷取欄位，用 infra/llm.py 的通用 chat()——
跟專案其他地方一樣，透過 infra/config.py 的 LLM_PROVIDER 切換
openai/gemini/ollama，不再綁定 Gemini 的 PDF binary 多模態能力，也不需
要 google-genai 這個套件了。

跟舊版的差異：舊版是把 PDF 檔案直接丟給 Gemini（連版面/圖片都能讀），
現在改成先用 pdfplumber 抽純文字（infra/pdf_text.py），再把文字丟給
LLM 做欄位擷取。如果公告 PDF 是掃描圖檔（沒有文字層），pdfplumber 抽不
出文字，這個方法就會失效，需要另外接 OCR——如果你這批公告有掃描件，跟
我說一聲。

之前欄位是「爬蟲抓的 listing 表格 + Gemini PDF 擷取」兩處來源合併，現
在整個 pipeline 只讀本機 PDF、沒有爬蟲抓到的 listing 表格了，所以這裡
的 prompt 擴充成一次擷取全部欄位（含原本從 listing 表格來的 序號/申報
日期/主辦承銷商/方式/發行性質/發行種類）。「序號」如果 PDF 內文找不到
明確的公告編號，就由呼叫端（nodes/extract_fields.py）用檔名頂替，確保
每份公告都有一個穩定、唯一的鍵可以拿去查詢/更新 SQLite。
"""
import json
import re

from infra.llm import chat

_DEFAULTS = {
    "序號": "—", "申報日期": "—", "主辦承銷商": "—", "案件名稱": "—",
    "方式": "—", "發行性質": "—", "發行種類": "—",
    "承銷商名稱": "—", "總承銷/洽商銷售金額": "—", "總承銷/洽商銷售數量": "—",
    "幣別": "TWD", "債券名稱": "—", "發行人": "—", "到期日": "—",
}

_PROMPT_TEMPLATE = """\
這是一份台灣公司債承銷公告的文字內容。請找出以下欄位並以 JSON 回傳
（找不到的欄位填 "—"，幣別找不到就填 "TWD"）：
{{
  "序號": "公告編號/文號，如果找不到明確的編號就填 \\"—\\"",
  "申報日期": "公告申報日期，格式盡量維持原文（例如 115/01/10）",
  "主辦承銷商": "...",
  "案件名稱": "...",
  "方式": "承銷/發行方式，例如 洽商、公開申購",
  "發行性質": "...",
  "發行種類": "...",
  "承銷商名稱": "實際承銷的券商名稱",
  "總承銷/洽商銷售金額": "...",
  "總承銷/洽商銷售數量": "...",
  "幣別": "TWD或USD或EUR或JPY等",
  "債券名稱": "...",
  "發行人": "...",
  "到期日": "..."
}}
只回傳 JSON，不要其他文字、不要用程式碼區塊包起來。

---公告內容---
{text}"""


def extract_fields(pdf_text: str, model: str = None) -> dict:
    """對一份公告 PDF 的純文字內容呼叫 LLM 擷取欄位。找不到的欄位回傳
    "—"（幣別回傳 "TWD"），不會拋例外中斷整個匯入流程——單一份公告解析
    失敗，不該讓其他公告也解析不了。"""
    trimmed = pdf_text[:15000]
    prompt = _PROMPT_TEMPLATE.format(text=trimmed)

    try:
        raw = chat(prompt, model=model)
    except Exception as e:
        print(f"  [warn] LLM 呼叫失敗：{e}")
        return dict(_DEFAULTS)

    raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw).strip()
    try:
        data = json.loads(raw)
        return {k: data.get(k, v) for k, v in _DEFAULTS.items()}
    except json.JSONDecodeError:
        print(f"  [warn] LLM 回傳非 JSON 格式：{raw[:120]}")
        return dict(_DEFAULTS)
