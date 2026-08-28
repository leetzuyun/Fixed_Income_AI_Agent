"""
infra/llm.py
Thin LLM wrapper. Supports two providers, switchable via config.LLM_PROVIDER:
  - "ollama": local Ollama REST API (default)
  - "openai": OpenAI (or any OpenAI-compatible) chat completions API

原本是專案根目錄的 llm.py，內容完全沒動，只把 `import config` 改成
`import infra.config as config`，因為之後法規知識庫、可轉債知識庫的
subagent 也會需要同一套 provider 切換邏輯，所以把它當成 infra 層的共
用模組，不放在 pipelines/market_report/ 底下。
"""
import requests
import infra.config as config
import json
import re


class LLMError(RuntimeError):
    pass


class OllamaError(LLMError):
    pass


class OpenAIError(LLMError):
    pass


class GeminiError(LLMError):
    pass


def _chat_ollama(prompt: str, model: str = None, host: str = None) -> str:
    model = model or config.OLLAMA_MODEL
    host = host or config.OLLAMA_HOST
    url = f"{host}/api/chat"

    try:
        response = requests.post(
            url,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=config.OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise OllamaError(
            f"Could not reach Ollama at {host}. Is it running? (`ollama serve`)"
        ) from e
    except requests.exceptions.Timeout as e:
        raise OllamaError(
            f"Ollama call timed out after {config.OLLAMA_TIMEOUT_SECONDS}s. "
            f"Try a smaller model or raise OLLAMA_TIMEOUT_SECONDS."
        ) from e
    except requests.exceptions.HTTPError as e:
        raise OllamaError(f"Ollama returned an error: {e}") from e

    data = response.json()
    try:
        return data["message"]["content"].strip()
    except (KeyError, TypeError) as e:
        raise OllamaError(f"Unexpected Ollama response shape: {data}") from e


def _chat_openai(prompt: str, model: str = None) -> str:
    model = model or config.OPENAI_MODEL
    if not config.OPENAI_API_KEY:
        raise OpenAIError(
            "OPENAI_API_KEY is not set. Export it as an environment variable "
            "before running (never hardcode it in config.py)."
        )
    url = f"{config.OPENAI_BASE_URL}/chat/completions"

    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=config.OPENAI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise OpenAIError(f"Could not reach {config.OPENAI_BASE_URL}.") from e
    except requests.exceptions.Timeout as e:
        raise OpenAIError(
            f"OpenAI call timed out after {config.OPENAI_TIMEOUT_SECONDS}s."
        ) from e
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = response.json().get("error", {}).get("message", "")
        except Exception:
            pass
        raise OpenAIError(f"OpenAI API error: {detail or e}") from e

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise OpenAIError(f"Unexpected OpenAI response shape: {data}") from e


def _chat_gemini(prompt: str, model: str = None) -> str:
    model = model or config.GEMINI_MODEL
    if not config.GEMINI_API_KEY:
        raise GeminiError(
            "GEMINI_API_KEY is not set. Export it as an environment variable "
            "before running (never hardcode it in config.py)."
        )
    url = f"{config.GEMINI_BASE_URL}/models/{model}:generateContent"

    try:
        response = requests.post(
            url,
            headers={
                "x-goog-api-key": config.GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=config.GEMINI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise GeminiError(f"Could not reach {config.GEMINI_BASE_URL}.") from e
    except requests.exceptions.Timeout as e:
        raise GeminiError(
            f"Gemini call timed out after {config.GEMINI_TIMEOUT_SECONDS}s."
        ) from e
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = response.json().get("error", {}).get("message", "")
        except Exception:
            pass
        raise GeminiError(f"Gemini API error: {detail or e}") from e

    data = response.json()
    try:
        candidates = data["candidates"]
        if not candidates:
            reason = data.get("promptFeedback", {}).get("blockReason", "unknown reason")
            raise GeminiError(f"Gemini returned no candidates (blocked: {reason}).")
        return candidates[0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise GeminiError(f"Unexpected Gemini response shape: {data}") from e


def _chat(prompt: str, model: str = None, host: str = None) -> str:
    if config.LLM_PROVIDER == "openai":
        return _chat_openai(prompt, model=model)
    if config.LLM_PROVIDER == "gemini":
        return _chat_gemini(prompt, model=model)
    return _chat_ollama(prompt, model=model, host=host)


def chat(prompt: str, model: str = None) -> str:
    """通用的一次性 LLM 呼叫，給不是「晨報摘要」這種特定格式的用途使用
    （例如法規 wiki 頁面撰寫）。跟 _chat() 邏輯完全一樣、一樣依照
    config.LLM_PROVIDER 切換 provider，只是開放給模組外部呼叫——原本的
    summarize_file / summarize_section 都是針對晨報格式寫死的 prompt，
    其他 domain 需要自己組 prompt 時就用這支。"""
    return _chat(prompt, model=model)


def _lang_instruction() -> str:
    return "請用繁體中文回覆。" if config.SUMMARY_LANGUAGE == "zh-TW" else "Respond in English."


def summarize_file(filename: str, text: str, model: str = None) -> str:
    trimmed = text[:12000]
    prompt = (
        f"{_lang_instruction()}\n\n"
        f"你是一位固定收益市場分析助理。以下是報告檔案「{filename}」的內容，"
        f"請用 3-6 條精簡的重點條列出這份報告的核心內容"
        f"（例如：市場動向、殖利率變化、重要數字、風險提示等）。"
        f"只列重點，不要多餘的開場白。\n\n"
        f"---報告內容---\n{trimmed}"
    )
    return _chat(prompt, model=model)


def summarize_combined(target_date: str, per_file_summaries: dict, model: str = None) -> str:
    """Roll up per-file bullet summaries into one daily overview."""
    joined = "\n\n".join(
        f"【{fname}】\n{summary}" for fname, summary in per_file_summaries.items()
    )
    prompt = (
        f"{_lang_instruction()}\n\n"
        f"以下是 {target_date} 當天所有固定收益報告的重點摘要。"
        f"將這些重點摘要內化成既有的知識，並且"
        f"整合成一份簡短的「當日總覽」（5-8 條重點），"
        f"點出當天最值得注意的共同主題、數字變化或風險。"
        f"不能只是原本的摘要重複貼上。\n\n"
        f"{joined}"
    )
    return _chat(prompt, model=model)


def summarize_section(target_date: str, section_title: str, section_focus: str,
                       per_file_summaries: dict, format_instruction: str = None,
                       model: str = None) -> str:
    if not per_file_summaries:
        return "（今日無相關資料）" if config.SUMMARY_LANGUAGE == "zh-TW" else "(No relevant data today.)"

    format_instruction = format_instruction or "請整合成通順的文字段落或條列重點（依內容性質選擇最適合的呈現方式）"

    joined = "\n\n".join(
        f"【{fname}】\n{summary}" for fname, summary in per_file_summaries.items()
    )
    prompt = (
        f"{_lang_instruction()}\n\n"
        f"以下是 {target_date} 「{section_title}」相關的重點摘要。{section_focus}\n"
        f"{format_instruction}，"
        f"避免重複相同的內容，並且要內化成自身的知識再產出摘要\n\n"
        f"{joined}"
    )
    return _chat(prompt, model=model)


def select_important_metrics(filename: str, text: str, candidate_metrics: list, model: str = None) -> list:

    if not candidate_metrics:
        return []
    if len(candidate_metrics) <= 3:
        return candidate_metrics  # nothing to trim

    trimmed_text = text[:6000]
    metrics_list = "、".join(candidate_metrics)
    prompt = (
        f"{_lang_instruction()}\n\n"
        f"以下是報告檔案「{filename}」的部分內容，以及從其中表格擷取出的欄位（指標）名稱清單。\n"
        f"請從這份清單中，選出對固定收益市場最重要、最值得做成圖表呈現的指標"
        f"（最多 5 個），排除不重要的欄位（例如流水號、頁碼、備註等非市場數據欄位）。\n\n"
        f"只能從提供的清單中選擇，不要自己發明新的名稱。\n"
        f"只回傳一個 JSON 陣列字串，例如 [\"殖利率\", \"成交量\"]，不要有其他文字或說明。\n\n"
        f"---指標清單---\n{metrics_list}\n\n"
        f"---報告內容（節錄）---\n{trimmed_text}"
    )

    try:
        raw = _chat(prompt, model=model)
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return candidate_metrics
        selected = json.loads(match.group(0))
        valid = [m for m in selected if m in candidate_metrics]
        return valid if valid else candidate_metrics
    except (LLMError, json.JSONDecodeError, TypeError):
        return candidate_metrics
