"""
Central configuration for the daily report agent.
Override any of these via environment variables of the same name,
e.g. `OLLAMA_MODEL=qwen2.5vl:7b python main.py --date 2026-07-28`
"""
import os
import re

from dotenv import load_dotenv

load_dotenv()

# --- LLM provider selection -----------------------------------------------
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai") # "ollama" or "openai" or "gemini"

# --- Ollama connection -------------------------------------------------
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")
OLLAMA_TIMEOUT_SECONDS = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "1000"))

# --- OpenAI (or OpenAI-compatible) connection -------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "spade-gpt-5.6-sol")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://sinocloudsecchat-litellm-webapp-uat.azurewebsites.net")
OPENAI_TIMEOUT_SECONDS = int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "180"))

# --- Gemini connection -------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
GEMINI_BASE_URL = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
GEMINI_TIMEOUT_SECONDS = int(os.environ.get("GEMINI_TIMEOUT_SECONDS", "180"))


# --- Paths ---------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.environ.get("REPORTS_DIR", os.path.join(BASE_DIR, "reports"))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(BASE_DIR, "output"))

# --- Filename date matching ----------------------------------------------
DATE_PATTERNS = [
    re.compile(r"(\d{4})-(\d{2})-(\d{2})"),   # YYYY-MM-DD
    re.compile(r"(\d{4})(\d{2})(\d{2})"),     # YYYYMMDD
    re.compile(r"(\d{4}).(\d{2}).(\d{2})"),
]

# --- Summarization language ----------------------------------------------
# Set to "en" for English.
SUMMARY_LANGUAGE = os.environ.get("SUMMARY_LANGUAGE", "zh-TW")

# --- Report source classification -------------------------------------------
# Splits each day's emails into two groups for the two-section report:
#   - filename contains one of these keywords -> 永豐投顧 section
#   - everything else -> external/market-news section
SINOPAC_KEYWORDS = [
    kw for kw in os.environ.get("SINOPAC_KEYWORDS", "永豐投顧,SinoPac,sinopac.com").split(",") if kw
]

# --- Charts ------------------------------------------------------------------
# Off for now — the pipeline is text-only while reading Outlook .msg files
# instead of PDF tables. chart.py / analyze.py are untouched and ready to
# go if/when charting comes back.
ENABLE_CHARTS = os.environ.get("ENABLE_CHARTS", "false").lower() == "true"

# --- Report output ---------------------------------------------------------
REPORT_TITLE = os.environ.get("REPORT_TITLE", "Daily Fixed Income Report Digest")
