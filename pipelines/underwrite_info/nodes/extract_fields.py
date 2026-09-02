"""
pipelines/underwrite_info/nodes/extract_fields.py
對每份本機 PDF：抽純文字（infra/pdf_text.py）-> LLM 擷取欄位
（extractor.py，透過 infra/llm.py 走 config.LLM_PROVIDER 設定的
provider）。

每份 PDF 擷取出來的欄位會存成一份對應的 JSON 快取檔
（domains/underwriting_kb/extracted/<檔名>.json），好處兩個：
  1. 重跑同一批 PDF 不會重複呼叫 LLM（省 API 費用、也省時間）——已經有
     快取檔就直接讀，不會再打一次 API。想強制重新解析某一份，把對應的
     JSON 快取檔刪掉再重跑即可。
  2. 每份公告都有一份人眼可讀的 JSON，要核對某一份公告到底擷取出什麼
     欄位，直接開那份 JSON 檔看就好，不用查 SQLite。

快取檔損毀（例如手動改壞、或被不相容的舊版格式寫入）會自動退回重新解
析，不會讓整個流程掛掉。

「序號」如果 LLM 從公告內文抓不到明確編號（回傳 "—"），就用檔名（去掉
副檔名）頂替，確保每份公告都有一個穩定、唯一的鍵可以拿去當 JSON 快取檔
名跟 SQLite 的鍵——不然多份找不到編號的公告會互相覆蓋掉，只剩最後一
份。這個頂替會在寫入快取「之前」就決定好，所以快取檔裡存的序號已經是
最終版本。
"""
import json
import os

from langchain_core.runnables import chain

from infra.paths import PROJECT_ROOT
from infra.pdf_text import extract_text
from pipelines.underwrite_info.extractor import extract_fields as llm_extract_fields

EXTRACTED_DIR = os.path.join(PROJECT_ROOT, "domains", "underwriting_kb", "extracted")


def _load_cache(cache_path: str):
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [warn] 快取檔案損毀（{e}），重新解析：{cache_path}")
        return None


@chain
def extract_fields(state: dict) -> dict:
    if state.get("skipped"):
        return {**state, "records": []}

    os.makedirs(EXTRACTED_DIR, exist_ok=True)
    records = []

    for path in state["source_paths"]:
        filename = os.path.splitext(os.path.basename(path))[0]
        cache_path = os.path.join(EXTRACTED_DIR, f"{filename}.json")

        fields = _load_cache(cache_path)
        if fields is not None:
            print(f"  -> {os.path.basename(path)} 已有快取，跳過 LLM 呼叫")
            records.append(fields)
            continue

        text = extract_text(path)
        if not text.strip():
            print(f"  [warn] {os.path.basename(path)} 讀不到任何文字內容（可能是掃描檔），跳過。")
            continue

        fields = llm_extract_fields(text)
        if fields.get("序號") in (None, "—", ""):
            fields["序號"] = filename

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(fields, f, ensure_ascii=False, indent=2)
        print(f"  -> 解析 {os.path.basename(path)}（序號: {fields['序號']}），已寫入快取")

        records.append(fields)

    return {**state, "records": records}
