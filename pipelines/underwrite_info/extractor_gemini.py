"""
pipelines/underwrite_info/extractor.py
用 Gemini 直接讀 PDF 二進位內容，擷取承銷公告裡的關鍵欄位。

這支刻意不透過 infra/llm.py——infra/llm.py 是文字 prompt 的
provider-agnostic 包裝（ollama/openai/gemini 三選一切換），這裡要用的
是 Gemini 特有的「直接吃 PDF binary」多模態能力，目前 openai/ollama 那
兩條路徑沒有對應的整合，所以這個擷取步驟目前綁定 Gemini，不會跟著
infra/config.py 的 LLM_PROVIDER 切換。API key 沿用 infra/config.py 的
GEMINI_API_KEY，不用另外設定 .env。

需要安裝：pip install google-genai（不在你現有的 pip list 裡）。
"""
import json
import re
import time

from google import genai
from google.genai import types

import infra.config as config

_DEFAULTS = {
    "承銷商名稱": "—", "總承銷/洽商銷售金額": "—",
    "總承銷/洽商銷售數量": "—", "幣別": "TWD",
    "債券名稱": "—", "發行人": "—", "到期日": "—",
}

_PROMPT = """\
這是一份台灣公司債承銷公告PDF。
請找出以下欄位並以JSON回傳（找不到填"—"）：
{
  "承銷商名稱": "...",
  "總承銷/洽商銷售金額": "...",
  "總承銷/洽商銷售數量": "...",
  "幣別": "TWD或USD或EUR或JPY等，找不到填TWD",
  "債券名稱": "...",
  "發行人": "...",
  "到期日": "..."
}
只回傳JSON，不要其他文字。"""


class QuotaExhaustedError(RuntimeError):
    """每日免費額度耗盡（quota limit: 0），繼續等待重試也沒用時拋出。"""
    pass


def extract_fields(pdf_bytes: bytes, max_retries: int = 5) -> dict:
    """對一份 PDF 呼叫 Gemini 擷取欄位，429/per-minute rate limit 自動等
    待重試；每日額度耗盡（limit: 0）則直接拋出 QuotaExhaustedError，讓
    呼叫端決定要不要停止後續呼叫（重試也沒用）。"""
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    types.Part.from_text(text=_PROMPT),
                ],
            )
            raw = response.text.strip()
            raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw).strip()
            try:
                data = json.loads(raw)
                return {k: data.get(k, v) for k, v in _DEFAULTS.items()}
            except json.JSONDecodeError:
                print(f"  [WARN] Gemini returned non-JSON: {raw[:120]}")
                return dict(_DEFAULTS)

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                if "PerDay" in err_str and "limit: 0" in err_str:
                    print("  [QUOTA] Daily free-tier quota exhausted (limit=0).")
                    raise QuotaExhaustedError("每日額度耗盡") from e
                delay_match = re.search(r"retryDelay.*?(\d+)s", err_str)
                retry_secs = int(delay_match.group(1)) if delay_match else 30
                wait = retry_secs + (attempt - 1) * 15
                print(f"  [429] Per-minute rate limit. Waiting {wait}s ({attempt}/{max_retries})...")
                time.sleep(wait)
                continue
            raise

    print("  [ERROR] Gemini failed after max retries. Returning defaults.")
    return dict(_DEFAULTS)
